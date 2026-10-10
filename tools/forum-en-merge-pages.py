#!/usr/bin/env python3
"""Merge already-downloaded CDX page files into the forum_en post-id census.

Pure local pass - no network. Idempotent: re-run after more pages land.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re

BOARD = "forum_en"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "page-*.tsv")))
    rows: list[list[str]] = []
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            for ln in fh:
                parts = ln.rstrip("\n").split("\t")
                if len(parts) >= 4:
                    rows.append(parts)

    ids: dict[str, dict] = {}
    forms: dict[str, set[str]] = {}
    for r in rows:
        orig = r[2]
        m = re.search(rf"/{BOARD}/(\d+)", orig) or re.search(r"document_srl=(\d+)", orig)
        if not m:
            continue
        pid = m.group(1)
        d = ids.setdefault(
            pid, {"id": pid, "statuses": set(), "caps": 0, "first": "9999", "last": "0", "orig": set()}
        )
        d["statuses"].add(r[3])
        d["caps"] += 1
        d["first"] = min(d["first"], r[1])
        d["last"] = max(d["last"], r[1])
        d["orig"].add(orig)
        if len(d["orig"]) > 8:
            forms.setdefault(pid, set())

    out = [
        {
            "id": p,
            "statuses": sorted(d["statuses"]),
            "captures": d["caps"],
            "first_ts": d["first"],
            "last_ts": d["last"],
            "orig": sorted(d["orig"])[:8],
        }
        for p, d in sorted(ids.items(), key=lambda kv: int(kv[0]))
    ]
    with open(os.path.join(args.dir, "post-ids.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(args.dir, "post-ids.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("id\tcaptures\tfirst_ts\tlast_ts\tstatuses\n")
        for r in out:
            fh.write(f"{r['id']}\t{r['captures']}\t{r['first_ts']}\t{r['last_ts']}\t{'|'.join(r['statuses'])}\n")

    # Which ids have a body-bearing form we can actually fetch?
    permalink = sum(1 for r in out if any("document_srl=" in o for o in r["orig"]))
    pathform = sum(1 for r in out if any(re.search(rf"/{BOARD}/\d+$", o) for o in r["orig"]))
    status200 = sum(1 for r in out if r["statuses"] == ["200"])
    print(f"pages={len(files)} rows={len(rows)} distinct_ids={len(out)}")
    print(f"  with document_srl form: {permalink}")
    print(f"  with /forum_en/<id> form: {pathform}")
    print(f"  index status==200 only: {status200}")
    multi = [r for r in out if len(r["orig"]) > 1]
    print(f"  ids with >1 distinct url form: {len(multi)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
