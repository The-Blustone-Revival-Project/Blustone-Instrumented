#!/usr/bin/env python3
"""Parse pass-2 forum_en board LIST captures into a whole-board metadata table.

Distinct from tools/forum-en-parse-lists.py (pass 1), which recovered 0 titles
because its TITLE_TAG2 anchor `<a ...>text</a>` cannot match a title cell whose
link body is wrapped in `<strong><span>`. Verified row markup in a real capture
(`pass2/get-list/list/rc002.html`):

    <tr class="notice">
      <td class="no">…</td>
      <td class="title">
        <a href="…&document_srl=1188138"><strong><span …>TITLE</span></strong></a>
        &nbsp;<span>[0]</span><span class="extraimages"><img …></span>
      </td>
      <td><a href="…#1188138_comment" title="Reply">0</a></td>
      <td class="author"><span><a …>Natara</a></span></td>
      <td class="time">2019.07.25</td>
      <td class="m_no">447</td>
    </tr>

Every field records its anchor and an absent anchor leaves the field EMPTY
rather than guessing. Pure local pass, no network.
"""

from __future__ import annotations

import argparse
import glob
import html
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# NOTE ON THE ATTRIBUTE PATTERNS. XE writes template conditions straight into
# attributes, e.g. `<span cond="!$document->isSecret()" class="wrp">`, so a `>`
# character can appear INSIDE a quoted attribute value. Any `[^>]*` attribute run
# therefore truncates early. ATTR below matches a quoted-aware attribute run and
# is used everywhere an attribute list is consumed.
ATTR = r'(?:[^<>"\']|"[^"]*"|\'[^\']*\')*'
TR = re.compile(rf"<tr\b({ATTR})>(.*?)</tr>", re.S | re.I)
TD = re.compile(rf'<td\b({ATTR})class="([^"]*)"({ATTR})>(.*?)</td>', re.S | re.I)
DSRL = re.compile(r"document_srl=(\d+)")
TITLE_LINK = re.compile(rf'<a\b({ATTR})>(.*?)</a>', re.S | re.I)
BRACKET = re.compile(r"\[(\d+)\]")
REPLY_A = re.compile(r'title="Reply"\s*>\s*([\d,]+)\s*<', re.I)
DATE = re.compile(r"(\d{4})[.\-/](\d{2})[.\-/](\d{2})")
TIME = re.compile(r"(\d{2}:\d{2})")
TAG = re.compile(r"""<(?:[^<>"']|"[^"]*"|'[^']*')+>""")
EXTRA = re.compile(r'<span class="extraimages">.*?</span>', re.S | re.I)
SECRET = re.compile(r'cond="[^"]*isSecret\(\)[^"]*"')


def text_of(frag: str) -> str:
    s = EXTRA.sub(" ", frag)
    s = TAG.sub(" ", s)
    s = html.unescape(s)
    s = s.replace("\u00a0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", s).strip()


def parse_page(path: str) -> list[dict]:
    txt = open(path, "rb").read().decode("utf-8", "replace")
    out: dict[int, dict] = {}
    for rm in TR.finditer(txt):
        cells = TD.findall(rm.group(2))
        if len(cells) < 4:
            continue
        cell = {}
        for _a1, cls, _a2, inner in cells:
            cell.setdefault(cls.split()[0] if cls else "?", []).append(inner)
        blob = " ".join(i for _, _, _, i in cells)
        dm = DSRL.search(blob)
        if not dm:
            continue
        pid = dm.group(1)

        title = ""
        secret = False
        for inner in cell.get("title", []):
            for m in TITLE_LINK.finditer(inner):
                # document_srl lives INSIDE the quoted href value, so it is read
                # out of the attribute blob rather than matched as a bare token
                # after it.
                dm2 = DSRL.search(m.group(1))
                if dm2 and dm2.group(1) == pid:
                    title = text_of(m.group(2))
                    secret = bool(SECRET.search(m.group(2)))
                    break
            if title:
                break
        title = BRACKET.sub("", title).strip()

        replies = ""
        for inner in cell.get("title", []):
            rm2 = REPLY_A.search(inner)
            if rm2:
                replies = rm2.group(1).replace(",", "")
                break
        if not replies:
            bm = BRACKET.search(text_of(" ".join(cell.get("title", []))))
            if bm:
                replies = bm.group(1)

        author = ""
        if "author" in cell:
            a = text_of(cell["author"][0])
            a = re.sub(r"\s*Lv\.\s*\d+.*$", "", a).strip()
            if a and a.lower() not in ("author", "level"):
                author = a

        date = time_s = ""
        if "time" in cell:
            tt = text_of(cell["time"][0])
            dm2 = DATE.search(tt)
            if dm2:
                date = "-".join(dm2.groups())
            tm = TIME.search(tt)
            if tm:
                time_s = tm.group(1)

        views = 0
        for key in ("m_no", "readed_count", "read_count"):
            if key in cell:
                v = text_of(cell[key][0]).replace(",", "")
                if v.isdigit():
                    views = int(v)
                    break

        sticky = "sticky" in rm.group(0)[:200].lower()
        rec = {
            "id": pid,
            "title": title,
            "replies": replies,
            "author": author,
            "date": date,
            "time": time_s,
            "views": views,
            "sticky": sticky,
            "secret_mark": secret,
            "src": os.path.basename(path),
        }
        prev = out.get(pid)
        if prev:
            rec["title"] = prev["title"] or title
            rec["author"] = prev["author"] or author
            rec["date"] = prev["date"] or date
            rec["time"] = prev["time"] or time_s
            rec["views"] = max(prev["views"], views)
            if prev["replies"] and prev["replies"] != rec["replies"]:
                rec["replies_note"] = f"{prev['replies']}~{rec['replies']}"
            else:
                rec["replies"] = prev["replies"] or rec["replies"]
        out[pid] = rec
    return list(out.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--glob", default="list/*.html")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.dir, a.glob)))
    merged: dict[str, dict] = {}
    used = 0
    for p in files:
        try:
            got = parse_page(p)
        except Exception as exc:  # noqa: BLE001
            print(f"  parse error {os.path.basename(p)}: {type(exc).__name__}: {exc}")
            continue
        if got:
            used += 1
        for r in got:
            cur = merged.get(r["id"])
            if not cur:
                merged[r["id"]] = dict(r, seen_in=1, pages=[r["src"]])
            else:
                cur["seen_in"] += 1
                cur["pages"].append(r["src"])
                for k in ("title", "author", "date", "time"):
                    if not cur[k] and r[k]:
                        cur[k] = r[k]
                cur["views"] = max(cur["views"], r["views"])
                if r["replies"] and (not cur["replies"] or int(r["replies"]) > int(cur["replies"])):
                    cur["replies"] = r["replies"]
    rows = sorted(merged.values(), key=lambda r: int(r["id"]))
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    with open(a.out.replace(".json", ".tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("id\ttitle\treplies\tviews\tauthor\tdate\tseen_in\tsticky\tsecret\n")
        for r in rows:
            fh.write(
                f"{r['id']}\t{r['title']}\t{r['replies']}\t{r['views']}\t{r['author']}\t"
                f"{r['date']}\t{r['seen_in']}\t{int(bool(r['sticky']))}\t"
                f"{int(bool(r.get('secret_mark')))}\n"
            )
    print(f"list captures parsed: {used}/{len(files)}")
    print(f"distinct posts seen: {len(rows)}")
    print(f"  with title:  {sum(1 for r in rows if r['title'])}")
    print(f"  with replies:{sum(1 for r in rows if r['replies'] != '')}")
    print(f"  with author: {sum(1 for r in rows if r['author'])}")
    print(f"  with date:   {sum(1 for r in rows if r['date'])}")
    print(f"  with views:  {sum(1 for r in rows if r['views'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())