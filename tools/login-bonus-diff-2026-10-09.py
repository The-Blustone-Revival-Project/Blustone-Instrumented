#!/usr/bin/env python3
"""Byte-identity of the attendance table region across the three captures,
plus the Veteran_Status / List_of_Blustone_Items cross-corroboration.

This distinguishes "the table is stable" (a maintained statement) from
"the whole page is frozen" (one lucky revision never edited again).
"""
import hashlib
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\login-bonus-2026-10-09"
V = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\vsfan-reward-2026-10-09"

CAPS = ["20190821011235", "20191015115618", "20200808181724"]


def region(t, start_id, tag="table"):
    i = t.find('id="%s"' % start_id)
    if i < 0:
        return None
    a = t.rfind("<%s" % tag, 0, i)
    b = t.find("</%s>" % tag, i)
    return t[a:b + len(tag) + 3]


print("### attendance table region sha256 per capture")
seen = {}
for st in CAPS:
    p = os.path.join(OUT, "Hunter_Supply_Office__%s.html" % st)
    if not os.path.exists(p):
        print(st, "MISSING")
        continue
    t = open(p, "rb").read().decode("utf-8", "replace")
    for rid in ("Daily_Rewards", "Cumulative_Attendence_Dates"):
        seg = region(t, rid)
        h = hashlib.sha256(seg.encode("utf-8")).hexdigest() if seg else "NONE"
        print("  %s  %-28s len=%-6s %s" % (st, rid, len(seg) if seg else 0, h[:32]))
        seen.setdefault(rid, set()).add(h)
    # whole page hash for contrast
    print("  %s  WHOLE PAGE                              len=%-6d %s"
          % (st, len(t), hashlib.sha256(t.encode("utf-8")).hexdigest()[:32]))
    # revision id
    m = re.search(r"oldid=(\d+)", t)
    print("  %s  oldid=%s" % (st, m.group(1) if m else "?"))

print()
print("### verdict")
for rid, hs in seen.items():
    print("  %-28s distinct digests across 3 captures = %d  -> %s"
          % (rid, len(hs), "STABLE" if len(hs) == 1 else "CHANGED"))

print()
print("=" * 70)
print("### List_of_Blustone_Items - 'Cumulative Attendence Dates' rows")
t = open(os.path.join(V, "List_of_Blustone_Items.txt"), encoding="utf-8", errors="replace").read()
for kw in ["login", "attend", "consecutive", "Daily", "Veteran Ticket", "Rupee Lottery"]:
    for m in re.finditer(re.escape(kw), t, re.I):
        print("  [%s] ...%s..." % (kw, t[max(0, m.start() - 160):m.end() + 160].replace("\n", " ")))
    print("  ---")