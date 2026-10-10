#!/usr/bin/env python3
"""Exhaustively extract every numeral from the forum_en bodies actually read,
with per-line context, so section 2 of the report can be complete rather than
illustrative. Every line is emitted; nothing is summarised away.
"""

from __future__ import annotations

import io
import json
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

NUMTOK = re.compile(r"\d[\d,\.]*%?")
IDENT = re.compile(
    r"\b(captain|lantern|mowgli|nene|tyltyl|hermes|denali|levi|diana|athena|akasha|"
    r"karl|lapis|metis|bruce|sylvester|loke|hecate|balian|sienna|robin|gerard|rebecca|"
    r"vincent|westfield|locke|bear|riko|audrey|genovia|celine|leon|juno|lawrence|"
    r"harley|crocus|anemone|calibur|heidi|joy|patrone|windblade|selene|alia|"
    r"teddy|sparky|lunar|hunter|hero|character|monster)\b",
    re.I,
)
STATWORD = re.compile(
    r"\b(hp|atk|def|defence|defense|health|damage|power|strength|rating|stat|stats)\b", re.I
)

recs = [r for r in json.load(open("recovered-assets/forum-en-2026-10-05/parsed.json", encoding="utf-8"))
        if not r.get("error") and r.get("has_doc_div")]
recs.sort(key=lambda r: r["id"])
# flag id/file disagreement: a URL carrying a second document_srl resolves to a
# different post than the filename claims, and the parser reports the true one
for r in recs:
    r["mismatch"] = r["id"] not in r["file"]

grand = 0
for r in recs:
    lines = [(("BODY"), l) for l in r["body"].split("\n")] + [(("REPLY"), l) for l in r.get("replies", "").split("\n")]
    hits = []
    for where, ln in lines:
        if not ln.strip():
            continue
        toks = NUMTOK.findall(ln)
        # drop pure view/reply counts already reported as metadata
        real = [t for t in toks if t not in ("0",)]
        if real:
            hits.append((where, ln.strip(), real))
    if not hits:
        continue
    print("=" * 90)
    print(f"{r['id']}  {r['date']}  {r['author']}  views={r['views']}  :: {r['title']}"
          + ("   [ID MISMATCH vs filename]" if r.get("mismatch") else ""))
    idents = sorted(set(m.group(0) for m in IDENT.finditer(r['body'] + '\n' + r.get('replies', ''))))
    print(f"  identity tokens in thread: {idents if idents else 'none'}")
    print(f"  stat-word present in thread: {bool(STATWORD.search(r['body'] + chr(10) + r.get('replies','')))}")
    for where, ln, toks in hits:
        print(f"   [{where}] {toks}")
        print(f"        {ln[:230]}")
        grand += len(toks)

print("=" * 90)
print(f"TOTAL numeral tokens across {len(recs)} posts (body + replies): {grand}")
