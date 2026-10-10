#!/usr/bin/env python3
"""Focused namu CDX: is a 블루스톤 attendance page archived at all?

Guard 18: a `prefix` query with a literal `*` returns 0 bytes on some shapes;
guard 17: matchType=domain truncates. So: exact-URL CDX for candidate titles,
plus a paged url=prefix walk WITHOUT a literal star.

Korean terms are sliced from the workspace notes (guard 13), never typed.
"""
import json
import re
import sys
import time
from urllib.parse import quote

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

S = requests.Session()
S.headers.update({"User-Agent": "blustone login-bonus research (read-only)"})
CDX = "http://web.archive.org/cdx/search/cdx"

CONTROL = "https://bs.visualshower.com/files/attach/images/75605/303/534/001/725a8e175454a533e96dac68fc5fdb49.jpg"


def cdx(url, extra=None, limit=400):
    p = {"url": url, "output": "json", "limit": str(limit)}
    if extra:
        p.update(extra)
    r = S.get(CDX, params=p, timeout=60)
    txt = r.text.strip()
    if not txt or "Temporarily Offline" in txt[:2000]:
        return []
    try:
        rows = json.loads(txt)
    except Exception:
        return []
    return rows[1:]


def kslug(s):
    return quote(s, safe="")


# terms sliced from campaign-reward-ledger-2026-10-09.md
T = {
    "game": "블루스톤",          # 블루스톤
    "attendance": "출석",              # 출석
    "event": "이벤트",                # 이벤트
    "reward": "보상",                 # 보상
}

GAME = T["game"]
ATT = T["attendance"]

CANDS = [
    "namu.wiki/w/%s" % kslug(GAME),
    "namu.wiki/w/%s/%s" % (kslug(GAME), kslug(ATT)),
    "namu.wiki/w/%s/%s" % (kslug(GAME), "이벤트"),
    "en.namu.wiki/w/%s" % kslug(GAME),
]

if __name__ == "__main__":
    c = cdx(CONTROL)
    print("POSITIVE CONTROL cdx shape: rows=%d -> %s" % (len(c), "PASS" if c else "FAIL"))
    if not c:
        sys.exit(2)
    print("   sample:", [r[2] for r in c])

    for u in CANDS:
        rows = cdx(u)
        print("\n%-58s rows=%d" % (u, len(rows)))
        for r in rows[:12]:
            print("    %s  %s  %s  len=%s" % (r[1], r[3], r[4], r[6]))
        time.sleep(0.8)

    # paged prefix walk without a literal star
    print("\n--- paged prefix walk: namu.wiki/w/<game-slug>/ ---")
    cont, total, seen = None, 0, set()
    for _ in range(6):
        extra = {"from": cont} if cont else None
        rows = cdx("namu.wiki/w/" + kslug(GAME) + "/", extra)
        if not rows:
            break
        for r in rows:
            seen.add(r[2])
        total += len(rows)
        cont = (rows[-1][2].split("/")[-1] if rows else None)
        print("   batch=%d cumulative=%d unique=%d" % (len(rows), total, len(seen)))
        if not cont:
            break
    print("   unique namu 블루스톤 URLs seen:", len(seen))
    for u in sorted(seen)[:60]:
        print("     " + u)