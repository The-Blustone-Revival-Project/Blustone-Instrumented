"""Add search, tag statistics and a durable notable-line stream to the collector.

The problem this solves: the collector keeps a bounded in-memory ring, and the
app's logcat stream is dominated by render spam. Even with the app-side noise
filter, anything that arrives late is gone from the ring before a human can
look at it, and a session that fails in one specific place looks empty.

Three additions, all server-side and all backwards compatible:

  GET /v1/events/search?q=<text>&event=<name>&since=<ms>&limit=<n>
      Case-insensitive substring search over the ring. The ring is small, so
      this is a straight scan; the point is not speed, it is not having to
      page through the newest 2000 lines to find one.

  GET /v1/stats
      Adds a per-event-type and per-log-tag histogram that is cumulative for the
      life of the collector. Counts survive ring eviction, so "we received 12
      CPVCDN lines an hour ago" is answerable even though the lines are gone.

  data/notable.ndjson
      Lines matching NOTABLE_PATTERNS are also appended to a separate file that
      is never rotated or truncated. This is the durable evidence trail for
      assertions, native tags, CDN errors and crashes.

Run from the workspace root:

    python tools/patch-collector-search.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "collector" / "server.js"

OLD_CONSTANTS = """const ring = [];
const ringLimit = 2000;
const artifacts = [];
const artifactLimit = 500;
let received = 0;
let rejected = 0;
let artifactsReceived = 0;
"""

NEW_CONSTANTS = """const ring = [];
const ringLimit = 2000;
const artifacts = [];
const artifactLimit = 500;
let received = 0;
let rejected = 0;
let artifactsReceived = 0;

// Durable, never-evicted stream for the lines that actually matter. The ring is
// bounded and the client is noisy, so without this a failure that happens once
// leaves no trace at all.
const notableFile = path.join(dataDir, "notable.ndjson");
const notablePatterns = [
  /BLUSTONE/,
  /\\bASSERT/i,
  /bGlobalAssert/,
  /\\.cpp\\b/,
  /CPVCDN/i,
  /PV_CDN_/,
  /\\[AST\\]/,
  /\\[CDN\\]/,
  /\\[JET\\]/,
  /\\bSIGSEGV\\b|\\bSIGABRT\\b|\\bSIGFPE\\b|\\bSIGBUS\\b/,
  /Fatal signal/,
  /tombstone/,
  /uncaught/i,
  /\\bTraceback\\b/,
  /Exception/,
  /\\bdlopen\\b|\\bundefined symbol\\b/,
  /thread_states/,
];
const eventTypeCounts = new Map();
const logTagCounts = new Map();
let notableCount = 0;

/** android_log lines look like "... I TAG    : message"; pull the tag out. */
function logTagOf(event) {
  if (!event || event.event !== "android_log") return null;
  const line = event.data && typeof event.data.line === "string" ? event.data.line : "";
  const match = line.match(/^\\S+\\s+\\S+\\s+\\d+\\s+\\d+\\s+[VDIWEF]\\s+([^:]+):/);
  return match ? match[1].trim() : null;
}

function isNotable(event) {
  if (!event) return false;
  if (event.event === "thread_states" || event.event === "thread_states_error") return true;
  const line = event.data && typeof event.data.line === "string" ? event.data.line : "";
  if (!line) return false;
  return notablePatterns.some((pattern) => pattern.test(line));
}

function bump(map, key) {
  if (!key) return;
  map.set(key, (map.get(key) || 0) + 1);
}
"""

OLD_APPEND = """  if (normalized.length) {
    fs.appendFileSync(eventFile, normalized.map((event) => JSON.stringify(event)).join("\\n") + "\\n", "utf8");
    received += normalized.length;
  }
  return normalized;
}"""

NEW_APPEND = """  if (normalized.length) {
    fs.appendFileSync(eventFile, normalized.map((event) => JSON.stringify(event)).join("\\n") + "\\n", "utf8");
    received += normalized.length;
  }
  for (const event of normalized) {
    bump(eventTypeCounts, event && event.event);
    bump(logTagCounts, logTagOf(event));
    if (isNotable(event)) {
      notableCount += 1;
      try {
        fs.appendFileSync(notableFile, JSON.stringify(event) + "\\n", "utf8");
      } catch (error) {
        // A failure to persist evidence must not drop the event itself.
        process.stderr.write(`notable append failed: ${error && error.message}\\n`);
      }
    }
  }
  return normalized;
}"""

OLD_STATS = """  if (request.method === "GET" && url.pathname === "/v1/stats") {
    return sendJson(response, 200, { received, rejected, artifacts_received: artifactsReceived, event_file: eventFile, artifact_file: artifactFile, ring_size: ring.length });
  }"""

NEW_STATS = """  if (request.method === "GET" && url.pathname === "/v1/stats") {
    return sendJson(response, 200, {
      received,
      rejected,
      artifacts_received: artifactsReceived,
      event_file: eventFile,
      artifact_file: artifactFile,
      notable_file: notableFile,
      notable_count: notableCount,
      ring_size: ring.length,
      // Cumulative for the life of the collector, so a line that has already
      // been evicted from the ring is still counted here.
      event_types: Object.fromEntries([...eventTypeCounts].sort((a, b) => b[1] - a[1])),
      log_tags: Object.fromEntries([...logTagCounts].sort((a, b) => b[1] - a[1]).slice(0, 40)),
    });
  }
  if (request.method === "GET" && url.pathname === "/v1/events/search") {
    const query = String(url.searchParams.get("q") || "").toLowerCase();
    const eventName = String(url.searchParams.get("event") || "");
    const since = Number(url.searchParams.get("since") || 0);
    const requested = Number(url.searchParams.get("limit") || 200);
    const limit = Math.max(1, Math.min(2000, Number.isFinite(requested) ? requested : 200));
    const matched = ring.filter((event) => {
      if (eventName && event.event !== eventName) return false;
      if (since && Number(event.ts) < since) return false;
      if (!query) return true;
      return JSON.stringify(event).toLowerCase().includes(query);
    });
    return sendJson(response, 200, { query, event: eventName, count: matched.length, events: matched.slice(-limit) });
  }"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "notableFile" in src:
        print("already patched")
        return 0

    for old, new, label in (
        (OLD_CONSTANTS, NEW_CONSTANTS, "constants"),
        (OLD_APPEND, NEW_APPEND, "appendEvents"),
        (OLD_STATS, NEW_STATS, "stats route"),
    ):
        if src.count(old) != 1:
            raise SystemExit(f"{label}: anchor found {src.count(old)} times, expected 1")
        src = src.replace(old, new)

    TARGET.write_text(src, encoding="utf-8")
    print(f"patched {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
