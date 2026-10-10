#!/usr/bin/env python3
"""Concurrent forum_en body fetcher.

Same discipline as tools/forum-en-fetch.py (control gate, status ledger, 000 is
never a result) but with a small worker pool, because this corpus is ~1,800
bodies and a serial pass does not fit the session budget.

Resumable: skips any target already present on disk with a non-zero size.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research-fetch/1.0"
CONTROL = (
    "http://web.archive.org/web/2021/"
    "https://bs.visualshower.com/files/attach/images/75605/303/534/001/"
    "725a8e175454a533e96dac68fc5fdb49.jpg"
)

_lock = threading.Lock()
_done = 0
_total = 0
_tally: dict[str, int] = {}


def is_image(b: bytes) -> str:
    if b[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return ""


def one(sess: requests.Session, url: str, tries: int, sleep: float) -> tuple[str, bytes, int]:
    for i in range(1, tries + 1):
        try:
            r = sess.get(url, timeout=120, allow_redirects=True)
            if r.status_code != 200:
                return str(r.status_code), r.content or b"", i
            body = r.content or b""
            if body:
                return "200", body, i
            return "200-empty", b"", i
        except Exception:  # noqa: BLE001 - transport failure
            pass
        time.sleep(sleep * i + random.uniform(0, 2))
    return "000", b"", tries


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tries", type=int, default=6)
    ap.add_argument("--sleep", type=float, default=2.0)
    args = ap.parse_args()

    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    # ---- control gate --------------------------------------------------
    print("=== POSITIVE CONTROL (75605/303/534/001) ===", flush=True)
    s0 = requests.Session()
    s0.headers.update({"User-Agent": UA})
    dest = os.path.join(outdir, "_control.jpg")
    st, body, tries = one(s0, CONTROL, 12, 2.0)
    ok = st == "200" and is_image(body) == "jpeg" and len(body) > 1000
    with open(dest, "wb") as fh:
        fh.write(body)
    print(f"control: code={st} bytes={len(body)} sig={body[:8].hex()} "
          f"image={is_image(body) or '-'} tries={tries} -> {'PASS' if ok else 'FAIL'}", flush=True)
    if not ok:
        print("CONTROL FAILED - zeros would be uninterpretable. ABORT.", file=sys.stderr, flush=True)
        return 2

    rows = []
    with open(args.queue, "r", encoding="utf-8") as fh:
        for ln in fh:
            if ln.strip():
                a, b = ln.rstrip("\n").split("\t")[:2]
                rows.append((a, b))

    todo = []
    for name, url in rows:
        p = os.path.join(outdir, name)
        if os.path.exists(p) and os.path.getsize(p) > 500:
            continue
        todo.append((name, url))
    global _total
    _total = len(todo)
    print(f"=== BATCH {len(todo)} targets ({len(rows)-len(todo)} already on disk) ===", flush=True)

    lf = open(args.ledger, "a", encoding="utf-8", newline="\n")
    if lf.tell() == 0:
        lf.write("name\tstatus\ttries\tbytes\tsig8\timage\n")
    lf_lock = threading.Lock()

    def work(item):
        name, url = item
        sess = requests.Session()
        sess.headers.update({"User-Agent": UA})
        st, body, tries = one(sess, url, args.tries, args.sleep)
        sig = body[:8].hex() if body else ""
        img = is_image(body) if body else ""
        if body:
            p = os.path.join(outdir, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(body)
        with lf_lock:
            lf.write(f"{name}\t{st}\t{tries}\t{len(body)}\t{sig}\t{img}\n")
            lf.flush()
        global _done
        with _lock:
            _done += 1
            _tally[st] = _tally.get(st, 0) + 1
            d = _done
            if d % 20 == 0 or st != "200":
                print(f"[{d}/{_total}] {name} status={st} bytes={len(body)} tries={tries} "
                      f"tally={_tally}", flush=True)
        return st

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(work, todo))
    finally:
        lf.close()
    print(f"=== DONE tally={_tally} ===", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
