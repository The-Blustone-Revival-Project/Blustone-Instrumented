"""Return the stage and area tables as bare arrays, not objects.

The object form has now been ruled out exhaustively: 180 stage records under six
container keys (`stage`, `stages`, `list`, `stage_list`) plus `total_cnt`/`cnt`/
`count` all produced a 504 KB response, and the client's stage table was still
empty - `CSRSyncMStage::RequestStart` kept asserting `sStageID.size() > 1` and
sending `"stage_id":""`.

The workspace notes record that this family of parsers consumes an array directly
and iterates it numerically (`GetCardInven`, `GetStage`, `BlockList`), and that
wrapping them in metadata objects caused native `Cannot find Ref Data` crashes.
An earlier session reached the opposite conclusion for GetStage ("a bare array
leaves the native stage table empty") and wrapped it in `{stage:[...]}`; that
conclusion is what this change reverses.

`ret_data` becomes the array itself. The envelope still carries `data`, so any
caller reading the alias sees the same value.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "game-routes.ts"

OLD_STAGE = """  if (route === "/reference/GetStage") {
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
  }"""

NEW_STAGE = """  if (route === "/reference/GetStage") {
    // Bare array. The container-key sweep proved the object form wrong: 180
    // records under six keys still left the client's table empty. This parser
    // family reads ret_data as an array and indexes it numerically.
    return state.envelope(starterStages.stage);
  }"""

OLD_AREA = '  if (route === "/reference/GetArea") return state.envelope(starterAreas);'
NEW_AREA = """  if (route === "/reference/GetArea") {
    // Bare array, for the same reason as GetStage.
    return state.envelope(starterAreas.area);
  }"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "Bare array." in src:
        print("already bare arrays")
        return 0
    for old, new in ((OLD_STAGE, NEW_STAGE), (OLD_AREA, NEW_AREA)):
        if src.count(old) != 1:
            raise SystemExit(f"anchor found {src.count(old)} times: {old[:50]!r}")
        src = src.replace(old, new)
    TARGET.write_text(src, encoding="utf-8")
    print(f"bare-array forms applied to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
