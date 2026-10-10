#!/usr/bin/env python3
"""Build fetch queues for the forum_en lane.

  list   - EN board list pages (cheap bulk metadata: title/author/date for many posts)
  body   - EN post bodies, canonical document_srl permalink, timestamp pinned to an
           archived capture so we never request an uncaptured URL

Output format is the two-column TSV the fetch harness wants: name<TAB>url
"""

from __future__ import annotations

import argparse
import json
import os
import re

DSRL = re.compile(r"[?&]document_srl=(\d+)")
PAGEQ = re.compile(r"[?&]page=(\d+)")


def wb(ts: str, orig: str, modifier: str = "") -> str:
    """Wayback replay URL at a known-captured timestamp."""
    scheme = "https" if orig.startswith("https") else "http"
    host = "bs.visualshower.com"
    rest = orig.split("://", 1)[1].split("/", 1)[1]
    return f"http://web.archive.org/web/{ts}{modifier}/{scheme}://{host}/{rest}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ids = json.load(open(os.path.join(args.dir, "en-post-ids.json"), encoding="utf-8"))

    # ---- list pages ---------------------------------------------------
    seen_list: set[str] = set()
    listq = []
    for r in ids:
        pass
    # list rows live in the raw page files, not in en-post-ids.json
    import glob

    for p in sorted(glob.glob(os.path.join(args.dir, "page-*.tsv"))):
        for ln in open(p, encoding="utf-8"):
            f = ln.rstrip("\n").split("\t")
            if len(f) < 5:
                continue
            ts, orig, status = f[1], f[2], f[4]
            q = orig.split("?", 1)[1] if "?" in orig else ""
            if status != "200" or "mid=forum_en" not in q:
                continue
            if not PAGEQ.search(q):
                continue
            if DSRL.search(q):
                continue  # thread pagination, not a list page
            if "l=en" not in q:
                continue
            if "search" in q or "act=" in q:
                continue
            # dedupe identical list pages seen at several capture timestamps;
            # the page NUMBER and sort must stay in the key
            key = re.sub(r"(?:&|^)l=[A-Za-z-]+", "", q)
            key = re.sub(r"&l=[A-Za-z-]+", "", key)
            if key in seen_list:
                continue
            seen_list.add(key)
            slug = re.sub(r"[^A-Za-z0-9]+", "-", q)[:60]
            listq.append((f"list/{slug}.html", wb(ts, orig)))
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "queue-list.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        for n, u in listq:
            fh.write(f"{n}\t{u}\n")

    # ---- bodies -------------------------------------------------------
    bodyq = []
    for r in ids:
        if r["canonical_ts"] and r["canonical"] and "200" in r["statuses"]:
            bodyq.append((f"body/{r['id']}.html", wb(r["canonical_ts"], r["canonical"])))
    with open(os.path.join(args.out, "queue-body-canonical.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        for n, u in bodyq:
            fh.write(f"{n}\t{u}\n")

    # fallback bodies: any 200 capture of any en body-ish form
    bodyq2 = []
    for r in ids:
        if "200" not in r["statuses"]:
            continue
        for o in r["orig"]:
            if "mid=forum_en" not in o:
                continue
            if "l=en" not in o and "l=" in o:
                continue
            if DSRL.search(o) or "/forum_en/" in o:
                bodyq2.append((f"body2/{r['id']}.html", wb(r["last_ts"], o)))
                break
    with open(os.path.join(args.out, "queue-body-alt.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        for n, u in bodyq2:
            fh.write(f"{n}\t{u}\n")

    print(f"list queue : {len(listq)}")
    print(f"body canonical: {len(bodyq)}")
    print(f"body alt      : {len(bodyq2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
