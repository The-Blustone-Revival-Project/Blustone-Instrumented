#!/usr/bin/env python3
"""Full text of the specific forum documents that bear on the calendar."""
import html
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\forum-en-2026-10-05\pass2\body"

DOCS = [
    "386474",   # cumulative attendance - does it reset?
    "691643",   # rainbow scroll glitch, day 28, 7th day
    "675557",   # day 7 reward / day 28
    "1422054",  # daily reward kinds, weekly scrolls, 10+1 third week
    "1167975",  # weekly -> monthly change
    "1561517",  # 4* selection on 7th day
    "1479784",  # veteran points 320/week
    "1566634",  # veteran pts, 7 daily tasks award 20pts
    "1187734",  # daily reset time
    "1209881",  # daily sign in update time
    "456343",   # 300 days celebration
    "1393319",  # login-counter, 4* selection monthly
]


def body_of(raw):
    chunks = re.findall(r'<div class="document_[^"]*xe_content">(.*?)</div>\s*</div>', raw, re.S)
    chunks += re.findall(r'<div class="comment_[^"]*xe_content">(.*?)</div>\s*</div>', raw, re.S)
    if not chunks:
        chunks = re.findall(r'xe_content">(.*?)</div>', raw, re.S)
    return chunks


def clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</p>", "\n\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


for d in DOCS:
    p = os.path.join(ROOT, d + ".html")
    if not os.path.exists(p):
        print("### %s  MISSING" % d)
        continue
    raw = open(p, "rb").read().decode("utf-8", "replace")
    t = re.search(r"<title>(.*?)</title>", raw, re.S)
    print("\n" + "=" * 78)
    print("### doc %s  |  %s" % (d, clean(t.group(1))[:120] if t else ""))
    print("=" * 78)
    for i, c in enumerate(body_of(raw)):
        txt = clean(c)
        if txt:
            print("[%02d] %s" % (i, txt[:2600]))
            print("-" * 40)
    sys.stdout.flush()