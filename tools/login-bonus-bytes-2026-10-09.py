#!/usr/bin/env python3
"""Byte-level verification of the vsfan Hunter_Supply_Office numerals.

Confirms the separator char is U+00D7 (MULTIPLICATION SIGN) and prints the
exact digit run per cell so a misread digit would be visible.
"""
import hashlib
import re
import sys

SRC = r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets\vsfan-reward-2026-10-09\Hunter_Supply_Office.html"

b = open(SRC, "rb").read()
print("bytes:", len(b), "sha256:", hashlib.sha256(b).hexdigest())
t = b.decode("utf-8")
print("U+FFFD in file:", t.count("\ufffd"))

# every <b>...</b> run, with the codepoints of the leading char
for m in re.finditer(r"<b>(.*?)</b>", t, re.S):
    s = m.group(1)
    cps = [hex(ord(c)) for c in s[:3]]
    print(repr(s), cps, "digits:", repr(re.sub(r"\D", "", s)))