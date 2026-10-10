#!/usr/bin/env python3
"""Cross-locale availability: for each EN forum_en post id, which other locales
also have an archived body capture?

Purely local over the paged CDX files. Answers whether a future pass can obtain
the same post in zh-cn/jp/ko/zh-tw for corroboration, without any network use.
"""
import glob
import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DSRL = re.compile(r"[?&]document_srl=(\d+)")
LANGS = re.compile(r"[?&]l=([A-Za-z-]+)")

lang_by_id: dict[str, set] = {}
rows = 0
for p in sorted(glob.glob("recovered-assets/forum-en-2026-10-05/census/page-*.tsv")):
    for ln in open(p, encoding="utf-8"):
        f = ln.rstrip("\n").split("\t")
        if len(f) < 5:
            continue
        rows += 1
        orig = f[2]
        q = orig.split("?", 1)[1] if "?" in orig else ""
        if "mid=forum_en" not in q:
            continue
        m = DSRL.search(q)
        if not m:
            continue
        lm = LANGS.search(q)
        lang = lm.group(1).lower() if lm else "default"
        lang_by_id.setdefault(m.group(1), set()).add(lang)

print(f"rows scanned: {rows}")
print(f"distinct ids with any locale body row: {len(lang_by_id)}")
combo = Counter()
for pid, ls in lang_by_id.items():
    combo[tuple(sorted(ls))] += 1
print("\nlocale combinations (top 15):")
for k, v in combo.most_common(15):
    print(f"  {v:>5}  {'+'.join(k)}")

en = {p for p, l in lang_by_id.items() if "en" in l}
multi = {p for p, l in lang_by_id.items() if len(l) > 1}
print(f"\nids available in EN:            {len(en)}")
print(f"ids available in >1 locale:     {len(multi)}  ({100*len(multi)/max(1,len(lang_by_id)):.1f}% of all ids)")
for want in ("zh-cn", "jp", "ko", "zh-tw"):
    s = {p for p, l in lang_by_id.items() if want in l}
    print(f"  {want:6s}: {len(s):>5} ids   (also EN: {len(s & en)})")
out = {p: sorted(l) for p, l in sorted(lang_by_id.items(), key=lambda kv: int(kv[0]))}
with open("recovered-assets/forum-en-2026-10-05/census/locale-by-id.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1)
print("\nwrote census/locale-by-id.json")
