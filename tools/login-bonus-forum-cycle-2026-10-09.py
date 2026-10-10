#!/usr/bin/env python3
"""Full text of the documents that define the cycle length and the tier rewards."""
import html
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\forum-en-2026-10-05\pass2\body"
DOCS = ["292924", "1058787", "1167975", "1393319", "1422054", "1368000",
        "675557", "691643", "1561517"]


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


for d in DOCS:
    p = os.path.join(ROOT, d + ".html")
    if not os.path.exists(p):
        print("### %s MISSING" % d)
        continue
    raw = open(p, "rb").read().decode("utf-8", "replace")
    t = re.search(r"<title>(.*?)</title>", raw, re.S)
    # dates are embedded in the comment markup
    dates = re.findall(r"\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}", clean(raw))
    print("\n" + "=" * 78)
    print("### doc %s | %s" % (d, clean(t.group(1))[:120] if t else ""))
    if dates:
        print("    dates seen: %s .. %s (n=%d)" % (dates[0], dates[-1], len(dates)))
    print("=" * 78)
    for i, c in enumerate(body_of(raw)):
        txt = re.sub(r"\n{3,}", "\n\n", clean(c)).strip()
        if txt:
            print("[%02d] %s" % (i, txt[:2400]))
            print("-" * 40)
    sys.stdout.flush()