#!/usr/bin/env python3
"""Fetch all three Hunter_Supply_Office captures and diff the attendance tables.

This is the decisive era test: does the day-by-day table change between
2019-08-21, 2019-10-15 and 2020-08-08?

GUARD: http:// only, ONE session, positive control first, hash every body.
"""
import hashlib
import html
import os
import re
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

S = requests.Session()
S.headers.update({"User-Agent": "blustone-login-bonus-research/1.0 (read-only)"})

BASE = "http://web.archive.org"
CONTROL = (BASE + "/web/2021/https://bs.visualshower.com/files/attach/images/75605/"
           "303/534/001/725a8e175454a533e96dac68fc5fdb49.jpg")

OUT = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\login-bonus-2026-10-09"

STAMPS = ["20190821011235", "20191015115618", "20200808181724"]
PAGE = "Hunter_Supply_Office"


def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            return S.get(url, timeout=60)
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def positive_control():
    r = get(CONTROL)
    sig = r.content[:4].hex() if r.content else "--"
    ok = r.status_code == 200 and len(r.content) == 57414 and sig.startswith("ffd8ffe1")
    print("POSITIVE CONTROL: code=%s size=%s sig=%s -> %s"
          % (r.status_code, len(r.content), sig, "PASS" if ok else "FAIL"), flush=True)
    return ok


def strip(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def tables(t):
    """Every wikitable on the page -> list of rows of cell dicts."""
    out = []
    for m in re.finditer(r"<table[^>]*>(.*?)</table>", t, re.S):
        seg = m.group(1)
        rows = []
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", seg, re.S):
            cells = []
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S):
                mi = re.search(r'alt="([^"]+?)"', c)
                cells.append({"text": strip(c), "item": mi.group(1) if mi else None})
            if cells:
                rows.append(cells)
        if rows:
            out.append(rows)
    return out


if __name__ == "__main__":
    if not positive_control():
        print("ABORT: instrument fault, not a content negative.")
        sys.exit(2)
    os.makedirs(OUT, exist_ok=True)
    for st in STAMPS:
        url = "%s/web/%sid_/https://vsfan.net/wiki/%s" % (BASE, st, PAGE)
        r = get(url)
        body = r.content
        head = body[:4000].decode("utf-8", "replace")
        if r.status_code != 200 or "Temporarily Offline" in head or "not archived" in head:
            print("\n== %s FETCH FAIL code=%s size=%d" % (st, r.status_code, len(body)))
            continue
        t = body.decode("utf-8", "replace")
        p = os.path.join(OUT, "%s__%s.html" % (PAGE, st))
        open(p, "wb").write(body)
        print("\n" + "=" * 70)
        print("capture %s  http=%d bytes=%d sha256=%s"
              % (st, r.status_code, len(body), hashlib.sha256(body).hexdigest()))
        m = re.search(r"oldid=(\d+)", t)
        print("oldid:", m.group(1) if m else None)
        m = re.search(r"This page was last edited on ([^<]+?)\.", t)
        print("last_edited:", m.group(1) if m else None)
        for ti, tbl in enumerate(tables(t)):
            print("  -- table %d --" % ti)
            for row in tbl:
                print("     " + " | ".join("%s{%s}" % (c["text"], c["item"]) for c in row))
        m = re.search(r"Claim your Daily reward.{0,120}", t, re.S)
        if m:
            print("  veteran sentence:", strip(m.group(0)))
        # any prose mentioning day counts / weekly / monthly
        prose = strip(re.sub(r"<table.*?</table>", " ", t, flags=re.S))
        for kw in ["weekly", "monthly", "consecutive", "day 2", "8Day", "28"]:
            for mm in re.finditer(re.escape(kw), prose, re.I):
                print("  PROSE[%s]: ...%s..." % (kw, prose[max(0, mm.start() - 110):mm.end() + 110]))
        sys.stdout.flush()
        time.sleep(1.0)