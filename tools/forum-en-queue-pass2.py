#!/usr/bin/env python3
"""Build pass-2 forum_en fetch queues from the on-disk census/signals only.

No board LIST page is consulted. Pass 1 established that list-page retrieval was
the rate-limit blocker and therefore that ranking was never applied; everything
here is derived from index rows already on disk, so it is immune to that.

Two target kinds are emitted, each with its own file name so the ledger and the
on-disk body dir stay self-describing:

  body/<id>.html        the canonical body-bearing capture (page 1). Same URL
                        choice rule as pass 1 (tools/forum-en-queue-targeted.py):
                        reject act=, reject a row whose own document_srl is not
                        this id, prefer l=en + https.
  page/<id>_p<N>.html   ONE later page of a long thread, chosen as the largest
                        archived page number for that id. Pass 1 read page 1 only,
                        and its single richest source (192349) was rich because
                        its REPLIES were rich. XE paginates replies, so a later
                        page is additional reply text for one more fetch.

Priority tiers (printed into the queue so the ordering is auditable):
  T1  official-announcement ids available in ALL FIVE locales (pass-1 lead M3).
      These are the translated vendor series -- the only place a vendor patch
      note or balance-change statement can live, and the 2019-09-05 rebalance is
      otherwise dated only from a TapTap announcement.
  T2  reply-dense threads (max_page >= --thread-pages), because replies carried
      every numeric reading pass 1 recovered.
  T3  ids adjacent (id distance <= --adjacency) to an already-read post.

Era is NOT a filter: it is carried through as a sort key and as a column, so a
caller can see what era a target belongs to before spending a fetch on it.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DSRL = re.compile(r"[?&]document_srl=(\d+)")
PAGEQ = re.compile(r"[?&]page=(\d+)")


def best_body_url(r: dict) -> tuple[str, str] | None:
    """(timestamp, original-url) for the best page-1 body capture, or None."""
    best = None
    for o in r["orig"]:
        if "document_srl=" not in o:
            continue
        ids = DSRL.findall(o)
        # EVERY document_srl in the row must be this id. Pass 1 recorded 10
        # capture substitutions where the row carried the requested id but the
        # archive served a different post; several of those rows carry a SECOND
        # document_srl appended (e.g. `document_srl=969559&l=en&l=en&
        # document_srl=1178349`), which pass 1's own `len(ids)>=2 and all(...)`
        # rule does not reject because the first id matches. Requiring set(ids)
        # == {id} rejects the whole class before the fetch is paid for.
        if set(ids) != {r["id"]}:
            continue
        if "act=" in o or PAGEQ.search(o):
            continue
        score = 0
        if "l=en" in o:
            score += 2
        if o.startswith("https"):
            score += 1
        if best is None or score > best[0]:
            best = (score, o)
    if best is None:
        return None
    ts = r["canonical_ts"] or r["first_ts"]
    return ts, best[1]


def wayback(ts: str, orig: str) -> str:
    scheme = "https" if orig.startswith("https") else "http"
    rest = orig.split("://", 1)[1].split("/", 1)[1]
    return f"http://web.archive.org/web/{ts}/{scheme}://bs.visualshower.com/{rest}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", required=True)
    ap.add_argument("--locales", required=True)
    ap.add_argument("--read-ids", required=True)
    ap.add_argument("--out-prefix", required=True)
    ap.add_argument("--thread-pages", type=int, default=20)
    ap.add_argument("--adjacency", type=int, default=2500)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    sig = json.load(open(a.signals, encoding="utf-8"))
    loc = json.load(open(a.locales, encoding="utf-8"))
    read = {ln.strip() for ln in open(a.read_ids, encoding="utf-8") if ln.strip()}
    read_i = sorted(int(x) for x in read)
    import bisect

    def dist(v: int):
        k = bisect.bisect_left(read_i, v)
        c = [x for x in (read_i[k - 1] if k else None,
                         read_i[k] if k < len(read_i) else None) if x is not None]
        return min(abs(v - x) for x in c) if c else None

    cand = []
    for r in sig:
        if r["read"]:
            continue
        if "200" not in r["statuses"]:
            continue
        tier = None
        if len(loc.get(r["id"], [])) >= 5:
            tier = 1
        elif r["max_page"] >= a.thread_pages:
            tier = 2
        elif (dist(int(r["id"])) or 10 ** 9) <= a.adjacency:
            tier = 3
        if tier is None:
            continue
        cand.append((tier, r))

    # Within a tier: most captures first (archive confidence), then densest
    # thread, then earliest capture year so the tier is era-spread, not
    # single-era. Recording the sort key makes the ordering reproducible.
    cand.sort(key=lambda tr: (tr[0], -tr[1]["captures"], -tr[1]["max_page"],
                              tr[1]["first_ts"], int(tr[1]["id"])))
    if a.limit:
        cand = cand[: a.limit]

    os.makedirs(os.path.dirname(a.out_prefix) or ".", exist_ok=True)
    qbody = open(a.out_prefix + "-body.tsv", "w", encoding="utf-8", newline="\n")
    qpage = open(a.out_prefix + "-page.tsv", "w", encoding="utf-8", newline="\n")
    manifest = open(a.out_prefix + "-manifest.tsv", "w", encoding="utf-8", newline="\n")
    manifest.write("target\ttier\tid\tfirst_ts\tlast_ts\tyears\tmax_page\tcaptures\t"
                   "nlocales\tcomment_rows\tdist_to_read\n")

    nb = np_ = 0
    used: set[str] = set()
    for tier, r in cand:
        b = best_body_url(r)
        if b:
            key = f"body/{r['id']}.html"
            if key not in used:
                qbody.write(f"{key}\t{wayback(*b)}\n")
                used.add(key)
                nb += 1
                manifest.write(f"{key}\t{tier}\t{r['id']}\t{r['first_ts']}\t{r['last_ts']}\t"
                               f"{'|'.join(r['years'])}\t{r['max_page']}\t{r['captures']}\t"
                               f"{len(loc.get(r['id'], []))}\t{r['comments']}\t"
                               f"{r['dist_to_read'] if r['dist_to_read'] is not None else ''}\n")
        # later page
        if r["max_page"] > 1:
            pg = None
            bestsc = -1
            for o in r["orig"]:
                m = PAGEQ.search(o)
                if not m:
                    continue
                ids = DSRL.findall(o)
                if set(ids) != {r["id"]}:
                    continue
                if "act=" in o:
                    continue
                n = int(m.group(1))
                sc = (n, 1 if "l=en" in o else 0)
                if sc > (bestsc, 0):
                    bestsc = n
                    pg = (n, o)
            if pg:
                key = f"page/{r['id']}_p{pg[0]}.html"
                if key not in used:
                    ts = r["canonical_ts"] or r["first_ts"]
                    qpage.write(f"{key}\t{wayback(ts, pg[1])}\n")
                    used.add(key)
                    np_ += 1
                    manifest.write(f"{key}\t{tier}\t{r['id']}\t{r['first_ts']}\t{r['last_ts']}\t"
                                   f"{'|'.join(r['years'])}\t{pg[0]}\t{r['captures']}\t"
                                   f"{len(loc.get(r['id'], []))}\t{r['comments']}\t"
                                   f"{r['dist_to_read'] if r['dist_to_read'] is not None else ''}\n")

    for f in (qbody, qpage, manifest):
        f.close()
    from collections import Counter
    tc = Counter(t for t, _ in cand)
    print(f"candidates={len(cand)}  by tier={dict(sorted(tc.items()))}")
    print(f"wrote body targets={nb}  later-page targets={np_}  manifest rows={nb+np_}")
    yr = Counter((t, r["first_ts"][:4]) for t, r in cand)
    print("tier x first-capture-year:", dict(sorted(yr.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
