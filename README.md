# BLUSTONE - Instrumented

This repository distributes the side-by-side BLUSTONE diagnostic build and
its local event collector. It does not replace the original
`com.vshower.prd_sr` installation: the diagnostic APK uses the separate
package `com.vshower.prd_sr.instrumented`.

## Current release

- Release: `2.8.0.1+1`
- Blustone app version: `2.8.0.1` (`versionCode 28010`)
- Instrumented build number: `1`
- Package: `com.vshower.prd_sr.instrumented`
- Label: `BLUSTONE - Instrumented`

Release versions use this format:

```text
<blustone-app-version>+<instrumented-build-number>
```

For example, the first build based on Blustone `2.8.0.1` is
`2.8.0.1+1`; a later build from the same app version could be
`2.8.0.1+13`.

## APK

Download `BLUSTONE-Instrumented.apk` from the
[2.8.0.1+1 release](https://github.com/The-Blustone-Revival-Project/Blustone-Instrumented/releases/tag/2.8.0.1%2B1).
The release asset is the signed, aligned diagnostic APK; APKs are deliberately
not committed to this repository.

Install it alongside the original app with the Android platform tools:

```powershell
adb install -r .\BLUSTONE-Instrumented.apk
```

The local `artifacts/<release-version>/` directory contains the generated
instrumented APK outputs and the original split APK set used for provenance.
That directory is gitignored. Original APKs are kept locally and are not
published as repository content or release assets.

## Local collector

The collector accepts diagnostic events and local-state artifacts from the
instrumented APK and stores them under `collector/data/`:

```powershell
docker compose up --build -d
```

Endpoints:

- UI: <http://127.0.0.1:8099/>
- Health: <http://127.0.0.1:8099/healthz>
- Events: `POST http://127.0.0.1:8099/v1/events`
- Artifacts: `POST http://127.0.0.1:8099/v1/artifacts`

The APK reaches the collector through `http://10.0.2.2:8099` from an Android
Emulator or BlueStacks. The diagnostic build also redirects the native
compatibility-server endpoint to `http://10.0.2.2:8080`; this Compose file
starts the collector only, not that compatibility server.

Stop the collector with:

```powershell
docker compose down
```

Collector output can contain local account or device state. The collector
redacts sensitive fields in event JSON, but uploaded binary artifacts can
contain private tokens. Keep `collector/data/` local and do not commit or
share it.

## Publishing a release

Keep the canonical version in `VERSION`, place the signed APK at
`artifacts/<version>/instrumented/BLUSTONE-Instrumented.apk`, and keep the
original split APKs under the corresponding `original/` directory. Commit and
push the tracked repository files, then create the matching GitHub release
from the repository root:

```powershell
$version = (Get-Content .\VERSION -Raw).Trim()
gh release create $version `
  ".\artifacts\$version\instrumented\BLUSTONE-Instrumented.apk" `
  --title "BLUSTONE - Instrumented $version" `
  --generate-notes
```

The release tag and title must use the same `<app-version>+<build-number>`
value. Only the signed instrumented APK is uploaded.
