#!/usr/bin/env python3
"""Misc checks against the forum_en census + parsed bodies."""
import io
import json
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ids = json.load(open("recovered-assets/forum-en-2026-10-05/census/en-post-ids.json", encoding="utf-8"))
byid = {r["id"]: r for r in ids}
print(f"EN ids: {len(ids)}")

for probe in ("192349", "100013", "100257", "10362", "105776", "121631"):
    r = byid.get(probe)
    if r:
        print(f"  {probe}: PRESENT caps={r['captures']} first={r['first_ts']} shapes={r['shapes']} statuses={r['statuses']}")
    else:
        print(f"  {probe}: ABSENT from the EN census")

# era distribution by first capture year
from collections import Counter
yr = Counter(r["first_ts"][:4] for r in ids)
print("\nfirst-capture year distribution:", dict(sorted(yr.items())))

# capture-count distribution -> which ids are most heavily archived (best fetch odds)
cc = Counter()
for r in ids:
    c = r["captures"]
    cc["1" if c == 1 else "2-3" if c <= 3 else "4-9" if c <= 9 else "10-24" if c <= 24 else "25+"] += 1
print("capture-count buckets:", dict(cc))

# numeric density in bodies + replies of what we have
recs = [r for r in json.load(open("recovered-assets/forum-en-2026-10-05/parsed-partial.json", encoding="utf-8"))
        if not r.get("error") and r.get("has_doc_div")]
NUM = re.compile(r"\d[\d,\.]*")
print(f"\nparsed real posts: {len(recs)}")
tot_r = 0
for r in recs:
    reps = [l for l in r.get("replies", "").split("\n") if NUM.search(l)]
    tot_r += len(reps)
    if reps:
        print(f"  {r['id']:>7} replies-with-numerals={len(reps)}")
        for l in reps[:4]:
            print("       |", l.strip()[:170])
print(f"total reply lines carrying numerals: {tot_r}")
