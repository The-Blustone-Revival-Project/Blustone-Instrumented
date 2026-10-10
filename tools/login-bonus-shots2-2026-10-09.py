#!/usr/bin/env python3
"""Exact-URL CDX for the three attendance screenshots.

CDX shape control: the 75605 image MUST return a row before any zero here
is believable (prefix queries 503 on this host - see login-bonus-cdx-shape).
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
ORIGIN = "https://bs.visualshower.com/files/attach/images/"

CONTROL_IMG = ORIGIN + "75605/303/534/001/725a8e175454a533e96dac68fc5fdb49.jpg"
CONTROL_URL = BASE + "/web/2021/" + CONTROL_IMG

SHOTS = [
    ("675557-rainbow-day28", "175/557/675/d66d49c862438f780e432d293601fc31.png"),
    ("691643-a", "175/643/691/9d95e10885834d81fe4442403ddc4fcb.png"),
    ("691643-b", "175/643/691/f03b66381ba71f60433a315e57ec4f53.png"),
    ("1167975-attendance-chart", "175/975/167/001/a7675b6ffb26b9e418218701fd59c153.png"),
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


def cdx_exact(u):
    r = get(CDX, params={"url": u, "output": "json", "limit": "200"})
    txt = r.text.strip()
    if not txt or "Temporarily Offline" in txt[:2000]:
        return []
    try:
        rows = json.loads(txt)
    except Exception:
        return []
    return rows[1:]


def pixels(path):
    try:
        from PIL import Image
        im = Image.open(path)
        im.load()
        return "%sx%s %s" % (im.size[0], im.size[1], im.mode)
    except Exception as e:
        return "no-decode(%s)" % str(e)[:60]


if __name__ == "__main__":
    # control 1: bytes
    r = get(CONTROL_URL)
    sig = r.content[:4].hex()
    ok1 = r.status_code == 200 and len(r.content) == 57414 and sig.startswith("ffd8ffe1")
    # control 2: the CDX shape
    ctl_rows = cdx_exact(CONTROL_IMG)
    ok2 = len(ctl_rows) >= 1
    print("CONTROL bytes : code=%s size=%s sig=%s -> %s"
          % (r.status_code, len(r.content), sig, "PASS" if ok1 else "FAIL"))
    print("CONTROL cdx   : rows=%d -> %s" % (len(ctl_rows), "PASS" if ok2 else "FAIL"))
    if not (ok1 and ok2):
        print("ABORT: instrument fault; zeros below would be meaningless.")
        sys.exit(2)

    os.makedirs(OUT, exist_ok=True)
    for tag, path in SHOTS:
        u = ORIGIN + path
        rows = cdx_exact(u)
        print("\n### %s\n    %s\n    cdx rows=%d" % (tag, u, len(rows)))
        for row in rows:
            print("      ts=%s status=%s mime=%s len=%s" % (row[1], row[4], row[3], row[6] if len(row) > 6 else "?"))
            for stamp in ([row[1]]):
                fu = "%s/web/%sid_/%s" % (BASE, stamp, u)
                fr = get(fu)
                body = fr.content
                head = body[:300].decode("utf-8", "replace").lower()
                bad = ("temporarily offline" in head or "not archived" in head)
                print("      fetch %s -> code=%s bytes=%d sha=%s bad=%s"
                      % (stamp, fr.status_code, len(body),
                         hashlib.sha256(body).hexdigest()[:20], bad))
                if fr.status_code == 200 and not bad and len(body) > 2000 and body[:8] != b"<":
                    fn = os.path.join(OUT, "attendance__%s__%s.png" % (tag, stamp))
                    open(fn, "wb").write(body)
                    print("      SAVED %s pixels=%s" % (fn, pixels(fn)))
                else:
                    print("      -> no usable image body; NOT evidence")
                sys.stdout.flush()
                time.sleep(1.0)
        time.sleep(1.0)