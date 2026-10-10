#!/usr/bin/env python3
"""Dump the verbatim forum contexts for login-bonus semantics.

Questions:
  Q2 cycle length / reset boundary
  Q3 consecutive-day / streak semantics
  Q5 Veteran-point reconciliation (G9)
"""
import html
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\forum-en-2026-10-05"


def body_only(raw):
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


QUERIES = {
    "Q2_cycle_reset": [
        r"day ?28", r"28[- ]day", r"\bweekly\b", r"\bmonthly\b",
        r"reset", r"resets",
    ],
    "Q3_streak": [
        r"\bconsecutive\b", r"\bstreak\b",
    ],
    "Q5_veteran": [
        r"[Vv]eteran [Pp]oint", r"veteran level", r"veteran exp",
    ],
    "day_rewards": [
        r"daily (?:login|sign|reward|bonus)", r"login (?:reward|bonus|calendar)",
        r"attendance", r"\bday ?[1-7]\b.{0,40}(?:reward|item|scroll|rupee)",
    ],
}


def main():
    seen = set()
    for name, pats in QUERIES.items():
        rx = re.compile("|".join(pats), re.I)
        print("\n" + "#" * 78)
        print("### %s" % name)
        print("#" * 78)
        n = 0
        for dirpath, _d, files in os.walk(ROOT):
            for fn in sorted(files):
                p = os.path.join(dirpath, fn)
                if "body-latest" in p or "topup" in p or "get-list" in p:
                    continue
                key = os.path.basename(p)[:-5] if fn.endswith(".html") else fn
                if key in seen:
                    continue
                raw = open(p, "rb").read().decode("utf-8", "replace")
                b = clean(body_only(raw))
                if not rx.search(b):
                    continue
                # keep only docs that are actually about login/attendance
                if not re.search(r"login|sign ?in|attendance|daily", b, re.I):
                    continue
                seen.add(key)
                n += 1
                title = re.search(r"<title>(.*?)</title>", raw, re.S)
                print("\n--- doc %s  %s" % (key, clean(title.group(1))[:110] if title else ""))
                for m in rx.finditer(b):
                    a = max(0, m.start() - 300)
                    z = m.end() + 300
                    frag = " ".join(b[a:z].split())
                    print("   >> ...%s..." % frag)
        print("\n[%s: %d docs]" % (name, n))


if __name__ == "__main__":
    main()