"""Size the card inventory from BLUSTONE_PARTY_SIZE, cloning the one real card.

`/lobby/GetCardInven` currently publishes a single instance while the deck
switch (`partyDeck`) can reference inst_id 1..N. Without matching instances the
extra slots have nothing to resolve, which is the same empty-ref-id failure the
switch is meant to diagnose.

Every clone carries the same `ref_id` ("001") on purpose: card 001 is the only
card whose art the replica serves, so this isolates party size from "does the
extra card have art".

The default (unset, or 1) is byte-identical to the current single instance.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "bootstrap.ts"

OLD = '''/** One starting card instance. */
export const starterInventory = [{
  inst_id: 1, ref_id: "001", rank: 1, rank_up_cnt: 0,
  overcome_cnt: 0, exp: 0, lock: 1, regdate: 0, mirage_remain_hp: 1000,
  equipment_exp: 0, awk_step: 0, awk_overcome: 0,
  weapon_rank: 1, weapon_level: 1, armor_rank: 1, armor_level: 1,
  accessory_rank: 1, accessory_level: 1, skill_1_level: 1, skill_2_level: 0,
  skill_3_level: 0, skill_4_level: 0, skill_5_level: 0,
  skin_ref_id: "", skin_id: "", skin_total_count: 0,
}];'''

NEW = '''/**
 * Card instances.
 *
 * `MakeStageInst` builds a battle participant per deck slot and calls
 * `CSRCard::SetRefID` with the instance's ref_id, so every slot needs an
 * instance that resolves to a real card.
 *
 * `BLUSTONE_PARTY_SIZE` (see `partyDeck` in state.ts) clones this instance that
 * many times. Every clone uses the same `ref_id`, because card 001 is the only
 * card whose art the replica serves - that keeps the experiment about party
 * size rather than about art. Default 1: exactly the previous single instance.
 */
const PARTY_SIZE = Math.max(1, Math.min(5, Number(process.env.BLUSTONE_PARTY_SIZE) || 1));

export const starterInventory = Array.from({ length: PARTY_SIZE }, (_, n) => ({
  inst_id: n + 1, ref_id: "001", rank: 1, rank_up_cnt: 0,
  overcome_cnt: 0, exp: 0, lock: 1, regdate: 0, mirage_remain_hp: 1000,
  equipment_exp: 0, awk_step: 0, awk_overcome: 0,
  weapon_rank: 1, weapon_level: 1, armor_rank: 1, armor_level: 1,
  accessory_rank: 1, accessory_level: 1, skill_1_level: 1, skill_2_level: 0,
  skill_3_level: 0, skill_4_level: 0, skill_5_level: 0,
  skin_ref_id: "", skin_id: "", skin_total_count: 0,
}));'''


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "PARTY_SIZE" in src:
        print("inventory already follows the party size")
        return 0
    if src.count(OLD) != 1:
        raise SystemExit(f"inventory anchor found {src.count(OLD)} times")
    TARGET.write_text(src.replace(OLD, NEW), encoding="utf-8")
    print("inventory now follows BLUSTONE_PARTY_SIZE (default unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
