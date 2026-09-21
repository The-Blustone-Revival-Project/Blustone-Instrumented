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

6. Stop the collector when finished:

   ```powershell
   docker compose down
   ```

## Data handling

The collector is intended for local use. Captured artifacts can contain
account, device, or other private application state. Keep `collector/data/`
local, and do not commit or share its contents without reviewing them first.
