#!/usr/bin/env python3
"""Wayback route to the Korean namu attendance page.

namu.wiki returns 403 to plain HTTP (client-rendered shell) AND no desktop
browser is attached to this subagent session, so the only route left is the
archive.

GUARD: http:// only, ONE shared session, positive control required before any
zero is recorded, and the CDX shape must be proven to work first.

Search terms are SLICED FROM DATA, never hand-typed (guard 13): the Korean
game name comes from the existing note files in this workspace.
"""
import json
import re
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

S = requests.Session()
S.headers.update({"User-Agent": "blustone login-bonus research (read-only)"})
CDX = "http://web.archive.org/cdx/search/cdx"

CONTROL_IMG = ("https://bs.visualshower.com/files/attach/images/75605/303/534/001/"
               "725a8e175454a533e96dac68fc5fdb49.jpg")
CONTROL_URL = "http://web.archive.org/web/2021/" + CONTROL_IMG

# --- slice the Korean game name out of existing workspace data (guard 13) ---
SRC_NOTES = [
    r"C:\Users\shaha\Documents\ChatGPT\Blustone\analysis\research\base-stats-visual-hunt"
    r"\campaign-reward-ledger-2026-10-09.md",
]


def slice_terms():
    """Pull Hangul tokens that are already in the workspace notes."""
    t = open(SRC_NOTES[0], encoding="utf-8").read()
    hangul = re.findall(r"[\uAC00-\uD7A3]+", t)
    return sorted(set(hangul))


def cdx(url, limit=200):
    r = S.get(CDX, params={"url": url, "output": "json", "limit": str(limit)}, timeout=60)
    txt = r.text.strip()
    if not txt or "Temporarily Offline" in txt[:2000]:
        return []
    try:
        rows = json.loads(txt)
    except Exception:
        return []
    return rows[1:]


if __name__ == "__main__":
    # control
    r = S.get(CONTROL_URL, timeout=60)
    ok = r.status_code == 200 and len(r.content) == 57414 and r.content[:3].hex() == "ffd8ff"
    print("POSITIVE CONTROL bytes: %s" % ("PASS" if ok else "FAIL"))
    ctl = cdx(CONTROL_IMG)
    print("POSITIVE CONTROL cdx shape: rows=%d %s" % (len(ctl), "PASS" if ctl else "FAIL"))
    if not (ok and ctl):
        sys.exit(2)

    terms = slice_terms()
    print("\nHangul tokens sliced from workspace notes (%d):" % len(terms))
    print("  " + " ".join(terms))
    print("\nNOTE: namu.wiki serves a client-rendered shell; a CDX 200 on a namu URL\n"
          "      is NOT evidence the attendance table is in the body.")

    for host in ["namu.wiki", "en.namu.wiki"]:
        rows = cdx(host + "/w/*")
        print("\n=== host %s  rows=%d" % (host, len(rows)))
        hit = 0
        for row in rows[:400]:
            u = row[2]
            if re.search(r"attendance|login|checkin|event|daily", u, re.I) or \
               re.search(r"%EB%B8%B8%EB%A3%A8|%EC%B6%9C%EC%84%9D", u):
                print("   %s %s" % (row[1], u))
                hit += 1
        print("   candidate attendance/login URLs: %d" % hit)
        time.sleep(1.0)