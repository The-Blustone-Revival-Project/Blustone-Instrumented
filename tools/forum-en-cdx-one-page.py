#!/usr/bin/env python3
"""Retry a single CDX page until it returns a parseable 200 body."""
import argparse
import json
import os
import time

import requests

ap = argparse.ArgumentParser()
ap.add_argument("--dir", required=True)
ap.add_argument("--page", type=int, required=True)
ap.add_argument("--limit", type=int, default=2000)
ap.add_argument("--tries", type=int, default=25)
args = ap.parse_args()

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 research-fetch/1.0"})
url = (
    "http://web.archive.org/cdx/search/cdx?url=bs.visualshower.com&matchType=domain"
    "&collapse=urlkey&output=json&filter=original:.*forum_en.*"
    f"&limit={args.limit}&page={args.page}"
)
out = os.path.join(args.dir, f"page-{args.page:03d}.tsv")
for i in range(1, args.tries + 1):
    try:
        r = s.get(url, timeout=240)
        if r.status_code == 200:
            t = r.text.strip()
            print(f"status=200 tries={i} len={len(t)} head={t[:200]!r}", flush=True)
            if t.startswith("["):
                data = json.loads(t)
                if data and isinstance(data[0], list):
                    rows = data[1:]
                    with open(out, "w", encoding="utf-8", newline="\n") as fh:
                        for row in rows:
                            fh.write("\t".join(str(x) for x in row) + "\n")
                    print(f"WROTE {out} rows={len(rows)}", flush=True)
                    break
    except Exception as exc:  # noqa: BLE001
        print(f"attempt {i}: {type(exc).__name__}", flush=True)
    time.sleep(3 * i)
else:
    print(f"EXHAUSTED {args.tries} tries - page {args.page} NOT obtained", flush=True)
