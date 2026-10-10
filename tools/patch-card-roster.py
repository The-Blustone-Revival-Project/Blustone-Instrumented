"""Publish a roster of real cards with a fillable party.

The battle builds five participants and each one has to resolve to a card, or
`CSRCard::SetRefID` asserts an empty ref id. The replica published exactly one
card (`001`), so every slot that wanted anything else failed.

The recovered PAD pack carries the art for hundreds of real cards
(`C001.jet` ... `C0NN.jet`, one family each), so this publishes a roster of the
first N cards, gives the account one instance of each, and fills all five deck
slots. Card ids match the art package names, which is what the resource manager
already resolves.

Art for the roster is served by folding the same C***.jet families into the
E_NEW PKGI tree; see tools/start-server.ps1.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server-ts" / "src" / "bootstrap.ts"

ROSTER = 6

OLD_REF_START = "export const starterReference = [{"
OLD_REF_END = "}]];"
OLD_INV_START = "export const starterInventory = [{"
OLD_INV_END = "}];"

NEW = '''/**
 * Card ids match the real art package names in the recovered PAD pack
 * (`C001.jet`, `C001_Q.jet`, ...), so the resource manager can resolve a
 * card's `_A*` and `_D*` animation slots. The replica published a single
 * synthetic `001`, which is why the card art never resolved and why the
 * client's SetRefID assertions fired once per battle slot.
 */
export const CARD_ROSTER = Array.from({ length: %d }, (_, n) => `C${String(n + 1).padStart(3, "0")}`);

export const starterReference = CARD_ROSTER.map((id, n) => ({
  base: { id, char_id: id, name: "%%user_name%%", is_main: n === 0 ? 1 : 0,
    attr: (n %% 4) + 1, role: (n %% 3) + 1, res_prefix: id, is_source: 0,
    source_field: 0, cool_time: 1000 },
  thumb: id,
  id, ref_id: id,
  equipment: [], skill: [], dialog: [],
  stat: [{ rank: 1, awk_step: 0, hp: String(1000 + n * 120), atk: String(100 + n * 15),
    def: String(50 + n * 8), spd: "100", crt_chance: "5", crt_dmg: "150",
    penetration: "0", block_chance: "0", block_dec_dmg: "0", attr_enhance: "0",
    attr_resist: "0", hp_regen: "0", hp_up: "10", atk_up: "1", def_up: "1" }],
}));

/** One instance per roster card, so every deck slot can be filled. */
export const starterInventory = CARD_ROSTER.map((id, n) => ({
  inst_id: n + 1, ref_id: id, rank: 1, rank_up_cnt: 0,
  overcome_cnt: 0, exp: 0, lock: 1, regdate: 0, mirage_remain_hp: 1000,
  equipment_exp: 0, awk_step: 0, awk_overcome: 0,
  weapon_rank: 1, weapon_level: 1, armor_rank: 1, armor_level: 1,
  accessory_rank: 1, accessory_level: 1, skill_1_level: 1, skill_2_level: 0,
  skill_3_level: 0, skill_4_level: 0, skill_5_level: 0,
  skin_ref_id: "", skin_id: "", skin_total_count: 0,
}));''' % ROSTER


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "CARD_ROSTER" in src:
        print("roster already published")
        return 0

    ref_start = src.index(OLD_REF_START)
    ref_end = src.index(OLD_REF_END, ref_start) + len(OLD_REF_END)
    inv_start = src.index(OLD_INV_START, ref_end)
    inv_end = src.index(OLD_INV_END, inv_start) + len(OLD_INV_END)

    src = src[:ref_start] + NEW + src[inv_end:]
    TARGET.write_text(src, encoding="utf-8")
    print(f"roster of {ROSTER} cards published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
