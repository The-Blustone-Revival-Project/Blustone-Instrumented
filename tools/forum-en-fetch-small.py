#!/usr/bin/env python3
"""Fetch a small explicit list of URLs and save them. Short timeout, few retries.

For targeted one-off acquisition (e.g. a specific post id) rather than bulk
crawling. Always runs the positive control first and refuses to proceed without
decodable pixels.
"""
import io
import os
import random
import sys
import time

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CONTROL = ("http://web.archive.org/web/2021/https://bs.visualshower.com/files/attach/images/"
           "75605/303/534/001/725a8e175454a533e96dac68fc5fdb49.jpg")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) blustone-research/1.0"


def is_jpeg(b):
    return b[:3] == b"\xff\xd8\xff"


def control(outdir):
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    for i in range(1, 7):
        try:
            r = s.get(CONTROL, timeout=45)
            if r.status_code == 200 and is_jpeg(r.content) and len(r.content) > 1000:
                with open(os.path.join(outdir, "_control.jpg"), "wb") as fh:
                    fh.write(r.content)
                print(f"control: 200 {len(r.content)}B jpeg tries={i} -> PASS", flush=True)
                return True
        except Exception:
            pass
        time.sleep(4 * i + random.uniform(1, 3))
    print("control FAILED -> ABORT", file=sys.stderr, flush=True)
    return False


def main():
    queue, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    if not control(outdir):
        return 2
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    n = 0
    with open(queue, encoding="utf-8") as fh:
        for ln in fh:
            if not ln.strip():
                continue
            name, url = ln.rstrip("\n").split("\t")[:2]
            dest = os.path.join(outdir, name)
            if os.path.exists(dest) and os.path.getsize(dest) > 2000:
                print(f"skip {name} (on disk)", flush=True)
                continue
            for i in range(1, 5):
                try:
                    r = s.get(url, timeout=45)
                    b = r.content or b""
                    if r.status_code == 200 and len(b) > 2000:
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with open(dest, "wb") as f:
                            f.write(b)
                        print(f"{name}: 200 {len(b)}B tries={i} sig={b[:8].hex()}", flush=True)
                        break
                    print(f"{name}: status={r.status_code} bytes={len(b)} tries={i}", flush=True)
                    if r.status_code == 404:
                        break
                except Exception as exc:  # noqa: BLE001
                    print(f"{name}: 000 ({type(exc).__name__}) tries={i}", flush=True)
                time.sleep(3 * i + random.uniform(1, 3))
            time.sleep(1.5)
            n += 1
    print(f"done {n} targets", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
