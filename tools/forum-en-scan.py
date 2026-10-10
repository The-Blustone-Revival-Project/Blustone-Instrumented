#!/usr/bin/env python3
"""Scan parsed forum_en bodies for numeric evidence.

Three independent sweeps, deliberately kept separate so a hit in one is never
silently promoted to a base-stat reading in another:

  TABLES   xe_content containing an HTML <table> -> render every row, in order
  STATS    an HP/ATK/DEF-style stat token with an adjacent numeral, anywhere
  ECONOMY  cost/exp/price/fuel/rupee-style tokens with numerals

Every hit keeps the post id, the verbatim line, and an identity-resolution flag
so the report can mark what is and is not attributable to a hunter.
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from html.parser import HTMLParser

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

STAT_WORDS = re.compile(
    r"\b(hp|atk|def|defence|defense|health|attack|damage|power|strength|rating|"
    r"speed|critical|crit|block|penetration|regen|regeneration|resistance|enhancement|"
    r"life\s*points?|agility|stamina|attack\s*speed)\b",
    re.I,
)
STAT_NUM = re.compile(
    r"(?:\b(?:hp|atk|def|power|strength|rating|damage|health|life\s*points?)\b\s*[:=]?\s*\d[\d,\.]*)"
    r"|(?:\d[\d,\.]*\s*(?:\b(?:hp|atk|def)\b))",
    re.I,
)
ECON_WORDS = re.compile(
    r"\b(cost|price|rupee|rupiah|exp|experience|fuel|crystal|fragment|mand[a]?|coin|"
    r"gem|scroll|ticket|crystals|fragments|energy|gold|heart[s]?|veteran|point[s]?|"
    r"material[s]?|recruit|pull[s]?|advance[d]?|transcend[a-z]*|level[s]?|max level)\b",
    re.I,
)
NUM = re.compile(r"\d[\d,\.]*")
IDENT = re.compile(
    r"\b(captain|lantern|mowgli|nene|tyltyl|hermes|denali|levi|diana|athena|akasha|karl|"
    r"lapis|metis|bruce|sylvester|loke|hecate|balian|sienna|robin|gerard|rebecca|"
    r"vincent|westfield|locke|bear|riko|audrey|genovia|celine|leon|juno|lawrence|"
    r"harley|crocus|anemone|calibur|heidi|joy|patrone|windblade|selene|alia|"
    r"teddy|bonk|sparky|lunar|fenrir|kain|nico|gerard)\b",
    re.I,
)


class TableGrab(HTMLParser):
    """Collect every <table> in the chunk as a list of row-cell text lists."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.tables: list[list[list[str]]] = []
        self.cur: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "table":
            self.cur = []
            self.tables.append(self.cur)
        elif tag == "tr" and self.cur is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ("td", "th") and self.cell is not None:
            if self.row is not None:
                self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.cur is not None and any(self.row):
                self.cur.append(self.row)
            self.row = None
        elif tag == "table":
            self.cur = None

    def handle_data(self, data):
        if self.skip:
            return
        if self.cell is not None:
            self.cell.append(data)


def tables_in(path: str) -> list[list[list[str]]]:
    txt = open(path, "rb").read().decode("utf-8", "replace")
    marks = list(re.finditer(r'<div class="((?:document|comment)_(\d+)_(\d+)) xe_content">', txt, re.I))
    out = []
    for i, m in enumerate(marks):
        s = m.end()
        cands = [txt.find(k, s) for k in ("<!--AfterDocument", "<!--AfterComment", "</article>")]
        cands = [c for c in cands if c != -1]
        e = min(cands) if cands else len(txt)
        if i + 1 < len(marks):
            e = min(e, marks[i + 1].start())
        g = TableGrab()
        try:
            g.feed(txt[s:e])
        except Exception:  # noqa: BLE001
            pass
        out.extend(g.tables)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parsed", required=True)
    ap.add_argument("--rawdir", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    recs = [r for r in json.load(open(a.parsed, encoding="utf-8")) if not r.get("error")]
    recs = [r for r in recs if r.get("has_doc_div") and r.get("body", "").strip()]

    table_hits = []
    stat_hits = []
    econ_hits = []
    for r in recs:
        p = os.path.join(a.rawdir, r["file"])
        if os.path.exists(p):
            for t in tables_in(p):
                rows = [row for row in t if row]
                if len(rows) >= 2:
                    table_hits.append({"id": r["id"], "title": r["title"], "author": r["author"],
                                       "date": r["date"], "file": r["file"], "rows": rows})
        text = r.get("body", "") + "\n" + r.get("replies", "")
        idents = sorted(set(m.group(0) for m in IDENT.finditer(text)))
        for ln in text.split("\n"):
            if not ln.strip():
                continue
            if STAT_NUM.search(ln):
                stat_hits.append({"id": r["id"], "title": r["title"], "author": r["author"],
                                  "date": r["date"], "idents": idents, "line": ln.strip()[:400]})
            if ECON_WORDS.search(ln) and NUM.search(ln):
                econ_hits.append({"id": r["id"], "title": r["title"], "author": r["author"],
                                  "date": r["date"], "idents": idents, "line": ln.strip()[:400]})

    for name, data in (("tables", table_hits), ("stat_hits", stat_hits), ("econ_hits", econ_hits)):
        with open(os.path.join(a.outdir, f"{name}.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        ids = {h["id"] for h in data}
        print(f"{name}: {len(data)} hits across {len(ids)} posts")
    big = sorted(table_hits, key=lambda h: -len(h["rows"]))
    print("\n--- largest tables ---")
    for h in big[:15]:
        print(f"  {h['id']:>8} rows={len(h['rows']):>3} {h['date']} {h['author']} :: {h['title'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
