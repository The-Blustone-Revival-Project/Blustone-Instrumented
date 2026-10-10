"""Update AGENTS.md section 11 with the mission-start state and the next lead."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "AGENTS.md"

NEW_TAIL = """
### Where it stops now, precisely

`tools/play-mission.ps1 [-Shoot]` runs the whole thing in one command: launch,
walk to the map, probe for the node that resolves, press Begin Battle, and print
the wire values plus the assertion counts. The node tap is *discovered* by
probing for the tap that makes the client issue
`/reference/GetTargetStageMonster`, because the map layout moves once the stage
table populates.

Verified end to end, twice, deterministically:

```text
village -> Airport -> cruise -> Snowfield map   (progress 3/9, nodes 3/6/9)
node tap  -> /reference/GetTargetStageMonster {"stage_id":"N003"}
Begin Battle -> /mission/Start {"stage_id":"N003"}
5x CSRCard::SetRefID  (SRCard.cpp:731)   sRefID.length() > 0
1x CSRGameMob::GetMonsterData (SRGameMob.cpp:38)  Cannot find MonsterData
then a native fault and the process dies
```

**The remaining defect is the card table, not the wire shape.** Five
`SetRefID` assertions is one per deck slot, which means every card the client
tries to instantiate resolves to an empty ref id - i.e. the card table is empty.
`/reference/GetCard` currently returns the array form
`[{base:{id:"001",...}, stat:[...], equipment:[], skill:[], dialog:[]}]`.

Ruled out for the card table:
- object keyed by `base.id` (same shape the monster container uses) - no change;
- publishing the monster under both `M001` and the card id `001` - cleared
  `GetMonsterData` once, and pointing the wave `ref_id` at card `001` instead of
  the monster id cut `SetRefID` from three to one, which is what identified the
  wave `ref_id` as the source of the enemy cards. Both are kept.
- populating the stage's `item` array - brought `GetMonsterData` back, reverted.

Next leads, in order:
1. `CSRCardInfoContainer::SetCard` (called by `CSRSyncRef::ReqCardCB` at
   0xf839f2) resolves **no** JSON keys of its own, so the reading is done by a
   helper it calls. Decompile the helper rather than `SetCard` itself; the
   container is a `std::map`/container keyed by card id, and the unresolved
   question is whether it iterates `ret_data` as an array of records with a
   `base` sub-object, or as an object keyed by id with the record inline.
2. The five failing slots include the one the player actually owns
   (`inst_id_1: 1`), so the card table is empty rather than the deck being
   wrong. A five-card starting team was tried and destabilised the run; the
   single-card fixture stands.
3. `GetCardInven` returns one instance with `ref_id: "001"`. If the card
   reference for `001` is not what the container files under, the instance
   resolves to nothing - check the id the container keys on, not just the field
   name.

"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    anchor = "`tools/walk-to-stage.ps1` drives the whole path and screenshots each step.\n"
    if "Where it stops now, precisely" in src:
        print("already updated")
        return 0
    if src.count(anchor) != 1:
        raise SystemExit(f"anchor found {src.count(anchor)} times")
    TARGET.write_text(src.replace(anchor, anchor + NEW_TAIL), encoding="utf-8")
    print("AGENTS.md updated with the mission-start state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
