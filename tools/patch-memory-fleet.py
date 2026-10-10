"""Record the proven battle-participant finding and the agent split in AGENTS.md."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "AGENTS.md"

ANCHOR = "### Next step\n"
FLEET = """### How the battle participants are built (proven from the decompile)

`MakeStageInst` (0x925798) constructs a *fresh* card and copies the ref id out
of an existing one:

```c
CSRGameActor::ACTOR_INFO::ACTOR_INFO(&local_c8);            // fresh, empty
CSRCard::SetRefID(local_94, (basic_string *)(local_44 + 0x5c));
CSRSkin::get();
CSRSkin::FindWornSkinByCardRefId(&local_e0);
```

So the five `SRCard.cpp(731)` assertions are the five deck slots, four of which
carried `inst_id = 0` and therefore had no card to copy from. The client never
calls `/mirage/RegisterDeck` in these runs - it builds the participants locally
from `/lobby/Enter` plus `/lobby/GetCardInven`.

Deck registration exists but is not on the exercised path; for the record
`RegisterDeck` posts `/mirage/RegisterDeck` with `inst_list` and `deck_info`,
and `/world/SetDeck` with `list`.

`BLUSTONE_PARTY_SIZE` (default 1, i.e. unchanged) clones the single card
instance N times and fills the deck, so the experiment separates party size from
"does the extra card have art". An earlier five-card attempt used five
different cards and produced a bare native fault, which was very likely just
four cards with no art.

### Agent split (this workspace)

Work is partitioned so nothing contends:

- **parent** owns `server-ts/src`, Ghidra (`analysis/ghidra-project` is locked
  while in use), and the emulator only when no tester is running.
- **tester agent** owns adb and BlueStacks exclusively and runs
  `tools/play-mission.ps1 -Shoot`, writing `analysis/testing/report-NNN.md`.
- **research agents** are read-only and work from the tables
  (`analysis/native-all-strings.tsv`, `analysis/native-evidence.tsv`,
  `server-ts/src/catalog.ts`), never Ghidra and never adb, each writing one file
  under `analysis/research/`.

Ghidra is a shared, locking resource and a 2 GB project, so it is deliberately
not shared. `tools/resolve-thumb-strings.py` was an attempt at a lock-free
equivalent; it is marked UNPROVEN and should not be trusted.

"""

NEW_NEXT = """### Next step

The party-size experiment is queued with the tester. After it:

1. `GetMonsterData` still misses. `AddMonster` (0xa0b540) reads `_server, title,
   attr, role, res_prefix, rank, level, overcome, hp, atk, def, crt_chance,
   crt_dmg, penetration, block_chance, block_dec_dmg, attr_enhance,
   attr_resist, hp_page, skill_start_time, skill_list, name, desc, type, effect,
   effect_type` - all of which the fixture already sends - and appears to take
   its identity from the object key, which the replica also supplies (`M001` and
   `001`). Since the lookup misses in both cases, the id the client asks for is
   neither. Next probe: publish the monster under the ids the client actually
   requests, by logging the requested id, or widen the published keys.
2. Once the battle scene opens, the campaign is
   `analysis/research/recruitment.md`, `training-supply.md`, `mail-social.md`
   and `shop-economy.md` - written by the research agents from the route
   catalog and the native string/symbol tables.

"""

def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "How the battle participants are built" in src:
        print("already recorded")
        return 0
    if src.count(ANCHOR) != 1:
        raise SystemExit(f"anchor found {src.count(ANCHOR)} times")
    src = src.replace(ANCHOR, FLEET + NEW_NEXT)
    TARGET.write_text(src, encoding="utf-8")
    print("AGENTS.md updated with the proven finding and the agent split")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
