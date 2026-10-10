"""Add a switchable party size so the 5x SetRefID can be isolated.

`MakeStageInst` reads a card instance (ref_id, rank, rank_up_cnt, overcome_cnt,
exp, skill_1..5_level, rival_pvid) and calls `CSRCard::SetRefID` with it. Five
assertions is one per battle slot, so the client is trying to build five
participants.

Filling the deck with five instances of five DIFFERENT cards was tried twice and
produced a bare native fault at the end of the lobby bootstrap. The obvious
variable not yet isolated is whether that fault came from the four extra cards
having no art - only card 001's family is served - rather than from the party
size itself. So clone the one card that does have art, N times.

The default (BLUSTONE_PARTY_SIZE unset or 1) is byte-identical to the previous
behaviour, so this is safe to have present while another test is in flight.

    $env:BLUSTONE_PARTY_SIZE = '5'
    . /tools/start-server.ps1
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "state.ts"

OLD_DECK = (
    "      deck: [{ type: 1, inst_id_1: game.leader_inst_id, "
    "inst_id_2: 0, inst_id_3: 0, inst_id_4: 0, inst_id_5: 0 }],"
)
NEW_DECK = "      deck: partyDeck(game.leader_inst_id),"

HELPER = '''/**
 * The five-slot deck.
 *
 * `CSRSyncMStage` builds five battle participants and `MakeStageInst` calls
 * `CSRCard::SetRefID` with each instance's ref_id, so a slot that cannot be
 * resolved to a card asserts. `BLUSTONE_PARTY_SIZE` fills the remaining slots
 * with extra instances of the same card, so the experiment does not also
 * depend on art that the replica is not serving.
 *
 * Default 1: leader only, exactly as before this switch existed.
 */
function partyDeck(leaderInstId: number): Array<Record<string, number>> {
  const size = Math.max(1, Math.min(5, Number(process.env.BLUSTONE_PARTY_SIZE) || 1));
  const slot: Record<string, number> = { type: 1 };
  for (let index = 0; index < 5; index += 1) {
    slot[`inst_id_${index + 1}`] = index < size ? leaderInstId + index : 0;
  }
  return [slot];
}

'''

CLASS_ANCHOR = "export class ServerState {"


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "partyDeck" in src:
        print("party switch already present")
        return 0
    if src.count(OLD_DECK) != 1:
        raise SystemExit(f"deck anchor found {src.count(OLD_DECK)} times")
    src = src.replace(OLD_DECK, NEW_DECK)
    if src.count(CLASS_ANCHOR) != 1:
        raise SystemExit("class anchor not unique")
    src = src.replace(CLASS_ANCHOR, HELPER + CLASS_ANCHOR)
    TARGET.write_text(src, encoding="utf-8")
    print("BLUSTONE_PARTY_SIZE switch added (default behaviour unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
