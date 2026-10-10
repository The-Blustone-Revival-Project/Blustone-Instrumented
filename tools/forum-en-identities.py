#!/usr/bin/env python3
"""Inventory every hunter-identity token that appears in the forum_en bodies and
replies actually read, with the post and the exact line.

This is identity/context evidence for the project's catalogue work, NOT stat
coverage: a name with no numeral attached cannot become a base tuple. The tool
exists so the report can say exactly which identities are attested here and in
what company they appear.
"""
import io
import json
import re
import sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

NAMES = r"""captain|lantern|mowgli|nene|tyltyl|hermes|denali|levi|diana|athena|akasha|karl|lapis|
metis|bruce|bradley|sylvester|loke|hecate|balian|sienna|robin|gerard|rebecca|vincent|
westfield|locke|bear|riko|audrey|genovia|celine|leon|juno|lawrence|harley|crocus|anemone|
calibur|heidi|joy|patrone|windblade|selene|alia|teddy|sparky|lunar|fenrir|kain|scar|
octavia|aerola|scylla|bomial|madelyn|junia|sylvie|eros|mimir|hugin|aladdin|genie|
marie|marcel|paimon|ares|diana|olympus|zeus|amadeus|vivaldi|melody|odysseus|minerva|
jupiter|apollo|ares|diana|zeus|poseidon|hermes|pollux|circe|cassandra|odette|vivian|
yun|lin|sully|agnes|agnes|agnes|agnes|agnes"""
NAME_RX = re.compile(rf"\b({NAMES})\b", re.I)

recs = [r for r in json.load(open("recovered-assets/forum-en-2026-10-05/parsed.json", encoding="utf-8"))
        if not r.get("error") and r.get("has_doc_div")]

where: dict[str, list] = defaultdict(list)
for r in recs:
    ctx = r["id"] not in r["file"]
    tag = f"{r['id']}{'*' if ctx else ''} ({r['date'][:10]}, {r['author']}) {r['title'][:40]}"
    for src, text in (("body", r.get("body", "")), ("reply", r.get("replies", ""))):
        for ln in text.split("\n"):
            for m in NAME_RX.finditer(ln):
                where[m.group(0).lower()].append((tag, src, ln.strip()[:170]))

print(f"distinct identity tokens attested: {len(where)}\n")
for name in sorted(where, key=lambda n: (-len(where[n]), n)):
    print(f"{name}  x{len(where[name])}")
    for tag, src, ln in where[name][:3]:
        print(f"    [{src}] {tag}")
        print(f"        {ln}")
    if len(where[name]) > 3:
        print(f"    ... +{len(where[name])-3} more")
    print()
