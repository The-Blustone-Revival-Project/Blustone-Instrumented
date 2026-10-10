"""Narrow the stage table to the identifiers the game actually ships.

Adding the `N001` scheme changed the client's behaviour from "asserts and
aborts" to "processes the records and throws `std::out_of_range: vector`" - so
the identifiers now resolve, and the fault is a bounds error while indexing, not
a missing entry any more. The crash's stack candidates sit in the libstdc++
`num_get` region, i.e. numeric parsing, which fits the client walking a record
list whose length disagrees with a count it derived.

Keeping 432 records across twelve schemes gives the parser far more chances to
disagree with a count. The PAD pack ships exactly these node resources:

    N001 .. N013, N500 .. N502

so publish only those sixteen, with the recovered `n_01_01` kept as the alias
the origin area links to. This is a much smaller table to reason about, and the
client either resolves an N-id or it does not - either way the answer is
unambiguous.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "bootstrap.ts"

OLD = """const STAGE_ID_SCHEMES: ((area: number, stage: number) => string)[] = [
  // The scheme the game's own assets use: N + three digits, with N001..N013
  // and N500..N502 recovered from the PAD resource pack. Kept first because it
  // is the only one backed by real files rather than a guess.
  (_area, stage) => `N${String(stage).padStart(3, "0")}`,
  (_area, stage) => `n${String(stage).padStart(3, "0")}`,
  (area, stage) => `n_${String(area).padStart(2, "0")}_${String(stage).padStart(2, "0")}`,
  (area, stage) => `n_${area}_${stage}`,
  (area, stage) => `n_${area}_${String(stage).padStart(2, "0")}`,
  (area, stage) => `n_${String(area).padStart(2, "0")}_${stage}`,
  (area, stage) => `${area}_${stage}`,
  (area, stage) => `${area}_${String(stage).padStart(2, "0")}`,
  (area, stage) => `st_${String(area).padStart(2, "0")}_${String(stage).padStart(2, "0")}`,
  (area, stage) => `st_${area}_${stage}`,
  (area, stage) => `s_${area}_${stage}`,
  (area, stage) => `${area}${String(stage).padStart(2, "0")}`,
];

const STAGE_SWEEP_AREAS = 3;
// 1..13 and 500..502 are the node numbers the PAD pack actually ships; the rest
// of the range is a harmless cushion.
const STAGE_SWEEP_STAGES = 12;

export const starterStages = {
  // CSRGameStage::SetStage indexes the top-level `stage` collection before
  // parsing each record. A bare array leaves the native stage table empty,
  // which later reaches CSRSyncMStage::RequestStart with an empty ID.
  stage: STAGE_ID_SCHEMES.flatMap((scheme, schemeIndex) =>
    Array.from({ length: STAGE_SWEEP_AREAS * STAGE_SWEEP_STAGES }, (_, n) => {
      const area = Math.floor(n / STAGE_SWEEP_STAGES) + 1;
      const stage = (n % STAGE_SWEEP_STAGES) + 1;
      return stageRecord(scheme(area, stage), schemeIndex * 1000 + n);
    }),
  ),
};"""

NEW = """/** Node identifiers the recovered PAD resource pack actually ships. */
const PAD_NODE_IDS = [
  ...Array.from({ length: 13 }, (_, i) => `N${String(i + 1).padStart(3, "0")}`),
  ...Array.from({ length: 3 }, (_, i) => `N${String(500 + i).padStart(3, "0")}`),
];

/** The one identifier recovered from `CSRStaticData::GetStageID`. */
const RECOVERED_STAGE_ID = "n_01_01";

export const starterStages = {
  // CSRGameStage::SetStage indexes the top-level `stage` collection before
  // parsing each record. Publish only the sixteen node identifiers the game
  // ships, plus the recovered `n_01_01`: an earlier twelve-scheme sweep of 432
  // records made the client resolve a node and then throw
  // `std::out_of_range: vector` while indexing, so a short, exact table is both
  // more likely to work and far easier to reason about.
  stage: [
    ...PAD_NODE_IDS.map((stageId, index) => stageRecord(stageId, index)),
    stageRecord(RECOVERED_STAGE_ID, PAD_NODE_IDS.length),
  ],
};"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "PAD_NODE_IDS" in src:
        print("already narrowed")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"anchor found {src.count(OLD)} times")
    TARGET.write_text(src.replace(OLD, NEW), encoding="utf-8")
    print(f"stage table narrowed in {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
