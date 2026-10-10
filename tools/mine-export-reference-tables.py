"""Export the recovered Blustone *_RO.db reference tables to analysis/recovered-data/.

Read-only against recovered-assets/. Writes JSON/TSV evidence under
analysis/recovered-data/leveldb-tables/.

Usage:
  python mine-export-reference-tables.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

CI = Path(r"C:\Users\shaha\Documents\ChatGPT\Blustone\analysis\leveldb-tooling-ci")
sys.path.insert(0, str(CI))
import plyvel  # type: ignore  # noqa: E402

GAME_ASSETS = Path(
    r"C:\Users\shaha\Documents\ChatGPT\Blustone\recovered-assets"
    r"\phone-2026-09-18\game-assets"
)
OUT_DEFAULT = Path(r"C:\Users\shaha\Documents\ChatGPT\Blustone\analysis\recovered-data\leveldb-tables")

TABLES = [
    "SKILL_REF_RO", "SKILL_TAG_RO", "SKILL_EFFECT_RO", "SKILL_DESC_RO",
    "TAG_REF_RO", "CHAR_STR_RO", "INGAME_TALK_RO", "ADMIN_ID_RO",
    "UI_EPISODE_RO", "UI_TEXT_RO", "UI_JSON_RO", "UI_XML_RO", "BADWORD_RO",
]


def read(name: str) -> dict[str, bytes]:
    db = plyvel.DB(str(GAME_ASSETS / (name + ".db")), create_if_missing=False)
    try:
        return {k.decode("utf-8", "replace"): v for k, v in db}
    finally:
        db.close()


def maybe_json(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    summary = {}
    raw_rows = {}
    for name in TABLES:
        rows = read(name)
        parsed = 0
        records = []
        for key, value in rows.items():
            obj = maybe_json(value)
            if obj is not None:
                parsed += 1
            records.append({"key": key, "json": obj, "raw": value.decode("utf-8", "replace")})
        raw_rows[name] = records
        summary[name] = {"entries": len(rows), "json_values": parsed}
        print(f"{name}: entries={len(rows)} json={parsed}")

    (out / "all-tables.json").write_text(
        json.dumps({"summary": summary, "tables": raw_rows}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )

    # ---- CHAR_STR_RO : the real card / character name table -------------------
    cs = raw_rows["CHAR_STR_RO"]
    chars = defaultdict(dict)
    for row in cs:
        key = row["key"]
        if "|" not in key:
            continue
        cid, field = key.split("|", 1)
        obj = row["json"] or {}
        chars[cid][field] = obj.get("EN") or obj.get("KO") or row["raw"][:120]
    with (out / "char-str.tsv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("card_id\tTITLE\tSUMMARY\tWEAPON\tARMOR\tACCESSORY\tVICTORY\n")
        for cid in sorted(chars, key=lambda s: (len(s), s)):
            c = chars[cid]
            fh.write("\t".join([
                cid,
                c.get("TITLE", ""), c.get("SUMMARY", ""), c.get("WEAPON", ""),
                c.get("ARMOR", ""), c.get("ACCESSORY", ""), c.get("VICTORY", ""),
            ]) + "\n")
    print(f"char-str.tsv: {len(chars)} ids")

    # ---- SKILL_REF_RO : the real skill formula table -------------------------
    sk = raw_rows["SKILL_REF_RO"]
    skills = defaultdict(list)
    for row in sk:
        key = row["key"]
        parts = key.split("|")
        if len(parts) != 3:
            continue
        skills[parts[0]].append((parts[1], parts[2], row["json"] or {}, row["raw"]))
    with (out / "skill-ref.tsv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("skill_id\trow\tcol\tFORMULAR\tIS_FLOAT\tSUB_SERIAL\tEN\n")
        for sid in sorted(skills, key=lambda s: (len(s), s)):
            for row_i, col, obj, raw in sorted(skills[sid]):
                fh.write("\t".join([
                    sid, row_i, col,
                    str(obj.get("FORMULAR", "")).replace("\t", " "),
                    str(obj.get("IS_FLOAT", "")),
                    str(obj.get("SUB_SERIAL", "")),
                    str(obj.get("EN", "")).replace("\t", " ").replace("\n", "\\n"),
                ]) + "\n")
    print(f"skill-ref.tsv: {len(skills)} skill ids")

    # ---- SKILL_TAG_RO --------------------------------------------------------
    with (out / "skill-tag.tsv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("skill_id\tslot\tTAG_KEY\n")
        for row in sorted(raw_rows["SKILL_TAG_RO"], key=lambda r: r["key"]):
            parts = row["key"].split("|")
            if len(parts) != 2:
                continue
            obj = row["json"] or {}
            fh.write(f"{parts[0]}\t{parts[1]}\t{obj.get('TAG_KEY', '')}\n")

    # ---- TAG_REF_RO : the effect tag vocabulary ------------------------------
    tags = {}
    for row in raw_rows["TAG_REF_RO"]:
        if "|" not in row["key"]:
            continue
        tag, field = row["key"].split("|", 1)
        obj = row["json"] or {}
        tags.setdefault(tag, {})[field] = obj.get("EN", "")
    with (out / "tag-ref.tsv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("tag\tTITLE\tDESC\n")
        for tag in sorted(tags):
            fh.write(f"{tag}\t{tags[tag].get('TITLE','')}\t{tags[tag].get('DESC','')}\n")
    print(f"tag-ref.tsv: {len(tags)} tags")

    # ---- INGAME_TALK_RO : in-battle barks, keyed by card id ------------------
    talks = defaultdict(list)
    for row in raw_rows["INGAME_TALK_RO"]:
        parts = row["key"].split("|")
        if len(parts) != 3:
            continue
        obj = row["json"] or {}
        talks[parts[0]].append({"slot": parts[1], "index": parts[2], "EN": obj.get("EN", "")})
    with (out / "ingame-talk.tsv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("card_id\tslot\tindex\tEN\n")
        for cid in sorted(talks):
            for t in talks[cid]:
                fh.write(f"{cid}\t{t['slot']}\t{t['index']}\t{t['EN']}\n")
    print(f"ingame-talk.tsv: {len(talks)} card ids")

    # ---- UI_EPISODE_RO : the real expedition area ids ------------------------
    with (out / "ui-episode.tsv").open("w", encoding="utf-8", newline="") as fh:
        fh.write("key\tEN\n")
        for row in sorted(raw_rows["UI_EPISODE_RO"], key=lambda r: r["key"]):
            obj = row["json"] or {}
            fh.write(f"{row['key']}\t{obj.get('EN', row['raw'])}\n")

    print(f"wrote to {out}")


if __name__ == "__main__":
    main()