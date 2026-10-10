"""Revert GetStage/GetArea to the object form.

The bare-array experiment was a regression and is reverted.

`/reference/GetArea` as a bare array broke area parsing outright: the village
progress denominator became `0/42949667266` (an unsigned 0xFFFFFFF2), i.e. the
area records were not read at all. With the object form the same screen showed a
sane `Airport 0/30` and, after a mission, `1/30`.

So this parser family does read an object here, and the earlier conclusion in
`bootstrap.ts` was right after all. The bare-array theory came from a workspace
note generalising `GetCardInven`/`BlockList` to `GetStage`; that generalisation
was wrong for these two routes.

Kept from the experiments, because both are independently evidenced:
  - areas keyed on `area_id` (the native SRGameStage.cpp key cluster)
  - the widened stage_id scheme sweep, so the client can resolve whichever
    identifier its map node uses
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "game-routes.ts"

OLD_STAGE = """  if (route === "/reference/GetStage") {
    // Bare array. The container-key sweep proved the object form wrong: 180
    // records under six keys still left the client's table empty. This parser
    // family reads ret_data as an array and indexes it numerically.
    return state.envelope(starterStages.stage);
  }"""
NEW_STAGE = """  if (route === "/reference/GetStage") {
    // Object form with the `stage` collection. A bare array was tried and is
    // wrong here: it broke the area/stage tables outright. 180 records under six
    // container keys also failed to populate the client's table, so the
    // remaining unknown is the stage identifier the map node uses, not the
    // container.
    return state.envelope(starterStages);
  }"""

OLD_AREA = """  if (route === "/reference/GetArea") {
    // Bare array, for the same reason as GetStage.
    return state.envelope(starterAreas.area);
  }"""
NEW_AREA = """  if (route === "/reference/GetArea") {
    // Object form. A bare array here regressed the village progress
    // denominator to 0/42949667266, so the area records were simply not read.
    return state.envelope(starterAreas);
  }"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "Object form with the `stage` collection" in src:
        print("already reverted")
        return 0
    for old, new in ((OLD_STAGE, NEW_STAGE), (OLD_AREA, NEW_AREA)):
        if src.count(old) != 1:
            raise SystemExit(f"anchor found {src.count(old)} times: {old[:50]!r}")
        src = src.replace(old, new)
    TARGET.write_text(src, encoding="utf-8")
    print(f"reverted to object form in {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
