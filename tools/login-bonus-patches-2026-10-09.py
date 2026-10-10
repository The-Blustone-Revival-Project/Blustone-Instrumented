#!/usr/bin/env python3
"""Read the vsfan patch notes + supply-station pages for attendance/login changes."""
import html
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

V = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\vsfan-reward-2026-10-09"


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


for fn in sorted(os.listdir(V)):
    if not fn.endswith(".txt"):
        continue
    t = open(os.path.join(V, fn), encoding="utf-8", errors="replace").read()
    low = t.lower()
    if not re.search(r"login|attend|sign.?in|daily", low):
        continue
    print("\n" + "=" * 74)
    print("### " + fn)
    print("=" * 74)
    for m in re.finditer(r"login|attend|daily|sign.?in", low):
        a = max(0, m.start() - 420)
        print("   >> ..." + clean(t[a:m.end() + 420]) + "...")
        print()