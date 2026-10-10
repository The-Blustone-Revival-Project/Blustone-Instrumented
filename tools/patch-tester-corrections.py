"""Correct two things the tester found, both of which invalidate earlier work.

1. The deck has FOUR slots, not five.
   `/mission/Start` sends `deck_inst_id_1..4` and there is no `_5`, yet the
   client builds five actors. `partyDeck` was writing an `inst_id_5` the client
   never sends, so the switch could not have tested what it claimed to.

2. The area's stage links are indexed by a ONE-BASED serial.
   Observed: chapter shield "1" resolves `N002`; chapter shield "3" resolves an
   EMPTY stage_id and then asserts `SRMStageSync.cpp(67)`. The links were
   published with serials 0,1,2, so shield 1 hit serial 1 and shield 3 fell off
   the end. That is exactly the observed behaviour, and it means the serials
   should be 1,2,3.

Both are evidence from the client, not guesses. The serial change is a real
behaviour change: shield 3 will now resolve N003 instead of nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "server-ts" / "src" / "bootstrap.ts"
STATE = ROOT / "server-ts" / "src" / "state.ts"

OLD_LINKS = """    stage: [
      { area_id: "n_00", stage_id: "n_01_01", serial: 0 },
      { area_id: "n_01", stage_id: "N001", serial: 0 },
      { area_id: "n_01", stage_id: "N002", serial: 1 },
      { area_id: "n_01", stage_id: "N003", serial: 2 },
    ] }],"""

NEW_LINKS = """    // The chapter shields index these by a ONE-BASED serial. Evidence: shield
    // "1" resolved N002 (serial 1) while shield "3" resolved an empty stage_id
    // and asserted, which is what 0-based serials 0,1,2 produce.
    stage: [
      { area_id: "n_00", stage_id: "n_01_01", serial: 1 },
      { area_id: "n_01", stage_id: "N001", serial: 1 },
      { area_id: "n_01", stage_id: "N002", serial: 2 },
      { area_id: "n_01", stage_id: "N003", serial: 3 },
    ] }],"""

OLD_PARTY = """  const slot: Record<string, number> = { type: 1 };
  for (let index = 0; index < 5; index += 1) {
    slot[`inst_id_${index + 1}`] = index < size ? leaderInstId + index : 0;
  }
  return [slot];"""

NEW_PARTY = """  // Four slots, not five: `/mission/Start` carries `deck_inst_id_1..4` and no
  // `_5`, even though the client builds five actors. The fifth is implicit on
  // the client's side, so publishing `inst_id_5` would have been a key the
  // client never sends.
  const slot: Record<string, number> = { type: 1 };
  for (let index = 0; index < 4; index += 1) {
    slot[`inst_id_${index + 1}`] = index < size ? leaderInstId + index : 0;
  }
  return [slot];"""


def main() -> int:
    changed = []
    for path, old, new in ((BOOTSTRAP, OLD_LINKS, NEW_LINKS), (STATE, OLD_PARTY, NEW_PARTY)):
        src = path.read_text(encoding="utf-8")
        if new.split("\n")[0].strip()[:40] in src:
            changed.append(f"{path.name}: already corrected")
            continue
        if src.count(old) != 1:
            raise SystemExit(f"{path.name}: anchor found {src.count(old)} times")
        path.write_text(src.replace(old, new), encoding="utf-8")
        changed.append(f"{path.name}: corrected")
    print("; ".join(changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
