#!/usr/bin/env python3
"""Polite forum_en fetcher: global rate limit, long backoff, resumable.

The archive rate-limits hard and answers with transport failures (recorded as
000). The failure mode here was per-worker backoff, which let 4 workers hammer
together. This uses ONE global minimum interval between requests regardless of
worker count, so throughput is capped by politeness rather than by threads.

Resumable: skips targets already on disk with a real (non-error-page) size.
"""

from __future__ import annotations

import argparse
import io
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) blustone-research/1.0 (+read-only archive fetch)"
CONTROL = (
    "http://web.archive.org/web/2021/"
    "https://bs.visualshower.com/files/attach/images/75605/303/534/001/"
    "725a8e175454a533e96dac68fc5fdb49.jpg"
)
WAYBACK_ERR = b"<!DO"  # the archive's own "not archived" page


class Gate:
    def __init__(self, interval: float):
        self.interval = interval
        self.lock = threading.Lock()
        self.last = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            dt = self.interval - (now - self.last)
            if dt > 0:
                time.sleep(dt + random.uniform(0, 0.8))
            self.last = time.monotonic()


def is_jpeg(b: bytes) -> bool:
    return b[:3] == b"\xff\xd8\xff"


def is_error_page(b: bytes) -> bool:
    return b[:8].startswith(WAYWAY_ERR) or b[:200].lower().startswith(b"<!do")


def one(sess, gate, url, tries, backoff, want_bytes=False):
    """Returns (status, body, tries). '000' only ever means transport failure."""
    for i in range(1, tries + 1):
        gate.wait()
        try:
            r = sess.get(url, timeout=150, allow_redirects=True)
            if r.status_code == 200:
                body = r.content or b""
                if body and not (want_bytes and is_error_page(body)):
                    return "200", body, i
                return "200-empty-or-errpage", body, i
            return str(r.status_code), r.content or b"", i
        except Exception:  # noqa: BLE001
            if i == tries:
                return "000", b"", i
            time.sleep(backoff * i + random.uniform(1, 5))
    return "000", b"", tries


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--interval", type=float, default=4.0, help="global seconds between requests")
    ap.add_argument("--tries", type=int, default=5)
    ap.add_argument("--backoff", type=float, default=8.0)
    ap.add_argument("--budget", type=int, default=0, help="stop after N targets (0=all)")
    ap.add_argument("--cooldown", type=float, default=0.0, help="seconds to sleep before starting")
    a = ap.parse_args()

    if a.cooldown:
        print(f"cooling down {a.cooldown}s before first request", flush=True)
        time.sleep(a.cooldown)

    outdir = os.path.abspath(a.outdir)
    os.makedirs(outdir, exist_ok=True)

    print("=== POSITIVE CONTROL (75605/303/534/001) ===", flush=True)
    s0 = requests.Session()
    s0.headers.update({"User-Agent": UA})
    g0 = Gate(a.interval)
    st, body, tries = one(s0, g0, CONTROL, 8, 8.0, want_bytes=True)
    ok = st == "200" and is_jpeg(body) and len(body) > 1000
    with open(os.path.join(outdir, "_control.jpg"), "wb") as fh:
        fh.write(body)
    print(f"control: code={st} bytes={len(body)} sig={body[:8].hex()} jpeg={is_jpeg(body)} "
          f"tries={tries} -> {'PASS' if ok else 'FAIL'}", flush=True)
    if not ok:
        print("CONTROL FAILED - zeros would be uninterpretable. ABORT.", file=sys.stderr, flush=True)
        return 2

    rows = []
    with open(a.queue, encoding="utf-8") as fh:
        for ln in fh:
            if ln.strip():
                n, u = ln.rstrip("\n").split("\t")[:2]
                rows.append((n, u))

    todo = []
    for n, u in rows:
        p = os.path.join(outdir, n)
        if os.path.exists(p) and os.path.getsize(p) > 500:
            continue
        todo.append((n, u))
    if a.budget:
        todo = todo[: a.budget]
    print(f"=== BATCH {len(todo)} targets ({len(rows)-len(todo)} already on disk) "
          f"workers={a.workers} interval={a.interval}s ===", flush=True)

    gate = Gate(a.interval)
    tally: dict[str, int] = {}
    tlock = threading.Lock()
    done = 0
    lf = open(a.ledger, "a", encoding="utf-8", newline="\n")
    if lf.tell() == 0:
        lf.write("name\tstatus\ttries\tbytes\tsig8\n")
    llock = threading.Lock()

    def work(item):
        nonlocal done
        name, url = item
        sess = requests.Session()
        sess.headers.update({"User-Agent": UA})
        st, body, tries = one(sess, gate, url, a.tries, a.backoff)
        if st == "200" and body and not is_error_page(body):
            p = os.path.join(outdir, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(body)
        with llock:
            lf.write(f"{name}\t{st}\t{tries}\t{len(body)}\t{body[:8].hex() if body else ''}\n")
            lf.flush()
        with tlock:
            done += 1
            tally[st] = tally.get(st, 0) + 1
            d = done
            if d % 15 == 0 or st != "200":
                print(f"[{d}/{len(todo)}] {name} status={st} bytes={len(body)} tries={tries} tally={tally}",
                      flush=True)

    try:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            list(ex.map(work, todo))
    finally:
        lf.close()
    print(f"=== DONE tally={tally} ===", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
