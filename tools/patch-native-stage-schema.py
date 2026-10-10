"""Correct the GetStage and GetArea shapes from the recovered native schema.

Resolved exactly from libnative_core.so with
`analysis/ghidra-scripts/ResolvePcRelativeStrings.java`, which models the Thumb
`ldr [pc,#imm]` + `add pc` string-reference pattern inside Ghidra (so the
relocated literal values are correct). Output kept in
`analysis/ghidra-setstage-exact.txt`.

    CSRGameStage::SetStage  (0xa274d0)
      ret_data                       <- iterated DIRECTLY as an array
        .id                          <- the identity field
        .ap_cost .character_exp .gold .group_exp
        .enemy_atk_per .enemy_hp_per .power .title .desc
        .res_prefix .thumb
        .story_id .begin_dialog_id .end_dialog_id .achieve_condition
        .order .type .value .item

    CSRGameStage::SetArea  (0xa28108)
      ret_data
        .area[]
          .id .type .serial .level_limit .title .desc
          .dialog_id .resource_id .explore_id
          .stage[]                   <- NESTED per area, not top level
            .area_id .stage_id .serial
        .achieve_reward[]
          .area_id .achieve_cnt .gold .free_iap .iap
          .item_list[] .id .qty
          .card_list[] .id .qty

Two bugs fall out of this, and they explain every symptom seen so far:

1. `/reference/GetStage` returned `{stage:[...]}`. The client indexes
   `ret_data` itself and type-dispatches on it, so an object never builds the
   stage table. Every stage lookup then missed and
   `CSRSyncMStage::RequestStart` was called with an empty `stage_id`
   (`sStageID.size() > 1`, SRMStageSync.cpp(67)).
2. `/reference/GetArea` put the area->stage link array at the top level of
   `ret_data`. The client reads it as `area[i].stage[]`, so no area ever had a
   stage list, which is why the expedition map had nothing selectable.

The identity field is `id`. `stage_id` is only used for the nested
`area[].stage[]` link records, so both are kept where each belongs.

`SetArea` still needs an object (it reads `ret_data.area`), which is why the
earlier combined bare-array experiment regressed the village progress
denominator to 0/42949667266: GetStage wants an array and GetArea wants an
object. They are not the same shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "server-ts" / "src" / "bootstrap.ts"
ROUTES = ROOT / "server-ts" / "src" / "game-routes.ts"

# ---------------------------------------------------------------- stage record
OLD_STAGE_REC = """function stageRecord(stageId: string, serial: number) {
  return {
    id: stageId, stage_id: stageId, ap_cost: 1, gold: 10,
    character_exp: 10, group_exp: 10, enemy_atk_per: 100, enemy_hp_per: 100,
    power: 1, title: "First Expedition", desc: "Local compatibility test encounter",
    res_prefix: "ST001", thumb: "ST001", story_id: "", begin_dialog_id: "",
    end_dialog_id: "", achieve_condition: "[]", item: [], serial,
  };
}"""

NEW_STAGE_REC = """function stageRecord(stageId: string, serial: number) {
  // Field set recovered from `CSRGameStage::SetStage` (0xa274d0) by resolving
  // its Thumb pc-relative string references in Ghidra. `id` is the identity the
  // native table is keyed on; `gold`, `order`, `type`, `value` and `item` were
  // being read and were missing.
  return {
    id: stageId,
    ap_cost: 1,
    gold: 10,
    character_exp: 10,
    group_exp: 10,
    enemy_atk_per: 100,
    enemy_hp_per: 100,
    power: 1,
    title: "First Expedition",
    desc: "Local compatibility test encounter",
    res_prefix: "ST001",
    thumb: "ST001",
    story_id: "",
    begin_dialog_id: "",
    end_dialog_id: "",
    achieve_condition: "[]",
    order: serial,
    type: 0,
    value: 0,
    item: [],
  };
}"""

# ------------------------------------------------------------------- area shape
OLD_AREA = """  area: [{ id: "n_00", area_id: "n_00", type: 1, serial: 0, level_limit: 0,
    title: "Village", desc: "Local origin node", dialog_id: "",
    resource_id: "MAP_ZONE_1", explore_id: "", achieve_cnt: 0 },
    { id: "n_01", area_id: "n_01", type: 1, serial: 1, level_limit: 1,
    title: "Snowfield", desc: "Local expedition test area", dialog_id: "",
    resource_id: "ST001", explore_id: "", achieve_cnt: 3 }],"""

NEW_AREA = """  // `SetArea` reads ret_data.area[] and then, per area, `stage[]` - the
  // area->stage link list is NESTED inside each area record, not a sibling of
  // `area`. Each link is {area_id, stage_id, serial}. That nesting is why the
  // expedition map had no selectable stage: the client never saw a link.
  area: [{ id: "n_00", type: 1, serial: 0, level_limit: 0,
    title: "Village", desc: "Local origin node", dialog_id: "",
    resource_id: "MAP_ZONE_1", explore_id: "",
    stage: [{ area_id: "n_00", stage_id: "n_01_01", serial: 0 }] },
    { id: "n_01", type: 1, serial: 1, level_limit: 1,
    title: "Snowfield", desc: "Local expedition test area", dialog_id: "",
    resource_id: "ST001", explore_id: "",
    stage: [{ area_id: "n_01", stage_id: "n_01_01", serial: 0 }] }],"""

OLD_AREA_STAGE_TAIL = """  // The first map scene opens on the persisted origin area (n_00), not on
  // the next area-selection marker.  Give that origin a real stage link so
  // CSRSceneMStage::OnInit has a non-empty stage list and can build the
  // first selectable node.  Keep the n_01 link as well: both routes are
  // useful while reconstructing the original area-selection progression.
  stage: [
    { area_id: "n_00", stage_id: "n_01_01", serial: 0 },
    { area_id: "n_01", stage_id: "n_01_01", serial: 0 },
  ],
  achieve_reward: [],"""

NEW_AREA_STAGE_TAIL = """  // The link list lives inside each area record now, so there is no top-level
  // `stage` here. `achieve_reward` entries are
  // {area_id, achieve_cnt, gold, free_iap, iap, item_list[], card_list[]}.
  achieve_reward: [],"""

OLD_AREA_EXPORT = """export const starterAreas = {"""
NEW_AREA_EXPORT = """export const starterAreas = {"""

# ------------------------------------------------------------------ route shapes
OLD_ROUTES = """  if (route === "/reference/GetStage") {
    // Object form with the `stage` collection. A bare array was tried and is
    // wrong here: it broke the area/stage tables outright. 180 records under six
    // container keys also failed to populate the client's table, so the
    // remaining unknown is the stage identifier the map node uses, not the
    // container.
    return state.envelope(starterStages);
  }"""
NEW_ROUTES = """  if (route === "/reference/GetStage") {
    // `SetStage` indexes `ret_data` itself and type-dispatches on it, so
    // ret_data must be the stage array directly. An object here (we used to
    // wrap it as {stage:[...]}) is never indexed and leaves the native stage
    // table empty.
    return state.envelope(starterStages.stage);
  }"""

OLD_AREA_ROUTE = """  if (route === "/reference/GetArea") {
    // Object form. A bare array here regressed the village progress
    // denominator to 0/42949667266, so the area records were simply not read.
    return state.envelope(starterAreas);
  }"""
NEW_AREA_ROUTE = """  if (route === "/reference/GetArea") {
    // Object form: `SetArea` reads ret_data.area[]. The stage links are nested
    // per area inside starterAreas.area[i].stage[].
    return state.envelope(starterAreas);
  }"""


def main() -> int:
    for path, pairs in (
        (BOOTSTRAP, [(OLD_STAGE_REC, NEW_STAGE_REC), (OLD_AREA, NEW_AREA),
                      (OLD_AREA_STAGE_TAIL, NEW_AREA_STAGE_TAIL)]),
        (ROUTES, [(OLD_ROUTES, NEW_ROUTES), (OLD_AREA_ROUTE, NEW_AREA_ROUTE)]),
    ):
        src = path.read_text(encoding="utf-8")
        for old, new in pairs:
            if src.count(old) != 1:
                raise SystemExit(f"{path.name}: anchor found {src.count(old)} times: {old[:60]!r}")
            src = src.replace(old, new)
        path.write_text(src, encoding="utf-8")
        print(f"patched {path.name}")


if __name__ == "__main__":
    raise SystemExit(main())
