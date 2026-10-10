"""Publish the stage table under every plausible container key at once.

`CSRGameStage::SetStage` (0xa274d0) is handed the whole response JSON by
`CSRSyncRef::ReqStageCB` (analysis/native-stage-bootstrap.txt), and the client's
stage table stays empty whatever single shape we send - `CSRSyncMStage::RequestStart`
still asserts `sStageID.size() > 1` and sends `"stage_id":""`.

The per-record field names are confirmed present in the binary
(`ap_cost`, `character_exp`, `group_exp`, `power`, `story_id`,
`begin_dialog_id`, `end_dialog_id`, `achieve_condition` at 0x1d6769e-0x1d676eb),
so the records are fine; what is unresolved is the *container*. Rather than keep
guessing one name, publish the identical array under every key the library could
plausibly index, so the client finds it whichever it reads. The response is a
few hundred KB at worst and `/reference/GetStage` is fetched once at boot.

Once the client resolves a stage, keep only the key it used and drop the rest -
this is a sweep, not a schema.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "game-routes.ts"

OLD = '  if (route === "/reference/GetStage") return state.envelope(starterStages);'

NEW = '''  if (route === "/reference/GetStage") {
    // Container-key sweep. `CSRGameStage::SetStage` receives the whole response
    // and its table has stayed empty under every single shape tried, while the
    // per-record field names are all confirmed present in the library. Publish
    // the same array under each key the parser could index so it resolves
    // whichever it reads. Trim to the real key once the client names a stage.
    const stage = starterStages.stage;
    return state.envelope({
      stage,
      stages: stage,
      list: stage,
      stage_list: stage,
      total_cnt: stage.length,
      cnt: stage.length,
      count: stage.length,
    });
  }'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "Container-key sweep" in src:
        print("already swept")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"anchor found {src.count(OLD)} times")
    TARGET.write_text(src.replace(OLD, NEW), encoding="utf-8")
    print(f"stage container sweep applied to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
