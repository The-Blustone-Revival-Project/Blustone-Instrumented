#!/usr/bin/env python3
"""Locate every image attachment referenced by the attendance/login forum docs,
and check whether the bytes were recovered locally."""
import html
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOTS = [
    r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\forum-en-2026-10-05",
    r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets",
]
DOCS = ["386474", "691643", "675557", "1561517", "1167975", "1422054",
        "1479784", "456343", "1393319", "1187734", "1209881"]

# index every image filename present anywhere in recovered-assets
have = set()
for r in ROOTS:
    for dp, _d, fs in os.walk(r):
        for f in fs:
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                have.add(f.lower())
print("image files present in recovered-assets:", len(have))

for d in DOCS:
    hits = []
    for sub in ("body", "body-latest", "topup", "get-list"):
        p = os.path.join(ROOTS[0], "pass2", sub, d + ".html")
        if not os.path.exists(p):
            continue
        raw = open(p, "rb").read().decode("utf-8", "replace")
        for m in re.finditer(r'([^"\'\s<>]+\.(?:png|jpe?g|gif|webp))', raw, re.I):
            fn = m.group(1)
            hits.append(fn)
        break
    uniq = sorted(set(hits))
    print("\n### doc %s  images referenced: %d" % (d, len(uniq)))
    for fn in uniq:
        base = fn.split("/")[-1].split("\\")[-1].lower()
        print("    %-55s %s" % (fn, "PRESENT" if base in have else "not-recovered"))