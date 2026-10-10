#!/usr/bin/env python3
"""Try to recover the three attendance-popup screenshots from the Wayback Machine.

These are [FIRSTPARTY] frames of the actual attendance board:
  doc 675557  "It still says I am on day 28"      (rainbow-scroll glitch)
  doc 691643  day-7 rainbow scroll, two images
  doc 1167975 "New attendance counter good"       (the attendance chart)

GUARD: http:// only, ONE session, positive control first, hash + magic-byte
check every body, and a rewritten URL is not evidence (guard: archive rewrites
img src to im_ even when the image was never captured -> decode pixels).
"""
import hashlib
import os
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

S = requests.Session()
S.headers.update({"User-Agent": "blustone-login-bonus-research/1.0 (read-only)"})

BASE = "http://web.archive.org"
OUT = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\login-bonus-2026-10-09"

CONTROL = (BASE + "/web/2021/https://bs.visualshower.com/files/attach/images/75605/"
           "303/534/001/725a8e175454a533e96dac68fc5fdb49.jpg")

# (doc, archive stamp already present in the forum HTML, path after the host)
SHOTS = [
    ("675557", "20200814022512", "175/557/675/d66d49c862438f780e432d293601fc31.png"),
    ("691643", "20210123115038", "175/643/691/9d95e10885834d81fe4442403ddc4fcb.png"),
    ("691643", "20210123115038", "175/643/691/f03b66381ba71f60433a315e57ec4f53.png"),
    ("1167975", "20191019100127", "175/975/167/001/a7675b6ffb26b9e418218701fd59c153.png"),
]

ORIGIN = "https://bs.visualshower.com/files/attach/images/"


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


def decode_pixels(path):
    """Guard: a 200 is not pixels. Decode and report real dimensions."""
    try:
        from PIL import Image
        im = Image.open(path)
        im.load()
        return im.size, im.mode
    except Exception as e:
        return None, str(e)[:80]


if __name__ == "__main__":
    if not positive_control():
        print("ABORT: instrument fault.")
        sys.exit(2)
    os.makedirs(OUT, exist_ok=True)
    for doc, stamp, path in SHOTS:
        url = "%s/web/%sim_/%s%s" % (BASE, stamp, ORIGIN, path)
        r = get(url)
        body = r.content
        head = body[:300].decode("utf-8", "replace").lower()
        bad = ("temporarily offline" in head or "not archived" in head
               or body[:8].startswith(b"<"))
        print("\n### doc %s  %s" % (doc, path))
        print("    url   %s" % url)
        print("    code=%s bytes=%d sha256=%s sig=%s suspect=%s"
              % (r.status_code, len(body), hashlib.sha256(body).hexdigest()[:24],
                 body[:4].hex(), bad))
        if r.status_code == 200 and not bad and len(body) > 2000:
            fn = os.path.join(OUT, "attendance_%s_%s" % (doc, os.path.basename(path)))
            open(fn, "wb").write(body)
            size, mode = decode_pixels(fn)
            print("    SAVED %s  pixels=%s mode=%s" % (fn, size, mode))
        else:
            print("    NOT a usable image body -> not evidence")
        sys.stdout.flush()
        time.sleep(1.2)