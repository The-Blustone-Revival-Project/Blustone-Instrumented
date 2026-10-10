#!/usr/bin/env python3
"""Extract the Veteran_Status ladder table from raw HTML.

Bears on G9: the wiki's '40 960 for Guru 3' only means something if the ladder
is a clean doubling series. Extract the FULL table, not the flattened text
(the flattened .txt showed 12 labels against 9 numbers).

GUARD: control = the raw HTML must still contain 'Guru3 need 40 960'.
"""
import html
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = (r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\vsfan-reward-2026-10-09"
       r"\Veteran_Status.html")


def strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


t = open(SRC, "rb").read().decode("utf-8", "replace")
print("control 'Guru3 need 40 960' present:", bool(re.search(r"Guru3 need 40 960", strip(t))))

i = t.find("Daily Reward")
j = t.find("Veteran level change")
print("\n--- prose before the table ---")
print(strip(t[i:j])[:900])

for m in re.finditer(r"<table[^>]*>(.*?)</table>", t, re.S):
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S)
    print("\n--- table with %d rows ---" % len(rows))
    for r in rows:
        cs = [strip(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        print("   | " + " | ".join(cs))

print("\n--- reward/point prose mentions ---")
prose = strip(re.sub(r"<table.*?</table>", " ", t, flags=re.S))
for kw in ["40 960", "40960", "points per day", "points per days", "F2P", "Veteran Points"]:
    for m in re.finditer(re.escape(kw), prose, re.I):
        print("   [%s] ...%s..." % (kw, prose[max(0, m.start() - 200):m.end() + 200]))

m = re.search(r"oldid=(\d+)", t)
print("\noldid:", m.group(1) if m else "?")
m = re.search(r"This page was last edited on ([^<]+?)\.", t)
print("last_edited:", m.group(1) if m else "?")