#!/usr/bin/env python3
"""Derive per-post structural signals for forum_en prioritisation, from the
already-downloaded CDX pages only (no network).

Rationale: the first pass could not retrieve board LIST pages, so the existing
prioritiser (tools/forum-en-rank.py) never ran. But the paged CDX rows already
on disk carry per-post structural evidence that needs no list page:

  pages      max `page=N` seen for the id. XE paginates replies, so pages>1
             proves the thread has more replies than fit on page 1 -- and the
             first pass's single richest source (192349) was rich because its
             REPLIES were rich. A later page is therefore a second fetchable
             body of reply text for one index lookup.
  shapes     which URL shapes the archive holds for this id.
  captures   distinct archived URLs for this id.
  ncomments  archived act=dispBoardReplyComment rows (individual replies).
  years      set of capture years -> era proxy.

Also computes adjacency to the pass-1 read set: XE assigns document_srl roughly
sequentially by creation, so ids near an already-read id are in the same topical
burst. Recorded as a WEAK signal only, never as evidence.
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DSRL = re.compile(r"[?&]document_srl=(\d+)")
PAGEQ = re.compile(r"[?&]page=(\d+)")
CSRL = re.compile(r"[?&]comment_srl=(\d+)")
LANGS = re.compile(r"[?&]l=([A-Za-z-]+)")


def load_rows(paths):
    for p in paths:
        with open(p, "r", encoding="utf-8") as fh:
            for ln in fh:
                parts = ln.rstrip("\n").split("\t")
                if len(parts) >= 5:
                    yield parts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cdx-dir", required=True)
    ap.add_argument("--census", required=True)
    ap.add_argument("--read-ids", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--adjacency", type=int, default=2500,
                    help="max id distance counted as 'adjacent'")
    a = ap.parse_args()

    sig = defaultdict(lambda: {"pages": 0, "comments": 0, "urls": set(),
                               "years": set(), "nrows": 0})
    rows = 0
    for parts in load_rows(sorted(glob.glob(os.path.join(a.cdx_dir, "page-*.tsv")))):
        rows += 1
        ts, orig = parts[1], parts[2]
        m = DSRL.search(orig)
        if not m:
            continue
        q = orig.split("?", 1)[1] if "?" in orig else ""
        lm = LANGS.search(q)
        if lm and lm.group(1).lower() != "en":
            continue
        pid = m.group(1)
        s = sig[pid]
        s["nrows"] += 1
        s["urls"].add(orig)
        s["years"].add(ts[:4])
        pm = PAGEQ.search(q)
        if pm:
            s["pages"] = max(s["pages"], int(pm.group(1)))
        if CSRL.search(q):
            s["comments"] += 1
    print(f"cdx rows scanned={rows}  EN body-ish ids with structural rows={len(sig)}")

    census = json.load(open(a.census, encoding="utf-8"))
    read = {ln.strip() for ln in open(a.read_ids, encoding="utf-8") if ln.strip()}
    read_i = sorted(int(x) for x in read)

    import bisect

    out = []
    for r in census:
        pid = r["id"]
        s = sig.get(pid, {"pages": 0, "comments": 0, "urls": set(), "years": set(),
                          "nrows": 0})
        dist = None
        if read_i:
            v = int(pid)
            k = bisect.bisect_left(read_i, v)
            cands = [x for x in (read_i[k - 1] if k else None,
                                 read_i[k] if k < len(read_i) else None) if x is not None]
            if cands:
                dist = min(abs(v - c) for c in cands)
        out.append({
            "id": pid,
            "read": pid in read,
            "captures": r["captures"],
            "shapes": r["shapes"],
            "statuses": r["statuses"],
            "first_ts": r["first_ts"],
            "last_ts": r["last_ts"],
            "canonical_ts": r["canonical_ts"],
            "canonical": r["canonical"],
            "orig": r["orig"],
            "max_page": s["pages"],
            "comments": s["comments"],
            "en_rows": s["nrows"],
            "years": sorted(s["years"]),
            "dist_to_read": dist,
        })

    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    unread = [r for r in out if not r["read"]]
    withp = [r for r in unread if r["max_page"] > 1]
    print(f"census={len(out)} read={len(out)-len(unread)} unread={len(unread)}")
    print(f"unread with a later thread page (max_page>1): {len(withp)}")
    from collections import Counter
    print("unread max_page histogram:", dict(sorted(
        Counter(min(r["max_page"], 6) for r in unread).items())))
    print("unread comments>0:", sum(1 for r in unread if r["comments"]))
    print("unread capture-year histogram:",
          dict(sorted(Counter(r["years"][0] if r["years"] else "?" for r in unread).items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
