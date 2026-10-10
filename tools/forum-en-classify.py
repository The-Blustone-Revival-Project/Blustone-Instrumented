#!/usr/bin/env python3
"""Classify forum_en CDX rows by URL shape + language and emit the EN post census.

Pure local pass. Reads every page-*.tsv in --dir plus any extra TSVs passed with
--extra, so the prefix-form query (which supplies /forum_en/<id> rows) can be
merged in.

Classification of a row's `original`:
  BODY      canonical permalink, no page= : mid=forum_en & document_srl=<id>
  BODYPAGE  same but with page=N          : a later page of the same thread
  COMMENT   act=dispBoardReplyComment     : one comment
  LIST      mid=forum_en & page=N, no srl : board list page
  LISTOTHER sort/category/search/order    : board list variants
  PATH      /forum_en/<id>                : pretty permalink form
  PATHBOARD /forum_en                     : board root
  OTHER     anything else

Language is read from l=<...>; absent means the default locale.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import Counter

DSRL = re.compile(r"[?&]document_srl=(\d+)")
PAGEQ = re.compile(r"[?&]page=(\d+)")
LANGS = re.compile(r"[?&]l=([A-Za-z-]+)")
PATHID = re.compile(r"/forum_en/(\d+)")


def classify(orig: str) -> str:
    path = orig.split("?", 1)
    if len(path) == 1:
        return "PATHBOARD" if path[0].rstrip("/").endswith("/forum_en") else "OTHER"
    q = path[1]
    m = PATHID.search(path[0])
    if m:
        return "PATH"
    has_srl = DSRL.search(q) is not None
    has_page = PAGEQ.search(q) is not None
    if "act=dispBoardReplyComment" in q:
        return "COMMENT"
    if "mid=forum_en" not in q and "forum_en" not in path[0]:
        return "OTHER"
    if has_srl:
        return "BODYPAGE" if has_page else "BODY"
    if has_page:
        return "LIST"
    return "LISTOTHER"


def load(paths: list[str]) -> list[list[str]]:
    rows = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as fh:
            for ln in fh:
                parts = ln.rstrip("\n").split("\t")
                if len(parts) >= 5:
                    rows.append(parts)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--extra", nargs="*", default=[])
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(args.dir, "page-*.tsv")))
    paths += [p for p in args.extra if os.path.exists(p)]
    rows = load(paths)

    shapes = Counter()
    langs = Counter()
    shape_lang = Counter()
    for r in rows:
        sh = classify(r[2])
        lm = LANGS.search(r[2].split("?", 1)[1] if "?" in r[2] else "")
        lang = lm.group(1).lower() if lm else "default"
        shapes[sh] += 1
        langs[lang] += 1
        shape_lang[(sh, lang)] += 1

    print(f"files={len(paths)} rows={len(rows)}")
    print("shapes:", dict(shapes))
    print("langs :", dict(langs))
    print("shape x lang (top 20):")
    for (sh, lg), n in shape_lang.most_common(20):
        print(f"   {sh:9s} {lg:8s} {n}")

    # English body-capable ids
    en_rows = [r for r in rows if classify(r[2]) in ("BODY", "BODYPAGE", "PATH", "COMMENT")]
    en_only = []
    for r in en_rows:
        q = r[2].split("?", 1)[1] if "?" in r[2] else ""
        lm = LANGS.search(q)
        if lm and lm.group(1).lower() != "en":
            continue
        en_only.append(r)
    print(f"\nEN body-ish rows: {len(en_only)}")

    ids: dict[str, dict] = {}
    for r in en_only:
        sh = classify(r[2])
        m = DSRL.search(r[2]) or PATHID.search(r[2])
        if not m:
            continue
        pid = m.group(1)
        d = ids.setdefault(
            pid, {"id": pid, "shapes": set(), "statuses": set(), "caps": 0, "first": "9999", "last": "0", "orig": set()}
        )
        d["shapes"].add(sh)
        d["statuses"].add(r[4])
        d["caps"] += 1
        d["first"] = min(d["first"], r[1])
        d["last"] = max(d["last"], r[1])
        d["orig"].add(r[2])
        if sh == "BODY":
            d.setdefault("canonical", r[2])
            d.setdefault("canonical_ts", r[1])

    out = []
    for p, d in sorted(ids.items(), key=lambda kv: int(kv[0])):
        out.append(
            {
                "id": p,
                "shapes": sorted(d["shapes"]),
                "statuses": sorted(d["statuses"]),
                "captures": d["caps"],
                "first_ts": d["first"],
                "last_ts": d["last"],
                "canonical_ts": d.get("canonical_ts"),
                "canonical": d.get("canonical"),
                "orig": sorted(d["orig"])[:10],
            }
        )
    with open(os.path.join(args.dir, "en-post-ids.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(args.dir, "en-post-ids.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("id\tcaptures\tfirst_ts\tlast_ts\tstatuses\tshapes\tcanonical_ts\n")
        for r in out:
            fh.write(
                f"{r['id']}\t{r['captures']}\t{r['first_ts']}\t{r['last_ts']}\t"
                f"{'|'.join(r['statuses'])}\t{'|'.join(r['shapes'])}\t{r['canonical_ts'] or ''}\n"
            )

    print(f"=== DISTINCT EN forum_en POST IDS: {len(out)} ===")
    nocanon = [r for r in out if not r["canonical_ts"]]
    with200 = [r for r in out if "200" in r["statuses"]]
    print(f"  ids with a canonical BODY row: {len(out)-len(nocanon)}")
    print(f"  ids with a 200 status row:      {len(with200)}")
    print(f"  ids with no canonical BODY row: {len(nocanon)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
