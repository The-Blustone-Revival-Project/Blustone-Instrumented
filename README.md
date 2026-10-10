# BLUSTONE Instrumented

BLUSTONE Instrumented is a side-by-side diagnostic Android build for
authorized research into the BLUSTONE client. It lets the original
`com.vshower.prd_sr` app remain installed while the instrumented package
`com.vshower.prd_sr.instrumented` records additional runtime evidence.

## What it is

The APK adds local diagnostics around the game without turning the project
into a replacement game client or a production telemetry service. It can
record:

- Android lifecycle, touch, crash, device, logcat, and local-file events;
- native local-database lookup traces; and
- selected local-state artifacts for offline analysis.

The repository also contains a Docker-based collector. The collector receives
those events and artifacts on the local machine and provides a small browser
view for inspecting recent events.

## Why use it

Use the instrumented build when you need to:

- investigate startup, UI, resource, or native-client failures;
- compare instrumented behavior with the original app while keeping the two
  installations separate;
- capture evidence from an Android Emulator or BlueStacks session; or
- preserve runtime observations for later offline analysis.

## Log filtering (important when reading a session)

The game's native engine is extremely chatty at `*:V`. Its resource manager
emits thousands of `RANN [RSM] ... is registered.` / `Removing Res:` lines per
second while a title or loading animation is on screen. On its own that noise
evicts every useful line - native assertions, `BLUSTONE_*` tags, LevelDB
lookup traces - from the collector's bounded event ring before anyone can read
it, which makes a session look like it produced "no information".

The build therefore filters at the source, in `Telemetry`:

- **Noise drop**: native `RANN [RSM]` render/resource-manager lines are never
  queued, never written to the local fallback stream, and never posted.
- **Repeat suppression**: any remaining line is keyed on a coarse shape (log
  tag plus the first few words, digits collapsed). The first 5 occurrences of a
  shape are always forwarded, then the shape is dropped, so a chatty loop costs
  5 lines instead of thousands while a genuinely new message family is still
  captured.
- **Visibility**: the filter reports what it dropped through periodic
  `android_log_filtered` events (`dropped_noise`, `dropped_repeat`).

`BLUSTONE_INSTRUMENTED`, `BLUSTONE_DB_TRACE`, `BLUSTONE_ARM`, and
`BLUSTONE_RESOURCE_GUARD` lines are never filtered. If you need raw logcat
anyway, read it directly with `adb logcat` rather than through the collector.

## How to use it

1. Download `BLUSTONE-Instrumented.apk` from the
   [latest GitHub release](https://github.com/The-Blustone-Revival-Project/Blustone-Instrumented/releases).

2. From this repository, start the local collector before launching the app:

   ```powershell
   docker compose up --build -d
   ```

3. Install the APK side-by-side with the original app:

   ```powershell
   adb install -r .\BLUSTONE-Instrumented.apk
   ```

4. Run the instrumented app in an Android Emulator or BlueStacks. It sends
   collector traffic to the host through `http://10.0.2.2:8099`.

5. Inspect the collector at <http://127.0.0.1:8099/>. Its health endpoint is
   <http://127.0.0.1:8099/healthz>, and collected data is stored locally under
   `collector/data/`.

   ```powershell
   Invoke-WebRequest http://127.0.0.1:8099/v1/events?limit=2000
   Invoke-WebRequest http://127.0.0.1:8099/v1/artifacts
   ```

   Events carry their text in `data.line` for `android_log` events. Filter that
   field for `BLUSTONE`, `ASSERTION`, `__bGlobalAssert`, and `.cpp` to see the
   interesting lines.

6. Stop the collector when finished:

   ```powershell
   docker compose down
   ```

## Native debug level

The game engine logs at `RMDBG_NONE` by default. The preserved `MainActivity`
raises it to `RMDBG_LOG(FULL)` from `dispatchTouchEvent`, so a single tap on the
game window enables the engine's own log output. Without a tap you only get the
pre-GL framework lines.

## Data handling

The collector is intended for local use. Captured artifacts can contain
account, device, or other private application state. Keep `collector/data/`
local, and do not commit or share its contents without reviewing them first.

## Preserving the native CDN index

Earlier builds ran an "A/B diagnostic" on every launch that replaced
`files/local/CDN.db` with a fixed pre-repair snapshot. That stopped the native
CDN manager (`CPVCDN2`) from ever keeping the index it wrote during the
previous session, and gave it the same mid-download state on every start - which
is a plausible way to make it wait forever for a download resume.

That restore is now opt-in:

```powershell
python tools/build-instrumented-apk.py --restore-pre-repair-cdn --install
```

Default builds leave the native CDN index untouched. The value is compiled in
as `BuildConfig.RESTORE_PRE_REPAIR_CDN` and is recorded in the build's
`BUILD-METADATA.json`.

## Reading a stalled session

The client currently stalls on the title screen. Two collector endpoints make
that diagnosable instead of guesswork:

- `GET /v1/events/search?q=<text>&event=<name>&limit=<n>` searches the event
  ring instead of paging it.
- `GET /v1/stats` includes `event_types` and `log_tags` histograms that are
  cumulative for the life of the collector, so a line that has already been
  evicted from the ring is still counted.

`thread_states` events report every thread's kernel blocking state. On a stalled
client this is the decisive datum: the main thread sitting in
`SyS_epoll_wait` means the engine is *waiting* for something, whereas
`futex_wait_queue_me` would mean it is deadlocked on a lock.

Lines matching assertions, `BLUSTONE_*`, `CPVCDN`, `PV_CDN_*`, `[AST]`,
`[CDN]`, `[JET]`, fatal signals and crashes are additionally appended to
`collector/data/notable.ndjson`, which is never rotated. The ring is bounded and
the client is noisy, so that file is the durable evidence trail.

## Seeing why the client refuses to continue

The engine's own assertion reporter is silenced in the default build, so a wrong
replica response used to look exactly like a hang. Build with:

```powershell
python tools/build-instrumented-apk.py --assert-log-continue --install
```

This keeps `ASSERTION Failed on 'file(line)'` logging and the on-screen
assertion box, but does not exit. The failure may still fault where the caller
dereferences the value it just asserted on - the assertion is in the log first,
naming the parser and source line, which is the point.

`--keep-asserts` leaves every assertion fully live, including the exit. It is
useful for confirming the video/`UI_MA_L1` compatibility patches are what keeps
BlueStacks alive, but the client will die on the first real assertion.

## Client source and reproducible local tooling

The migrated diagnostic Java/native source, seed assets, build/patch tools, and host regression tests are now included. See [migrated build documentation](docs/build/MIGRATED-SOURCE.md). Private signing keys, toolchains, build inputs and retained fixtures stay under ignored `local/`. Existing release metadata was preserved; this local-only migration does not rebuild, install or publish an APK.
