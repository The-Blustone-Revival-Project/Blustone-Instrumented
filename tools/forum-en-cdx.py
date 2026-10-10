#!/usr/bin/env python3
"""CDX enumeration for a bs.visualshower.com board.

Retries hard; transport failure is '000' and is never a result. Prints the
domain-form result AND a prefix-form fallback, because share-en-panels-2026-10-05
.md §2.4(3) records the domain form as unreliable while prefix form works.

Usage:
  python tools/forum-en-cdx.py --board forum_en --out <dir>
  python tools/forum-en-cdx.py --board forum_en --out <dir> --prefixes 1
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research-fetch/1.0"
CDX = "http://web.archive.org/cdx/search/cdx"


def get(url: str, tries: int, sleep: float) -> tuple[str, bytes, int]:
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    last = "000"
    for i in range(1, tries + 1):
        try:
            r = sess.get(url, timeout=180)
            last = str(r.status_code)
            if last == "200":
                return last, r.content or b"", i
        except Exception:  # noqa: BLE001
            last = "000"
        time.sleep(sleep * i + random.uniform(0, 2))
    return last, b"", tries


def rows_of(body: bytes) -> tuple[list[list[str]], str]:
    """CDX json output -> (row lists, parser note). HTTP 200 is not a guarantee
    that the body is parseable CDX json; the archive answers 200 with an error
    page for oversized/failed queries. Both cases are recorded."""
    txt = body.decode("utf-8", "replace").strip()
    if not txt:
        return [], "200-empty-body"
    if not txt.startswith("["):
        return [], "200-non-json:" + txt[:120].replace("\n", " ")
    try:
        data = json.loads(txt)
    except json.JSONDecodeError as exc:
        return [], f"200-json-error:{exc}"
    if not data:
        return [], "200-json-empty"
    if not isinstance(data[0], list):
        return [], "200-json-unexpected-shape"
    return data[1:], "ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tries", type=int, default=8)
    ap.add_argument("--sleep", type=float, default=3.0)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    log: list[dict] = []

    queries = [
        (
            "domain",
            CDX
            + "?url=bs.visualshower.com&matchType=domain&collapse=urlkey&output=json"
            + f"&filter=original:.*{args.board}.*&limit=20000",
        ),
        (
            "prefix-board",
            CDX
            + f"?url=bs.visualshower.com/{args.board}&matchType=prefix"
            + "&collapse=urlkey&output=json&limit=20000",
        ),
        (
            "prefix-root",
            CDX
            + f"?url=bs.visualshower.com/&matchType=prefix"
            + "&filter=original:.*{args.board}.*&collapse=urlkey&output=json&limit=20000",
        ),
        (
            "prefix-images",
            CDX
            + "?url=bs.visualshower.com/files/attach/images/"
            + "&matchType=prefix&collapse=urlkey&output=json&limit=20000",
        ),
    ]

    rows_by_tag: dict[str, list[list[str]]] = {}
    for tag, url in queries:
        print(f"--- CDX [{tag}] ---", flush=True)
        st, body, tries = get(url, args.tries, args.sleep)
        n = 0
        note = "no-200"
        if st == "200":
            rows, note = rows_of(body)
            n = len(rows)
            with open(os.path.join(args.out, f"cdx-{tag}.raw"), "wb") as fh:
                fh.write(body)
            if rows:
                with open(os.path.join(args.out, f"cdx-{tag}.tsv"), "w", encoding="utf-8", newline="\n") as fh:
                    for r in rows:
                        fh.write("\t".join(str(x) for x in r) + "\n")
            rows_by_tag[tag] = rows
        else:
            print(f"    status={st} (no result recorded)", flush=True)
        print(f"    status={st} rows={n} tries={tries} note={note}", flush=True)
        log.append({"tag": tag, "url": url, "status": st, "rows": n, "tries": tries, "note": note, "bytes": len(body)})
        time.sleep(args.sleep)

    with open(os.path.join(args.out, "cdx-ledger.json"), "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=2)

    # Distinct post ids across every row set that mentions the board.
    import re

    ids: dict[str, dict] = {}
    for tag, rows in rows_by_tag.items():
        if tag == "prefix-images":
            continue
        for r in rows:
            orig = r[2] if len(r) > 2 else ""
            m = re.search(rf"/{args.board}/(\d+)", orig)
            if not m:
                m = re.search(rf"document_srl=(\d+)", orig)
            if m:
                pid = m.group(1)
                d = ids.setdefault(
                    pid, {"id": pid, "forms": set(), "statuses": set(), "timestamps": [], "orig": []}
                )
                d["forms"].add(orig.split("?")[0][:200])
                d["statuses"].add(r[3] if len(r) > 3 else "?")
                d["timestamps"].append(r[1])
                d["orig"].append(orig)

    out = []
    for pid, d in sorted(ids.items(), key=lambda kv: int(kv[0])):
        out.append(
            {
                "id": pid,
                "statuses": sorted(d["statuses"]),
                "captures": len(d["timestamps"]),
                "first_ts": min(d["timestamps"]),
                "last_ts": max(d["timestamps"]),
                "orig": sorted(set(d["orig"]))[:6],
            }
        )
    with open(os.path.join(args.out, "post-ids.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    print(f"=== DISTINCT {args.board} POST IDS: {len(out)} ===", flush=True)
    for row in out:
        print(f"  {row['id']:>9}  caps={row['captures']}  {row['first_ts']}..{row['last_ts']}  {row['statuses']}")
    if not out:
        print("NO IDS - treat as unknown, not as zero.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
