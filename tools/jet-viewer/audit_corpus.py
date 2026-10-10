"""Exhaustive offline audit for the canonical Blustone JET corpus."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import zlib

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from jet_decoder import (  # noqa: E402
    _looks_like_mp3_frame,
    _mp3_frame_length as decoder_mp3_frame_length,
    _unwrap_rw,
    find_media,
    i2_resource_size,
    inspect_file,
    inflate_jet_resources,
)


def _u32be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "big")


def validate_png(data: bytes) -> str | None:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "missing PNG signature"
    position = 8
    saw_iend = False
    while position + 12 <= len(data):
        length = _u32be(data, position)
        end = position + 12 + length
        if end > len(data):
            return f"PNG chunk overruns payload at {position}"
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        expected_crc = _u32be(data, position + 8 + length)
        actual_crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            return f"PNG CRC mismatch for {kind!r} at {position}"
        position = end
        if kind == b"IEND":
            saw_iend = True
            break
    if not saw_iend:
        return "PNG has no IEND"
    if position != len(data):
        return f"PNG has {len(data) - position} trailing bytes"
    return None


def validate_mp4(data: bytes) -> str | None:
    position = 0
    boxes = 0
    while position + 8 <= len(data):
        size = _u32be(data, position)
        header = 8
        if size == 1:
            if position + 16 > len(data):
                return f"MP4 extended box header overruns payload at {position}"
            size = int.from_bytes(data[position + 8 : position + 16], "big")
            header = 16
        elif size == 0:
            size = len(data) - position
        if size < header or position + size > len(data):
            return f"MP4 invalid box size at {position}"
        boxes += 1
        position += size
    if boxes == 0 or position != len(data):
        return f"MP4 has {len(data) - position} unparsed bytes"
    return None


def _mp3_frame_length(data: bytes, offset: int) -> int | None:
    if not _looks_like_mp3_frame(data, offset):
        return None
    first, second, third, _fourth = data[offset : offset + 4]
    version = (second >> 3) & 0x03
    layer = (second >> 1) & 0x03
    bitrate_index = (third >> 4) & 0x0F
    sample_rate_index = (third >> 2) & 0x03
    padding = (third >> 1) & 0x01
    bitrate_tables = {
        (3, 3): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
        (3, 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0],
        (3, 1): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
        (2, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0],
        (2, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
        (2, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
        (0, 3): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
        (0, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
        (0, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
    }
    bitrates = bitrate_tables.get((version, layer))
    if not bitrates or bitrate_index >= len(bitrates) or not bitrates[bitrate_index]:
        return None
    sample_rates = {
        3: [44100, 48000, 32000],
        2: [22050, 24000, 16000],
        0: [11025, 12000, 8000],
    }.get(version)
    if not sample_rates or sample_rate_index >= len(sample_rates):
        return None
    bitrate = bitrates[bitrate_index] * 1000
    sample_rate = sample_rates[sample_rate_index]
    if layer == 3:
        return ((12 * bitrate // sample_rate) + padding) * 4
    coefficient = 144 if version == 3 else 72
    return coefficient * bitrate // sample_rate + padding


def validate_mp3(data: bytes) -> str | None:
    def id3_size(start: int) -> int:
        return sum((data[start + 6 + index] & 0x7F) << (7 * (3 - index)) for index in range(4))

    position = 0
    if data.startswith(b"ID3") and len(data) >= 10:
        tag_size = id3_size(0)
        position = 10 + tag_size + (10 if data[5] & 0x10 else 0)
    frames = 0
    while position < len(data):
        if data[position : position + 3] == b"ID3" and position + 10 <= len(data):
            tag_size = id3_size(position)
            position += 10 + tag_size
            continue
        if data[position : position + 3] == b"TAG" and position + 128 <= len(data):
            position += 128
            break
        length = decoder_mp3_frame_length(data, position)
        if length is None:
            return f"MP3 invalid frame at {position} after {frames} frames"
        if position + length > len(data):
            return f"MP3 frame overruns payload at {position}"
        position += length
        frames += 1
    return None if frames >= 2 and position == len(data) else f"MP3 has only {frames} complete frames"


def validate_sfnt(data: bytes) -> str | None:
    if len(data) < 12 or data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"ttcf", b"true", b"typ1"):
        return "missing sfnt signature"
    if data[:4] == b"ttcf":
        return None if len(data) >= 12 else "truncated TTC header"
    table_count = int.from_bytes(data[4:6], "big")
    directory_end = 12 + table_count * 16
    if directory_end > len(data):
        return "sfnt table directory overruns payload"
    for index in range(table_count):
        entry = 12 + index * 16
        offset = int.from_bytes(data[entry + 8 : entry + 12], "big")
        length = int.from_bytes(data[entry + 12 : entry + 16], "big")
        if offset + length > len(data):
            return f"sfnt table {index} overruns payload"
    return None


def validate_media(mime: str, data: bytes) -> str | None:
    if mime == "image/png":
        return validate_png(data)
    if mime == "video/mp4":
        return validate_mp4(data)
    if mime == "audio/mpeg":
        return validate_mp3(data)
    if mime == "font/ttf":
        return validate_sfnt(data)
    if mime == "image/jpeg":
        return None if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9") else "invalid JPEG bounds"
    if mime in ("image/webp", "audio/wav"):
        return None if data.startswith(b"RIFF") and data[8:12] in (b"WEBP", b"WAVE") else "invalid RIFF media"
    if mime == "audio/ogg":
        return None if data.startswith(b"OggS") else "invalid Ogg signature"
    return None


def audit_file(path: Path) -> dict[str, object]:
    analysis, variants = inspect_file(path)
    issues: list[str] = []
    for media in analysis["media"]:
        issue = validate_media(str(media["mime"]), variants[str(media["id"])])
        if issue:
            issues.append(f"{media['id']}: {issue}")
    resources = inflate_jet_resources(path.read_bytes())
    for index, (_offset, resource, _chunks) in enumerate(resources):
        if resource.startswith(b"I2"):
            size = i2_resource_size(resource)
            tail = resource[size:] if size is not None else resource
            known_auxiliary = tail.startswith((b"S2", b"AT"))
            if size is None or (size != len(resource) and not known_auxiliary):
                issues.append(f"resource {index}: I2 extent {size} != {len(resource)}")
        elif resource.startswith(b"RW") and not resource.startswith(b"RWM"):
            payload = _unwrap_rw(resource)
            if payload is None:
                issues.append(f"resource {index}: invalid RW length wrapper")
            elif payload[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"ttcf", b"true", b"typ1"):
                issue = validate_sfnt(payload)
                if issue:
                    issues.append(f"resource {index}: {issue}")
    return {
        "path": path.name,
        "size": path.stat().st_size,
        "kind": analysis["kind"],
        "resources": analysis.get("resourceCount", 0),
        "media": len(analysis["media"]),
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit every canonical Blustone JET file")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2] / "analysis" / "extracted" / "assets")
    parser.add_argument("--recursive", action="store_true", help="audit every .jet path below --root, deduplicating identical bytes")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    files = sorted(args.root.rglob("*.jet") if args.recursive else args.root.glob("*.jet"))
    if args.recursive:
        groups: dict[str, list[Path]] = {}
        for path in files:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            groups.setdefault(digest, []).append(path)
        results = []
        for digest, paths in groups.items():
            result = audit_file(paths[0])
            result["sha256"] = digest
            result["copies"] = len(paths)
            result["path"] = str(paths[0].relative_to(args.root))
            results.append(result)
    else:
        results = [audit_file(path) for path in files]
    issue_files = [result for result in results if result["issues"]]
    summary = {
        "root": str(args.root.resolve()),
        "files": len(files),
        "uniqueContents": len(results),
        "resources": sum(int(result["resources"]) for result in results),
        "media": sum(int(result["media"]) for result in results),
        "issueFiles": len(issue_files),
        "issues": issue_files,
        "kinds": dict(Counter(str(result["kind"]) for result in results)),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.json_out:
        args.json_out.write_text(json.dumps({"summary": summary, "files": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    raise SystemExit(1 if issue_files else 0)


if __name__ == "__main__":
    main()
