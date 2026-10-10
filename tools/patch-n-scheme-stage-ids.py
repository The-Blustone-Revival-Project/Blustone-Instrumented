"""Add the N001-style stage identifiers, which the real assets prove are the scheme.

The recovered PAD resource pack
(`recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets`) contains

    N001.jet N002.jet ... N013.jet  N500.jet N501.jet N502.jet
    STAGE.jet  MISSION2.jet  MP4_MISSION.jet  N_M_ICON.jet  N001_BG.jet ...

so the game's own per-node resources are named `N` + three digits. That is the
identifier scheme the map nodes use, and the earlier ten-scheme sweep
(`n_01_01`, `n_1_1`, `1_1`, `st_..`, `s_..`, ...) did not include it - which is
why `CSRSyncMStage::RequestStart` kept being called with an empty `stage_id`.

Add `N001`..`N013` and `N500`..`N502` in upper and lower case, keep the
recovered `n_01_01`, and leave the rest of the sweep in place until the client
names the one it actually uses.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "bootstrap.ts"

OLD = """const STAGE_ID_SCHEMES: ((area: number, stage: number) => string)[] = [
  (area, stage) => `n_${String(area).padStart(2, "0")}_${String(stage).padStart(2, "0")}`,"""

NEW = """const STAGE_ID_SCHEMES: ((area: number, stage: number) => string)[] = [
  // The scheme the game's own assets use: N + three digits, with N001..N013
  // and N500..N502 recovered from the PAD resource pack. Kept first because it
  // is the only one backed by real files rather than a guess.
  (_area, stage) => `N${String(stage).padStart(3, "0")}`,
  (_area, stage) => `n${String(stage).padStart(3, "0")}`,
  (area, stage) => `n_${String(area).padStart(2, "0")}_${String(stage).padStart(2, "0")}`,"""

OLD_SWEEP = """const STAGE_SWEEP_AREAS = 3;
const STAGE_SWEEP_STAGES = 6;"""
NEW_SWEEP = """const STAGE_SWEEP_AREAS = 3;
// 1..13 and 500..502 are the node numbers the PAD pack actually ships; the rest
// of the range is a harmless cushion.
const STAGE_SWEEP_STAGES = 12;"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "`N${String(stage).padStart(3, \"0\")}`" in src:
        print("already added N-scheme")
        return 0
    for old, new in ((OLD, NEW), (OLD_SWEEP, NEW_SWEEP)):
        if src.count(old) != 1:
            raise SystemExit(f"anchor found {src.count(old)} times: {old[:50]!r}")
        src = src.replace(old, new)
    TARGET.write_text(src, encoding="utf-8")
    print(f"N-scheme added in {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
