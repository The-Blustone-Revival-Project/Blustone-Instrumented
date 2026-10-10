#!/usr/bin/env python3
"""CDX prefix census for the attendance screenshots + the visualshower attach tree.

GUARD:
  * http:// only, ONE session, positive control first
  * a `prefix` query with a literal `*` returns 0 bytes -> use url= prefix, no star
  * CDX can return "Temporarily Offline" as a body -> hash-check every body
  * a rewritten im_ URL is NOT evidence the bytes exist -> decode pixels
"""
import hashlib
import json
import os
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

S = requests.Session()
S.headers.update({"User-Agent": "blustone-login-bonus-research/1.0 (read-only)"})

BASE = "http://web.archive.org"
CDX = BASE + "/cdx/search/cdx"
OUT = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\login-bonus-2026-10-09"

CONTROL = (BASE + "/web/2021/https://bs.visualshower.com/files/attach/images/75605/"
           "303/534/001/725a8e175454a533e96dac68fc5fdb49.jpg")

# each of these three path-shares is derived from the forum doc id
PREFIXES = [
    "bs.visualshower.com/files/attach/images/175/557/675/",
    "bs.visualshower.com/files/attach/images/175/643/691/",
    "bs.visualshower.com/files/attach/images/175/975/167/001/",
]


def get(url, params=None, tries=4):
    last = None
    for i in range(tries):
        try:
            return S.get(url, params=params, timeout=60)
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


def cdx(url_prefix, limit=2000):
    p = {"url": url_prefix, "output": "json", "limit": str(limit), "collapse": "digest"}
    r = get(CDX, params=p)
    txt = r.text
    if not txt.strip():
        return [], 0
    if "Temporarily Offline" in txt[:3000]:
        return [], -1
    try:
        rows = json.loads(txt)
    except Exception:
        return [], -2
    return rows[1:], r.status_code


if __name__ == "__main__":
    if not positive_control():
        print("ABORT: instrument fault.")
        sys.exit(2)

    # A control for the CDX shape itself: a prefix known to have captures.
    ctl_rows, ctl_code = cdx("bs.visualshower.com/files/attach/images/75605/")
    print("CDX SHAPE CONTROL (75605/): code=%s rows=%d -> %s"
          % (ctl_code, len(ctl_rows), "PASS" if ctl_rows else "FAIL"))
    if not ctl_rows:
        print("ABORT: the CDX shape is not working; zeros below would be meaningless.")
        sys.exit(2)

    for pre in PREFIXES:
        rows, code = cdx(pre)
        print("\n=== prefix %s  code=%s rows=%d" % (pre, code, len(rows)))
        for r_ in rows[:60]:
            print("    %s  %s  %s  len=%s" % (r_[1], r_[2], r_[3], r_[4]))
        sys.stdout.flush()
        time.sleep(1.2)