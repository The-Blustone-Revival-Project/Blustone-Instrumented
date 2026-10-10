"""Rewrite AGENTS.md section 11 with the proven native schemas and current state."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "AGENTS.md"

NEW = """## 11. STATUS 2026-10-02: game boots; expedition map populated; battle start next

**The pre-login stall is fixed and the expedition map is now driven by replica
data.** Read `analysis/ghidra-setstage-exact.txt` and
`analysis/2026-10-02-cdn-stall-findings.md` alongside this.

### What the client does now

launcher -> shared secret -> reslist -> `/v2/account/Login` -> 23 MB data
download prompt -> full lobby bootstrap -> village (AP 47/50, Mail, Supply) ->
Airport (`1/30`) -> Isla's dialogue -> *cruise* -> Expedition Area ->
**Snowfield stage map, reading `3/9` progress, nodes labelled `3`/`6`/`9`, and
star-rated chapter shields** -> battle preparation.

### How the schemas were actually recovered

The JSON keys are no longer guessed. A new Ghidra script,
`analysis/ghidra-scripts/ResolvePcRelativeStrings.java`, models the Thumb
`ldr [pc,#imm]` + `add pc` pattern through Ghidra's instruction API and reads
each literal from Ghidra's *relocated* memory (the on-disk value is a
pre-relocation placeholder, which is why reading the .so directly gives
garbage). Output: `analysis/ghidra-setstage-exact.txt`.

Do not trust the `DAT_xxxx` labels in the older dumps - they are not
literal-pool pointers and do not dereference to strings.

    CSRGameStage::SetStage  (0xa274d0)
      ret_data            <- indexed DIRECTLY as an array
        .id               <- the identity field
        .ap_cost .character_exp .gold .group_exp .enemy_atk_per .enemy_hp_per
        .power .title .desc .res_prefix .thumb .story_id .begin_dialog_id
        .end_dialog_id .achieve_condition .order .type .value .item

    CSRGameStage::SetArea  (0xa28108)
      ret_data.area[]      .id .type .serial .level_limit .title .desc
                           .dialog_id .resource_id .explore_id
        .area[i].stage[]   <- NESTED per area: {area_id, stage_id, serial}
      ret_data.achieve_reward[]  .area_id .achieve_cnt .gold .free_iap .iap
                                 .item_list[].id .qty  .card_list[].id .qty

Two shape bugs fell out of this, and they explain every earlier symptom:

1. `/reference/GetStage` returned `{stage:[...]}`. The client indexes `ret_data`
   itself and type-dispatches, so an object never built the stage table at all.
   It is now the **bare array**, keyed on `id`. `gold`, `order`, `type`,
   `value` and `item` were also being read and were missing.
2. `/reference/GetArea` put the area->stage links at the top level. The client
   reads `area[i].stage[]`. **Both forms are now sent**: the nested form is what
   the decompile shows, and the top-level array is what brings the chapter
   shield markers back. Drop the top-level one only once the marker is
   understood.

`GetStageData(string)` confirms the layout: a linear scan of the stage vector,
stride `0xac`, comparing the string at `+0x1c` - matching `GetStageIDList`.

### GetStage wants an array, GetArea wants an object

That is why an earlier combined bare-array experiment regressed the village
progress denominator to `0/42949667266`. The revert note was right about
GetArea and wrong to conclude the same for GetStage. Both experiments and both
reverts are kept as scripts with their evidence.

### Real stage identifiers

The recovered PAD resource pack
(`recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets`) ships
`N001.jet`..`N013.jet`, `N500`..`N502`, `STAGE.jet`, `MISSION2.jet`. The stage
table is published as exactly those sixteen ids plus the recovered `n_01_01`.
`MISSION2.jet` is textures, not text data - do not re-check it.

### Experiments that were tried and reverted

| Experiment | Result | Kept as |
|---|---|---|
| 180 stages over 10 naming schemes | no change to the empty `stage_id` | reverted |
| same 180 under 6 container keys + count fields | no change | reverted |
| bare array for GetArea | denominator `0/42949667266` | reverted |
| mission catalogs as JSON objects | no change to `0/0`, removed the shield | reverted |
| mission catalogs as arrays (kept) | current state | - |

### Next step

`Begin Battle` should now resolve a real `stage_id`; confirm it on the wire
with `BLUSTONE_LOG_GAME_VALUES=1` (it logs
`/reference/GetTargetStageMonster {"stage_id":...}`). Then shape
`/mission/Start` and `/mission/Complete` to the recovered parsers:
`analysis/native-mission-complete.txt` has `CSRSyncMStage::ReqCompleteCB`
(0xb426ac) decompiled; the start-side callback is a lambda inside
`RequestStart` (0xb39d2a). `ResolvePcRelativeStrings.java` will read its keys the
same way.

`tools/walk-to-stage.ps1` drives the whole path and screenshots each step.

"""


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    start = src.index("## 11. STATUS")
    end = src.index("## 12. Community notes")
    TARGET.write_text(src[:start] + NEW + src[end:], encoding="utf-8")
    print("AGENTS.md section 11 rewritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
