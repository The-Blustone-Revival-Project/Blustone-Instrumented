#!/usr/bin/env python3
"""Probe every forum_en 175/ attachment URL and record the exact HTTP status.

Positive control runs first and aborts the batch if it fails, so a zero is only
readable as a real absence. Every target's status is written to a TSV ledger;
'000' (transport failure) is recorded as such and is never a result.
"""
import io
import os
import random
import sys
import time

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CONTROL = ("http://web.archive.org/web/2021/https://bs.visualshower.com/files/attach/images/"
           "75605/303/534/001/725a8e175454a533e96dac68fc5fdb49.jpg")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) blustone-research/1.0"
QUEUE = "recovered-assets/forum-en-2026-10-05/queue/queue-img175.tsv"
LEDGER = "recovered-assets/forum-en-2026-10-05/get-img/_ledger-img175.tsv"
OUT = "recovered-assets/forum-en-2026-10-05/get-img"


def is_jpeg(b):
    return b[:3] == b"\xff\xd8\xff"


s = requests.Session()
s.headers.update({"User-Agent": UA})

# --- control gate -------------------------------------------------------
ctrl = "000"
for i in range(1, 7):
    try:
        r = s.get(CONTROL, timeout=45)
        if r.status_code == 200 and is_jpeg(r.content) and len(r.content) > 1000:
            ctrl = "PASS"
            break
    except Exception:  # noqa: BLE001
        pass
    time.sleep(4 * i)
print(f"control: {ctrl}")
if ctrl != "PASS":
    print("CONTROL FAILED - ABORT", file=sys.stderr)
    raise SystemExit(2)

rows = []
with open(QUEUE, encoding="utf-8") as fh:
    for ln in fh:
        if ln.strip():
            n, u = ln.rstrip("\n").split("\t")[:2]
            rows.append((n, u))

tally = {}
with open(LEDGER, "w", encoding="utf-8", newline="\n") as lf:
    lf.write("name\tstatus\ttries\tbytes\tsig8\n")
    for i, (n, u) in enumerate(rows, 1):
        st, b, tries = "000", b"", 0
        dest = os.path.join(OUT, n)
        if os.path.exists(dest) and os.path.getsize(dest) > 2000:
            st, tries = "200-on-disk", 0
        else:
            for k in range(1, 4):
                try:
                    r = s.get(u, timeout=45)
                    st, b, tries = str(r.status_code), r.content or b"", k
                    if st == "200" and len(b) > 2000:
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with open(dest, "wb") as f:
                            f.write(b)
                        break
                    if st == "404":
                        break
                except Exception:  # noqa: BLE001
                    st, b, tries = "000", b"", k
                time.sleep(2 * k + random.uniform(0.5, 2))
        tally[st] = tally.get(st, 0) + 1
        lf.write(f"{n}\t{st}\t{tries}\t{len(b)}\t{b[:8].hex() if b else ''}\n")
        if st not in ("404", "200-on-disk"):
            print(f"  [{i}/{len(rows)}] {n} status={st} bytes={len(b)}", flush=True)
        if i % 40 == 0:
            print(f"  [{i}/{len(rows)}] tally={tally}", flush=True)
        time.sleep(0.6)

print(f"TOTAL {len(rows)} targets, tally={tally}")
