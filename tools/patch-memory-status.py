"""Rewrite AGENTS.md section 11 with the 2026-10-02 resolution."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "AGENTS.md"

NEW = """## 11. STATUS 2026-10-02: the game boots; one specific bug remains

**The pre-login stall is FIXED. The client now runs from the title screen all
the way to the battle preparation screen.** The expedition is reachable; what is
left is a single, precisely-identified defect at mission start.

### The fix that unblocked everything

`/launcher/GetBaseInfo` was missing four `url_list` keys. `CPVDataMgr` resolves
URLs by `url_key` and the binary carries the failure string `cannot find cdn
url`, so a key the client looks up but the replica does not advertise leaves it
with no address and no request at all. We advertised `_SR`, `ad_unit_id_1`,
`d_unit_id_1`, `maintenance`, `api`, `cdn`; the working community private server
advertises `Main`, `auth`, `sns_list`, `cdn`, `resource`. `resource` is the CDN
base used to build `/<name>_<stamp>.pkg`.

All five are now advertised (the original keys stay, so nothing regressed). The
**login** response already had the right five - only the launcher response was
wrong. That asymmetry is why this was hard to see.

The client now does: launcher -> shared secret -> reslist -> `/v2/account/Login`
-> 23 MB data-download prompt -> full lobby bootstrap -> village -> Airport ->
cruise -> Expedition Area -> Snowfield -> stage map -> **Prepare for Battle**.
Airport progress reads `1/30` where it used to be `0/30`.

### The one remaining bug

Tapping Begin Battle raises:

```text
[AST] [RequestStart]
(sStageID.size() > 1) is FALSE
ASSERTION Failed on 'SRMStageSync.cpp(67)'
```

`CSRSyncMStage::RequestStart` (0xb39d2a) is called with an **empty
`stage_id`** - confirmed on the wire with `BLUSTONE_LOG_GAME_VALUES=1`, which
shows `/reference/GetTargetStageMonster {"stage_id":""}` sent immediately
before it. The client cannot resolve an identifier for the node that was tapped.

### What has been ruled out for the stage id

| Hypothesis | Test | Result |
|---|---|---|
| wrong identifier scheme | 180 stages across 10 naming schemes (`n_01_01`, `n_1_1`, `1_1`, `st_..`, `s_..`, `..`) in the stage table | still empty |
| wrong container key | same 180 under `stage`, `stages`, `list`, `stage_list` + `total_cnt`/`cnt`/`count` - a 504 KB response | still empty |
| stage table shape | bare array instead of `{stage:[...]}` | **regression, reverted** - see below |
| area not addressable | areas now keyed on `area_id` (the real native key) + `achieve_cnt` | fixed, denominators sane |
| link catalogs | `/lobby/GetMissionInst` `stage` catalog widened to all 180 ids | still empty |

**Bare arrays are wrong for `GetStage`/`GetArea`.** Tried and reverted: the
village denominator became `0/42949667266`, so the records were not read at all.
A workspace note had generalised `GetCardInven`/`BlockList` ("parsers consume an
array directly") to these two routes; that generalisation is wrong for them. The
object form is correct. Both the experiment and the revert are kept as scripts
with their evidence, so it is not re-tried.

### Confirmed native schemas (from string clusters in libnative_core.so)

These are real, not guessed - the keys exist as standalone NUL-terminated
strings in the library:

- **Stage record** (0x1d6769e-0x1d676eb): `ap_cost`, `character_exp`,
  `group_exp`, `power`, `story_id`, `begin_dialog_id`, `end_dialog_id`,
  `achieve_condition`.
- **Area record** (0x1d676fd-0x1d6773c): `area`, `level_limit`, `resource_id`,
  `explore_id`, `area_id`, `achieve_reward`, `achieve_cnt`. Identity is
  **`area_id`**, not `id`; `CSRGameStage::GetAreaData` takes an area_id.

Note there is **no id field in either cluster**, so the stage's identity key is
still unknown - that is the open question.

### Next step for the stage id

Do not sweep more identifiers. Read `CSRGameStage::SetStage` (0xa274d0) and
`SetArea` (0xa28108) properly in Ghidra - they are the only functions that build
the stage/area tables, and the answer is in how they key the records. Ghidra
project: `analysis/ghidra-project`; NDK `llvm-objdump` is at
`tools/android-sdk/ndk/29.0.14206865/toolchains/llvm/prebuilt/windows-x86_64/bin/`.
Note that Ghidra's `DAT_xxxx` refs in the existing dumps are **not** literal-pool
pointers and do not dereference to strings - the dumps are not sufficient on
their own.

Second-best option: the assertion box is now on screen and the game stays alive,
so a targeted native trace stub on `SetStage`/`SetArea` can log the key each
record is filed under.

"""

def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    start = src.index("## 11. THE CURRENT BLOCKER")
    end = src.index("## 12. Community notes")
    TARGET.write_text(src[:start] + NEW + src[end:], encoding="utf-8")
    print("AGENTS.md section 11 rewritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
