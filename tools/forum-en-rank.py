#!/usr/bin/env python3
"""Rank forum_en posts for body fetching, and emit a prioritised queue.

Signals, deliberately kept separate so a score can be audited:
  title keywords  guide/stat/rate/tier/table/data/formula/cost/exp/level/growth...
  era             post date after the 2019-09-05 equipment/crystal rebalance is
                  worth more to the base-stat goal than pre-rebalance, because
                  share_en could only supply the pre-rebalance era
  reads           a community guide that nobody read is weak evidence
  length          unknown before the body is fetched, so views stand in for it

Outputs a queue TSV for tools/forum-en-fetch-polite.py, in priority order.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HIGH = re.compile(
    r"\b(stat|stats|statistic|ranking|tier|tier\s*list|rate|rating|formula|calculation|"
    r"damage\s*(calc|formula)|table|data|chart|growth|curve|analysis|research|"
    r"guide|guidebook|manual|reference|chart|compilation|list\s*of|all\s+hunter|"
    r"every\s+hunter|full\s+stat|evo\s*(chart|table))\b",
    re.I,
)
MED = re.compile(
    r"\b(advance|advancement|transcend|transcendence|awaken|awakening|equip|equipment|"
    r"gem|jewel|level|exp|experience|training|fodder|material|cost|price|shop|"
    r"energy|fuel|recruit|recruitment|arena|fight\s*club|tier)\b",
    re.I,
)
NEG = re.compile(r"\b(signature|\bno\b)\b", re.I)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lists", required=True)
    ap.add_argument("--ids", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", type=int, default=400)
    a = ap.parse_args()

    meta = {str(r["id"]): r for r in json.load(open(a.lists, encoding="utf-8"))}
    ids = json.load(open(a.ids, encoding="utf-8"))

    scored = []
    for r in ids:
        pid = r["id"]
        m = meta.get(pid, {})
        title = m.get("title", "")
        author = m.get("author", "")
        reads = m.get("reads", 0)
        date = m.get("date", "")
        # fall back to the earliest archived capture when the list page had no date
        if not date:
            d = r["first_ts"]
            date = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) >= 8 else ""
        score = 0
        why = []
        if HIGH.search(title):
            score += 60
            why.append("HIGH-title")
        if MED.search(title):
            score += 25
            why.append("MED-title")
        if reads >= 500:
            score += 25
            why.append("reads>=500")
        elif reads >= 150:
            score += 15
            why.append("reads>=150")
        elif reads >= 40:
            score += 6
            why.append("reads>=40")
        if date >= "2019-09-05":
            score += 20
            why.append("POST-rebalance")
        elif date and date >= "2018-01-01":
            score += 10
            why.append("2018")
        if author in ("VSpang", "Master"):
            score += 15
            why.append("vendor-author")
        if r["captures"] >= 10:
            score += 5
            why.append("well-archived")
        if not title:
            score -= 10
            why.append("no-title")
        scored.append({"id": pid, "score": score, "why": ",".join(why), "title": title,
                       "author": author, "date": date, "reads": reads,
                       "ts": r["canonical_ts"] or r["last_ts"], "orig": r["canonical"] or (r["orig"][0] if r["orig"] else "")})

    scored.sort(key=lambda x: (-x["score"], -x["reads"], x["id"]))
    with open(a.out.replace(".tsv", "-ranked.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(scored, fh, ensure_ascii=False, indent=1)

    n = 0
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        for s in scored:
            if not s["orig"]:
                continue
            scheme = "https" if s["orig"].startswith("https") else "http"
            rest = s["orig"].split("://", 1)[1].split("/", 1)[1]
            url = f"http://web.archive.org/web/{s['ts']}/{scheme}://bs.visualshower.com/{rest}"
            fh.write(f"body/{s['id']}.html\t{url}\n")
            n += 1
            if n >= a.top:
                break

    from collections import Counter
    print(f"scored {len(scored)} ids; queue holds {n}")
    print("signal counts:", dict(Counter(w for s in scored for w in s["why"].split(",") if w)))
    print(f"  with a list-page title: {sum(1 for s in scored if s['title'])}")
    print("\n--- top 30 ---")
    for s in scored[:30]:
        print(f"  {s['score']:>4} {s['id']:>8} {s['date'] or '?':>10} reads={s['reads']:>6} "
              f"{s['author'][:12]:<12} {s['title'][:64]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
