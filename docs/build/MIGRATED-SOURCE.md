# Migrated client source and host tooling

The client Java source is in src/, native probes in native/, compile stubs in stubs/, and seed assets in assets/. Existing collector, Compose, VERSION and release notes are preserved. VERSION now tracks the existing +15 release line. Historical release titles/statuses are normalized without rebuilding or replacing APK assets.

Build/patch/observe/device/battle tools are retained together under tools/ to preserve their interdependencies. Historical shared parsers are a pinned compatibility snapshot; DataDump owns their primary research copies. Runtime build inputs are independently copied to local/legacy-analysis/, SDK/JDK/NDK tooling to local/toolchains/, and signing identity to local/private/blustone-instrumented.jks.

```powershell
. ./tools/env.ps1
python tools/check-build-inputs.py
python -m unittest discover -s tools/tests -p 'test_*.py'
```

A future authorized build uses `python tools/build-instrumented-apk.py` and writes local/build/instrumented-apk. It must keep the original package separate, preserve the signing key, and satisfy the standing GitHub release requirement. This migration deliberately does not rebuild/install an APK or publish a release because the user requested local-only changes.

All retained native originals and source snapshots remain unchanged. Automated battle scripts remain idle; finder/guard tests are host-only. Historical exploratory tools may still describe retired experiments; current supported commands are listed here and in the migration report.
