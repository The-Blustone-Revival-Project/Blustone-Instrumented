#!/usr/bin/env python3
"""Dump every vsfan patch note's date + Changes block, flagging attendance/login lines."""
import html
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

V = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\vsfan-reward-2026-10-09"


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


rows = []
for fn in sorted(os.listdir(V)):
    if not (fn.startswith("Patch_") and fn.endswith(".txt")):
        continue
    t = open(os.path.join(V, fn), encoding="utf-8", errors="replace").read()
    name = fn[:-4]
    m = re.search(r"Date ([A-Za-z]+ \d+, \d{4})", t)
    date = m.group(1) if m else "?"
    i = t.find("Changes")
    j = t.find("Bug Fixes", i)
    body = clean(t[i:j]) if i >= 0 else "(no Changes block)"
    rows.append((date, name, body))

rows.sort(key=lambda r: r[0])

for date, name, body in rows:
    hits = re.findall(r"[^.]*?(attendance|Attendance|login|Login|sign|Sign|supply|Supply|Veteran|veteran|reset)[^.]*\.", body)
    flag = "  <== ATTENDANCE" if hits else ""
    print("\n%-12s %s%s" % (date, name, flag))
    if hits:
        for h in hits:
            print("      * " + h.strip())
    else:
        print("      (no attendance/login/supply line)")