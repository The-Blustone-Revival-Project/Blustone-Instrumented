# 2.8.0.1+5

Two changes. The first is a fix; the second is the diagnostic that made the
remaining bug visible at all.

## Fix: the launcher was missing four `url_list` keys

`CPVDataMgr` resolves URLs by `url_key`, and the binary carries the failure
string `cannot find cdn url`. A key the client looks up but the replica does not
advertise leaves it with no address and no request.

The launcher response advertised only `_SR`, `ad_unit_id_1`, `d_unit_id_1`,
`maintenance`, `api` and `cdn`. The working community private server advertises
`Main`, `auth`, `sns_list`, `cdn` and `resource` — so `Main`, `auth`, `sns_list`
and especially `resource` (the CDN base used to build `/<name>_<stamp>.pkg`)
were all missing. The login response already had the right five; only the
launcher response was wrong.

With all five added the client completes login, shows the initial 23 MB data
download prompt, runs the whole lobby bootstrap, and reaches the village, the
Airport, the Expedition Area, the Snowfield stage map and Prepare for Battle.
Airport progress reads `1/30` instead of `0/30`.

## New: `--assert-log-continue`

Until now a wrong replica response was indistinguishable from a hang. The
shipped patch set stubs `_RMAssert` (0x10B3ABC) to a no-op and inverts two
call-site conditionals, so a failing assertion is stepped over *silently*.

`--assert-log-continue` keeps the real reporter and replaces only the
terminating `blx` at `0x10b3b5c` with a branch to the function's own epilogue at
`0x10b3b4c`. The assertion is still logged with its source file and line, the
process is not killed, and the client shows an on-screen ASSERTION box it
previously could not survive.

```powershell
python tools/build-instrumented-apk.py --assert-log-continue --install
```

This is what turned the remaining mission bug from invisible into specific:

```text
[AST] [RequestStart]
(sStageID.size() > 1) is FALSE
ASSERTION Failed on 'SRMStageSync.cpp(67)'
```

`CSRSyncMStage::RequestStart` is being sent with an empty `stage_id`. Execution
may still fault where the caller dereferences the value it just asserted on —
that is fine, the assertion is in the log first, naming the parser and line.

`--keep-asserts` no longer returns early, so the video / `UI_MA_L1`
compatibility patches always apply; it now only controls the three assertion
patches. (Leaving all assertions live makes the client die on the known
BlueStacks `UI_MA_L1` video fault at the lobby bootstrap, which is why the
earlier version of that flag was useless.)

## Collector

Unchanged since `2.8.0.1+4`: `/v1/events/search`, cumulative `event_types` and
`log_tags` histograms, and `collector/data/notable.ndjson`.

## Verified

- `python tools/build-instrumented-apk.py --assert-log-continue --install`
  builds, signs and installs; the patched library is byte-checked and the
  literal pool at `0x10b3b60` is left untouched.
- Village -> Airport -> cruise -> Expedition Area -> Snowfield -> Prepare for
  Battle all reachable, and the Begin Battle tap produces the assertion above
  with the game still running.
