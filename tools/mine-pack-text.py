"""Corpus-wide text extraction from the recovered JET pack.

Read-only. Inflates every .jet with tools/jet-viewer/jet_decoder.py, unwraps
RW records, and reports any inner payload that is mostly printable text
(UTF-8 or CP949/UTF-16), so game data tables can be located.

Usage:
  python mine-pack-text.py --list            # per-file text summary
  python mine-pack-text.py --dump NAME       # write all text payloads of NAME to a dir
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

JET_VIEWER = Path(r"C:\Users\shaha\Documents\ChatGPT\Blustone\tools\jet-viewer")
sys.path.insert(0, str(JET_VIEWER))
from jet_decoder import inflate_jet_resources, _unwrap_rw  # noqa: E402

ASSETS = Path(
    r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets"
    r"\phone-2026-09-18\extracted\split_PADResource\assets"
)


def decodings(data: bytes) -> dict[str, str]:
    out = {}
    for enc in ("utf-8-sig", "cp949", "utf-16-le"):
        try:
            out[enc] = data.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            pass
    return out


def printable_ratio(sample: bytes) -> float:
    if not sample:
        return 0.0
    good = sum(b in (9, 10, 13) or 32 <= b <= 126 or b >= 0x80 for b in sample)
    return good / len(sample)


def text_payloads(data: bytes):
    """Yield (logical_index, offset, text, encoding) for printable inner payloads."""
    for index, (offset, resource, _chunks) in enumerate(inflate_jet_resources(data)):
        candidates = [(resource, "inflated")]
        inner = _unwrap_rw(resource) if resource.startswith(b"RW") and not resource.startswith(b"RWM") else None
        if inner is not None:
            candidates.append((inner, "rw"))
        for payload, layer in candidates:
            if not payload or len(payload) < 16:
                continue
            head = payload[:8]
            if head[:4] in (b"\x89PNG", b"ID3\x04", b"\xff\xd8\xff", b"OggS", b"RIFF", b"ftyp"):
                continue
            if head[:2] in (b"I2",):
                continue
            sample = payload[:65536]
            if printable_ratio(sample) < 0.95:
                continue
            for enc, text in decodings(payload).items():
                printable = sum(1 for c in text[:65536] if c.isprintable() or c in "\r\n\t")
                if printable / max(1, len(text[:65536])) > 0.95 and len(text) > 16:
                    yield index, offset, layer, enc, text
                    break


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dump", metavar="NAME")
    parser.add_argument("--dump-dir", type=Path)
    parser.add_argument("--grep")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    files = sorted(ASSETS.glob("*.jet"))

    if args.dump:
        target = ASSETS / args.dump
        outdir = args.dump_dir or Path(r"C:\Users\shaha\AppData\Local\Temp\opencode\jetdump")
        outdir.mkdir(parents=True, exist_ok=True)
        data = target.read_bytes()
        for index, offset, layer, enc, text in text_payloads(data):
            path = outdir / f"{target.stem}__r{index:03d}_off{offset}_{layer}.txt"
            path.write_text(text, encoding="utf-8")
            print(f"{path}  {len(text)} chars  enc={enc}")
        return

    summary = []
    for path in files:
        data = path.read_bytes()
        hits = list(text_payloads(data))
        if not hits:
            continue
        record = {
            "file": path.name,
            "textResources": len(hits),
            "totalChars": sum(len(h[4]) for h in hits),
            "resources": [
                {"index": h[0], "offset": h[1], "layer": h[2], "enc": h[3], "chars": len(h[4]),
                 "preview": h[4][:200].replace("\r", " ").replace("\n", " ")}
                for h in hits
            ],
        }
        if args.grep:
            keep = []
            for r in record["resources"]:
                data_path = None
                for index, offset, layer, enc, text in hits:
                    if index == r["index"] and offset == r["offset"] and layer == r["layer"]:
                        if args.grep.lower() in text.lower():
                            keep.append(r)
            if not keep:
                continue
            record["resources"] = keep
        summary.append(record)
        print(f"{path.name:24s} text_resources={record['textResources']:3d} chars={record['totalChars']:8d}")
        for r in record["resources"]:
            print(f"    [{r['index']:3d}] {r['layer']:9s} {r['enc']:10s} {r['chars']:8d}  {r['preview'][:120]}")
    if args.json_out:
        args.json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {args.json_out}")


if __name__ == "__main__":
    main()