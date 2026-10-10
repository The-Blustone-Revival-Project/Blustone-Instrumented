#!/usr/bin/env python3
"""Verify the positive control really decodes to pixels (not just a JPEG magic)."""
import sys
from PIL import Image

p = sys.argv[1]
with Image.open(p) as im:
    im.verify()
with Image.open(p) as im:
    print("format", im.format, "size", im.size, "mode", im.mode)
    px = im.convert("RGB").getdata()
    distinct = len(set(list(px)[:20000]))
    print("distinct colours in first 20000 px:", distinct)
print("DECODE OK" if distinct > 50 else "DECODE SUSPECT - flat/blank")
