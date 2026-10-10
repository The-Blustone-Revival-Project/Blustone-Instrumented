#!/usr/bin/env python3
"""Parse forum_en board LIST pages into a whole-board metadata table.

One list page carries title + author + date + read count for every post it shows,
so 543 captures are a far cheaper route to whole-board coverage than 1,811 body
fetches. Anchors are the XE board list markup; each field records its source and
anything unparsed is left empty rather than guessed.
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from html.parser import HTMLParser

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TAG = re.compile(r"<[^>]+>")
DSRL = re.compile(r"document_srl=(\d+)")
TITLE_TAG = re.compile(r'<a href="[^"]*document_srl=(\d+)[^"]*"[^>]*title="([^"]*)"', re.I)
TITLE_TAG2 = re.compile(r'<a href="[^"]*document_srl=(\d+)[^"]*"[^>]*>\s*([^<]{2,200}?)\s*</a>', re.I)
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
CELL = re.compile(r"<t[dh][^>]*class=\"([^\"]*)\"[^>]*>(.*?)</t[dh]>", re.I | re.S)
DATE = re.compile(r"(\d{4}\.\d{2}\.\d{2})")
READ = re.compile(r"^\s*([\d,]+)\s*$")


def clean(s: str) -> str:
    s = TAG.sub(" ", s)
    s = s.replace("\u00a0", " ").replace("\u200b", "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_list(path: str) -> list[dict]:
    txt = open(path, "rb").read().decode("utf-8", "replace")
    out: dict[int, dict] = {}
    for rm in ROW.finditer(txt):
        row = rm.group(1)
        cells = CELL.findall(row)
        if len(cells) < 3:
            continue
        cellmap = {}
        for cls, inner in cells:
            key = cls.split()[0] if cls else "?"
            cellmap.setdefault(key, []).append(inner)
        blob = " ".join(inner for _, inner in cells)
        mid = DSRL.search(blob)
        if not mid:
            continue
        pid = int(mid.group(1))
        title = ""
        m = TITLE_TAG.search(blob)
        if m and int(m.group(1)) == pid:
            title = clean(m.group(2))
        if not title:
            for mm in TITLE_TAG2.finditer(blob):
                if int(mm.group(1)) == pid:
                    title = clean(mm.group(2))
                    break
        replies = ""
        rc = re.search(r"\[(\d+)\]", blob)
        if rc:
            replies = rc.group(1)
        author = ""
        for key in ("author", "nickname", "name"):
            if key in cellmap:
                a = clean(cellmap[key][0])
                a = re.sub(r"\s*Lv\.\s*\d+.*$", "", a).strip()
                if a and a.lower() != "author":
                    author = a
                    break
        date = ""
        for key in ("time", "date", "regdate"):
            if key in cellmap:
                d = DATE.search(clean(cellmap[key][0]))
                if d:
                    date = d.group(1).replace(".", "-")
                    break
        reads = 0
        for key in ("readed_count", "read_count", "reads"):
            if key in cellmap:
                rr = READ.match(clean(cellmap[key][0]))
                if rr:
                    reads = int(rr.group(1).replace(",", ""))
                    break
        prev = out.get(pid)
        rec = {"id": pid, "title": title, "author": author, "date": date,
               "reads": reads, "replies": replies, "src": os.path.basename(path)}
        if prev:
            rec["title"] = prev["title"] or title
            rec["author"] = prev["author"] or author
            rec["date"] = prev["date"] or date
            rec["reads"] = max(prev["reads"], reads)
        out[pid] = rec
    return list(out.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.dir, "list", "*.html")))
    merged: dict[int, dict] = {}
    pages = 0
    for p in files:
        pages += 1
        try:
            for r in parse_list(p):
                cur = merged.get(r["id"])
                if not cur:
                    merged[r["id"]] = dict(r, seen_in=1)
                else:
                    cur["seen_in"] += 1
                    for k in ("title", "author", "date"):
                        if not cur[k] and r[k]:
                            cur[k] = r[k]
                    cur["reads"] = max(cur["reads"], r["reads"])
                    if r["replies"]:
                        cur["replies"] = r["replies"]
        except Exception as exc:  # noqa: BLE001
            print(f"  parse error {os.path.basename(p)}: {type(exc).__name__}: {exc}")
    rows = sorted(merged.values(), key=lambda r: r["id"])
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    with open(a.out.replace(".json", ".tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("id\ttitle\tauthor\tdate\treads\treplies\tseen_in\n")
        for r in rows:
            fh.write(f"{r['id']}\t{r['title']}\t{r['author']}\t{r['date']}\t{r['reads']}\t{r['replies']}\t{r['seen_in']}\n")
    print(f"list pages parsed: {pages}")
    print(f"distinct posts seen: {len(rows)}")
    print(f"  with title:  {sum(1 for r in rows if r['title'])}")
    print(f"  with author: {sum(1 for r in rows if r['author'])}")
    print(f"  with date:   {sum(1 for r in rows if r['date'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
