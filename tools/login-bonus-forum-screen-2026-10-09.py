#!/usr/bin/env python3
"""Mine the recovered English board corpus for Login Bonus / attendance semantics.

Instrument-fault notes carried from the prior lane:
  * The XE board template repeats every thread title in a sidebar, so a
    whole-page keyword screen is meaningless (2668/4169 false hits).
    Extract only the post body + comment bodies.
  * Run a POSITIVE CONTROL before believing any zero.
"""
import html
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\forum-en-2026-10-05"

CONTROL_DOC = "149251"
CONTROL_TERMS = ["Metron Crystals", "5000 Rupees"]


def body_only(raw):
    """Post body + every comment body. Sidebar/titles excluded."""
    chunks = re.findall(r'<div class="document_[^"]*xe_content">(.*?)</div>\s*</div>', raw, re.S)
    chunks += re.findall(r'<div class="comment_[^"]*xe_content">(.*?)</div>\s*</div>', raw, re.S)
    if not chunks:
        chunks = re.findall(r'xe_content">(.*?)</div>', raw, re.S)
    return "\n".join(chunks)


def clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"[ \t]+", " ", s)


def walk():
    for dirpath, _dirs, files in os.walk(ROOT):
        for fn in files:
            p = os.path.join(dirpath, fn)
            try:
                raw = open(p, "rb").read().decode("utf-8", "replace")
            except Exception:
                continue
            yield p, raw


SCREENS = {
    "login": [r"\blogin\b", r"\blog ?in\b", r"\bsign ?in\b", r"\bsigned? ?in\b"],
    "attendance": [r"\battendance\b", r"\battend(?:s|ence|ing)?\b", r"\bdaily sign\b", r"\bsign-?in\b"],
    "consecutive": [r"\bconsecutive\b", r"\bstreak\b"],
    "calendar_cycle": [r"\bday ?28\b", r"\b28 ?day\b", r"\bweekly\b", r"\bmonthly\b"],
}


def main():
    db = []
    for p, raw in walk():
        body = clean(body_only(raw))
        db.append((p, body))
    print("files scanned:", len(db))

    # ---- POSITIVE CONTROL ----
    ctl = [(p, b) for p, b in db if CONTROL_DOC in p]
    ok = False
    if ctl:
        b = ctl[0][1]
        ok = all(t in b for t in CONTROL_TERMS)
        print("control copy len:", len(b), "terms:",
              {t: b.count(t) for t in CONTROL_TERMS})
    print("POSITIVE CONTROL (%s, expect %r): %s -> %s"
          % (CONTROL_DOC, CONTROL_TERMS, "found %d copies" % len(ctl),
             "PASS" if ok else "FAIL"))
    if not ok:
        print("ABORT: instrument fault, not a content negative.")
        return

    hits = {}
    for name, pats in SCREENS.items():
        rx = re.compile("|".join(pats), re.I)
        f = [(p, b) for p, b in db if rx.search(b)]
        hits[name] = f
        print("screen %-16s body-only files: %d" % (name, len(f)))
    json.dump({k: [p for p, _ in v] for k, v in hits.items()},
              open(r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets"
                   r"\login-bonus-2026-10-09\forum-screens.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()