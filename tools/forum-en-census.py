#!/usr/bin/env python3
"""Page the CDX index to a complete forum_en post-id census.

The single-shot domain query saturates at its limit (20,000 rows) and is then
truncated, so a single query CANNOT enumerate this board. This pages with
showNumPages/page and merges, then reports whether any page came back short.

GET-only. HTTP 200 with an unparseable body is recorded, never silently zero.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research-fetch/1.0"
CDX = "http://web.archive.org/cdx/search/cdx"
BOARD = "forum_en"


def get(url: str, tries: int, sleep: float) -> tuple[str, bytes, int]:
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    for i in range(1, tries + 1):
        try:
            r = sess.get(url, timeout=240)
            if r.status_code == 200:
                return "200", r.content or b"", i
        except Exception:  # noqa: BLE001
            pass
        time.sleep(sleep * i + random.uniform(0, 2))
    return "000", b"", tries


def parse(body: bytes) -> tuple[list[list[str]], str]:
    txt = body.decode("utf-8", "replace").strip()
    if not txt:
        return [], "200-empty"
    if not txt.startswith("["):
        return [], "200-non-json"
    try:
        d = json.loads(txt)
    except json.JSONDecodeError as e:
        return [], f"200-json-error:{e}"
    if not d:
        return [], "200-json-empty"
    if not isinstance(d[0], list):
        return [], "200-json-shape"
    return d[1:], "ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument("--tries", type=int, default=8)
    ap.add_argument("--sleep", type=float, default=3.0)
    ap.add_argument("--maxpages", type=int, default=60)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    base = (
        CDX
        + f"?url=bs.visualshower.com&matchType=domain&collapse=urlkey&output=json"
        + f"&filter=original:.*{BOARD}.*&limit={args.limit}"
    )

    st, body, tries = get(base + "&showNumPages=true", args.tries, args.sleep)
    pages = 0
    if st == "200":
        try:
            pages = int(json.loads(body.decode("utf-8", "replace").strip())[0]["pages"])
        except Exception as exc:  # noqa: BLE001
            print(f"showNumPages unparseable ({exc}); falling back to maxpages", flush=True)
    print(f"showNumPages: status={st} pages={pages} tries={tries}", flush=True)

    rows: list[list[str]] = []
    ledger = []
    npages = min(pages, args.maxpages) if pages else args.maxpages
    for p in range(1, npages + 1):
        st, body, tries = get(base + f"&page={p}", args.tries, args.sleep)
        pr, note = parse(body) if st == "200" else ([], f"status-{st}")
        rows.extend(pr)
        ledger.append({"page": p, "status": st, "rows": len(pr), "tries": tries, "note": note})
        print(f"  page {p}/{npages}: status={st} rows={len(pr)} note={note}", flush=True)
        if pr:
            with open(os.path.join(args.out, f"page-{p:03d}.tsv"), "w", encoding="utf-8", newline="\n") as fh:
                for r in pr:
                    fh.write("\t".join(str(x) for x in r) + "\n")
        time.sleep(args.sleep)
        if pages and p == pages:
            break

    ledger.append({"page": 0, "status": "TOTAL", "rows": len(rows), "tries": 0, "note": f"pages_reported={pages}"})
    with open(os.path.join(args.out, "page-ledger.json"), "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2)

    # ---- id extraction -------------------------------------------------
    ids: dict[str, dict] = {}
    for r in rows:
        orig = r[2] if len(r) > 2 else ""
        m = re.search(rf"/{BOARD}/(\d+)", orig) or re.search(rf"document_srl=(\d+)", orig)
        if m:
            pid = m.group(1)
            d = ids.setdefault(
                pid,
                {"id": pid, "statuses": set(), "caps": 0, "first": "9999", "last": "0", "orig": set()},
            )
            d["statuses"].add(r[3] if len(r) > 3 else "?")
            d["caps"] += 1
            d["first"] = min(d["first"], r[1])
            d["last"] = max(d["last"], r[1])
            d["orig"].add(orig)

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
    with open(os.path.join(args.out, "post-ids.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(args.out, "post-ids.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("id\tcaptures\tfirst_ts\tlast_ts\tstatuses\n")
        for r in out:
            fh.write(f"{r['id']}\t{r['captures']}\t{r['first_ts']}\t{r['last_ts']}\t{'|'.join(r['statuses'])}\n")

    print(f"=== TOTAL ROWS {len(rows)}   DISTINCT IDS {len(out)}   PAGES_REPORTED {pages} ===", flush=True)
    if pages and npages < pages:
        print(f"!! TRUNCATED: only {npages} of {pages} pages fetched", file=sys.stderr)
    if not out:
        print("NO IDS - unknown, not zero.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
