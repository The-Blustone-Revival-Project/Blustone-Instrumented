#!/usr/bin/env python3
"""Write the first frame of each fetched GIF as PNG for inspection."""
import glob
import io
import os
import sys

from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

out = "recovered-assets/forum-en-2026-10-05/get-img/frames"
os.makedirs(out, exist_ok=True)
for p in sorted(glob.glob("recovered-assets/forum-en-2026-10-05/get-img/img/*.gif")):
    with Image.open(p) as im:
        n = getattr(im, "n_frames", 1)
        im.seek(0)
        dst = os.path.join(out, os.path.basename(p).rsplit(".", 1)[0] + "_f0.png")
        im.convert("RGB").save(dst)
        print(f"{os.path.basename(p)}: frames={n} size={im.size} -> {os.path.basename(dst)}")
