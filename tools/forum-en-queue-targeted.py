#!/usr/bin/env python3
"""Build a targeted queue of forum_en bodies by explicit id, using the best
available archived capture for each. Used to chase named high-value posts
(the FAQ's cited damage-formula topic, vendor accounts, and the highest-traffic
ids) rather than crawling the whole board.
"""
import argparse
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ap = argparse.ArgumentParser()
ap.add_argument("--ids", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--pick", nargs="*", required=True, help="explicit ids")
ap.add_argument("--topreads", type=int, default=0, help="add N ids by capture count")
a = ap.parse_args()

ids = {r["id"]: r for r in json.load(open(a.ids, encoding="utf-8"))}
sel = []
for p in a.pick:
    if p in ids:
        sel.append(ids[p])
    else:
        print(f"  (not in census: {p})")
if a.topreads:
    rest = sorted(ids.values(), key=lambda r: -r["captures"])
    have = {r["id"] for r in sel}
    for r in rest:
        if r["id"] in have:
            continue
        sel.append(r)
        if len(sel) - len(a.pick) >= a.topreads:
            break

def clean_orig(r):
    """Pick the best body URL for an id.

    Rejects, in order of preference lost:
      * act=...           - a login/member form capture, not the document
      * a second document_srl - the row belongs to a different post than r['id']
      * page=             - a later page of a thread, incomplete on its own
    """
    best = None
    for o in r["orig"]:
        if "document_srl=" not in o and "/forum_en/" not in o:
            continue
        ids = re.findall(r"document_srl=(\d+)", o)
        if len(ids) >= 2 and all(i != r["id"] for i in ids):
            continue
        if ids and ids[0] != r["id"]:
            continue
        if "act=" in o or "page=" in o:
            continue
        score = 0
        if "l=en" in o:
            score += 2
        if o.startswith("https"):
            score += 1
        if best is None or score > best[0]:
            best = (score, o)
    return best[1] if best else None


os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
    for r in sel:
        ts = r["canonical_ts"] or r["last_ts"]
        orig = clean_orig(r)
        if not orig:
            print(f"  (no clean body URL in census rows: {r['id']})")
            continue
        scheme = "https" if orig.startswith("https") else "http"
        rest = orig.split("://", 1)[1].split("/", 1)[1]
        url = f"http://web.archive.org/web/{ts}/{scheme}://bs.visualshower.com/{rest}"
        fh.write(f"body/{r['id']}.html\t{url}\n")
print(f"wrote {len(sel)} targets to {a.out}")
