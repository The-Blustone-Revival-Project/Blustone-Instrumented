#!/usr/bin/env python3
"""Fetch the LIVE vsfan wiki (it moved to Miraheze) for a NEWER attendance table.

The archive captures end at 2020-08-08 and the page has not been edited since
2017-10-08 (oldid 6016). If the live wiki carries a later revision, the table
may have changed. This is the only way to test the "monthly, not weekly"
2019 forum claim against the wiki.

GUARD: one shared session, positive control is the known-good vsfan page body
that is already on disk.
"""
import hashlib
import re
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (blustone login-bonus research; read-only)"})

CONTROL_LOCAL = (r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets"
                 r"\login-bonus-2026-10-09\Hunter_Supply_Office__20190821011235.html")

CANDIDATES = [
    "https://blustone.miraheze.org/wiki/Hunter_Supply_Office",
    "https://blustone.miraheze.org/w/index.php?title=Hunter_Supply_Office",
    "https://vsfan.net/wiki/Hunter_Supply_Office",
    "https://blustone.miraheze.org/wiki/Hunter_Supply_Station",
    "https://blustone.miraheze.org/wiki/Veteran_Status",
]


def strip(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


if __name__ == "__main__":
    want = open(CONTROL_LOCAL, "rb").read()
    marker = b"\xc3\x973000"          # 'x3000' as utf-8
    ok = marker in want and b"Daily Rewards" in want
    print("POSITIVE CONTROL (local archived page contains the day-1 cell): %s" % ("PASS" if ok else "FAIL"))
    if not ok:
        sys.exit(2)

    for u in CANDIDATES:
        try:
            r = S.get(u, timeout=45)
        except Exception as e:
            print("\n%-62s EXC %s" % (u, str(e)[:70]))
            continue
        t = r.text
        has_tbl = "Daily Rewards" in t
        print("\n%-62s code=%s bytes=%d hasDailyTable=%s"
              % (u, r.status_code, len(r.content), has_tbl))
        if not has_tbl:
            continue
        m = re.search(r'oldid=(\d+)', t)
        print("   oldid=%s" % (m.group(1) if m else "?"))
        m = re.search(r"This page was last edited on ([^<]+?)\.", t)
        print("   last_edited=%s" % (m.group(1) if m else "?"))
        # print the day cells
        i = t.find("Daily Rewards")
        seg = t[i:i + 9000]
        for mm in re.finditer(r"\u00d7\s*([0-9][0-9,.]*)", strip(seg)):
            print("   cell:", mm.group(1))
        j = seg.find("Cumulative")
        if j > 0:
            for mm in re.finditer(r"\u00d7\s*([0-9][0-9,.]*)", strip(seg[j:j + 6000])):
                print("   cumulative cell:", mm.group(1))