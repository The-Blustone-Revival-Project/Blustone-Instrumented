#!/usr/bin/env python3
"""Pass-2 forum_en fetcher: shared per-thread HTTP sessions + control gate.

Same discipline as tools/forum-en-fetch-concurrent.py — positive control first and
ABORT on failure, every HTTP status recorded, curl-style transport failure is
`000` and is NEVER a result, resumable against files already on disk.

The one change is connection reuse. tools/forum-en-fetch-concurrent.py builds a
fresh requests.Session per target, so no TCP/TLS connection is ever reused; every
body pays a full handshake against a rate-limiting host. Here each worker thread
keeps one Session (thread-local, so it is never shared across threads), which is
what the previous harness should have done.

`http://` only: on this host `https://web.archive.org` is REFUSED (WinError
10061) and that refusal masquerades as "the archive is gone".
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research-fetch/2.0"
CONTROL = (
    "http://web.archive.org/web/2021/"
    "https://bs.visualshower.com/files/attach/images/75605/303/534/001/"
    "725a8e175454a533e96dac68fc5fdb49.jpg"
)
CONTROL_SHA256 = "afd4a19eeb779651"  # first 16 hex of the known-good control digest

_tls = threading.local()


def session() -> requests.Session:
    s = getattr(_tls, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Connection": "keep-alive"})
        ad = HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
        s.mount("http://", ad)
        s.mount("https://", ad)
        _tls.s = s
    return s


def is_image(b: bytes) -> str:
    if b[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return ""


def one(url: str, tries: int, sleep: float) -> tuple[str, bytes, int]:
    s = session()
    for i in range(1, tries + 1):
        try:
            r = s.get(url, timeout=120, allow_redirects=True)
            if r.status_code != 200:
                return str(r.status_code), r.content or b"", i
            body = r.content or b""
            return ("200" if body else "200-empty"), body, i
        except Exception:  # noqa: BLE001 - transport failure, never a result
            pass
        time.sleep(sleep * i + random.uniform(0, 2.0))
    return "000", b"", tries


_lock = threading.Lock()
_done = 0
_total = 0
_tally: dict[str, int] = {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--tries", type=int, default=6)
    ap.add_argument("--sleep", type=float, default=1.5)
    ap.add_argument("--deadline-min", type=float, default=0.0,
                    help="stop issuing NEW requests after this many minutes "
                         "(in-flight ones still finish and are recorded)")
    args = ap.parse_args()

    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    print("=== POSITIVE CONTROL (75605/303/534/001) ===", flush=True)
    st, body, tries = one(CONTROL, 12, 2.0)
    ok = st == "200" and is_image(body) == "jpeg" and len(body) > 1000
    with open(os.path.join(outdir, "_control.jpg"), "wb") as fh:
        fh.write(body)
    print(f"control: code={st} bytes={len(body)} sig={body[:8].hex()} "
          f"image={is_image(body) or '-'} tries={tries} -> {'PASS' if ok else 'FAIL'}",
          flush=True)
    if not ok:
        print("CONTROL FAILED - zeros would be uninterpretable. ABORT.",
              file=sys.stderr, flush=True)
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

    global _total, _done
    _total = len(todo)
    print(f"=== BATCH {_total} targets ({len(rows)-_total} already on disk) ===", flush=True)

    lf = open(args.ledger, "a", encoding="utf-8", newline="\n")
    if lf.tell() == 0:
        lf.write("name\tstatus\ttries\tbytes\tsig8\timage\n")
    lf_lock = threading.Lock()
    t_start = time.time()
    deadline = t_start + args.deadline_min * 60 if args.deadline_min else None
    stop = threading.Event()

    def work(item):
        global _done
        name, url = item
        if deadline and time.time() > deadline:
            with lf_lock:
                lf.write(f"{name}\tSKIPPED-DEADLINE\t0\t0\t\t\n")
                lf.flush()
            return "SKIPPED-DEADLINE"
        st, body, tries = one(url, args.tries, args.sleep)
        if body:
            p = os.path.join(outdir, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(body)
        with lf_lock:
            lf.write(f"{name}\t{st}\t{tries}\t{len(body)}\t"
                     f"{body[:8].hex() if body else ''}\t{is_image(body) if body else ''}\n")
            lf.flush()
            _done += 1
            _tally[st] = _tally.get(st, 0) + 1
            d = _done
            el = time.time() - t_start
            if d % 20 == 0 or st != "200":
                rate = d / max(el / 60.0, 1e-9)
                print(f"[{d}/{_total}] {name} status={st} bytes={len(body)} "
                      f"tries={tries} rate={rate:.1f}/min tally={json.dumps(_tally)}",
                      flush=True)
        return st

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(work, todo))
    finally:
        lf.close()
        if deadline:
            stop.set()
    el = time.time() - t_start
    print(f"=== DONE {_done} attempts in {el/60:.1f} min tally={json.dumps(_tally)} ===",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())