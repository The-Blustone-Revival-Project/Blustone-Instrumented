# 2.8.0.1+3

Two fixes. Both are instrumentation defects that were suppressing evidence, not
game-logic changes: no change to the native library, the resource seed, or the
`10.0.2.2:8080` CDN redirect.

## 1. The telemetry stream was unusable

**Symptom.** Every session's event ring was 100% `RANN [RSM]` lines. Grouping
the last 2000 events by tag gave 1997/2000 `RANN`. No `BLUSTONE_*` line, no
native assertion and no LevelDB lookup survived - the diagnostic channel the
whole project depends on was effectively blind, and a session failing in a
specific place looked like it had produced nothing.

**Cause.** The engine logs its resource manager at `*:V`, emitting
`[RSM] 'BATCHDRAW<n>'(0x...), type:18 is registered.` with a matching
`Removing Res:` line roughly every 17 ms while a loading animation plays. A
title screen alone produces thousands per minute. The collector keeps a bounded
ring, so the useful lines were evicted before anyone could read them.

**Fix** (in `Telemetry`):

- native `RANN [RSM]` render/resource-manager lines are dropped at the source,
  before they are queued, so they never reach the local fallback stream or the
  collector;
- remaining lines are repeat-suppressed on a shape of `tag + first 4 message
  words` with digits collapsed - the first 5 occurrences of a shape are always
  forwarded, then it is dropped;
- the filter reports what it discarded through periodic `android_log_filtered`
  events (`dropped_noise` / `dropped_repeat`), so it is never silently hiding
  evidence.

`BLUSTONE_INSTRUMENTED`, `BLUSTONE_DB_TRACE`, `BLUSTONE_ARM` and
`BLUSTONE_RESOURCE_GUARD` are never filtered. With the filter in place the
engine's own startup log becomes readable, including the `Debug Log Level`
line and the `[ERR] [ADS]` failure that explain part of the current stall.

Also documented in the README: a single tap makes the preserved `MainActivity`
raise the engine to `RMDBG_LOG(FULL)` (it is `RMDBG_NONE` otherwise), and
event text lives in `data.line`.

## 2. A diagnostic mode was left permanently enabled

`restorePreRepairCdn` is commented as an "A/B diagnostic mode" that restores
the pre-repair `CDN.db` snapshot, but it ran on **every launch**. That meant
the diagnostic snapshot overwrote whatever the native CDN manager (`CPVCDN2`)
had written during the previous session, so the engine could never accumulate
its own CDN index and every launch presented it with the same fixed
mid-download state.

That matters because the native HTTP layer has resume support - the binary
contains `Couldn't resume download`, `File already completely downloaded`,
`partial download completed, closing connection` and a `rewinding stream ...
bytecount =` trace. A snapshot that records an in-flight download is exactly
the state in which the client can wait indefinitely for a resume that never
arrives, and the current BlueStacks session does hang immediately after
`GET /reslist_*.list` with no further request and no pending socket.

The restore is now opt-in at build time:

```powershell
python tools/build-instrumented-apk.py --restore-pre-repair-cdn --install
```

The default build leaves the native CDN index alone. The switch is a generated
`BuildConfig.RESTORE_PRE_REPAIR_CDN` constant rather than a checked-in file, so
the value used is visible in the build metadata
(`analysis/instrumented-apk/BUILD-METADATA.json`).

Honest note: this is a real defect and worth fixing on its own merits, but it
did **not** by itself unblock the current stall - the client still hangs at the
same point with the restore disabled. Recorded here so nobody re-derives it.

## Verified

- `python tools/build-instrumented-apk.py --install` succeeds and signs.
- The app launches, the collector receives events, and the filtered stream shows
  the engine's real startup log.
- The replica's own suite is unchanged by this release.
