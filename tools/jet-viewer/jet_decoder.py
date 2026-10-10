"""Read-only, best-effort decoder for the Blustone JET resource files.

The game uses more than one payload shape behind the .jet extension.  This
module deliberately does not pretend that the native format is fully
documented.  It recognizes the formats that can be established from the
recovered files:

* ISO-BMFF/MP4 payloads preceded by a small JET header;
* JET payloads with a zlib stream beginning at offset 24;
* the readable RW/RWM resource records found after inflation; and
* metadata/hex/string inspection for the remaining native binary formats.

No function in this module writes to the source JET file.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import struct
from pathlib import Path
from typing import Iterable
import zlib
import xml.etree.ElementTree as ET


MAX_INFLATED_BYTES = 256 * 1024 * 1024
MAX_TEXT_BYTES = 120_000
MAX_STRINGS = 160
MAX_STRING_LENGTH = 240

_ZLIB_HEADERS = (b"\x78\x01", b"\x78\x5e", b"\x78\x9c", b"\x78\xda")


@dataclass(frozen=True)
class MediaBlob:
    """A browser-playable or downloadable embedded payload."""

    source: str
    index: int
    label: str
    mime: str
    suffix: str
    offset: int
    data: bytes

    @property
    def variant_id(self) -> str:
        return f"media-{self.source}-{self.index}"


def _u32le(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 4 > len(data):
        return None
    return struct.unpack_from("<I", data, offset)[0]


def _u16le(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 2 > len(data):
        return None
    return struct.unpack_from("<H", data, offset)[0]


def _u32be(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 4 > len(data):
        return None
    return struct.unpack_from(">I", data, offset)[0]


def _u64be(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 8 > len(data):
        return None
    return struct.unpack_from(">Q", data, offset)[0]


def _find_all(data: bytes, needle: bytes, limit: int = 64) -> list[int]:
    positions: list[int] = []
    cursor = 0
    while len(positions) < limit:
        position = data.find(needle, cursor)
        if position < 0:
            break
        positions.append(position)
        cursor = position + 1
    return positions


def _png_end(data: bytes, start: int) -> int:
    """Return the end of a PNG if its chunk table is valid."""

    position = start + 8
    while position + 12 <= len(data):
        length = _u32be(data, position)
        if length is None:
            break
        end = position + 12 + length
        if end > len(data):
            break
        if data[position + 4 : position + 8] == b"IEND":
            return end
        position = end
    return len(data)


def _jpeg_end(data: bytes, start: int) -> int | None:
    if data[start : start + 3] != b"\xff\xd8\xff":
        return None
    position = start + 2
    saw_frame = False
    while position + 2 <= len(data):
        if data[position] != 0xFF:
            return None
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            return None
        marker = data[position]
        position += 1
        if marker == 0xD9:
            return position if saw_frame else None
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(data):
            return None
        length = int.from_bytes(data[position : position + 2], "big")
        if length < 2 or position + length > len(data):
            return None
        if 0xC0 <= marker <= 0xC3 or 0xC5 <= marker <= 0xC7 or 0xC9 <= marker <= 0xCB or 0xCD <= marker <= 0xCF:
            saw_frame = True
        position += length
        if marker == 0xDA:
            end = data.find(b"\xff\xd9", position)
            return end + 2 if saw_frame and end >= 0 else None
    return None


def _riff_end(data: bytes, start: int) -> int:
    length = _u32le(data, start + 4)
    if length is None:
        return len(data)
    return min(len(data), start + 8 + length)


def _looks_like_mp3_frame(data: bytes, offset: int) -> bool:
    if offset < 0 or offset + 4 > len(data):
        return False
    first, second, third, _fourth = data[offset : offset + 4]
    if first != 0xFF or (second & 0xE0) != 0xE0:
        return False
    version = (second >> 3) & 0x03
    layer = (second >> 1) & 0x03
    bitrate_index = (third >> 4) & 0x0F
    sample_rate_index = (third >> 2) & 0x03
    return version != 0x01 and layer != 0 and bitrate_index != 0x0F and sample_rate_index != 0x03


def _find_mp3_start(data: bytes) -> int | None:
    # The recovered SND JETs use a 34-byte wrapper before either an ID3 tag or
    # the first MPEG frame. Also accept ordinary MP3 files that start at zero.
    preferred = [0, 34]
    for position in preferred:
        if data[position : position + 3] == b"ID3" or _looks_like_mp3_frame(data, position):
            return position
    for position in _find_all(data[:4096], b"ID3", limit=4):
        if position == 0 or position >= 24:
            return position
    for position in range(min(len(data), 4096)):
        if _looks_like_mp3_frame(data, position):
            return position
    return None


def _id3_tag_end(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 10 > len(data) or data[offset : offset + 3] != b"ID3":
        return None
    size = sum((data[offset + 6 + index] & 0x7F) << (7 * (3 - index)) for index in range(4))
    return min(len(data), offset + 10 + size + (10 if data[offset + 5] & 0x10 else 0))


def _mp3_frame_length(data: bytes, offset: int) -> int | None:
    if not _looks_like_mp3_frame(data, offset):
        return None
    second = data[offset + 1]
    third = data[offset + 2]
    version = (second >> 3) & 0x03
    layer = (second >> 1) & 0x03
    bitrate_index = (third >> 4) & 0x0F
    sample_rate_index = (third >> 2) & 0x03
    padding = (third >> 1) & 0x01
    tables = {
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
    rates = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}
    bitrate = tables.get((version, layer), [])[bitrate_index] if bitrate_index < len(tables.get((version, layer), [])) else 0
    sample_rate = rates.get(version, [])[sample_rate_index] if sample_rate_index < len(rates.get(version, [])) else 0
    if not sample_rate:
        return None
    if bitrate_index == 0:
        # Free-bitrate streams do not carry a frame size. Use the next frame
        # sync with matching version/layer/sample-rate as the boundary.
        for candidate in range(offset + 4, min(len(data), offset + 256 * 1024)):
            if not _looks_like_mp3_frame(data, candidate):
                continue
            if data[candidate + 1] & 0x1E == second & 0x1E and data[candidate + 2] & 0x0C == third & 0x0C:
                return candidate - offset
        return None
    if not bitrate:
        return None
    if layer == 3:
        return ((12 * bitrate * 1000 // sample_rate) + padding) * 4
    return (144 if version == 3 else 72) * bitrate * 1000 // sample_rate + padding


def find_mp3_resources(data: bytes, source: str) -> list[MediaBlob]:
    """Split the concatenated MP3 JET chunks used by SND/VOICE resources."""

    resources: list[MediaBlob] = []
    cursor = 0
    while cursor + 34 < len(data):
        start = cursor + 34
        if data[start : start + 3] != b"ID3" and not _looks_like_mp3_frame(data, start):
            if cursor == 0:
                direct = _find_mp3_start(data)
                if direct is None:
                    break
                start = direct
            else:
                break
        position = start
        tag_end = _id3_tag_end(data, position)
        if tag_end is not None:
            position = tag_end
        frames = 0
        while position < len(data):
            if frames and data[position : position + 3] == b"ID3":
                break
            if data[position : position + 3] == b"TAG" and position + 128 <= len(data):
                position += 128
                break
            length = _mp3_frame_length(data, position)
            if length is None or position + length > len(data):
                break
            position += length
            frames += 1
        if frames == 0:
            break
        end = position
        if end <= start:
            break
        resources.append(
            MediaBlob(
                source=source,
                index=len(resources),
                label=f"embedded MP3 audio {len(resources) + 1}",
                mime="audio/mpeg",
                suffix=".mp3",
                offset=start,
                data=data[start:end],
            )
        )
        if end >= len(data):
            break
        if data[end : end + 3] == b"TAG" and end + 128 <= len(data):
            cursor = end + 128
        else:
            cursor = end
    return resources


def _unwrap_rw(data: bytes) -> bytes | None:
    """Remove the six-byte RW length wrapper when it is internally consistent."""

    if not data.startswith(b"RW") or len(data) < 6:
        return None
    length = _u32le(data, 2)
    if length is None or length > len(data) - 6:
        return None
    return data[6 : 6 + length]


def _font_payload(data: bytes) -> bool:
    return data[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"ttcf", b"true", b"typ1")


def _rw_payload_kind(data: bytes) -> str:
    normalized = data.lstrip(b"\xef\xbb\xbf \t\r\n")
    if _font_payload(data):
        return "TrueType/OpenType font"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG image resource"
    if b"3.6.53" in data[:128]:
        return "Spine 3.6 binary skeleton/animation"
    if _shader_info(data) is not None:
        return "GLSL shader source"
    if _motion_info(data) is not None:
        return "Motion XML resource"
    if normalized.startswith((b"//", b"#version", b"precision ")):
        return "GLSL shader source"
    if normalized.startswith((b"{", b"[")):
        return "JSON resource"
    return "RW payload"


def _spine_info(data: bytes) -> dict[str, object] | None:
    match = re.search(rb"3\.6\.53[A-Za-z0-9._-]*", data[:256])
    if not match:
        return None
    return {
        "version": match.group().decode("ascii", errors="replace"),
        "strings": extract_strings(data)[:120],
    }


def _shader_info(data: bytes) -> dict[str, str] | None:
    text = data.decode("utf-8", errors="replace")
    marker = text.find("}//*")
    if marker < 0:
        marker = text.find("//Don't delete this mark")
        if marker < 0:
            return None
    second_marker = text.find("}//*", marker + 4)
    vertex = text[: marker + 1]
    fragment = text[marker + 4 : (second_marker + 1 if second_marker >= 0 else len(text))]
    if "void main" not in vertex or "void main" not in fragment:
        return None
    return {"vertex": vertex, "fragment": fragment}


def _motion_info(data: bytes) -> dict[str, object] | None:
    text = data.decode("utf-8", errors="replace").replace("\x00", "")
    start = text.find("<motion")
    end = text.rfind("</motion>")
    if start < 0 or end < start:
        return None
    xml_text = text[start : end + len("</motion>")]
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    keyframes: list[dict[str, object]] = []
    duration = 0.0
    for child in root:
        raw_time = child.attrib.get("time", "0")
        try:
            time = float(raw_time)
        except ValueError:
            time = 0.0
        duration = max(duration, time)
        item: dict[str, object] = {"tag": child.tag, "time": time}
        if "pos" in child.attrib:
            match = re.search(r"\(\s*([-+0-9.]+)\s*,\s*([-+0-9.]+)\s*\)", child.attrib["pos"])
            if match:
                item["x"] = float(match.group(1))
                item["y"] = float(match.group(2))
        for key in ("opacity", "ampli", "vibCount", "vibCycle"):
            if key in child.attrib:
                try:
                    item[key] = float(child.attrib[key])
                except ValueError:
                    item[key] = child.attrib[key]
        for key in ("resname", "dir"):
            if key in child.attrib:
                item[key] = child.attrib[key]
        keyframes.append(item)
    return {"name": root.attrib.get("name", "motion"), "duration": duration, "keyframes": keyframes}


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _rgba_png(width: int, height: int, pixels: bytes) -> bytes:
    rows = b"".join(
        b"\x00" + pixels[row * width * 4 : (row + 1) * width * 4]
        for row in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(rows, 6))
        + _png_chunk(b"IEND", b"")
    )


def decode_i2_texture(data: bytes) -> tuple[int, int, bytes] | None:
    """Reconstruct the tiled RGBA8 atlas used by the recovered I2 layers."""

    if not data.startswith(b"I2") or len(data) < 56:
        return None
    width = _u16le(data, 42)
    height = _u16le(data, 46)
    pixel_format = _u32le(data, 50)
    if width is None or height is None or pixel_format != 4 or not width or not height:
        return None

    # The first RMPOT marker terminates the fixed I2 header. Each following
    # marker terminates a 24-byte tile descriptor; the final descriptor sits
    # immediately after the last marker as a footer. The table is near the
    # beginning of the inflated layer, so keep pixel data from creating false
    # marker hits in large atlases.
    first_marker = data.find(b"RMPOT", 0, min(len(data), 256 * 1024))
    if first_marker < 0:
        return None
    markers = [first_marker]
    next_marker = first_marker + 29
    while data[next_marker : next_marker + 5] == b"RMPOT":
        markers.append(next_marker)
        next_marker += 29

    records: list[tuple[int, int, int, int, int, int]] = []
    for marker in markers[1:]:
        if marker < 24:
            return None
        records.append(struct.unpack_from("<6I", data, marker - 24))
    footer_start = markers[-1] + 5
    if footer_start + 24 > len(data):
        return None
    records.append(struct.unpack_from("<6I", data, footer_start))
    data_start = footer_start + 24

    pixels = bytearray(width * height * 4)
    cursor = data_start
    for stored_width, stored_height, actual_width, actual_height, x, y in records:
        if not stored_width or not stored_height:
            return None
        if actual_width > stored_width or actual_height > stored_height:
            return None
        if x + actual_width > width or y + actual_height > height:
            return None
        tile_size = stored_width * stored_height * 4
        if cursor + tile_size > len(data):
            return None
        tile = data[cursor : cursor + tile_size]
        cursor += tile_size
        for row in range(actual_height):
            source_start = row * stored_width * 4
            target_start = ((y + row) * width + x) * 4
            row_bytes = actual_width * 4
            pixels[target_start : target_start + row_bytes] = tile[
                source_start : source_start + row_bytes
            ]

    return width, height, _rgba_png(width, height, bytes(pixels))


def i2_resource_size(data: bytes) -> int | None:
    """Return the byte extent of one I2 resource, excluding any outer JET header."""

    if not data.startswith(b"I2") or len(data) < 56:
        return None
    first_marker = data.find(b"RMPOT", 0, min(len(data), 256 * 1024))
    if first_marker < 0:
        return None
    markers = [first_marker]
    next_marker = first_marker + 29
    while data[next_marker : next_marker + 5] == b"RMPOT":
        markers.append(next_marker)
        next_marker += 29
    records: list[tuple[int, int, int, int, int, int]] = []
    for marker in markers[1:]:
        if marker < 24:
            return None
        records.append(struct.unpack_from("<6I", data, marker - 24))
    footer_start = markers[-1] + 5
    if footer_start + 24 > len(data):
        return None
    records.append(struct.unpack_from("<6I", data, footer_start))
    data_start = footer_start + 24
    total = data_start + sum(stored_width * stored_height * 4 for stored_width, stored_height, *_ in records)
    return total if total <= len(data) else None


def split_raw_i2_resources(data: bytes) -> list[tuple[int, bytes]]:
    """Split a raw (non-zlib) payload containing concatenated I2 resources."""

    starts = _find_all(data, b"I2\x00\x00", limit=1024)
    resources: list[tuple[int, bytes]] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(data)
        candidate = data[start:end]
        if decode_i2_texture(candidate) is not None:
            resources.append((start, candidate))
    return resources


def _looks_like_mp4_box(data: bytes, start: int) -> bool:
    size = _u32be(data, start)
    if size is None or size < 8:
        return False
    if size == 1:
        extended = _u64be(data, start + 8)
        return extended is not None and extended >= 16 and start + extended <= len(data)
    return start + size <= len(data)


def _mp4_extent(data: bytes, start: int) -> int | None:
    position = start
    boxes = 0
    while position + 8 <= len(data):
        size = _u32be(data, position)
        header = 8
        if size == 1:
            if position + 16 > len(data):
                break
            size = _u64be(data, position + 8) or 0
            header = 16
        elif size == 0:
            return len(data) if boxes else None
        if size < header or position + size > len(data):
            break
        boxes += 1
        position += size
    return position if boxes else None


def find_media(data: bytes, source: str) -> list[MediaBlob]:
    """Find standard media payloads embedded in a raw or inflated layer.

    The custom JET header before an MP4 is intentionally not returned.  The
    checked JET MP4 files contain a normal MP4 box table whose chunk offsets
    are relative to that stripped payload, so keeping the four-byte MP4 box
    size immediately before ``ftyp`` is important.
    """

    # RW/I2 resources have their own payload readers. Scanning their binary
    # bodies for MP3/JPEG byte patterns creates false media candidates.
    if data.startswith((b"I2", b"RW", b"RWM")):
        return []

    found: list[MediaBlob] = []
    seen: set[tuple[str, int]] = set()
    mp4_end = 0

    for ftyp in _find_all(data, b"ftyp"):
        start = ftyp - 4
        if start < 0 or not _looks_like_mp4_box(data, start):
            continue
        key = ("video/mp4", start)
        if key in seen:
            continue
        seen.add(key)
        mp4_end = _mp4_extent(data, start) or len(data)
        found.append(
            MediaBlob(
                source=source,
                index=len(found),
                label="embedded MP4",
                mime="video/mp4",
                suffix=".mp4",
                offset=start,
                data=data[start:mp4_end],
            )
        )
        break

    if not mp4_end:
        for audio in find_mp3_resources(data, source):
            key = (audio.mime, audio.offset)
            if key not in seen:
                seen.add(key)
                found.append(audio)

    search_data = data[mp4_end:] if mp4_end else data
    search_offset = mp4_end if mp4_end else 0

    png_signature = b"\x89PNG\r\n\x1a\n"
    for position in _find_all(search_data, png_signature):
        absolute_position = search_offset + position
        key = ("image/png", absolute_position)
        if key in seen:
            continue
        seen.add(key)
        found.append(
            MediaBlob(
                source=source,
                index=len(found),
                label="embedded PNG",
                mime="image/png",
                suffix=".png",
                offset=absolute_position,
                data=search_data[position : _png_end(search_data, position)],
            )
        )
        break

    for position in _find_all(search_data, b"\xff\xd8\xff"):
        end = _jpeg_end(search_data, position)
        if end is None:
            continue
        absolute_position = search_offset + position
        key = ("image/jpeg", absolute_position)
        if key in seen:
            continue
        seen.add(key)
        found.append(
            MediaBlob(
                source=source,
                index=len(found),
                label="embedded JPEG",
                mime="image/jpeg",
                suffix=".jpg",
                offset=absolute_position,
                data=search_data[position:end],
            )
        )
        break

    for position in _find_all(search_data, b"RIFF"):
        form = search_data[position + 8 : position + 12]
        if form not in (b"WEBP", b"WAVE"):
            continue
        mime = "image/webp" if form == b"WEBP" else "audio/wav"
        suffix = ".webp" if form == b"WEBP" else ".wav"
        absolute_position = search_offset + position
        key = (mime, absolute_position)
        if key in seen:
            continue
        seen.add(key)
        found.append(
            MediaBlob(
                source=source,
                index=len(found),
                label="embedded WebP" if form == b"WEBP" else "embedded WAV",
                mime=mime,
                suffix=suffix,
                offset=absolute_position,
                data=search_data[position : _riff_end(search_data, position)],
            )
        )
        break

    for position in _find_all(search_data, b"OggS"):
        absolute_position = search_offset + position
        key = ("audio/ogg", absolute_position)
        if key in seen:
            continue
        seen.add(key)
        found.append(
            MediaBlob(
                source=source,
                index=len(found),
                label="embedded Ogg audio",
                mime="audio/ogg",
                suffix=".ogg",
                offset=absolute_position,
                data=search_data[position:],
            )
        )
        break

    return found


def inflate_jet_resources(data: bytes) -> list[tuple[int, bytes, int]]:
    """Inflate concatenated JET chunks into logical resources.

    A single file can contain one resource split across several JET/zlib
    chunks, or several resources back-to-back. A new I2/RW/RWM header starts a
    new logical resource; continuation chunks are appended to the current one.
    """

    resources: list[list[object]] = []
    remaining = data
    absolute_base = 0
    cursor = 0
    while len(remaining) >= 26:
        payload_start = 24
        if remaining[payload_start : payload_start + 2] == b"I2":
            size = i2_resource_size(remaining[payload_start:])
            if size is None:
                break
            resources.append(
                [
                    absolute_base + payload_start,
                    bytearray(remaining[payload_start : payload_start + size]),
                    1,
                ]
            )
            consumed = payload_start + size
            absolute_base += consumed
            remaining = remaining[consumed:]
            continue

        position = payload_start if remaining[payload_start : payload_start + 2] in _ZLIB_HEADERS else -1
        if position < 0:
            break
        try:
            decompressor = zlib.decompressobj()
            inflated = decompressor.decompress(remaining[position:], MAX_INFLATED_BYTES + 1)
            inflated += decompressor.flush()
        except (zlib.error, OverflowError):
            break
        if not inflated or len(inflated) > MAX_INFLATED_BYTES:
            break

        absolute_offset = absolute_base + position
        starts_resource = inflated.startswith((b"I2", b"RW", b"RWM"))
        if starts_resource or not resources:
            resources.append([absolute_offset, bytearray(), 0])
        resources[-1][1].extend(inflated)  # type: ignore[union-attr]
        resources[-1][2] = int(resources[-1][2]) + 1

        unused = decompressor.unused_data
        consumed = len(remaining) - len(unused)
        if not unused or consumed <= 0:
            break
        absolute_base += consumed
        remaining = unused

    return [
        (int(offset), bytes(payload), int(chunk_count))
        for offset, payload, chunk_count in resources
    ]


def inflate_jet(data: bytes) -> tuple[int, bytes] | None:
    """Backward-compatible first logical inflated resource."""

    resources = inflate_jet_resources(data)
    return (resources[0][0], resources[0][1]) if resources else None


def _format_hex(data: bytes, limit: int = 512) -> str:
    clipped = data[:limit]
    lines: list[str] = []
    for offset in range(0, len(clipped), 16):
        block = clipped[offset : offset + 16]
        hex_part = " ".join(f"{byte:02x}" for byte in block)
        hex_part = f"{hex_part:<47}"
        ascii_part = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in block)
        lines.append(f"{offset:08x}  {hex_part}  {ascii_part}")
    if len(data) > limit:
        lines.append(f"... {len(data) - limit:,} more bytes")
    return "\n".join(lines)


def extract_strings(data: bytes) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(rb"[\x20-\x7e]{4,}", data):
        value = match.group().decode("ascii", errors="replace")[:MAX_STRING_LENGTH]
        if value not in seen:
            values.append(value)
            seen.add(value)
        if len(values) >= MAX_STRINGS:
            break
    return values


def _text_view(data: bytes) -> str | None:
    if not data:
        return None
    if data.startswith(b"I2"):
        return None
    sample = data[: min(len(data), MAX_TEXT_BYTES)]
    printable = sum(byte in (9, 10, 13) or 32 <= byte <= 126 for byte in sample)
    ratio = printable / len(sample)
    looks_named_resource = sample.startswith((b"RW", b"RWM")) or b"<motion" in sample[:4096]
    if ratio < 0.72 and not looks_named_resource:
        return None
    text = sample.decode("utf-8", errors="replace").replace("\x00", "")
    return text


def _layer_kind(data: bytes) -> str:
    if data.startswith((b"local UI_XML_RO", b"UI_XML_RO reconstructed package marker")):
        return "text/resource placeholder"
    if data.startswith(b"RWM"):
        return "RWM animation/resource text"
    if data.startswith(b"RW"):
        return "RW atlas/resource text"
    if data.startswith(b"I2"):
        return "I2 custom texture/resource"
    if inflate_jet(data) is not None:
        return "zlib-compressed JET"
    if find_media(data, "layer"):
        return "embedded media"
    return "binary JET/resource data"


def _i2_info(data: bytes) -> dict[str, int] | None:
    if not data.startswith(b"I2") or len(data) < 56:
        return None
    info: dict[str, int] = {}
    # The dimensions are packed as 16-bit values between the final float
    # fields and the 32-bit pixel-format field in the recovered I2 headers.
    width = _u16le(data, 42)
    height = _u16le(data, 46)
    pixel_format = _u32le(data, 50)
    if width is not None:
        info["width"] = width
    if height is not None:
        info["height"] = height
    if pixel_format is not None:
        info["format"] = pixel_format
    info["rmpotRecords"] = data.count(b"RMPOT")
    return info


def _header_info(data: bytes) -> dict[str, object]:
    info: dict[str, object] = {
        "firstBytes": data[:32].hex(" "),
    }
    if len(data) >= 16:
        info["u32le"] = [_u32le(data, offset) for offset in (0, 4, 8, 12)]
    if len(data) >= 26 and data[24:26] in _ZLIB_HEADERS:
        info["zlibOffset"] = 24
    ftyp = data.find(b"ftyp", 0, 4096)
    if ftyp >= 4:
        info["mp4BoxOffset"] = ftyp - 4
        info["mp4Brand"] = data[ftyp + 4 : ftyp + 8].decode("ascii", errors="replace")
    return info


def _layer_summary(data: bytes, source: str) -> dict[str, object]:
    return {
        "source": source,
        "size": len(data),
        "kind": _layer_kind(data),
        "hex": _format_hex(data),
        "strings": extract_strings(data),
        "text": _text_view(data),
        "i2": _i2_info(data),
        "shader": _shader_info(data),
        "motion": _motion_info(data),
    }


def inspect_bytes(data: bytes, name: str) -> tuple[dict[str, object], dict[str, bytes]]:
    """Return JSON-safe inspection data and named byte variants."""

    inflated_resources = inflate_jet_resources(data)
    variants: dict[str, bytes] = {"raw": data}
    layers = [_layer_summary(data, "raw JET")]
    # Compressed binary payloads routinely contain byte triples that resemble
    # JPEG/RIFF signatures.  Only inspect the raw layer for media when it is
    # not itself a confirmed zlib-wrapped JET.
    blobs = [] if inflated_resources else find_media(data, "raw")
    variant_descriptions: list[dict[str, object]] = [
        {"id": "raw", "label": "Original JET bytes", "size": len(data)}
    ]

    for resource_index, (offset, inflated, chunk_count) in enumerate(inflated_resources):
        inflated_id = f"inflated-{resource_index}"
        variants[inflated_id] = inflated
        is_raw_resource = data[offset : offset + 2] == b"I2"
        resource_label = "raw I2 resource" if is_raw_resource else "inflated resource"
        resource_layer = {
            **_layer_summary(
                inflated,
                f"{resource_label} {resource_index + 1} @ {offset} ({chunk_count} chunk{'s' if chunk_count != 1 else ''})",
            ),
            "resourceOffset" if is_raw_resource else "inflateOffset": offset,
            "chunkCount": chunk_count,
        }
        # The useful RW payload is added below; avoid selecting the wrapper's
        # binary-polluted text as the main text view.
        if inflated.startswith(b"RW") and not inflated.startswith(b"RWM"):
            resource_layer["text"] = None
            resource_layer["shader"] = None
            resource_layer["motion"] = None
            resource_layer["spine"] = None
        layers.append(resource_layer)
        variant_descriptions.append(
            {
                "id": inflated_id,
                "label": f"{resource_label.capitalize()} {resource_index + 1}",
                "size": len(inflated),
            }
        )

        if inflated.startswith(b"I2"):
            core_size = i2_resource_size(inflated)
            if core_size is not None and core_size < len(inflated):
                auxiliary = inflated[core_size:]
                auxiliary_id = f"auxiliary-{resource_index}"
                variants[auxiliary_id] = auxiliary
                auxiliary_kind = (
                    "S2 sprite/metadata records"
                    if auxiliary.startswith(b"S2")
                    else "AT auxiliary records"
                    if auxiliary.startswith(b"AT")
                    else "I2 auxiliary bytes"
                )
                layers.append(
                    {
                        **_layer_summary(auxiliary, f"{auxiliary_kind} for resource {resource_index + 1}"),
                        "kind": auxiliary_kind,
                        "resourceIndex": resource_index,
                    }
                )
                variant_descriptions.append(
                    {
                        "id": auxiliary_id,
                        "label": f"{auxiliary_kind} for resource {resource_index + 1}",
                        "size": len(auxiliary),
                    }
                )
            decoded_i2 = decode_i2_texture(inflated)
            if decoded_i2 is not None:
                width, height, png = decoded_i2
                blobs.append(
                    MediaBlob(
                        source=f"i2-{resource_index}",
                        index=0,
                        label=f"decoded I2 texture atlas {resource_index + 1} ({width}×{height})",
                        mime="image/png",
                        suffix=".png",
                        offset=0,
                        data=png,
                    )
                )
        elif inflated.startswith(b"RW") and not inflated.startswith(b"RWM"):
            payload = _unwrap_rw(inflated)
            if payload is not None:
                payload_id = f"rw-payload-{resource_index}"
                variants[payload_id] = payload
                payload_kind = _rw_payload_kind(payload)
                payload_layer = _layer_summary(payload, f"RW payload {resource_index + 1}")
                payload_layer["kind"] = payload_kind
                payload_layer["rwWrapper"] = inflated_id
                spine = _spine_info(payload)
                if spine is not None:
                    payload_layer["spine"] = spine
                layers.append(payload_layer)
                variant_descriptions.append(
                    {
                        "id": payload_id,
                        "label": f"Unwrapped RW payload {resource_index + 1}",
                        "size": len(payload),
                    }
                )
                if _font_payload(payload):
                    blobs.append(
                        MediaBlob(
                            source=f"font-{resource_index}",
                            index=0,
                            label=f"decoded TrueType/OpenType font {resource_index + 1}",
                            mime="font/ttf",
                            suffix=".ttf",
                            offset=0,
                            data=payload,
                        )
                    )
                elif payload.startswith(b"\x89PNG\r\n\x1a\n"):
                    blobs.append(
                        MediaBlob(
                            source=f"rw-png-{resource_index}",
                            index=0,
                            label=f"decoded RW PNG resource {resource_index + 1}",
                            mime="image/png",
                            suffix=".png",
                            offset=0,
                            data=payload,
                        )
                    )
        else:
            blobs.extend(find_media(inflated, f"inflated-{resource_index}"))

    media_descriptions: list[dict[str, object]] = []
    for blob in blobs:
        # The index is source-local, so this remains stable even when a raw
        # and inflated layer each contain one media stream.
        variants[blob.variant_id] = blob.data
        media_descriptions.append(
            {
                "id": blob.variant_id,
                "source": blob.source,
                "label": blob.label,
                "mime": blob.mime,
                "suffix": blob.suffix,
                "offset": blob.offset,
                "size": len(blob.data),
            }
        )

    inflated_text = next(
        (layer["text"] for layer in layers if layer["source"] != "raw JET" and layer["text"]),
        None,
    )
    all_strings: list[str] = []
    seen_strings: set[str] = set()
    for layer in layers:
        for value in layer["strings"]:  # type: ignore[index]
            if value not in seen_strings:
                all_strings.append(value)
                seen_strings.add(value)

    text_resources = [
        {
            "source": str(layer["source"]),
            "kind": str(layer["kind"]),
            "text": str(layer["text"]),
        }
        for layer in layers
        if layer["source"] != "raw JET" and layer.get("text")
    ]

    analysis: dict[str, object] = {
        "name": name,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "header": _header_info(data),
        "kind": (
            "multi-resource JET"
            if len(inflated_resources) > 1
            else layers[-1]["kind"] if len(layers) > 1 else layers[0]["kind"]
        ),
        "layers": layers,
        "media": media_descriptions,
        "text": inflated_text or layers[0]["text"],
        "textResources": text_resources,
        "strings": all_strings,
        "variants": variant_descriptions,
        "resourceCount": len(inflated_resources),
    }
    return analysis, variants


def inspect_file(path: Path) -> tuple[dict[str, object], dict[str, bytes]]:
    data = path.read_bytes()
    return inspect_bytes(data, path.name)


def quick_kind(data: bytes) -> str:
    """Cheap classification used while building the file list."""

    if data.find(b"ftyp", 0, 1024) >= 4:
        return "MP4 payload"
    if len(data) >= 38 and (
        data[34:37] == b"ID3" or _looks_like_mp3_frame(data, 34)
    ):
        return "MP3 payload"
    if len(data) >= 26 and data[24:26] in _ZLIB_HEADERS:
        return "zlib JET"
    if len(data) >= 26 and data[24:26] == b"I2":
        return "I2 resource"
    if data.startswith(b"I2"):
        return "I2 resource"
    if data.startswith(b"RWM"):
        return "RWM resource"
    if data.startswith(b"RW"):
        return "RW resource"
    return "binary JET"


def quick_fingerprint(data: bytes) -> str:
    """A non-cryptographic grouping key for duplicate UI entries."""

    sample = data[:512] + data[-512:] if len(data) > 1024 else data
    return f"{len(data)}:{hashlib.sha1(sample).hexdigest()[:16]}"
