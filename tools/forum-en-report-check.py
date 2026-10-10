#!/usr/bin/env python3
"""Health-check the report file itself (GUARD rule 2: verify the file, not the console).

Reports U+FFFD, CRLF, mojibake, Hangul, CJK, and whether Hangul/box-drawing
survived, plus a non-ASCII inventory. Also cross-checks the headline numbers
against the on-disk artifacts so a typo in the prose cannot hide.
"""
import glob
import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

P = "analysis/research/base-stats-visual-hunt/forum-en-census-2026-10-05.md"
raw = open(P, "rb").read()
t = raw.decode("utf-8")

print(f"file: {P}")
print(f"bytes: {len(raw)}   chars: {len(t)}   lines: {t.count(chr(10))+1}")
print(f"U+FFFD            : {t.count(chr(0xFFFD))}   (must be 0)")
print(f"CRLF              : {t.count(chr(13)+chr(10))}   (must be 0)")
print(f"lone CR           : {t.count(chr(13))}")
print(f"mojibake 'Ã'      : {t.count('Ã')}   (must be 0)")
print(f"em-dash U+2014    : {t.count(chr(0x2014))}")
print(f"Hangul            : {len(re.findall(r'[가-힣]', t))}")
print(f"CJK               : {len(re.findall(r'[一-鿿]', t))}")
print(f"box-drawing       : {len(re.findall(r'[─-╿]', t))}")
print(f"star glyph U+2605 : {t.count(chr(0x2605))}")
print(f"korean author name: {t.count('Maeko')+t.count('로이마스터')}")

nonascii = Counter(c for c in t if ord(c) > 127)
print("\nnon-ASCII inventory (top 20):")
for c, n in nonascii.most_common(20):
    print(f"   U+{ord(c):04X} {c!r} x{n}")

# ---- cross-check headline numbers against artifacts -------------------
base = "recovered-assets/forum-en-2026-10-05"
en = json.load(open(f"{base}/census/en-post-ids.json", encoding="utf-8"))
parsed = json.load(open(f"{base}/parsed.json", encoding="utf-8"))
real = [r for r in parsed if not r.get("error") and r.get("has_doc_div")]
distinct = {r["id"] for r in real}
loc = json.load(open(f"{base}/census/locale-by-id.json", encoding="utf-8"))
multi = sum(1 for v in loc.values() if len(v) > 1)
tables = sum(1 for r in real if r["n_tables"] > 0)

checks = [
    ("EN census ids", len(en), 3193),
    ("parsed records", len(parsed), 166),
    ("records with body", len(real), 162),
    ("DISTINCT posts read", len(distinct), 154),
    ("posts with an HTML table", tables, 0),
    ("multi-locale ids", multi, 2298),
    ("all-locale ids", len(loc), 3398),
    ("body chars", sum(r["chars"] for r in real), 76603),
    ("reply chars", sum(r["reply_chars"] for r in real), 65488),
]
print("\ncross-check against on-disk artifacts:")
ok = True
for name, got, want in checks:
    flag = "OK " if got == want else "MISMATCH"
    if got != want:
        ok = False
    print(f"   {flag} {name:<28} artifact={got:<8} report={want}")

# ledger sanity
led = f"{base}/get-img/_ledger-img175.tsv"
if os.path.exists(led):
    st = Counter(l.split("\t")[1] for l in open(led, encoding="utf-8").read().splitlines()[1:])
    print(f"\nimage ledger statuses: {dict(st)}")
    print("   OK 188/188 404" if st.get("404") == 188 else "   CHECK ledger")

print("\nRESULT:", "consistent" if ok and t.count(chr(0xFFFD)) == 0 and t.count(chr(13)) == 0 else "PROBLEM")
