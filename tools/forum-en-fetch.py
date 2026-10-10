#!/usr/bin/env python3
"""forum_en lane fetch harness.

GET-only reads of web.archive.org. Python only (GUARD-encoding-and-archive-traps.md).

Discipline:
  * every attempt's HTTP status is recorded; curl-style transport failure is
    reported as '000' and is NEVER a result
  * a positive control runs first and ABORTS the batch if it fails
  * retries grow a backoff; archive is heavily rate-limited
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research-fetch/1.0"
CONTROL = (
    "http://web.archive.org/web/2021/"
    "https://bs.visualshower.com/files/attach/images/75605/303/534/001/"
    "725a8e175454a533e96dac68fc5fdb49.jpg"
)
LEDGER = "_ledger.tsv"


def sig8(b: bytes) -> str:
    return b[:8].hex()


def is_image(b: bytes) -> str:
    """Return a non-empty signature name if b starts with a known image magic."""
    if b[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if b[:2] == b"BM":
        return "bmp"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp"
    return ""


def http_status(exc: Exception) -> str:
    """Map a requests exception onto a status token. Transport failures = '000'."""
    if isinstance(exc, requests.exceptions.HTTPError):
        r = exc.response
        return str(r.status_code) if r is not None else "000"
    return "000"


def fetch(url: str, out_path: str | None, tries: int, sleep_base: float) -> dict:
    """One target, retried until a real HTTP status (or tries exhausted)."""
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    rec = {
        "url": url,
        "out": out_path or "-",
        "tries": 0,
        "status": "000",
        "bytes": 0,
        "sig8": "",
        "image": "",
        "note": "",
    }
    body = b""
    for i in range(1, tries + 1):
        rec["tries"] = i
        try:
            r = sess.get(url, timeout=90, allow_redirects=True)
            rec["status"] = str(r.status_code)
            body = r.content or b""
            if r.status_code == 200 and not body:
                rec["status"] = "200"
                rec["note"] = "200-empty"
                body = b""
        except Exception as exc:  # noqa: BLE001 - transport failure is '000'
            rec["status"] = http_status(exc)
            rec["note"] = type(exc).__name__
            body = b""
        if rec["status"] != "000":
            break
        time.sleep(sleep_base * i + random.uniform(0, 1.5))
    rec["bytes"] = len(body)
    if body:
        rec["sig8"] = sig8(body)
        rec["image"] = is_image(body)
        if out_path:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as fh:
                fh.write(body)
            rec["sha256"] = hashlib.sha256(body).hexdigest()
    return rec


class Ledger:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.fh = open(path, "a", encoding="utf-8", newline="\n")
        if self.fh.tell() == 0:
            self.fh.write("url\tout\ttries\tstatus\tbytes\tsig8\timage\tnote\n")

    def add(self, rec: dict) -> None:
        self.fh.write(
            "\t".join(
                str(rec.get(k, ""))
                for k in ("url", "out", "tries", "status", "bytes", "sig8", "image", "note")
            )
            + "\n"
        )
        self.fh.flush()

    def close(self) -> None:
        self.fh.close()


def run_control(out_dir: str, tries: int, sleep_base: float) -> dict:
    """Hard gate. Returns the record; caller decides PASS/FAIL."""
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, "_control.jpg")
    rec = fetch(CONTROL, dest, tries, sleep_base)
    rec["control"] = True
    ok = rec["status"] == "200" and rec["image"] == "jpeg" and rec["bytes"] > 1000
    rec["verdict"] = "PASS" if ok else "FAIL"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True, help="TSV: outfile<TAB>url")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--tries", type=int, default=8)
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    out_dir = os.path.abspath(args.outdir)
    ledger = Ledger(os.path.join(out_dir, LEDGER))

    print("=== POSITIVE CONTROL (75605/303/534/001) ===", flush=True)
    c = run_control(out_dir, args.tries, args.sleep)
    ledger.add(c)
    print(
        f"control: code={c['status']} bytes={c['bytes']} sig={c['sig8']} "
        f"image={c['image'] or '-'} tries={c['tries']} -> {c['verdict']}",
        flush=True,
    )
    if c["verdict"] != "PASS":
        print(
            "CONTROL FAILED - zeros would be uninterpretable. ABORT.",
            file=sys.stderr,
            flush=True,
        )
        ledger.close()
        return 2

    with open(args.queue, "r", encoding="utf-8") as fh:
        rows = [ln.rstrip("\n").split("\t") for ln in fh if ln.strip()]
    if args.limit:
        rows = rows[: args.limit]

    print(f"=== BATCH: {len(rows)} targets ===", flush=True)
    n200 = 0
    tally: dict[str, int] = {}
    for i, row in enumerate(rows, 1):
        name, url = row[0], row[1]
        dest = os.path.join(out_dir, name)
        rec = fetch(url, dest, args.tries, args.sleep)
        ledger.add(rec)
        tally[rec["status"]] = tally.get(rec["status"], 0) + 1
        if rec["status"] == "200":
            n200 += 1
        if i % 10 == 0 or rec["status"] != "200":
            print(
                f"[{i}/{len(rows)}] {name} status={rec['status']} "
                f"bytes={rec['bytes']} sig={rec['sig8']} tries={rec['tries']}",
                flush=True,
            )
        time.sleep(args.sleep + random.uniform(0, 1.0))
    print(f"=== DONE http200={n200}/{len(rows)} tally={json.dumps(tally)} ===", flush=True)
    ledger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
