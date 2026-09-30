gh release create '2.8.0.1+2' -R The-Blustone-Revival-Project/Blustone-Instrumented --title 'BLUSTONE - Instrumented 2.8.0.1+2' --notes @'
## 2.8.0.1+2 - logcat noise filter

Startup sessions on BlueStacks were producing an unusable event stream. The
native engine logs its resource manager at `*:V`, emitting thousands of
`RANN [RSM] ... is registered.` / `Removing Res:` lines per second while a
loading animation plays. Because the collector keeps a bounded ring, that noise
evicted the native assertions, `BLUSTONE_*` tags, and LevelDB lookup traces
before they could be read - a session would appear to contain nothing useful
even though the game was failing in a specific, identifiable place.

This build filters at the source in `Telemetry`:

- native `RANN [RSM]` render/resource-manager lines are dropped before they are
  queued, so they never reach the local fallback stream or the collector;
- remaining lines are repeat-suppressed on a coarse shape (tag plus the first
  few words, digits collapsed) - the first 5 occurrences of a shape are always
  forwarded, then it is dropped;
- the filter reports what it discarded via periodic `android_log_filtered`
  events with `dropped_noise` / `dropped_repeat`.

`BLUSTONE_INSTRUMENTED`, `BLUSTONE_DB_TRACE`, `BLUSTONE_ARM`, and
`BLUSTONE_RESOURCE_GUARD` are never filtered. With the filter in place the
`[FWK]` / `[ERR]` / `[ADS]` / `[JUC]` engine lines and the full engine
`Debug Log Level` line become readable, which is what makes the remaining
startup stall diagnosable.

Also documented in the README: the tap-to-enable `RMDBG_LOG(FULL)` behavior,
and where event text lives (`data.line`).

No change to game logic, native library, resource seed, or the CDN redirect.

'@ --target main 'C:\Users\shaha\Documents\ChatGPT\Blustone\analysis\instrumented-apk\BLUSTONE-Instrumented.apk#BLUSTONE-Instrumented.apk'
