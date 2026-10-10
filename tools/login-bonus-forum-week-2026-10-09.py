#!/usr/bin/env python3
"""Targeted sweep for the rest of the cycle: rainbow scroll, weeks 2-4,
28-day reset, and the day-7 conflict.

Instrument faults carried from earlier:
  * XE sidebar repeats every thread title -> body-only extraction required
  * positive control before any zero (149251: Metron Crystals / 5000 Rupees)
"""
import html
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\forum-en-2026-10-05\pass2\body"


def body_of(raw):
    c = re.findall(r'<div class="document_[^"]*xe_content">(.*?)</div>\s*</div>', raw, re.S)
    c += re.findall(r'<div class="comment_[^"]*xe_content">(.*?)</div>\s*</div>', raw, re.S)
    if c:
        return "\n".join(c)
    return "\n".join(re.findall(r'xe_content">(.*?)</div>', raw, re.S))


def clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</p>", "\n\n", s)
    return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s)))


SCREENS = {
    "rainbow_scroll": r"rainbow",
    "day28_cycle": r"(day ?28|28 ?day|4\* ?selection every|every 28)",
    "week2_3_4": r"(second week|third week|2nd week|3rd week|fourth week|week 2|week 3|week 4|10\+1)",
    "cumulative": r"cumulative",
    "attendance_counter": r"attendance counter|login counter|sign ?in (?:counter|chart|board)",
}

if __name__ == "__main__":
    db = []
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".html"):
            continue
        raw = open(os.path.join(ROOT, fn), "rb").read().decode("utf-8", "replace")
        db.append((fn[:-5], clean(body_of(raw)), raw))

    ctl = [b for k, b, _ in db if k == "149251"]
    print("control copies: %d, len=%s" % (len(ctl), [len(x) for x in ctl]))
    if ctl:
        print("control term counts: Metron Crystals=%d 5000 Rupees=%d Transcendence=%d"
              % (ctl[0].count("Metron Crystals"), ctl[0].count("5000 Rupees"),
                 ctl[0].count("Transcendence")))
    ok = ctl and "Metron Crystals" in ctl[0] and "5000 Rupees" in ctl[0]
    print("POSITIVE CONTROL (149251): %s" % ("PASS" if ok else "FAIL"))
    if not ok:
        sys.exit(2)

    for name, pat in SCREENS.items():
        rx = re.compile(pat, re.I)
        hits = [(k, b) for k, b, _ in db if rx.search(b)]
        print("\n" + "#" * 74)
        print("### %s : %d body-only docs" % (name, len(hits)))
        print("#" * 74)
        for k, b in hits:
            # require the doc to be actually about attendance, else it is noise
            if not re.search(r"login|sign.?in|attendance|daily", b, re.I):
                continue
            t = re.search(r"<title>(.*?)</title>", db[[d[0] for d in db].index(k)][2], re.S)
            print("\n--- doc %s | %s" % (k, clean(t.group(1))[:100] if t else ""))
            for m in rx.finditer(b):
                a = max(0, m.start() - 340)
                print("   >> ...%s..." % re.sub(r"\s+", " ", b[a:m.end() + 340]))