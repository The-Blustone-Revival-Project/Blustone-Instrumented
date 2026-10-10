"""Widen the reconstructed stage table.

`CSRSyncMStage::RequestStart` asserts `sStageID.size() > 1`
(SRMStageSync.cpp(67)) and the client sends `"stage_id":""`, so its stage table
lookup is failing for the node the player tapped. `GetStage` is fetched with no
filter - the client takes the whole table - so the number of entries is not the
problem; the *identifier scheme* is.

Rather than keep guessing one ID, publish a table that covers the schemes the
map could be using, so the client resolves whichever one its node references.
This is a diagnostic widening, not a claim about the real content: mark it so
it can be narrowed once the client tells us which ID it wanted.

The decisive read is which stage the client then selects; once it sends a
non-empty stage_id, replace the sweep with just the schemes that resolved.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "bootstrap.ts"

OLD = '''export const starterStages = {
  // CSRGameStage::SetStage indexes the top-level `stage` collection before
  // parsing each record. A bare array leaves the native stage table empty,
  // which later reaches CSRSyncMStage::RequestStart with an empty ID.
  stage: [{
    // The native lookup key is `stage_id`; keep `id` as a compatibility alias
    // for the debug/fixture contract and assert that the two stay aligned.
    id: "n_01_01", stage_id: "n_01_01", ap_cost: 1, gold: 10,
    character_exp: 10, group_exp: 10, enemy_atk_per: 100, enemy_hp_per: 100,
    power: 1, title: "First Expedition", desc: "Local compatibility test encounter",
    res_prefix: "ST001", thumb: "ST001", story_id: "", begin_dialog_id: "",
    end_dialog_id: "", achieve_condition: "[]", item: []
  }],
};'''

NEW = '''/**
 * One stage record.
 *
 * The native lookup key is `stage_id`; `id` is kept as a compatibility alias
 * for the debug/fixture contract and the two must stay aligned.
 */
function stageRecord(stageId: string, serial: number) {
  return {
    id: stageId, stage_id: stageId, ap_cost: 1, gold: 10,
    character_exp: 10, group_exp: 10, enemy_atk_per: 100, enemy_hp_per: 100,
    power: 1, title: "First Expedition", desc: "Local compatibility test encounter",
    res_prefix: "ST001", thumb: "ST001", story_id: "", begin_dialog_id: "",
    end_dialog_id: "", achieve_condition: "[]", item: [], serial,
  };
}

/**
 * Identifiers the mission map could be using for its stage nodes.
 *
 * `n_01_01` is the one recovered from `CSRStaticData::GetStageID` and is the
 * only one that was published until the client proved it did not match the node
 * it was asked to play: `CSRSyncMStage::RequestStart` asserts
 * `sStageID.size() > 1` and the request went out with an empty `stage_id`.
 * The remaining schemes are guesses at the real naming, published so the client
 * can resolve whichever one its node actually uses.
 *
 * This is a deliberate diagnostic sweep, not recovered content. Once the
 * client names the ID it wants, keep only that scheme.
 */
const STAGE_ID_SCHEMES: ((area: number, stage: number) => string)[] = [
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
const STAGE_SWEEP_STAGES = 6;

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
};'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "STAGE_ID_SCHEMES" in src:
        print("already widened")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"anchor found {src.count(OLD)} times")
    TARGET.write_text(src.replace(OLD, NEW), encoding="utf-8")
    print(f"widened stage table in {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
