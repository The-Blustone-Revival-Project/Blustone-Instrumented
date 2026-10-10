#!/usr/bin/env python3
"""Build the pass-2 forum_en BODY fetch queue from local data only.

No index query. Inputs are already on disk:
  census/page-*.tsv + census/en-post-ids.json  (pass-1 CDX census)
  pass2/list-index.json                        (pass-2 board list-page index)
  get-body/parsed.json                         (pass-1 bodies already read)

URL choice per post id: the LATEST captured timestamp whose `original` carries
an explicit `l=en` and a 200 status. "Latest" is chosen deliberately: a re-capture
of an old thread includes every reply added since the pass-1 (2018) capture, and
reply text is where this board's density lives. Every candidate is written to the
sidecar meta so a second capture can be requested without re-querying the index.

Scoring, in priority order, then stable by id:
  1000 * <topic weight>      explicit screen for the three open questions
  +  60 * min(replies, 30)   list-page reply count = reply density
  +  10 * log10(views + 1)
  +  40 vendor/author bonus  the three official accounts
  +  20 adjacency bonus      |id - id of a pass-1 read post| <= 3
  +   5 sticky bonus

The topic screen is a SCREEN, not a determination: a title keyword only decides
what is fetched first. Nothing is concluded from a title.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import re

DSRL = re.compile(r"[?&]document_srl=(\d+)")
LANG = re.compile(r"[?&]l=([A-Za-z-]+)")

# topic -> (regex, weight). Weight 3 is a direct hit on one of the three open
# questions; 2 is adjacent economy; 1 is generic mechanics.
TOPICS: dict[str, tuple[str, int]] = {
    # ---- Q1 transcendence: does a second transcendence compound or scale? -------
    "t1_transcendence": (r"transcenden|trascenden|超越|transend", 3),
    "t1_transc_form": (r"final form|fully ?transcend|power of .{0,24}transcend|max transcend", 3),
    "t1_advanc_vs_trans": (r"advanc.{0,30}(transcend|rank)|transcend.{0,30}advanc", 3),
    "t1_guru_gate": (r"guru|reputation .{0,20}(vincent|unlock)", 2),
    # ---- Q2 per-level growth ------------------------------------------------
    "t2_stat_changes": (r"stat change|stat (increase|growth|per|boost)|stat up|raw stat", 3),
    "t2_max_stats": (r"max stats?|stat cap|max(?:imum)? (?:level|lv)", 3),
    "t2_awaken_stats": (r"awaken", 3),
    "t2_char_stats": (r"character stats?|stats? page|abilities.{0,10}stats", 3),
    "t2_dmg_calc": (r"damage (calc|formula|calculation|number)|skill damage|how much damage", 3),
    "t2_crit_block": (r"crit|critical|block chance|attack speed|penetrat", 2),
    # ---- Q3 equipment / accessory stat values -------------------------------
    "t3_equip_system": (r"equipment|armou?r|weapon", 3),
    "t3_jewel": (r"jewel|gem\b|jewelry", 3),
    "t3_equip_slot": (r"equip.{0,25}(slot|level|advance)|slot.{0,20}equip", 3),
    "t3_plus_stats": (r"\+\s*\d+\s*(hp|atk|def|attack|defen)", 3),
    # ---- economy / costs ---------------------------------------------------
    "e_cost": (r"\bcost|\bprice|expensive|cheapest|how much|gold|rupee|manda|ticket", 2),
    "e_gacha": (r"gacha|recruit|pull|summon|scroll|rainbow|legendary selection|banner|rate", 2),
    "e_rankup": (r"rank ?up|advanc|star ?up|\b[3-5]\s?\*|grade", 2),
    "e_train": (r"train|gym|level ?up|\bexp\b|experience", 2),
    "e_arena": (r"fight club|arena|pvp|guild|colosse", 1),
    "e_ap": (r"\bap\b|stamina|fuel|energy|timer", 1),
    "e_drop": (r"drop rate|loot|chance|percent|%", 2),
    # ---- guides / vendor ----------------------------------------------------
    "g_guide": (r"guide|tip|how to|advice|best|strategy|meta|recommend|priority", 2),
    "g_notice": (r"^\s*\[notice\]|\[notice\]", 2),
    "g_patch": (r"patch|update|balance|version|release note", 2),
    # ---- content-ish --------------------------------------------------------
    "m_monster": (r"monster|boss|snowfox|pandahawk|moonwoof|mook", 2),
    "e_element": (r"element|weakness|resist|attribute|fire|ice|lightning|water|dark|light", 1),
    "s_stat": (r"\bstat|\batk\b|\bdef\b|\bhp\b|damage|power|heal", 1),
}
COMPILED = {k: (re.compile(p, re.I), w) for k, (p, w) in TOPICS.items()}

VENDORS = {"vspang", "master", "natara"}


def topic_hits(title: str) -> dict[str, int]:
    return {k: w for k, (rx, w) in COMPILED.items() if rx.search(title or "")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", required=True)
    ap.add_argument("--listindex", required=True)
    ap.add_argument("--parsed1", required=True, help="pass-1 parsed.json (bodies already read)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=900)
    ap.add_argument("--topup-out", default="",
                    help="optional second queue: the LATEST later EN capture of the "
                         "pass-1 posts that already have a body on disk. A re-capture "
                         "of an old thread carries every reply added since the 2018 "
                         "capture pass 1 read, so this is new text, not a re-read.")
    ap.add_argument("--topup-limit", type=int, default=0)
    ap.add_argument("--capture-policy", choices=("reply-rich", "latest"), default="reply-rich",
                    help="which archived capture of each post to fetch. "
                         "'reply-rich' takes the newest capture dated <= 2020-12-31; "
                         "'latest' takes the newest capture of any date. Measured: over "
                         "the first 291 captures, mean replies/post are 3.57 (2018), 3.57 "
                         "(2019), 3.44 (2020), 1.31 (2021), 0.80 (2022), 0.22 (2023), so the "
                         "later XE template stores far fewer replies on the same post.")
    ap.add_argument("--cutover", default="20201231")
    args = ap.parse_args()

    rows = []
    for f in sorted(glob.glob(os.path.join(args.census, "page-*.tsv"))):
        for ln in open(f, encoding="utf-8"):
            p = ln.rstrip("\n").split("\t")
            if len(p) >= 5:
                rows.append(p)

    # best EN capture per id, plus the full candidate list
    cand: dict[str, list] = collections.defaultdict(list)
    for r in rows:
        ts, orig, status = r[1], r[2], r[4]
        m = DSRL.search(orig)
        if not m or status != "200":
            continue
        lm = LANG.search(orig)
        lang = lm.group(1).lower() if lm else "default"
        if lang != "en":
            continue
        cand[m.group(1)].append((ts, orig))

    listidx = {}
    if os.path.exists(args.listindex):
        for r in json.load(open(args.listindex, encoding="utf-8")):
            listidx[r["id"]] = r

    read = set()
    if os.path.exists(args.parsed1):
        for r in json.load(open(args.parsed1, encoding="utf-8")):
            if not r.get("error") and r.get("has_doc_div"):
                read.add(r["id"])
    read_sorted = sorted(read, key=int)

    scored = []
    for pid, cs in cand.items():
        if pid in read:
            continue
        li = listidx.get(pid, {})
        title = li.get("title", "")
        hits = topic_hits(title)
        tw = sum(hits.values())
        reps = int(li.get("replies") or 0)
        views = int(li.get("views") or 0)
        author = (li.get("author") or "").strip().lower()
        score = (
            1000 * tw
            + 60 * min(reps, 30)
            + 10 * math.log10(views + 1)
            + (40 if author in VENDORS else 0)
            + (5 if li.get("sticky") else 0)
        )
        # adjacency: closest pass-1 read id
        near = min((abs(int(pid) - int(x)) for x in read_sorted), default=10 ** 9)
        if near <= 3:
            score += 20
        elif near <= 15:
            score += 10
        elif near <= 100:
            score += 4
        cut = args.cutover
        rich = [c for c in cs if c[0] <= cut]
        if args.capture_policy == "reply-rich" and rich:
            pick_ts, pick_orig = max(rich)
            pick_rule = f"newest<= {cut}"
        elif args.capture_policy == "reply-rich":
            pick_ts, pick_orig = min(cs)
            pick_rule = "earliest (no pre-cutover capture exists)"
        else:
            pick_ts, pick_orig = max(cs)
            pick_rule = "newest of any date"
        scored.append({
            "id": pid, "score": score, "topics": hits, "title": title,
            "author": li.get("author", ""), "date": li.get("date", ""),
            "replies": reps, "views": views, "near_read": near,
            "known": bool(li),
            "captures_en": len(cs),
            "latest_ts": max(c[0] for c in cs),
            "latest_orig": max(cs)[1],
            "pick_ts": pick_ts,
            "pick_orig": pick_orig,
            "pick_rule": pick_rule,
        })

    scored.sort(key=lambda d: (-d["score"], -d["replies"], int(d["id"])))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    todo = scored[: args.limit]
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        for d in todo:
            fh.write(f"body/{d['id']}.html\thttp://web.archive.org/web/{d['pick_ts']}/{d['pick_orig']}\n")

    meta = {
        "candidates_with_en_200_capture": len(cand),
        "pass1_read_ids": len(read),
        "unread_with_en_200_capture": len(scored),
        "queued": len(todo),
        "score_bands": {},
        "topic_counts_over_queued": dict(collections.Counter(
            k for d in todo for k in d["topics"])),
        "queued_no_title": sum(1 for d in todo if not d["known"]),
        "queued_rows": todo,
    }
    for d in scored:
        b = d["score"] // 1000
        meta["score_bands"][str(b)] = meta["score_bands"].get(str(b), 0) + 1
    with open(args.out + ".meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)

    print(f"EN 200-capture ids: {len(cand)}   pass1 read: {len(read)}")
    print(f"unread & fetchable:  {len(scored)}   queued: {len(todo)}")
    print(f"queued without a list-page title: {meta['queued_no_title']}")
    print(f"topic counts: {json.dumps(meta['topic_counts_over_queued'])}")
    print(f"weight bands (0=unmatched): {json.dumps(meta['score_bands'])}")

    # ---- optional reply top-up of the pass-1 posts ------------------------
    if args.topup_out:
        tups = []
        for pid in read:
            cs = cand.get(pid, [])
            if len({c[0] for c in cs}) < 2:
                continue  # only one capture: a re-fetch would re-read, not add
            ts, orig = max(cs)
            earliest = min(c[0] for c in cs)
            if ts <= earliest:
                continue
            li = listidx.get(pid, {})
            tups.append({
                "id": pid, "ts": ts, "orig": orig, "earliest": earliest,
                "title": li.get("title", ""), "replies": int(li.get("replies") or 0),
            })
        # densest-reply threads first: that is where pass 1 found the content
        tups.sort(key=lambda d: (-d["replies"], -int(d["ts"]), int(d["id"])))
        if args.topup_limit:
            tups = tups[: args.topup_limit]
        with open(args.topup_out, "w", encoding="utf-8", newline="\n") as fh:
            for d in tups:
                fh.write(f"topup/{d['id']}.html\thttp://web.archive.org/web/{d['ts']}/{d['orig']}\n")
        with open(args.topup_out + ".meta.json", "w", encoding="utf-8") as fh:
            json.dump({"queued": len(tups), "rows": tups}, fh, ensure_ascii=False, indent=1)
        print(f"reply top-up queue: {len(tups)} (of {len(read)} pass-1 posts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())