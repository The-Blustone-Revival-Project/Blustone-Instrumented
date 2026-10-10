#!/usr/bin/env python3
"""Wayback CDX enumeration for the vsfan attendance pages.

GUARD (GUARD-encoding-and-archive-traps.md):
  * http:// only  (https refused on this host, WinError 10061)
  * ONE requests.Session reused for the whole run
  * low concurrency
  * positive control BEFORE any zero is recorded
  * hash every body; "Temporarily Offline" is an instrument fault
  * CDX exact-URL can return false negatives -> cross-check with id_ fetch
"""
import json
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

S = requests.Session()
S.headers.update({"User-Agent": "blustone-login-bonus-research/1.0 (read-only)"})

CDX = "http://web.archive.org/cdx/search/cdx"
BASE = "http://web.archive.org"

# The exact form that WORKED in the prior lane (tools/vsfan-reward-fetch-2026-10-09.py).
CONTROL = (BASE + "/web/2021/https://bs.visualshower.com/files/attach/images/75605/"
           "303/534/001/725a8e175454a533e96dac68fc5fdb49.jpg")


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


def cdx(url_exact, extra=None):
    p = {"url": url_exact, "output": "json", "limit": "400"}
    if extra:
        p.update(extra)
    r = get(CDX, params=p)
    txt = r.text
    if not txt.strip():
        return [], r.status_code
    if "Temporarily Offline" in txt[:3000]:
        print("   !! archive returned Temporarily Offline for", url_exact)
        return [], r.status_code
    try:
        rows = json.loads(txt)
    except Exception:
        return [], r.status_code
    return (rows[1:] if len(rows) > 1 else []), r.status_code


def fetch(stamp, page):
    u = "%s/web/%sid_/https://vsfan.net/wiki/%s" % (BASE, stamp, page)
    r = get(u)
    body = r.content
    off = ("Temporarily Offline" in body[:4000].decode("utf-8", "replace")
           or "not archived" in body[:4000].decode("utf-8", "replace"))
    return r.status_code, len(body), off, body


TARGETS = [
    "vsfan.net/wiki/Hunter_Supply_Office",
    "vsfan.net/wiki/Hunter_Supply_Station",
    "vsfan.net/wiki/Veteran_Status",
    "vsfan.net/wiki/List_of_Blustone_Items",
]

if __name__ == "__main__":
    if not positive_control():
        print("ABORT: instrument fault, not a content negative.")
        sys.exit(2)
    for t in TARGETS:
        rows, code = cdx(t)
        print("\n=== %s  (cdx code %s, rows %d)" % (t, code, len(rows)), flush=True)
        for r in rows:
            print("    %s  %s  %s  len=%s  %s" % (r[1], r[2], r[3], r[4], r[6]), flush=True)
        time.sleep(1.0)