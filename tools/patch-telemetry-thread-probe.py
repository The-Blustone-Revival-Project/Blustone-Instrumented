"""Insert the thread-state probe and stderr logcat buffer into Telemetry.java.

Kept as a script so the edit is reviewable and re-runnable instead of being a
large hand-applied patch. Run from the workspace root:

    python tools/patch-telemetry-thread-probe.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src" / "Telemetry.java"

PROBE = '''
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
'''

OLD_LOGREADER = (
    'process = Runtime.getRuntime().exec(new String[]{"logcat", "-v", "threadtime", '
    '"-b", "main", "-b", "system", "-b", "crash", "*:V"});'
)
NEW_LOGREADER = (
    '// "stderr" is included so anything the native library writes to '
    'stdout/stderr\n'
    '                // is captured too; that is the channel a native trace '
    'stub would use.\n'
    '                process = Runtime.getRuntime().exec(new String[]{"logcat", "-v", '
    '"threadtime",\n'
    '                        "-b", "main", "-b", "system", "-b", "crash", "-b", '
    '"stderr", "*:V"});'
)

OLD_HEARTBEAT = """                emit("heartbeat", snapshot(context));
                scheduleArtifactUpload();"""
NEW_HEARTBEAT = """                emit("heartbeat", snapshot(context));
                // Sample thread blocking state alongside the heartbeat. Cheap
                // enough to always run, and it is the only signal that
                // distinguishes a lock deadlock from waiting on the network.
                emitThreadStates();
                scheduleArtifactUpload();"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "emitThreadStates" in src:
        print("already patched")
        return 0

    anchor = "    private Telemetry() {}"
    if src.count(anchor) != 1:
        raise SystemExit(f"anchor not unique: {src.count(anchor)}")
    src = src.replace(anchor, anchor + "\n" + PROBE)

    if src.count(OLD_LOGREADER) != 1:
        raise SystemExit("logcat exec line not found exactly once")
    src = src.replace(OLD_LOGREADER, NEW_LOGREADER)

    if src.count(OLD_HEARTBEAT) != 1:
        raise SystemExit("heartbeat block not found exactly once")
    src = src.replace(OLD_HEARTBEAT, NEW_HEARTBEAT)

    TARGET.write_text(src, encoding="utf-8")
    print(f"patched {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
