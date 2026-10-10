"""Dump every text payload of the whole pack to a directory, plus a grep index.

Read-only. Uses tools/jet-viewer/jet_decoder.inflate_jet_resources.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

JET_VIEWER = Path(r"C:\Users\shaha\Documents\ChatGPT\Blustone\tools\jet-viewer")
sys.path.insert(0, str(JET_VIEWER))
from jet_decoder import inflate_jet_resources, _unwrap_rw  # noqa: E402

ASSETS = Path(
    r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets"
    r"\phone-2026-09-18\extracted\split_PADResource\assets"
)

SKIP_HEAD = (b"\x89PNG", b"ID3\x04", b"\xff\xd8\xff", b"OggS", b"RIFF")


def is_text(payload: bytes) -> bool:
    if not payload or len(payload) < 16:
        return False
    head = payload[:8]
    if head[:4] in SKIP_HEAD or head[:2] == b"I2":
        return False
    if b"ftyp" == payload[4:8]:
        return False
    sample = payload[:65536]
    good = sum(b in (9, 10, 13) or 32 <= b <= 126 or b >= 0x80 for b in sample)
    if good / len(sample) < 0.95:
        return False
    for enc in ("utf-8-sig", "cp949", "utf-16-le"):
        try:
            text = payload.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
        window = text[:65536]
        printable = sum(1 for c in window if c.isprintable() or c in "\r\n\t")
        if printable / max(1, len(window)) > 0.95 and len(text) > 16:
            return True
    return False


def decode(payload: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "cp949", "utf-16-le"):
        try:
            text = payload.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
        window = text[:65536]
        printable = sum(1 for c in window if c.isprintable() or c in "\r\n\t")
        if printable / max(1, len(window)) > 0.95 and len(text) > 16:
            return enc, text
    return "", ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pattern", default="*.jet")
    parser.add_argument("--max-chars", type=int, default=400_000)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    index = []
    for path in sorted(ASSETS.glob(args.pattern)):
        data = path.read_bytes()
        for i, (offset, resource, chunks) in enumerate(inflate_jet_resources(data)):
            candidates = [("inflated", resource)]
            if resource.startswith(b"RW") and not resource.startswith(b"RWM"):
                inner = _unwrap_rw(resource)
                if inner is not None:
                    candidates.append(("rw", inner))
            for layer, payload in candidates:
                if not is_text(payload):
                    continue
                enc, text = decode(payload)
                if not text:
                    continue
                name = f"{path.stem}__r{i:03d}_off{offset}_{layer}.txt"
                (args.out / name).write_text(text, encoding="utf-8")
                index.append({
                    "file": path.name, "resource": i, "offset": offset, "layer": layer,
                    "encoding": enc, "chars": len(text), "out": name,
                })
        print(f"{path.name} done", flush=True)
    (args.out / "_index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(f"{len(index)} text resources -> {args.out}")


if __name__ == "__main__":
    main()