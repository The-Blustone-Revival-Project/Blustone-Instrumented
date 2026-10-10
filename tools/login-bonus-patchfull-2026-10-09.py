#!/usr/bin/env python3
"""Full Changes block for the patches that mention attendance/login/supply."""
import html
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

V = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\vsfan-reward-2026-10-09"
WANT = ["Patch_1.0.8.0", "Patch_1.0.7.0", "Patch_1.0.6.1", "Patch_1.0.4.0", "Patch_1.1.6.0"]


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


for fn in sorted(os.listdir(V)):
    if not (fn.endswith(".txt") and any(fn.startswith(w) for w in WANT)):
        continue
    t = open(os.path.join(V, fn), encoding="utf-8", errors="replace").read()
    i = t.find("Changes")
    j = t.find("Bug Fixes", i)
    body = clean(t[i:j]) if i >= 0 else "(none)"
    print("\n" + "=" * 76)
    print("### " + fn)
    print("=" * 76)
    for s in re.split(r"(?<=\.)\s+(?=[A-Z])", body):
        print("  - " + s)