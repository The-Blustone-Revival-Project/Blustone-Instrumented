#!/usr/bin/env python3
"""Find a CDX query shape that WORKS, using a known-good target, before
believing any zero about the attendance screenshots.

Known-good control target (documented in this workspace):
  https://bs.visualshower.com/files/attach/images/75605/303/534/001/725a8e175454a533e96dac68fc5fdb49.jpg
  -> HTTP 200, 57414 B, ffd8ffe1

GUARD: http:// only, ONE session.
"""
import json
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

S = requests.Session()
S.headers.update({"User-Agent": "blustone-login-bonus-research/1.0 (read-only)"})

CDX = "http://web.archive.org/cdx/search/cdx"

IMG = ("https://bs.visualshower.com/files/attach/images/75605/303/534/001/"
       "725a8e175454a533e96dac68fc5fdb49.jpg")

SHAPES = [
    ("exact full-https", {"url": IMG}),
    ("exact no-scheme", {"url": IMG.split("://", 1)[1]}),
    ("prefix folder", {"url": IMG.rsplit("/", 1)[0] + "/"}),
    ("matchType prefix", {"url": IMG, "matchType": "prefix"}),
    ("host prefix", {"url": "bs.visualshower.com/files/attach/images/75605"}),
    ("collapse-free prefix", {"url": IMG.rsplit("/", 1)[0] + "/", "collapse": ""}),
]


def get(params, tries=3):
    last = None
    for i in range(tries):
        try:
            return S.get(CDX, params=params, timeout=60)
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


for name, p in SHAPES:
    p = dict(p)
    p["output"] = "json"
    p.setdefault("limit", "50")
    try:
        r = get(p)
        txt = r.text.strip()
        n = 0
        if txt and "Temporarily Offline" not in txt[:2000]:
            try:
                rows = json.loads(txt)
                n = max(0, len(rows) - 1)
            except Exception:
                n = -2
        print("%-24s code=%s bytes=%-6d rows=%-4d  %s"
              % (name, r.status_code, len(r.content), n, txt[:150].replace("\n", " ")))
    except Exception as e:
        print("%-24s EXC %s" % (name, e))
    sys.stdout.flush()
    time.sleep(1.0)