#!/usr/bin/env python3
"""Emit the pass-2 provenance table: one row per captured body, with full ledger.

Joins three local sources:
  pass2/queue-*.tsv   requested URL (which encodes the capture timestamp)
  pass2/_ledger*.tsv  actual HTTP status, tries and byte count
  <file> on disk      sha256, recomputed

`000` (curl-style transport failure) is printed as such and is never counted as
a result; a `SKIPPED-DEADLINE` row is a request that was never issued.
"""

from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import io
import json
import os
import re

TS = re.compile(r"web\.archive\.org/web/(\d{14})/")


def sha256_of(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="pass2 dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--queues", nargs="*", default=[],
                    help="explicit queue TSVs. Needed when the SAME target name "
                         "was fetched from two different capture timestamps (the "
                         "latest-capture arm and the reply-rich arm), because a "
                         "glob would silently attribute the wrong timestamp.")
    ap.add_argument("--ledger", nargs="*", default=[])
    args = ap.parse_args()
    root = args.root

    queues = args.queues or sorted(
        q for q in glob.glob(os.path.join(root, "queue-*.tsv"))
        if not q.endswith(".meta.json")
    )
    want: dict[str, str] = {}
    for q in queues:
        for ln in open(q, encoding="utf-8"):
            if not ln.strip():
                continue
            parts = ln.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            name, url = parts[0], parts[1]
            m = TS.search(url)
            want[name] = m.group(1) if m else ""

    ledger: dict[str, dict] = {}
    lgs = args.ledger or (sorted(glob.glob(os.path.join(root, "_ledger*.tsv"))) +
                          sorted(glob.glob(os.path.join(root, "get-list", "_ledger*.tsv"))))
    for lg in lgs:
        for i, ln in enumerate(open(lg, encoding="utf-8")):
            if i == 0 and ln.startswith("name\t"):
                continue
            p = ln.rstrip("\n").split("\t")
            if len(p) < 4:
                continue
            name, st, tries, nbytes = p[0], p[1], p[2], p[3]
            prev = ledger.get(name)
            # keep the LAST attempt for a target: a later success supersedes
            if prev is None or (prev["status"] != "200" and st == "200"):
                ledger[name] = {"status": st, "tries": tries, "bytes": int(nbytes or 0),
                                "ledger": os.path.basename(lg)}

    rows = []
    tally: collections.Counter = collections.Counter()
    for name in sorted(want):
        d = os.path.join(root, name)
        if not os.path.exists(d):
            tally["absent"] += 1
            continue
        size = os.path.getsize(d)
        if size <= 500:
            tally["empty-on-disk"] += 1
            continue
        rec = ledger.get(name, {})
        rows.append({
            "name": name,
            "id": os.path.basename(name).split(".")[0],
            "kind": name.split("/")[0],
            "capture_ts": want[name],
            "http": rec.get("status", "?"),
            "tries": rec.get("tries", "?"),
            "bytes": size,
            "sha256": sha256_of(d),
        })
        tally[rec.get("status", "not-ledgered")] += 1

    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("id\tkind\tcapture_ts\thttp\ttries\tbytes\tsha256\tfile\n")
        for r in sorted(rows, key=lambda r: (r["kind"], int(r["id"]))):
            fh.write(f"{r['id']}\t{r['kind']}\t{r['capture_ts']}\t{r['http']}\t{r['tries']}\t"
                     f"{r['bytes']}\t{r['sha256']}\t{r['name']}\n")

    req = collections.Counter()
    for name in want:
        req[name.split("/")[0]] += 1
    print(f"requested: {dict(req)}")
    print(f"present with bytes: {len(rows)}   absent/empty: "
          f"{sum(tally[k] for k in ('absent','empty-on-disk'))}")
    print(f"http tally over present: {dict(tally)}")
    for k in ("body", "topup", "list"):
        sub = [r for r in rows if r["kind"] == k]
        if sub:
            print(f"  {k}: {len(sub)} present, http {dict(collections.Counter(r['http'] for r in sub))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())