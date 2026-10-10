#!/usr/bin/env python3
"""Analyse pass-2 forum_en bodies: provenance ledger + numeric-structure screen.

Reads the captured HTML with the SAME verified XE anchors as
tools/forum-en-parse.py (so pass-1 and pass-2 numbers are comparable), then
screens each post for the things this lane is looking for:

  * an HTML <table>            -> a real numeric table (pass 1 found 0/154)
  * digit density              -> numerator-rich prose
  * body/reply keyword hits    -> the three open questions, matched on the
                                  BODY TEXT, not on the title

Every record keeps the capture filename and the sha256 of the bytes on disk, so
each reading below can be re-verified against a specific archived capture.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# NOTE: no stdout rewrap here. tools/forum-en-parse.py installs its own
# TextIOWrapper around sys.stdout.buffer at import time; wrapping the buffer a
# second time means the first wrapper is garbage-collected and CLOSES the shared
# buffer, producing "I/O operation on closed file" on the first print.

import importlib.util as _ilu  # noqa: E402

# tools/forum-en-parse.py has hyphens in its name, so it cannot be imported
# normally; load it by path so the ANCHORS stay single-sourced with pass 1.
_spec = _ilu.spec_from_file_location(
    "forum_en_parse",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "forum-en-parse.py"),
)
P = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(P)

# Body-text screens for the three open questions. Separate from the title screen
# in forum-en-pass2-bodyq.py on purpose: a title is not evidence.
BODY_Q = {
    "q1_second_transcendence": re.compile(
        r"(?:t\s*2|two|second|3rd|third)\s*(?:transcenden|trascenden)|transcenden\w*\s*(?:t\s*2|lv\s*2|level\s*2|2\b)|"
        r"second transcenden", re.I),
    "q1_compound": re.compile(
        r"compoun|multipli\w*|additive|scal\w*\s*(?:up|off|from)|from base|\+\s*\d+(?:\.\d+)?\s*%", re.I),
    "q1_t1_value": re.compile(
        r"t\s*1[^.\n]{0,60}(?:\d+(?:\.\d+)?\s*%|\d+\s*%)|transcenden[^.\n]{0,80}\d+(?:\.\d+)?\s*%", re.I),
    "q2_per_level": re.compile(
        r"per\s+(?:level|lv|each level)|every\s+level|each\s+level\s+(?:up|gain|give)|level\s*\+?\s*1\s*[:=]|\+\d+(?:\.\d+)?\s*%\s*(?:per|each)|"
        r"(?:hp|atk|attack|defen\w*)[^.\n]{0,30}\d+(?:\.\d+)?\s*%", re.I),
    "q2_stat_total": re.compile(
        r"\b(?:hp|atk|attack|defen\w*)\b\s*[:=]?\s*\d{2,5}", re.I),
    "q2_curves": re.compile(
        r"curve|formula|growth|scaling|stat\s*(?:table|chart|list|growth|increase)", re.I),
    "q3_equip_stat": re.compile(
        r"\+\s*\d+(?:\.\d+)?\s*(?:%|hp|atk|atk\b|def\b|defen\w*)|"
        r"(?:hp|atk|attack|defen\w*)\s*\+\s*\d+(?:\.\d+)?|"
        r"(?:equipment|armou?r|weapon|jewel|gem|accessor\w*)[^.\n]{0,40}\d{1,3}\s*(?:%|hp|atk|def)", re.I),
    "q3_equip_cost": re.compile(
        r"(?:equipment|armou?r|weapon|jewel|gem)[^.\n]{0,40}\d[\d,]*\s*(?:gold|rupee|manda|coin|zenny)", re.I),
    "economy_cost": re.compile(
        r"\b\d[\d,]*\s*(?:gold|rupee|manda|coin|gems?)\b|\b(?:costs?|price[sd]?)\s*[:=]?\s*\d[\d,]*", re.I),
    "gacha_rate": re.compile(
        r"\d+(?:\.\d+)?\s*%|percent|rate\s*(?:is|of|:)|odds|chance", re.I),
    "element_table": re.compile(
        r"(?:fire|ice|lightning|water|light|dark)[^.\n]{0,30}(?:weak|strong|resist|counter)", re.I),
    "max_level": re.compile(
        r"max(?:imum)?\s*(?:level|lv)\s*[:=]?\s*\d+|lv(?:el)?\s*\d+\s*(?:is|max|/)", re.I),
    "damage_formula": re.compile(
        r"damage\s*(?:=|is|=|formula|calc)|deals?\s*\d+|takes?\s*\d+\s*damage", re.I),
}

UNIT_LINE = re.compile(
    r"(?:\b\d[\d,]*(?:\.\d+)?\s*(?:%|hp|atk|def\b|defen\w*|gold|rupee|manda|coin)\b)"
    r"|(?:\+\s*\d+(?:\.\d+)?\s*(?:%|hp|atk|def))",
    re.I)


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def analyse(path: str) -> dict:
    rec = P.parse(path)
    rec["sha256"] = sha256_of(path)
    body = rec.get("body") or ""
    repl = rec.get("replies") or ""
    both = body + "\n" + repl
    hits = {k: len(rx.findall(both)) for k, rx in BODY_Q.items()}
    hits = {k: v for k, v in hits.items() if v}
    numeric_lines = []
    for ln in both.split("\n"):
        ln = ln.strip()
        if ln and UNIT_LINE.search(ln) and len(ln) < 400:
            numeric_lines.append(ln)
    rec["body_q_hits"] = hits
    rec["numeric_lines"] = numeric_lines
    rec["n_numeric_lines"] = len(numeric_lines)
    rec["usable"] = validity(rec)
    return rec


# Captures that are an XE error / gate page rather than the post. Wayback happily
# stores a 200 response for these, so an HTTP 200 is NOT evidence of content.
ERROR_TITLES = re.compile(
    r"you do not have permission|permission to access|login|log in|error|"
    r"not found|blustone\s*$|captcha|forbidden|access denied",
    re.I)


def validity(rec: dict) -> dict:
    """Verdict on whether this capture actually carries the post.

    NOT a rejection criterion: a missing `date m_no` span or a missing Views
    counter. Measured, not assumed: 82 of the first 160 pass-2 captures carry a
    real post and real replies but use the later XE template, which renders
    neither anchor, while the 2018-era pass-1 captures carry both. Treating
    those as unusable would have discarded 82 genuine posts. The absence is
    recorded as `template` instead.
    """
    why = []
    if not rec.get("has_doc_div"):
        why.append("no-document-div")
    t = (rec.get("title") or "").strip()
    if t and ERROR_TITLES.match(t):
        why.append("error-or-gate-title:" + t[:60])
    if not t:
        why.append("no-title")
    if (rec.get("chars") or 0) < 40 and (rec.get("reply_chars") or 0) < 40:
        why.append("near-empty-text")
    return {
        "ok": not why,
        "why": why,
        "template": "full" if (rec.get("date") and rec.get("views")) else "no-date-views-anchors",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--glob", default="body/*.html")
    ap.add_argument("--out", required=True)
    ap.add_argument("--digest", default="")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.dir, a.glob)))
    recs = []
    err = 0
    for p in files:
        try:
            recs.append(analyse(p))
        except Exception as exc:  # noqa: BLE001
            err += 1
            recs.append({"file": os.path.basename(p), "error": f"{type(exc).__name__}: {exc}"})
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(recs, fh, ensure_ascii=False, indent=1)
    good = [r for r in recs if not r.get("error")]
    usable = [r for r in good if (r.get("usable") or {}).get("ok")]
    distinct = {r["id"] for r in good if r.get("has_doc_div")}
    distinct_u = {r["id"] for r in usable}
    print(f"files={len(files)} parsed={len(good)} errors={err} distinct_posts={len(distinct)}")
    print(f"  USABLE captures: {len(usable)}  distinct usable posts: {len(distinct_u)}")
    bad = [r for r in good if r not in usable]
    import collections as _c
    whyc = _c.Counter(w for r in bad for w in (r["usable"]["why"] or ["?"]))
    tmpl = _c.Counter((r["usable"].get("template")) for r in good)
    print(f"  rejected: {len(bad)} -> {json.dumps(dict(whyc))}")
    print(f"  template forms: {json.dumps(dict(tmpl))}")
    print(f"  with a document div: {sum(1 for r in good if r.get('has_doc_div'))}")
    print(f"  body chars={sum(r['chars'] for r in good)} reply chars={sum(r['reply_chars'] for r in good)}")
    print(f"  with an HTML <table>: {sum(1 for r in good if r.get('n_tables'))}")
    print(f"  with images: {sum(1 for r in good if r.get('imgs'))}")
    print(f"  with >=1 numeric unit line: {sum(1 for r in good if r.get('n_numeric_lines'))}")
    print(f"  total numeric unit lines: {sum(r.get('n_numeric_lines', 0) for r in good)}")
    import collections
    q = collections.Counter(k for r in good for k in (r.get("body_q_hits") or {}))
    print("  body-text screen hits:", json.dumps(dict(q.most_common()), indent=0).replace("\n", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())