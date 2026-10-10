#!/usr/bin/env python3
"""Fetch the docs that exist only in body-latest, and do a final numeric sweep
for attendance reward QUANTITIES stated in prose (the wiki table is the only
source so far that names item+amount together)."""
import html
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\forum-en-2026-10-05"
SUBS = [os.path.join("get-body", "body"), os.path.join("pass2", "topup")]


def body_of(raw):
    c = re.findall(r'<div class="document_[^"]*xe_content">(.*?)</div>\s*</div>', raw, re.S)
    c += re.findall(r'<div class="comment_[^"]*xe_content">(.*?)</div>\s*</div>', raw, re.S)
    if c:
        return c
    return re.findall(r'xe_content">(.*?)</div>', raw, re.S)


def clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</p>", "\n\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t]+", " ", html.unescape(s))


for sub in SUBS:
    for d in ("1393319", "1422054"):
        p = os.path.join(BASE, sub, d + ".html")
        if not os.path.exists(p):
            continue
        raw = open(p, "rb").read().decode("utf-8", "replace")
        t = re.search(r"<title>(.*?)</title>", raw, re.S)
        dates = re.findall(r"\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}", clean(raw))
        print("\n" + "=" * 78)
        print("### %s/%s | %s" % (sub, d, clean(t.group(1))[:110] if t else ""))
        if dates:
            print("    dates: %s .. %s" % (dates[0], dates[-1]))
        print("=" * 78)
        for i, c in enumerate(body_of(raw)):
            txt = re.sub(r"\n{3,}", "\n\n", clean(c)).strip()
            if txt:
                print("[%02d] %s" % (i, txt[:2200]))
                print("-" * 40)