# 2.8.0.1+4

Two instrumentation additions that exist to answer one question the project
could not previously answer: **why is the client hung?**

## 1. Thread blocking-state probe

The client stalls on the title screen. Everything observed from outside said
"asleep", which does not distinguish the causes that matter:

- blocked on a lock or condition variable (a callback that will never be
  signalled), versus
- waiting on a socket, versus
- waiting on a timer, versus
- genuinely idle.

Telemetry now samples `/proc/self/task/<tid>/{stat,wchan,comm}` for every
thread on each heartbeat and emits a `thread_states` event. Reading its own
`/proc` needs no root, so this works inside the app.

This immediately produced the answer. On the stalled client:

```
main thread   tid 5309   state S   wchan SyS_epoll_wait
94 threads: 70 futex_wait_queue_me, 12 SyS_epoll_wait, 3 hrtimer_nanosleep, 3 running
```

The main thread is parked in the HTTP event loop, **not** on a mutex, and the
process is not deadlocked. Combined with the socket evidence (one
`CLOSE_WAIT` to the replica, no pending outbound request) this says the engine
is *waiting* for a transfer or callback that will not arrive, rather than
blocked on a lock. That redirected the investigation away from "deadlock" and
toward "the CDN step completes and then nothing calls the next step".

## 2. `logcat -b stderr`

The reader now also captures the `stderr` buffer. That is the channel a native
trace stub would use, and it also picks up anything the engine writes directly
to stdout/stderr.

## 3. `--keep-asserts` build flag

The shipped native patch set makes the game's assertion machinery silent:
`RMAssert` (0x10B3ABC) is stubbed to `movs r0,#0; bx lr`, and two call-site
conditionals (0x107FA10, 0x784CFE) are inverted. A failing assertion is
therefore stepped over silently, which makes "the replica sent something wrong"
look exactly like "the client hung".

```powershell
python tools/build-instrumented-apk.py --keep-asserts --install
```

leaves all three live. **Result: nothing fires.** The stall is not a silenced
assertion, so this stays off by default. It is worth keeping because the next
missing-response failure will be silent otherwise.

The build script now runs the native patcher itself, so the flags always
produce a coherent `libnative_core` instead of reusing a stale override.

## Collector changes (this repository)

- `GET /v1/events/search?q=&event=&since=&limit=` - substring search over the
  ring, so a specific line does not have to be found by paging the newest 2000.
- `GET /v1/stats` - adds `event_types` and `log_tags` histograms that are
  cumulative for the life of the collector. Counts survive ring eviction, so
  "there were 12 CPVCDN lines an hour ago" stays answerable.
- `data/notable.ndjson` - lines matching assertions, `BLUSTONE_*`, `CPVCDN`,
  `PV_CDN_*`, `[AST]`/`[CDN]`/`[JET]`, fatal signals and crashes are also
  appended to a file that is never rotated. The ring is bounded and the client
  is noisy; without this a one-off failure leaves no trace at all.

## Server changes (in the main workspace, not this repo)

`BLUSTONE_TRACE_CONNECTIONS=1` tracks TCP connections at the socket level, so a
client that opens a connection and never speaks HTTP becomes visible instead of
looking like silence. Keep-alive/header timeouts are now explicit and long
rather than Node's 5 s defaults.
