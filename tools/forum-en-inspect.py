#!/usr/bin/env python3
"""Inspect parsed forum_en bodies. UTF-8 safe on stdout (GUARD rule 2)."""
import argparse
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ap = argparse.ArgumentParser()
ap.add_argument("--file", required=True)
ap.add_argument("--top", type=int, default=15)
ap.add_argument("--chars", type=int, default=600)
ap.add_argument("--grep", default=None)
ap.add_argument("--minchars", type=int, default=0)
ap.add_argument("--withbody", action="store_true")
ap.add_argument("--limit", type=int, default=0)
a = ap.parse_args()

recs = json.load(open(a.file, encoding="utf-8"))
recs = [r for r in recs if not r.get("error")]
if a.minchars:
    recs = [r for r in recs if r["chars"] >= a.minchars]
if a.grep:
    import re
    rx = re.compile(a.grep, re.I)
    recs = [r for r in recs if rx.search(r["body"]) or rx.search(r["title"])]

print(f"{len(recs)} records match")
for r in recs[: a.limit or a.top]:
    print("-" * 78)
    print(f"{r['file']:>16}  chars={r['chars']:>6} digits={r['digits']:>4} imgs={len(r['imgs'])}")
    print(f"  title  [{r['title_src']}] {r['title'][:150]}")
    print(f"  author {r['author']!r}   date {r['date']}   views={r.get('views')}  replies={r.get('n_comments')}")
    if a.withbody:
        print("  BODY:")
        for ln in r["body"][: a.chars].split("\n"):
            if ln.strip():
                print("    | " + ln[:160])
