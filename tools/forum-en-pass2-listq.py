#!/usr/bin/env python3
"""Build the pass-2 list-page fetch queue directly from the pass-1 CDX census.

No index query: every (timestamp, url) pair comes from census/page-*.tsv, which
is already on disk. Pure local pass, no network.

Emits `outfile<TAB>wayback_url` rows for tools/forum-en-fetch-concurrent.py.
Preference order inside the queue:

  1. `sort_index=readed_count&order_type=desc` pages, lowest page number first
     -> the board's own view-order, so page 2..N walks DOWN the most-viewed list.
  2. unsorted (`none`) list pages, lowest page number first
     -> default board order (usually newest first).

`l=en` is enforced by construction: only rows whose `l=` is absent or `en` are
considered, so the `default`/other-locale rows cannot leak in.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re

DSRL = re.compile(r"[?&]document_srl=(\d+)")
PAGEQ = re.compile(r"[?&]page=(\d+)")
LANG = re.compile(r"[?&]l=([A-Za-z-]+)")
SORT = re.compile(r"[?&]sort_index=([a-z_]+)")
ORDER = re.compile(r"[?&]order_type=(asc|desc)")

RANK_SORT = {"readed_count": 0, "regdate": 1, "title": 3, "": 2}


def query_of(orig: str) -> str:
    return orig.split("?", 1)[1] if "?" in orig else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--maxpages", type=int, default=45)
    args = ap.parse_args()

    rows = []
    for f in sorted(glob.glob(os.path.join(args.census, "page-*.tsv"))):
        for ln in open(f, encoding="utf-8"):
            p = ln.rstrip("\n").split("\t")
            if len(p) >= 5:
                rows.append(p)

    best: dict[tuple, dict] = {}
    n_seen = n_en = n_list = 0
    for r in rows:
        ts, orig, status, mime = r[1], r[2], r[4], r[3]
        if DSRL.search(orig):
            continue  # a body/boardpage row, not a list page
        q = query_of(orig)
        pm = PAGEQ.search(q)
        if not pm or "mid=forum_en" not in q:
            continue
        n_list += 1
        lm = LANG.search(q)
        if lm and lm.group(1).lower() != "en":
            continue
        n_en += 1
        if status != "200":
            continue
        sm = SORT.search(q)
        om = ORDER.search(q)
        skey = (sm.group(1) if sm else "", om.group(1) if om else "desc")
        page = int(pm.group(1))
        k = (skey, page)
        prev = best.get(k)
        if prev is None or ts < prev["ts"]:
            best[k] = {"ts": ts, "orig": orig, "sort": skey[0], "order": skey[1],
                       "page": page, "mime": mime}

    chosen = sorted(
        best.values(),
        key=lambda d: (RANK_SORT.get(d["sort"], 2),
                       d["order"] != "desc",
                       d["page"]),
    )[: args.maxpages]

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        for d in chosen:
            name = "list/rc%03d.html" % d["page"] if d["sort"] == "readed_count" \
                else "list/n%03d.html" % d["page"]
            url = f"http://web.archive.org/web/{d['ts']}/{d['orig']}"
            fh.write(f"{name}\t{url}\n")
            n_seen += 1

    meta = {
        "list_rows_total": n_list,
        "list_rows_en": n_en,
        "distinct_en_list_keys": len(best),
        "queue_rows": n_seen,
        "queue": [
            {"name": ("list/rc%03d.html" % d["page"] if d["sort"] == "readed_count"
                      else "list/n%03d.html" % d["page"]),
             "ts": d["ts"], "sort": d["sort"], "order": d["order"],
             "page": d["page"], "orig": d["orig"]}
            for d in chosen
        ],
    }
    with open(args.out + ".meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    print(f"list rows total={n_list} en={n_en} distinct en keys={len(best)} queued={n_seen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())