#!/usr/bin/env python3
"""Parse the vsfan Hunter_Supply_Office attendance tables out of raw HTML.

Read-only. Writes a UTF-8 JSON dump next to the output note.
"""
import html
import json
import os
import re
import sys

SRC = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\vsfan-reward-2026-10-09\Hunter_Supply_Office.html"


def cells(row_html):
    """Return the cell inner-HTML list of a <tr>."""
    return re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)


def strip(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def item_name(cell_html):
    """Item identity from the linked image alt, or the /wiki/File: link."""
    m = re.search(r'alt="([^"]+?)"', cell_html)
    if m:
        return m.group(1)
    m = re.search(r"/wiki/File:([^#]+)", cell_html)
    if m:
        return m.group(1)
    m = re.search(r'title="([^"#]+)#', cell_html)
    if m:
        return m.group(1)
    return None


def parse_table(t, start_marker):
    i = t.find(start_marker)
    if i < 0:
        return None
    j = t.find("</table>", i)
    seg = t[i:j]
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", seg, re.S)
    out = []
    for r in rows:
        cs = cells(r)
        out.append([{"text": strip(c), "item": item_name(c)} for c in cs])
    return out


def main():
    t = open(SRC, "rb").read().decode("utf-8")
    result = {
        "source_file": SRC,
        "sha_note": "raw archived HTML, decoded strictly as utf-8",
        "daily_rewards": parse_table(t, 'id="Daily_Rewards"'),
        "cumulative": parse_table(t, 'id="Cumulative_Attendence_Dates"'),
    }
    # the veteran sentence
    m = re.search(r"Claim your Daily reward.{0,200}", t, re.S)
    result["veteran_sentence"] = strip(m.group(0)) if m else None
    # revision provenance
    m = re.search(r"oldid=(\d+)", t)
    result["oldid"] = m.group(1) if m else None
    m = re.search(r'This page was last edited on ([^<]+?)\.', t)
    result["last_edited"] = m.group(1) if m else None

    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()