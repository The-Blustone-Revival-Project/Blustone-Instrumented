# BLUSTONE - Instrumented

This directory contains the side-by-side diagnostic build and its local event
collector. The original `com.vshower.prd_sr` package and APKs are not replaced.

## Build

From the workspace root:

```powershell
python tools/build-instrumented-apk.py
```

The output is `analysis/instrumented-apk/BLUSTONE-Instrumented.apk` with:

- package `com.vshower.prd_sr.instrumented`;
- label `BLUSTONE - Instrumented`;
- a distinct signing key at `analysis/instrumented-apk/blustone-instrumented.jks`;
- the preserved working native/assets archive;
- the existing native crash probe plus Java lifecycle, touch, uncaught-exception,
  local-file, device, and logcat telemetry.

The build uses `tools/patch-native-ui-animation.py` to generate an
instrumented-only `libnative_core` copy. The patch redirects the native
launcher literal `pv-prd.vshower.com` to `http://10.0.2.2:8080` through the
host-compatible `10.0.2.2:8080` literal, and makes the BlueStacks-only
`UI_MA_L1` video animation return null instead of crashing. The original
library is read-only and is never overwritten.

Before the native engine opens LevelDB, `Telemetry` installs
`instrumentation/assets/instrumented-seed-complete-ui-delta-v2/UI_XML_RO.db`.
It preserves the native multi-SSTable base and adds only the verified launcher
records `EN/SR_FLOW/7_UI_FL7` and `EN/SR_GLOBAL/0_GL_PROGRESS/0_PROGRESS`.
The English `DEFINE_COLOR` alias is deliberately absent because it reproduces
the native `BuildColorTable` assertion.

The native diagnostic library also emits `BLUSTONE_DB_TRACE` records for the
exported `CGMLevelDB` JSON/string getters. These records contain local lookup
keys and return status, so a later resource/LevelDB failure can be tied to a
specific key without changing the database or game response data.

## Collector

```powershell
docker compose -f instrumentation/docker-compose.yml up --build -d
```

The collector listens on `http://127.0.0.1:8099` and the APK reaches it through
`http://10.0.2.2:8099` from BlueStacks or the Android Emulator.

- UI: `http://127.0.0.1:8099/`
- health: `http://127.0.0.1:8099/healthz`
- event API: `POST http://127.0.0.1:8099/v1/events`
- artifact API: `POST http://127.0.0.1:8099/v1/artifacts`
- durable local stream: `instrumentation/collector/data/events.ndjson`
- durable artifact stream: `instrumentation/collector/data/artifacts.ndjson` and
  `instrumentation/collector/data/artifacts/`

If Docker is unavailable, the APK still writes a bounded local fallback at
`files/instrumentation/events.ndjson` inside its own application data.

On startup and when selected files change, the diagnostic APK uploads local
state artifacts to the Docker collector: `cloud/v2pv.acct`, `local/CDN.db`,
`local/USER.db`, `local/UI_XML_RO.db`, `local/ETC.db`, and the downloaded
`E_NEW.jet`/`E_MIDAGE.jet`. This is local-machine diagnostic storage, not a
production telemetry service; the account artifact can contain private tokens.

## Install

The build script only installs when explicitly passed `--install`; it targets
the side-by-side package and never uses `pm install -r` against the original
package.

```powershell
python tools/build-instrumented-apk.py --install
```
