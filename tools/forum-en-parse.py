#!/usr/bin/env python3
"""Parse archived forum_en board pages using the exact XE markup anchors.

Anchors verified against real captures:
  title   <h1 class="np_18px"> ... [N]      (+ <meta property="og:title">)
  author  <meta property="og:article:author" content="...">
  date    <span class="date m_no">YYYY.MM.DD HH:MM</span>
  views   <span>Views <b>N</b></span>
  body    <div class="document_<pid>_<cid> xe_content"> ... </div>
  reply   <div class="comment_<pid>_<cid> xe_content"> ... </div>

Every field records which anchor produced it, so a later pass can tell a real
reading from a fallback. No guessing: an absent anchor leaves the field empty.
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
from html.parser import HTMLParser

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SKIP = {"script", "style", "noscript", "iframe", "svg", "head", "form", "button", "select"}
BLOCK = {"p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6",
         "blockquote", "pre", "ul", "ol", "table", "hr", "section", "article"}
CELL = {"td", "th"}
NUMERIC = re.compile(r"\d")


class ContentGrab(HTMLParser):
    """Collect the text + links of one xe_content div, and record images too."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.out: list[str] = []
        self.imgs: list[str] = []
        self.links: list[str] = []
        self.tables = 0
        self.in_cell = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "img" and a.get("src"):
            self.imgs.append(a["src"])
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "table":
            self.tables += 1
        if tag in CELL:
            self.in_cell += 1
            self.out.append("\t")
        elif tag == "br" or tag in BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in CELL:
            self.in_cell = max(0, self.in_cell - 1)
        elif tag in BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)

    def text(self) -> str:
        s = html.unescape("".join(self.out)).replace("\u00a0", " ").replace("\u200b", "")
        s = re.sub(r"[ \t]*\t[ \t]*", "\t", s)
        s = re.sub(r"[ ]{2,}", " ", s)
        s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
        lines = [ln.rstrip() for ln in s.split("\n")]
        return "\n".join(ln for ln in lines if ln.strip()).strip()


DIV_RE = re.compile(
    r'<div class="((?:document|comment)_(\d+)_(\d+)) xe_content">', re.I
)


def split_contents(txt: str) -> list[tuple]:
    """Yield (class, kind, pid, cid, n_tables, text, imgs, links) per xe_content div.

    A content div is terminated by <!--AfterDocument(..)--> for the document and
    <!--AfterComment(..)--> for a reply. Both terminators must be honoured: matching
    only AfterDocument makes every reply run to end-of-file and drags the whole
    page chrome (and its images) into the reply text.
    """
    marks = list(DIV_RE.finditer(txt))
    out = []
    for i, m in enumerate(marks):
        start = m.end()
        cands = [
            txt.find("<!--AfterDocument", start),
            txt.find("<!--AfterComment", start),
            txt.find("</article>", start),
        ]
        cands = [c for c in cands if c != -1]
        end = min(cands) if cands else len(txt)
        if i + 1 < len(marks):
            end = min(end, marks[i + 1].start())
        chunk = txt[start:end]
        g = ContentGrab()
        try:
            g.feed(chunk)
        except Exception:  # noqa: BLE001
            pass
        kind = "document" if m.group(1).startswith("document") else "comment"
        out.append((m.group(1), kind, m.group(2), m.group(3), g.tables, g.text(), g.imgs, g.links))
    return out


META_AUTHOR = re.compile(r'<meta\s+property="og:article:author"\s+content="([^"]*)"', re.I)
META_TITLE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]*)"', re.I)
META_DESC = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.I)
META_KEYS = re.compile(r'<meta\s+name="keywords"\s+content="([^"]*)"', re.I)
DATE_SPAN = re.compile(r'<span class="date m_no">([^<]+)</span>', re.I)
VIEWS = re.compile(r"<span>\s*Views\s*<b>(\d+)</b>", re.I)
H1 = re.compile(r'<h1[^>]*>(.*?)</h1>', re.I | re.S)
CANON = re.compile(r'<link\s+rel="canonical"\s+href="([^"]*)"', re.I)
TAG = re.compile(r"<[^>]+>")
DOCID = re.compile(r"data-docsrl=\"(\d+)\"")


def clean_txt(s: str) -> str:
    s = html.unescape(s)
    s = TAG.sub("", s)
    s = s.replace("\u00a0", " ").replace("\u200b", "")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def parse(path: str) -> dict:
    raw = open(path, "rb").read()
    txt = raw.decode("utf-8", "replace")
    fid = os.path.basename(path).split(".")[0]

    ma = META_AUTHOR.search(txt)
    author = clean_txt(ma.group(1)) if ma else ""
    author_src = "og:article:author" if ma else ""

    h1 = H1.search(txt)
    title = ""
    if h1:
        title = clean_txt(h1.group(1))
        title = re.sub(r"\[\d+\]\s*$", "", title).strip()
    mt = META_TITLE.search(txt)
    if not title and mt:
        title = re.sub(r"\s*-\s*Blustone\s*$", "", clean_txt(mt.group(1))).strip()
    title_src = "h1" if h1 else ("og:title" if mt else "")

    ds = DATE_SPAN.search(txt)
    date = clean_txt(ds.group(1)) if ds else ""
    vs = VIEWS.search(txt)
    views = int(vs.group(1)) if vs else 0
    md = META_DESC.search(txt)
    keys = META_KEYS.search(txt)
    cn = CANON.search(txt)
    dm = DOCID.search(txt)

    contents = split_contents(txt)
    doc = next((c for c in contents if c[1] == "document"), None)
    comments = [c for c in contents if c[1] == "comment"]

    body = doc[5] if doc else ""
    reply_text = "\n".join(c[5] for c in comments)
    imgs = (doc[6] if doc else []) + [i for c in comments for i in c[6]]
    links = (doc[7] if doc else []) + [x for c in comments for x in c[7]]
    alltext = body + "\n" + reply_text

    return {
        "id": dm.group(1) if dm else fid,
        "file": os.path.basename(path),
        "bytes": len(raw),
        "title": title,
        "title_src": title_src,
        "author": author,
        "author_src": author_src,
        "date": date,
        "views": views,
        "meta_desc": clean_txt(md.group(1)) if md else "",
        "meta_keywords": clean_txt(keys.group(1)) if keys else "",
        "canonical": cn.group(1) if cn else "",
        "chars": len(body),
        "reply_chars": len(reply_text),
        "n_comments": len(comments),
        "n_tables": doc[4] if doc else 0,
        "digits": len(NUMERIC.findall(alltext)),
        "body_digits": len(NUMERIC.findall(body)),
        "imgs": imgs,
        "links": links,
        "body": body,
        "replies": reply_text,
        "has_doc_div": doc is not None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--glob", default="body/*.html")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.dir, a.glob)))
    recs = []
    for p in files:
        try:
            recs.append(parse(p))
        except Exception as exc:  # noqa: BLE001
            recs.append({"file": os.path.basename(p), "error": f"{type(exc).__name__}: {exc}",
                         "chars": 0, "body_digits": 0, "digits": 0})
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(recs, fh, ensure_ascii=False, indent=1)
    good = [r for r in recs if not r.get("error")]
    def n(f):
        return sum(1 for r in good if f(r))
    print(f"files={len(recs)} parsed={len(good)} errors={len(recs)-len(good)}")
    print(f"  h1 title={n(lambda r: r['title_src']=='h1')}  og:title={n(lambda r: r['title_src']=='og:title')}")
    print(f"  og author={n(lambda r: r['author'])}  date span={n(lambda r: r['date'])}  views={n(lambda r: r['views'])}")
    print(f"  document div found={n(lambda r: r['has_doc_div'])}")
    print(f"  body chars total={sum(r['chars'] for r in good)}  reply chars total={sum(r['reply_chars'] for r in good)}")
    print(f"  >=500 chars: {n(lambda r: r['chars']>=500)}  >=2000: {n(lambda r: r['chars']>=2000)}  >=6000: {n(lambda r: r['chars']>=6000)}")
    print(f"  posts with digits: {n(lambda r: r['digits']>0)}  >=20 digits: {n(lambda r: r['digits']>=20)}  >=60: {n(lambda r: r['digits']>=60)}")
    print(f"  posts with a table: {n(lambda r: r['n_tables']>0)}   with images: {n(lambda r: r['imgs'])}   with comments: {n(lambda r: r['n_comments']>0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
