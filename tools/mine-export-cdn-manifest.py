"""Export the recovered CDN.db pack manifest from the phone snapshot.

Read-only.  CDN.db is the LevelDB the native CPVCDN2 indexer wrote on the
device; its keys are the pack names the client actually downloaded, plus the
`packs[]` filename/sign/size triples.  This is the authoritative list of which
resource packs exist for the shipped 2.8.0.1 client.

Usage:
  python mine-export-cdn-manifest.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, r"C:\Users\shaha\Documents\ChatGPT\Blustone\analysis\leveldb-tooling-ci")
import plyvel  # type: ignore  # noqa: E402

ROOT = Path(
    r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets"
    r"\phone-2026-09-18\private\files\local"
)
OUT = Path(r"C:\Users\shaha\Documents\ChatGPT\Blustone\analysis\recovered-data\cdn-manifest")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    db = plyvel.DB(str(ROOT / "CDN.db"), create_if_missing=False)
    rows = {k.decode("utf-8", "replace"): v for k, v in db}
    db.close()

    # pack state: name -> {stamp, packs:[{filename,sign,size}]}
    packs: dict[str, dict] = {}
    stamps: dict[str, int] = {}
    for key, value in rows.items():
        if not key.startswith("CDN\\PVC\\"):
            continue
        rest = key[len("CDN\\PVC\\"):]
        if rest.endswith("\\stamp"):
            name = rest[: -len("\\stamp")]
            try:
                stamps[name] = int(value.decode("utf-8", "replace").strip("\" "))
            except ValueError:
                stamps[name] = value.decode("utf-8", "replace").strip("\" ")
            packs.setdefault(name, {"packs": []})
            continue
        parts = rest.split("\\")
        if len(parts) == 2 and parts[1] == "packs":
            packs.setdefault(parts[0], {"packs": []})
            continue
        if len(parts) == 4 and parts[1] == "packs" and parts[3] in ("filename", "sign", "size"):
            name = parts[0]
            idx = int(parts[2].strip("[]"))
            entry = packs.setdefault(name, {"packs": []}).setdefault("packs", [])
            while len(entry) <= idx:
                entry.append({})
            field = parts[3]
            text = value.decode("utf-8", "replace").strip("\" ")
            entry[idx][field] = int(text) if field == "size" and text.isdigit() else text

    manifest = {
        name: {"stamp": stamps.get(name), "packs": info.get("packs", [])}
        for name, info in sorted(packs.items())
    }
    (args.out / "cdn-packs.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    names = sorted(manifest)
    with (args.out / "cdn-packs.tsv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("pack\tstamp\tpack_parts\ttotal_size\n")
        for name in names:
            parts = manifest[name]["packs"]
            total = sum(p.get("size", 0) or 0 for p in parts if isinstance(p.get("size"), int))
            fh.write(f"{name}\t{manifest[name]['stamp']}\t{len(parts)}\t{total}\n")

    def bucket(prefix_re: str) -> list[str]:
        rx = re.compile(prefix_re)
        return [n for n in names if rx.fullmatch(n)]

    groups = {
        "monsters_M###": bucket(r"M\d{3}"),
        "chapters_N###": bucket(r"N\d{3}"),
        "stages_ST###": bucket(r"ST\d{3}"),
        "cards_C###(+variant)": [n for n in names if re.fullmatch(r"C\d{3}[A-C]?", n)],
        "card_Q": [n for n in names if re.fullmatch(r"C\d{3}[A-C]?_Q", n)],
        "card_EFT": [n for n in names if re.fullmatch(r"C\d{3}[A-C]?_EFT", n)],
        "card_SND": [n for n in names if re.fullmatch(r"C\d{3}[A-C]?_SND", n)],
    }
    (args.out / "cdn-pack-groups.json").write_text(
        json.dumps(groups, indent=1), encoding="utf-8"
    )
    print(f"packs={len(names)} -> {args.out}")
    for g, v in groups.items():
        print(f"  {g}: {len(v)}  {v}")


if __name__ == "__main__":
    main()