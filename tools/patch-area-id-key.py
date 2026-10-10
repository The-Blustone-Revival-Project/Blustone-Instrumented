"""Key the area records on `area_id`, as the native parser does.

Evidence: the SRGameStage.cpp JSON key cluster in libnative_core.so
(0x1d676fd-0x1d6773c) is

    area  level_limit  resource_id  explore_id  area_id  achieve_reward  achieve_cnt

so the area record is identified by `area_id` and carries `achieve_cnt`. The
replica's fixtures used `id` instead, so `CSRGameStage::GetAreaData(area_id)`
never found a record.

That is the whole expedition blocker. With no area record, the mission map
cannot resolve which area a node belongs to, the stage lookup yields nothing, and
`CSRSyncMStage::RequestStart` asserts `sStageID.size() > 1` (SRMStageSync.cpp(67))
and the request goes out with `"stage_id":""`.

Keep `id` as a compatibility alias so nothing that reads the fixture debug
contract regresses, and add `achieve_cnt` so the progress denominator is
populated natively rather than only through the diagnostic skip.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "bootstrap.ts"

OLD = '''export const starterAreas = {
  // SetMarker deliberately hides slot 0 (origin); GetAreaData still needs
  // that slot so the first visible destination can be addressed at slot 1.
  area: [{ id: "n_00", type: 1, serial: 0, level_limit: 0,
    title: "Village", desc: "Local origin node", dialog_id: "",
    resource_id: "MAP_ZONE_1", explore_id: "" },
    { id: "n_01", type: 1, serial: 1, level_limit: 1,
    title: "Snowfield", desc: "Local expedition test area", dialog_id: "",
    resource_id: "ST001", explore_id: "" }],'''

NEW = '''export const starterAreas = {
  // SetMarker deliberately hides slot 0 (origin); GetAreaData still needs
  // that slot so the first visible destination can be addressed at slot 1.
  //
  // The identity field is `area_id`, not `id`. The SRGameStage.cpp key cluster
  // in the native library is `area, level_limit, resource_id, explore_id,
  // area_id, achieve_reward, achieve_cnt`, and `CSRGameStage::GetAreaData`
  // takes an area_id. Publishing only `id` left the area table unresolvable,
  // so the mission map could not place a node and `CSRSyncMStage::RequestStart`
  // asserted `sStageID.size() > 1` and sent an empty stage_id. `id` is kept as
  // an alias for the fixture/debug contract; `achieve_cnt` gives the progress
  // denominator natively.
  area: [{ id: "n_00", area_id: "n_00", type: 1, serial: 0, level_limit: 0,
    title: "Village", desc: "Local origin node", dialog_id: "",
    resource_id: "MAP_ZONE_1", explore_id: "", achieve_cnt: 0 },
    { id: "n_01", area_id: "n_01", type: 1, serial: 1, level_limit: 1,
    title: "Snowfield", desc: "Local expedition test area", dialog_id: "",
    resource_id: "ST001", explore_id: "", achieve_cnt: 3 }],'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if 'id: "n_00", area_id: "n_00"' in src:
        print("already keyed on area_id")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"anchor found {src.count(OLD)} times")
    TARGET.write_text(src.replace(OLD, NEW), encoding="utf-8")
    print(f"area records keyed on area_id in {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
