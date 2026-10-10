"""Build local AT compatibility metadata referencing untouched original scenery.

This is not a recovered original area mapping. Never edits preserved packages.
Native CRMAnim2.Load consumes the original transform prefix, count and frame
records; CRMResourceMgr4.LoadAnim2 requires an animation instead of an S2 sprite.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
PAD = ROOT / 'recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets'
ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ._'

def resource_id(name):
    value = 0
    for character in name:
        value = value * 38 + ALPHABET.index(character)
    if value >= 2**64:
        raise ValueError('resource identity exceeds native uint64')
    return value

def read_original(name, expected):
    data = (PAD / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('original source fingerprint differs: ' + name)
    return data

def record(data, identity):
    offset = 0
    found = None
    while offset < len(data):
        if offset + 24 > len(data):
            raise ValueError('truncated JET header')
        packed = struct.unpack_from('<I', data, offset + 8)[0]
        end = offset + 24 + packed
        if end > len(data):
            raise ValueError('truncated JET body')
        if struct.unpack_from('<Q', data, offset + 12)[0] == identity:
            if found is not None:
                raise ValueError('duplicate resource identity')
            found = (data[offset:offset+24], zlib.decompress(data[offset+24:end]))
        offset = end
    if found is None:
        raise ValueError('named resource not found')
    return found

def build():
    ui = read_original('UI_TUTO.jet', '06e94376790ea5fcef72d597fe01ecc03a870ca4e4bbecdfc99e13461af9c99a')
    scenery = read_original('MAP_ZONE_1.jet', '258e21f9e203b4dd837cf8e4ba945c1a14f2834b52b3f1ccaa879da1c028ee11')
    header, template = record(ui, resource_id('MAP_ANI'))
    _, sprite = record(scenery, resource_id('MS_MAP2'))
    if template[:2] != b'AT' or len(template) != 341 or struct.unpack_from('<I', template, 43)[0] != 21 or sprite[:2] != b'S2':
        raise ValueError('unexpected typed original template or sprite')
    # Retain the exact original identity transform/flags, replace only frame data.
    body = template[:43] + struct.pack('<I', 1) + struct.pack('<QfH', resource_id('MS_MAP2'), 0.05, 0)
    compressed = zlib.compress(body)
    output_header = bytearray(header)
    struct.pack_into('<IIIQ', output_header, 0, len(body), len(body), len(compressed), resource_id('LOCAL_MAP'))
    result = bytes(output_header) + compressed
    verified_header, verified_body = record(result, resource_id('LOCAL_MAP'))
    if verified_header[22:24] != b'AT' or verified_body != body or len(body) != 61:
        raise ValueError('wrapper round trip failed')
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'analysis/generated-map-wrapper/LOCAL_MAP.jet')
    args = parser.parse_args()
    target = args.out.resolve()
    if target == PAD or PAD in target.parents or target.exists():
        raise SystemExit('refusing original-directory output or overwrite')
    output = build()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as handle:
        handle.write(output)
    print(json.dumps({'path': str(target), 'bytes': len(output), 'sha256': hashlib.sha256(output).hexdigest(),
                      'animation': 'LOCAL_MAP', 'sprite': 'MS_MAP2', 'policy': 'local wrapper; original area assignment unknown'}))
