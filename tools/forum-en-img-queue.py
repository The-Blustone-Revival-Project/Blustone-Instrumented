#!/usr/bin/env python3
"""Emit a probe queue for forum_en's own attachment namespace.

The namespace was derived from the bodies actually read: board prefix 175, and
the directory pair is (document_srl % 1000)/(document_srl // 1000) - the same
scheme share_en used, where post 197745 -> 565/745/197.

Wayback rewrites img src to im_ form whether or not the bytes exist, so every
URL here is a CANDIDATE. Each is queued for a nearest-capture fetch, and the
positive control must pass in the same session before any zero is readable.
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

recs = [r for r in json.load(open("recovered-assets/forum-en-2026-10-05/parsed.json", encoding="utf-8"))
        if not r.get("error")]

# nearest-capture replay is timestamp-independent in form: web/2018/<orig>
WB = "http://web.archive.org/web/2018/"


def nearest(u: str) -> str:
    return WB + u

rows = []
seen = set()
for r in recs:
    for im in r.get("imgs", []):
        if "/files/attach/images/175/" not in im:
            continue
        # strip the wayback prefix down to the original URL
        o = re.sub(r"^.*?(https?://bs\.visualshower\.com/files/attach/images/175/)", r"\1", im)
        o = o.replace("im_", "")
        if o in seen:
            continue
        seen.add(o)
        pid = r["id"]
        ext = o.rsplit(".", 1)[-1].lower()
        name = f"img/{pid}_{o.rsplit('/',1)[-1]}"
        # nearest-capture replay: web/2018/<original> is form-independent, so a
        # 404 there means "no capture of this exact URL at any timestamp"
        rows.append((name, nearest(o), pid, r["date"][:10], r["author"], r["title"][:40], ext))

os.makedirs("recovered-assets/forum-en-2026-10-05/queue", exist_ok=True)
with open("recovered-assets/forum-en-2026-10-05/queue/queue-img175.tsv", "w", encoding="utf-8", newline="\n") as fh:
    for n, u, *_ in rows:
        fh.write(f"{n}\t{u}\n")
with open("recovered-assets/forum-en-2026-10-05/queue/queue-img175-index.tsv", "w", encoding="utf-8", newline="\n") as fh:
    fh.write("post\tdate\tauthor\ttitle\text\n")
    for n, u, pid, d, a, t, ext in rows:
        fh.write(f"{pid}\t{d}\t{a}\t{t}\t{ext}\n")
print(f"wrote {len(rows)} candidate image URLs from {len(seen)} distinct files")
for pid, d, a, t, ext in [(x[2], x[3], x[4], x[5], x[6]) for x in rows]:
    pass
print("\nby post:")
from collections import Counter
for k, v in Counter(r[2] for r in rows).most_common():
    print(f"  post {k:>8}: {v} image(s)")
