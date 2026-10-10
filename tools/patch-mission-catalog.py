"""Feed every known stage identifier into the mission-instance catalogs.

`CSRTutorialMStageMap::OnInit` builds its AREA_ACHIEVE_INFO and STAGE_INFO maps
from the two catalogs in `/lobby/GetMissionInst`, then looks the tapped node's
stage up in STAGE_INFO. That catalog currently carries a single hard-coded
`{stage_id:"n_01_01", achieve:3}` row, so any node whose identifier differs
resolves to nothing and `CSRSyncMStage::RequestStart` is called with an empty
`stage_id` - which is exactly the assertion it raises.

The stage table is already a sweep over ten identifier schemes (180 entries).
Publish all of those identifiers here too, so whichever one the map node uses
resolves. `BLUSTONE_SKIP_MISSION_TUTORIAL=1` remains the gate, because without
it these catalogs are the newbiew empty fixture.

Once the client names the stage it wanted, collapse this back to one row.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "state.ts"

OLD = """      return this.envelope({
        area_achieve: [
          { area_id: "n_01", achieve_cnt: 3 },
          { area_id: "n_00", achieve_cnt: 3 },
        ],
        stage: [
          { stage_id: "n_01_01", achieve: 3 },
        ],
        mission: game.missions,
        missions: game.missions,
      });"""

NEW = """      return this.envelope({
        area_achieve: [
          { area_id: "n_01", achieve_cnt: 3 },
          { area_id: "n_00", achieve_cnt: 3 },
        ],
        // Every identifier in the stage table, not just one row. The stage map
        // resolves a tapped node through this catalog, and a node whose
        // identifier is missing here is sent to RequestStart with an empty
        // stage_id. The table is a deliberate scheme sweep, so the catalog
        // mirrors it until the client names the real identifier.
        stage: starterStages.stage.map((stage) => ({ stage_id: stage.stage_id, achieve: 3 })),
        mission: game.missions,
        missions: game.missions,
      });"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "Every identifier in the stage table" in src:
        print("already widened")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"anchor found {src.count(OLD)} times")
    src = src.replace(OLD, NEW)
    if "starterStages" not in src.split("export class")[0]:
        src = src.replace(
            'import { starterAreas,',
            'import { starterAreas, starterStages,',
            1,
        )
    TARGET.write_text(src, encoding="utf-8")
    print(f"mission catalog widened in {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
