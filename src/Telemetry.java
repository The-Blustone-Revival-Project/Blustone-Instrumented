package com.vshower.instrumented;

import com.vshower.instrumented.BuildConfig;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.Log;
import android.view.MotionEvent;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Local-only telemetry for the side-by-side diagnostic APK.
 *
 * Every event is written to the app-private fallback stream before it is sent
 * to the collector, so a collector outage cannot hide the beginning of a
 * failure. Secrets are not intentionally collected and common sensitive keys
 * are redacted by the collector as a second boundary.
 */
public final class Telemetry {
    private static final String TAG = "BLUSTONE_INSTRUMENTED";
    private static final String DEFAULT_ENDPOINT = "http://10.0.2.2:8099/v1/events";
    private static final String[] SELECTED_ARTIFACT_PATHS = {
            "cloud/v2pv.acct",
            "local/CDN.db",
            "local/USER.db",
            "local/UI_XML_RO.db",
            "local/ETC.db",
            "local/E_NEW.jet",
            "local/E_MIDAGE.jet",
            "local/UI_MAIN.jet",
            "instrumentation/pre-repair/CDN.db",
            "instrumentation/pre-repair/UI_XML_RO.db",
    };
    private static final int QUEUE_CAPACITY = 4096;
    /**
     * High-volume native render/resource chatter. The stock logcat reader is
     * `*:V`, so the native engine's per-frame resource-manager spam (thousands
     * of `RANN [RSM] ... is registered.` lines per second) evicts every useful
     * line - including the assertions and LevelDB lookups we are actually
     * hunting - from the bounded ring before anyone can read them. These
     * prefixes are dropped at the source. Diagnostic tags
     * (BLUSTONE_*), the RANN non-RSM lines, and every Java/Android line are
     * still forwarded untouched.
     */
    private static final String[] LOG_NOISE_PREFIXES = {
            "RANN    : [RSM]",
            "RANN    : [RSM]",
    };
    private static final String[] LOG_NOISE_SUBSTRINGS = {
            "[RSM] 'BATCHDRAW",
            "[RSM] 'BATCH",
            "[RSM] Removing Res",
            "[RSM] Registering Res",
            "[RSM] Loading Res",
            "[RSM] Unloading Res",
    };
    /**
     * Repeat suppression for the remaining noisy-but-possibly-useful native
     * lines. Keyed on a coarse shape (the log tag plus the leading words), so
     * a chatty loop collapses to a few samples instead of thousands of copies.
     * The first BLUSTONE_REPEAT_SUPPRESS_MAX occurrences of a shape are always
     * forwarded, so a short burst of identical lines is never lost.
     */
    private static final int BLUSTONE_REPEAT_SUPPRESS_MAX = 5;
    private static final Map<String, Integer> LOG_REPEAT_COUNTS = new HashMap<>();
    private static final Object LOG_FILTER_LOCK = new Object();
    /**
     * Compile-time switch for the pre-repair CDN restore A/B diagnostic. Set by
     * the build (GenerateBuildConfig writes the value below); false by default
     * so the native CDN manager keeps the index it wrote last session.
     */
    private static final boolean restorePreRepairCdnEnabled = BuildConfig.RESTORE_PRE_REPAIR_CDN;
    private static final Object LOCK = new Object();
    private static final ArrayBlockingQueue<String> QUEUE = new ArrayBlockingQueue<>(QUEUE_CAPACITY);
    private static final ExecutorService EXECUTOR = Executors.newCachedThreadPool();
    private static volatile boolean installed;
    private static volatile Context context;
    private static volatile File localFile;
    private static volatile String endpoint = DEFAULT_ENDPOINT;
    private static volatile String sessionId;
    private static volatile Thread.UncaughtExceptionHandler previousUncaught;
    private static final Map<String, String> UPLOADED_ARTIFACTS = new HashMap<>();
    private static final AtomicBoolean ARTIFACT_UPLOAD_IN_FLIGHT = new AtomicBoolean();

    private Telemetry() {}

    /**
     * Sample every thread of this process and report what each one is blocked
     * on in the kernel.
     *
     * Why this exists: the client hangs on the title screen with its main thread
     * asleep, and "asleep" does not say why. Reading
     * /proc/self/task/&lt;tid&gt;/wchan plus the state field from .../stat from
     * inside the app needs no root, and it separates the candidate causes at a
     * glance:
     *
     *   futex_wait / futex_wait_queue   blocked on a lock or condition
     *                                   variable - a client-side deadlock, or
     *                                   a callback that will never be signalled
     *   poll / select / epoll / read    waiting on a socket or file descriptor
     *   do_sigtimedwait / hrtimer...    waiting on a timer
     *   unavailable                     kernel did not expose wchan
     *
     * That is the difference between "the server sent something wrong" and "the
     * engine is waiting for an event that never arrives", and none of it is
     * visible from the HTTP side.
     */
    private static void emitThreadStates() {
        try {
            File taskDir = new File("/proc/self/task");
            File[] tids = taskDir.listFiles();
            JSONArray threads = new JSONArray();
            int running = 0;
            if (tids != null) {
                for (File tidDir : tids) {
                    JSONObject entry = new JSONObject();
                    put(entry, "tid", tidDir.getName());
                    put(entry, "comm", readSmall(new File(tidDir, "comm")).trim());
                    put(entry, "state", threadState(readSmall(new File(tidDir, "stat"))));
                    String wchan = readSmall(new File(tidDir, "wchan")).trim();
                    put(entry, "wchan", wchan.isEmpty() ? "unavailable" : wchan);
                    if ("R".equals(entry.optString("state"))) running++;
                    threads.put(entry);
                }
            }
            JSONObject data = new JSONObject();
            put(data, "thread_count", threads.length());
            put(data, "running", running);
            put(data, "blocked", threads.length() - running);
            put(data, "threads", threads);
            emit("thread_states", data);
        } catch (Throwable throwable) {
            JSONObject data = new JSONObject();
            put(data, "error", throwable.getClass().getName());
            put(data, "message", throwable.getMessage());
            emit("thread_states_error", data);
        }
    }

    /** /proc/&lt;tid&gt;/stat state letter, which sits just after the comm field. */
    private static String threadState(String stat) {
        int close = stat.indexOf(')');
        if (close < 0 || close + 2 >= stat.length()) return "?";
        return stat.substring(close + 2, close + 3);
    }

    /** Read a small /proc file; "" when it cannot be read. */
    private static String readSmall(File file) {
        try (FileInputStream input = new FileInputStream(file)) {
            byte[] buffer = new byte[256];
            int count = input.read(buffer);
            return count <= 0 ? "" : new String(buffer, 0, count, StandardCharsets.UTF_8);
        } catch (Throwable ignored) {
            return "";
        }
    }


    public static void install(final Application application) {
        synchronized (LOCK) {
            if (installed) return;
            context = application.getApplicationContext();
            sessionId = UUID.randomUUID().toString();
            endpoint = resolveEndpoint(context);
            localFile = new File(new File(context.getFilesDir(), "instrumentation"), "events.ndjson");
            installed = true;
        }
        restoreBundledJets(context);
        restoreSeededUiXml(context);
        if (!restorePreRepairCdnEnabled && "com.vshower.prd_sr.instrumented".equals(context.getPackageName())) {
            try {
                String status = CdnCompressionMigration.migrate(context.getFilesDir(), name -> context.getAssets().open(name));
                JSONObject migration = new JSONObject();
                put(migration, "status", status);
                emit("cdn_compression_migration", migration);
                Log.i(TAG, "CDN compression migration: " + status);
            } catch (Throwable failure) {
                Log.w(TAG, "CDN compression migration held; preserved cache retained", failure);
            }
        }
        restorePreRepairCdn(context);
        previousUncaught = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread, throwable) -> {
            JSONObject data = new JSONObject();
            put(data, "thread", thread == null ? "unknown" : thread.getName());
            put(data, "type", throwable == null ? "unknown" : throwable.getClass().getName());
            put(data, "message", throwable == null ? "" : throwable.getMessage());
            put(data, "stack", stack(throwable));
            emit("uncaught_exception", data);
            if (previousUncaught != null) previousUncaught.uncaughtException(thread, throwable);
        });
        emit("process_start", snapshot(application));
        startPump();
        startLogcatReader();
        EXECUTOR.execute(Telemetry::dumpSelectedFiles);
        scheduleArtifactUpload();
        EXECUTOR.execute(() -> {
            String previousGymSnapshot = "";
            String previousSearchSnapshot = "";
            String previousEpisodeSnapshot = "";
            while (installed) {
                emit("heartbeat", snapshot(context));
                JSONObject gym = NativeGymSnapshot.capture(context);
                String currentGymSnapshot = gym.toString();
                if (!currentGymSnapshot.equals(previousGymSnapshot)) {
                    emit("native_gym_state", gym);
                    previousGymSnapshot = currentGymSnapshot;
                }
                JSONObject search = NativeGymSnapshot.captureSearch(context);
                String currentSearchSnapshot = search.toString();
                if (!currentSearchSnapshot.equals(previousSearchSnapshot)) {
                    emit("native_search_state", search);
                    previousSearchSnapshot = currentSearchSnapshot;
                }
                JSONObject episode = EpisodeResourceSnapshot.capture(context);
                String currentEpisodeSnapshot = episode.toString();
                if (!currentEpisodeSnapshot.equals(previousEpisodeSnapshot)) {
                    emit("episode_resource_state", episode);
                    previousEpisodeSnapshot = currentEpisodeSnapshot;
                }
                // Sample thread blocking state alongside the heartbeat. Cheap
                // enough to always run, and it is the only signal that
                // distinguishes a lock deadlock from waiting on the network.
                emitThreadStates();
                scheduleArtifactUpload();
                try {
                    Thread.sleep(5000L);
                } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                    return;
                }
            }
        });
        if (Build.VERSION.SDK_INT >= 14) {
            application.registerActivityLifecycleCallbacks(new Application.ActivityLifecycleCallbacks() {
                @Override public void onActivityCreated(Activity activity, Bundle state) { activity("callback_created", activity, state == null ? "fresh" : "restored"); }
                @Override public void onActivityStarted(Activity activity) { activity("callback_started", activity, null); }
                @Override public void onActivityResumed(Activity activity) { activity("callback_resumed", activity, null); }
                @Override public void onActivityPaused(Activity activity) { activity("callback_paused", activity, null); }
                @Override public void onActivityStopped(Activity activity) { activity("callback_stopped", activity, null); }
                @Override public void onActivitySaveInstanceState(Activity activity, Bundle state) { activity("callback_save_state", activity, null); }
                @Override public void onActivityDestroyed(Activity activity) { activity("callback_destroyed", activity, null); }
            });
        }
    }

    public static void activity(String name, Activity activity, String detail) {
        JSONObject data = new JSONObject();
        put(data, "activity", activity == null ? "unknown" : activity.getClass().getName());
        put(data, "detail", detail);
        emit(name, data);
    }

    public static void activityResult(Activity activity, int requestCode, int resultCode, android.content.Intent intent) {
        JSONObject data = new JSONObject();
        put(data, "activity", activity == null ? "unknown" : activity.getClass().getName());
        put(data, "request_code", requestCode);
        put(data, "result_code", resultCode);
        put(data, "intent_action", intent == null ? null : intent.getAction());
        emit("activity_result", data);
    }

    public static void touch(Activity activity, MotionEvent event) {
        if (event == null) return;
        JSONObject data = new JSONObject();
        put(data, "activity", activity == null ? "unknown" : activity.getClass().getName());
        put(data, "action", event.getActionMasked());
        put(data, "pointer_count", event.getPointerCount());
        put(data, "x", event.getX());
        put(data, "y", event.getY());
        put(data, "event_time", event.getEventTime());
        emit("touch", data);
    }

    private static void startPump() {
        EXECUTOR.execute(() -> {
            while (installed) {
                try {
                    String first = QUEUE.poll(1000L, TimeUnit.MILLISECONDS);
                    if (first == null) continue;
                    StringBuilder batch = new StringBuilder(first).append('\n');
                    for (int i = 0; i < 49; i++) {
                        String next = QUEUE.poll();
                        if (next == null) break;
                        batch.append(next).append('\n');
                    }
                    post(batch.toString());
                } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                    return;
                } catch (Throwable throwable) {
                    Log.e(TAG, "telemetry pump failure", throwable);
                }
            }
        });
    }

    /**
     * True when the line is high-volume native render/resource chatter that
     * would otherwise evict the diagnostic events we are collecting. This is
     * a source-side filter: the line is never queued, never written to the
     * local fallback stream, and never posted to the collector, so it cannot
     * evict anything from the bounded ring.
     */
    private static boolean isLogNoise(String line) {
        for (String prefix : LOG_NOISE_PREFIXES) {
            if (line.contains(prefix)) return true;
        }
        for (String noise : LOG_NOISE_SUBSTRINGS) {
            if (line.contains(noise)) return true;
        }
        return false;
    }

    /**
     * Collapses a repeatedly-emitted log line to a small number of samples.
     * The shape is the log tag plus the first few whitespace-separated words
     * after the tag, with embedded numbers collapsed, so `BATCHDRAW49` and
     * `BATCHDRAW50` count as the same shape while a genuinely new message
     * family is still captured.
     */
    private static boolean isRepeatedLogShape(String line) {
        String shape = logShape(line);
        synchronized (LOG_FILTER_LOCK) {
            Integer seen = LOG_REPEAT_COUNTS.get(shape);
            int count = seen == null ? 1 : seen + 1;
            LOG_REPEAT_COUNTS.put(shape, count);
            return count > BLUSTONE_REPEAT_SUPPRESS_MAX;
        }
    }

    private static String logShape(String line) {
        // threadtime format: "MM-DD HH:MM:SS.mmm  PID  TID LEVEL TAG : message"
        int colon = line.indexOf(" : ");
        String head = colon >= 0 ? line.substring(0, colon) : line;
        String message = colon >= 0 ? line.substring(colon + 3) : "";
        StringBuilder shape = new StringBuilder();
        shape.append(head.replaceAll("\\d+", "#"));
        shape.append("|");
        String[] words = message.trim().split("\\s+");
        for (int i = 0; i < Math.min(4, words.length); i++) {
            shape.append(words[i].replaceAll("[0-9]+", "#")).append(' ');
        }
        return shape.toString();
    }

    private static void startLogcatReader() {
        EXECUTOR.execute(() -> {
            Process process = null;
            try {
                // "stderr" is included so anything the native library writes to stdout/stderr
                // is captured too; that is the channel a native trace stub would use.
                process = Runtime.getRuntime().exec(new String[]{"logcat", "-v", "threadtime",
                        "-b", "main", "-b", "system", "-b", "crash", "-b", "stderr", "*:V"});
                BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8));
                String line;
                int droppedNoise = 0;
                int droppedRepeat = 0;
                while ((line = reader.readLine()) != null && installed) {
                    if (line.contains(TAG)) continue;
                    if (isLogNoise(line)) {
                        droppedNoise++;
                        continue;
                    }
                    if (isRepeatedLogShape(line)) {
                        droppedRepeat++;
                        continue;
                    }
                    JSONObject data = new JSONObject();
                    put(data, "line", line);
                    emit("android_log", data);
                    if (droppedNoise + droppedRepeat >= 2000) {
                        JSONObject summary = new JSONObject();
                        put(summary, "dropped_noise", droppedNoise);
                        put(summary, "dropped_repeat", droppedRepeat);
                        put(summary, "reason", "logcat noise filter");
                        emit("android_log_filtered", summary);
                        droppedNoise = 0;
                        droppedRepeat = 0;
                    }
                }
            } catch (Throwable throwable) {
                JSONObject data = new JSONObject();
                put(data, "type", throwable.getClass().getName());
                put(data, "message", throwable.getMessage());
                emit("logcat_reader_error", data);
            } finally {
                if (process != null) process.destroy();
            }
        });
    }

    private static void emit(String name, JSONObject data) {
        if (!installed) return;
        JSONObject event = new JSONObject();
        put(event, "schema", "blustone.instrumented.event.v1");
        put(event, "event", name);
        put(event, "ts", System.currentTimeMillis());
        put(event, "elapsed_ms", SystemClock.elapsedRealtime());
        put(event, "session_id", sessionId);
        put(event, "pid", android.os.Process.myPid());
        put(event, "tid", android.os.Process.myTid());
        put(event, "package", context == null ? "unknown" : context.getPackageName());
        put(event, "endpoint", endpoint);
        if (data != null) put(event, "data", data);
        String line = event.toString();
        appendLocal(line);
        QUEUE.offer(line);
    }

    private static void post(String body) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(endpoint).openConnection();
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(1500);
            connection.setReadTimeout(1500);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/x-ndjson; charset=utf-8");
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(bytes.length);
            connection.getOutputStream().write(bytes);
            int status = connection.getResponseCode();
            if (status < 200 || status >= 300) Log.w(TAG, "collector status=" + status);
        } catch (Throwable ignored) {
            // The local fallback has already captured these events.
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private static String artifactEndpoint() {
        String marker = "/v1/events";
        int index = endpoint.lastIndexOf(marker);
        return index >= 0 ? endpoint.substring(0, index) + "/v1/artifacts" : endpoint + "/artifacts";
    }

    private static void scheduleArtifactUpload() {
        if (!installed || !ARTIFACT_UPLOAD_IN_FLIGHT.compareAndSet(false, true)) return;
        EXECUTOR.execute(() -> {
            try {
                uploadSelectedFilesIfChanged();
            } finally {
                ARTIFACT_UPLOAD_IN_FLIGHT.set(false);
            }
        });
    }

    private static void uploadSelectedFilesIfChanged() {
        Context value = context;
        if (value == null) return;
        for (String relative : SELECTED_ARTIFACT_PATHS) {
            File source = new File(value.getFilesDir(), relative);
            uploadTreeIfChanged(source, relative);
        }
    }

    private static void uploadTreeIfChanged(File source, String relative) {
        if (!source.exists()) return;
        if (source.isDirectory()) {
            File[] children = source.listFiles();
            if (children == null) return;
            for (File child : children) uploadTreeIfChanged(child, relative + "/" + child.getName());
            return;
        }
        String fingerprint = source.length() + ":" + source.lastModified();
        synchronized (UPLOADED_ARTIFACTS) {
            if (fingerprint.equals(UPLOADED_ARTIFACTS.get(relative))) return;
        }
        if (postArtifact(source, relative)) {
            synchronized (UPLOADED_ARTIFACTS) {
                UPLOADED_ARTIFACTS.put(relative, fingerprint);
            }
        }
    }

    private static boolean postArtifact(File source, String relative) {
        HttpURLConnection connection = null;
        try {
            String name = URLEncoder.encode(relative, "UTF-8");
            connection = (HttpURLConnection) new URL(artifactEndpoint() + "?name=" + name).openConnection();
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(1500);
            connection.setReadTimeout(4000);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/octet-stream");
            connection.setRequestProperty("X-Blustone-Session", sessionId == null ? "unknown" : sessionId);
            connection.setRequestProperty("X-Blustone-Package", context == null ? "unknown" : context.getPackageName());
            connection.setRequestProperty("X-Blustone-Artifact-Name", relative);
            connection.setRequestProperty("X-Blustone-SHA256", sha256(source));
            connection.setFixedLengthStreamingMode(source.length());
            FileInputStream input = new FileInputStream(source);
            OutputStream output = null;
            try {
                output = connection.getOutputStream();
                byte[] buffer = new byte[16384];
                int count;
                while ((count = input.read(buffer)) > 0) output.write(buffer, 0, count);
                output.flush();
            } finally {
                input.close();
                if (output != null) output.close();
            }
            int status = connection.getResponseCode();
            if (status >= 200 && status < 300) {
                JSONObject data = new JSONObject();
                put(data, "name", relative);
                put(data, "bytes", source.length());
                put(data, "sha256", sha256(source));
                emit("artifact_uploaded", data);
                return true;
            }
        } catch (Throwable ignored) {
            // Event telemetry and the app-private fallback remain available.
        } finally {
            if (connection != null) connection.disconnect();
        }
        return false;
    }

    private static String sha256(File source) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        FileInputStream input = new FileInputStream(source);
        try {
            byte[] buffer = new byte[16384];
            int count;
            while ((count = input.read(buffer)) > 0) digest.update(buffer, 0, count);
        } finally {
            input.close();
        }
        StringBuilder result = new StringBuilder(64);
        for (byte value : digest.digest()) result.append(String.format("%02x", value & 0xff));
        return result.toString();
    }

    private static void appendLocal(String line) {
        synchronized (LOCK) {
            if (localFile == null) return;
            try {
                File parent = localFile.getParentFile();
                if (parent != null) parent.mkdirs();
                if (localFile.exists() && localFile.length() > 32L * 1024L * 1024L) {
                    File rotated = new File(localFile.getParentFile(), "events.ndjson.1");
                    if (rotated.exists()) rotated.delete();
                    localFile.renameTo(rotated);
                }
                FileOutputStream output = new FileOutputStream(localFile, true);
                output.write((line + "\n").getBytes(StandardCharsets.UTF_8));
                output.close();
            } catch (Throwable ignored) {
                // Never interfere with the game for diagnostics.
            }
        }
    }

    private static JSONObject snapshot(Context value) {
        JSONObject data = new JSONObject();
        put(data, "model", Build.MODEL);
        put(data, "manufacturer", Build.MANUFACTURER);
        put(data, "sdk", Build.VERSION.SDK_INT);
        put(data, "release", Build.VERSION.RELEASE);
        put(data, "abi", Build.CPU_ABI);
        put(data, "files_dir", value == null ? null : value.getFilesDir().getAbsolutePath());
        put(data, "network", network(value));
        try {
            if (value != null) {
                PackageInfo info = value.getPackageManager().getPackageInfo(value.getPackageName(), 0);
                put(data, "version_name", info.versionName);
                put(data, "version_code", info.versionCode);
            }
        } catch (Throwable ignored) {}
        JSONArray files = new JSONArray();
        if (value != null) listFiles(value.getFilesDir(), value.getFilesDir(), files, 0);
        put(data, "files", files);
        return data;
    }

    private static void listFiles(File root, File current, JSONArray files, int depth) {
        if (root == null || current == null || depth > 6 || files.length() >= 300 || !current.exists()) return;
        File[] children = current.listFiles();
        if (children == null) return;
        for (File child : children) {
            JSONObject item = new JSONObject();
            put(item, "path", root.toURI().relativize(child.toURI()).getPath());
            put(item, "bytes", child.length());
            put(item, "directory", child.isDirectory());
            files.put(item);
            if (child.isDirectory()) listFiles(root, child, files, depth + 1);
            if (files.length() >= 300) return;
        }
    }

    /**
     * Recreate the native engine's bundled main-menu resource before startup.
     *
     * The recovered good run registered UI_MA_L1 from files/local/UI_MAIN.jet,
     * while a clean diagnostic install has no private copy after pm clear. The
     * APK already contains the byte-identical offline asset, so seed only the
     * missing file and leave any later downloaded replacement untouched.
     */
    private static void restoreBundledJets(Context value) {
        File target = new File(value.getFilesDir(), "local/UI_MAIN.jet");
        if (target.exists()) return;
        try {
            copyAssetFile(value, "UI_MAIN.jet", target);
            JSONObject repair = new JSONObject();
            put(repair, "name", "UI_MAIN.jet");
            put(repair, "bytes", target.length());
            emit("bundled_jet_seed", repair);
            Log.i(TAG, "seeded bundled UI_MAIN.jet into files/local");
        } catch (Throwable throwable) {
            Log.w(TAG, "bundled UI_MAIN.jet seed skipped", throwable);
        }
    }

    /**
     * Diagnostic-only export for BlueStacks inspection.  It copies only the
     * small persisted account file and the local CDN/user LevelDB trees to a
     * package-specific external directory; it never deletes or edits the
     * originals.
     */
    private static void dumpSelectedFiles() {
        Context value = context;
        if (value == null) return;
        try {
            File root = new File(value.getExternalFilesDir(null), "BlustoneInstrumentedDump");
            copyFile(new File(value.getFilesDir(), "cloud/v2pv.acct"), new File(root, "cloud/v2pv.acct"));
            copyTree(new File(value.getFilesDir(), "local/CDN.db"), new File(root, "local/CDN.db"));
            copyTree(new File(value.getFilesDir(), "local/USER.db"), new File(root, "local/USER.db"));
            Log.i(TAG, "selected private files exported to " + root.getAbsolutePath());
        } catch (Throwable throwable) {
            Log.w(TAG, "selected private file export failed", throwable);
        }
    }

    /**
     * Install the instrumented-only UI XML seed before MainActivity opens the
     * native LevelDB handles. The seed is a complete offline snapshot of the
     * recovered UI_XML_RO database, including both language trees and the
     * launcher/progress records needed before the first server request. The
     * original tree is copied once under instrumentation/pre-repair so this
     * diagnostic experiment remains reversible and auditable.
     */
    private static void restoreSeededUiXml(Context value) {
        File current = new File(value.getFilesDir(), "local/UI_XML_RO.db");
        File backup = new File(value.getFilesDir(), "instrumentation/pre-repair/UI_XML_RO.db");
        try {
            if (current.exists() && !backup.exists()) copyTree(current, backup);
            clearTree(current);
            if (!current.mkdirs() && !current.isDirectory()) {
                throw new Exception("mkdir failed: " + current);
            }
            copyAssetTree(value, "instrumented-seed-episode-ui-delta-v1/UI_XML_RO.db", current);
            JSONObject repair = new JSONObject();
            put(repair, "mode", "native-compatible-ui-episode-six-core-delta-without-en-define-color");
            put(repair, "preserved_backup", backup.exists());
            emit("ui_xml_repair", repair);
            Log.i(TAG, "clean-rebuilt UI_XML_RO database with verified mission/battle and six Episode UI aliases");
        } catch (Throwable throwable) {
            Log.w(TAG, "UI_XML_RO seed skipped", throwable);
        }
    }

    /**
     * Repair the instrumented package's CDN index before MainActivity loads
     * the native engine.  The known-good header is only the two server
     * packages and is rebuilt from the first successful bootstrap snapshot.
     * The existing index is preserved under app-private instrumentation data
     * and uploaded as a separate artifact before any later repair is possible.
     */
    private static void repairSeededCdn(Context value) {
        File current = new File(value.getFilesDir(), "local/CDN.db");
        File backup = new File(value.getFilesDir(), "instrumentation/pre-repair/CDN.db");
        try {
            if (current.exists() && !backup.exists()) copyTree(current, backup);
            File target = new File(value.getFilesDir(), "local/CDN.db");
            // A LevelDB overlay is not sufficient here: stale MANIFEST/log files
            // can be replayed on open and reintroduce the malformed records. The
            // original tree is already preserved above, so rebuild this
            // instrumented-only cache as a genuinely clean database directory.
            clearTree(target);
            if (!target.mkdirs() && !target.isDirectory()) {
                throw new Exception("mkdir failed: " + target);
            }
            copyAssetFile(value, "instrumented-seed-bootstrap/CDN.db/000005.ldb", new File(target, "000005.ldb"));
            copyAssetFile(value, "instrumented-seed-bootstrap/CDN.db/CURRENT", new File(target, "CURRENT"));
            copyAssetFile(value, "instrumented-seed-bootstrap/CDN.db/MANIFEST-000004", new File(target, "MANIFEST-000004"));
            JSONObject repair = new JSONObject();
            put(repair, "mode", "clean-rebuild");
            put(repair, "preserved_backup", backup.exists());
            emit("cdn_repair", repair);
            Log.i(TAG, "clean-rebuilt CDN index from known-good bootstrap snapshot");
        } catch (Throwable throwable) {
            Log.w(TAG, "CDN index repair skipped", throwable);
        }
    }

    /**
     * A/B diagnostic mode: restore the untouched CDN tree captured before the
     * seed repair. This is used to prove whether the clean LevelDB rewrite is
     * what suppresses the launcher's first network request.
     *
     * IMPORTANT: this is OFF by default. It used to run on every launch, which
     * meant the diagnostic snapshot overwrote whatever the native CDN manager
     * (`CPVCDN2`) had written during the previous session. The engine could
     * therefore never accumulate its own CDN index, and every launch presented
     * it with the same fixed mid-download state - which is consistent with the
     * client hanging in `CPVCDN2` after fetching the reslist without ever
     * requesting a package or proceeding to login. The native HTTP layer has
     * resume support ("Couldn't resume download", "File already completely
     * downloaded", "partial download completed, closing connection"), so a
     * snapshot that records an in-flight download is exactly the state in which
     * it can wait forever for a resume that never arrives.
     *
     * Enable it only for a deliberate A/B run; build with
     * `tools/build-instrumented-apk.py --restore-pre-repair-cdn`.
     */
    private static void restorePreRepairCdn(Context value) {
        if (!restorePreRepairCdnEnabled) {
            return;
        }
        File current = new File(value.getFilesDir(), "local/CDN.db");
        File backup = new File(value.getFilesDir(), "instrumentation/pre-repair/CDN.db");
        try {
            if (!backup.exists()) {
                repairSeededCdn(value);
                return;
            }
            clearTree(current);
            copyTree(backup, current);
            JSONObject repair = new JSONObject();
            put(repair, "mode", "restore-pre-repair");
            put(repair, "preserved_backup", true);
            emit("cdn_repair", repair);
            Log.i(TAG, "restored pre-repair CDN index for A/B bootstrap test");
        } catch (Throwable throwable) {
            Log.w(TAG, "pre-repair CDN restore skipped", throwable);
        }
    }

    private static void clearTree(File target) throws Exception {
        if (target == null || !target.exists()) return;
        if (target.isDirectory()) {
            File[] children = target.listFiles();
            if (children == null) throw new Exception("list failed: " + target);
            for (File child : children) clearTree(child);
        }
        if (!target.delete()) throw new Exception("delete failed: " + target);
    }

    private static void copyTree(File source, File destination) throws Exception {
        if (!source.exists()) return;
        if (source.isDirectory()) {
            if (!destination.exists() && !destination.mkdirs()) throw new Exception("mkdir failed: " + destination);
            File[] children = source.listFiles();
            if (children == null) return;
            for (File child : children) copyTree(child, new File(destination, child.getName()));
            return;
        }
        copyFile(source, destination);
    }

    private static void copyFile(File source, File destination) throws Exception {
        if (!source.exists() || !source.isFile()) return;
        File parent = destination.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) throw new Exception("mkdir failed: " + parent);
        FileInputStream input = new FileInputStream(source);
        FileOutputStream output = new FileOutputStream(destination, false);
        byte[] buffer = new byte[16384];
        int count;
        while ((count = input.read(buffer)) > 0) output.write(buffer, 0, count);
        output.close();
        input.close();
    }

    private static void copyAssetFile(Context value, String assetName, File destination) throws Exception {
        File parent = destination.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) throw new Exception("mkdir failed: " + parent);
        InputStream input = value.getAssets().open(assetName);
        FileOutputStream output = new FileOutputStream(destination, false);
        byte[] buffer = new byte[16384];
        int count;
        while ((count = input.read(buffer)) > 0) output.write(buffer, 0, count);
        output.close();
        input.close();
    }

    private static void copyAssetTree(Context value, String assetName, File destination) throws Exception {
        String[] children = value.getAssets().list(assetName);
        if (children == null || children.length == 0) {
            copyAssetFile(value, assetName, destination);
            return;
        }
        if (!destination.exists() && !destination.mkdirs()) {
            throw new Exception("mkdir failed: " + destination);
        }
        for (String child : children) {
            copyAssetTree(value, assetName + "/" + child, new File(destination, child));
        }
    }

    private static String network(Context value) {
        try {
            ConnectivityManager manager = (ConnectivityManager) value.getSystemService(Context.CONNECTIVITY_SERVICE);
            NetworkInfo info = manager == null ? null : manager.getActiveNetworkInfo();
            return info == null ? "none" : info.getTypeName() + ":" + info.getState();
        } catch (Throwable ignored) {
            return "unknown";
        }
    }

    private static String resolveEndpoint(Context value) {
        try {
            ApplicationInfo info = value.getPackageManager().getApplicationInfo(value.getPackageName(), 128);
            if (info.metaData != null) {
                String configured = info.metaData.getString("blustone.instrumented.endpoint");
                if (configured != null && !configured.trim().isEmpty()) return configured.trim();
            }
        } catch (Throwable ignored) {}
        return DEFAULT_ENDPOINT;
    }

    private static String stack(Throwable throwable) {
        if (throwable == null) return "";
        StringWriter writer = new StringWriter();
        throwable.printStackTrace(new PrintWriter(writer));
        return writer.toString();
    }

    private static void put(JSONObject object, String key, Object value) {
        try { object.put(key, value == null ? JSONObject.NULL : value); } catch (Throwable ignored) {}
    }

}
