# Current battle AUTO modes and manual bench skills

Source-backed operating distinction: **DASH/type1 is the candidate for automatic
ordinary attacks while retaining manual skill and exchange control.** Full
AUTO/type2 installs native skill/exchange AI. No live DASH selection, mode
transition, manual heal or new battle was verified in this investigation.
Root's earlier AUTO clicks and tiny screenshot labels do not establish a mode.

All native addresses use original ELF SHA256
`c4646ac3817b0008b6ea387fde9c8279fd439343ccc272acdc5883fab9d00eec`;
G addresses are file/code offsets plus0x10000. No UI/device/runtime/private-save
access, APK patch, setting write or implementation change occurred here.

## Actual ordinary/Mirage handler and mode cycle

CSRGameBase.OnTouch G9d72fc recognizes current named panels, not a held AUTO
gesture. Its source transitions are:

- Clicking **PA_AUTO_OFF** persists type2, hides OFF and shows ALL; emits
  native protocol22 with JSON `type:2`.
- Clicking **PA_AUTO_ALL** persists type1 at G9d734c, hides ALL and shows
  PA_AUTO_DASH; emits protocol22 with `type:1`.
- Clicking **PA_AUTO_DASH** persists type0 at G9d73b0, hides DASH and shows
  PA_AUTO_OFF; emits protocol22 with `type:0`.

Thus the current cycle is **OFF0→ALL2→DASH1→OFF0**. The visible panel is
the current state; pressing it selects the next state. No fourth AUTO+ state
or minimum hold time was found in this handler. Separate PA_X1/PA_X2 and
PA_SPEED_LOCK branches control speed; arrows alone do not identify AUTO mode.

The handler returns early when game+0x140 pause is nonzero and bit0x10 is
clear. A normal paused HUD can be inspected, but changing AUTO under that pause
is not established. Do not change pause masks. Read/prepare while paused, then
use the admitted ordinary UI when resuming; verify a real transition instead
of assuming the paused contact worked.

PA_AUTO_LOCK displays a toast from exact key
`먼저 %d스테이지를 클리어해야 합니다.` at G9d7478, formatting
GetStageSerial(TU_TYPE0x2b). Original GetStageID's TBB table Gf4282e
index43 selects Gf428ee→n_01_06. This closes the lock toast's Snowfield6
identity, not every producer of the initial lock panel. No forced unlock is
authorized or needed by this source report.

## What native automation actually does

CSRGameNet.OnProcAutoPlay Ga10a1c parses the type and calls
CSRGameBase.SetAuto(camp0,type) at Ga10a84. SetAuto G9d9b1c has distinct
type1/type2 paths. Type2 creates CSRGameActorHunterAuto, wires its skill and
exchange events at G9da1de/G9da20e, sets its actor at G9da22a and installs
it as the `run` back-state at G9da248. Type1 replaces that behavior with a
plain CActorStateHandler at G9da63c–G9da684. Original vtables independently
identify those exact classes; this is not inferred from an AUTO caption.

HunterAuto.OnUpdate G98f4da checks source stun, then attempts automatic
exchange at G98f4f2. If that does not complete an exchange, it tails into
OnUpdateSkill at G98f504. Both have further liveness, cooldown, HP/role,
Rage/skill and target predicates; full AUTO is not guaranteed to heal at a
chosen instant. It can choose exchanges and spend Rage without a manual tap,
so it can invalidate a planned healer-on-bench setup.

Automatic ordinary attacks have a separate draw-group control:
CSRGameActorGroupDraw.RunnerAutoAtk G9a686c checks its word+0x84c
nonzero at G9a6882, its additional byte+0x848 gate, current runner and attack
admission, then invokes OnProcLeftActorClick at G9a68c2.
OnProcToggleAuto G9a99f4 stores the parsed toggle at draw-group+0x84c
at G9a9ad0. A probe must qualify that exact draw-group owner before using
these offsets; they are not fields of CSRGameBase or the model group.

This separates automatic attacks from HunterAuto's skill/exchange AI.
Type1/DASH is therefore the source-backed mode to qualify for manual bench
healing. Keep ordinary attack bursts prompt until actual automatic attack
cadence is verified in the selected native mode; do not infer combat progress
from a rotating icon.

## Persistence and an important older-UI trap

The current handler calls CSRUserDB.PutBattleAutoCombat with
**game+0x2ec MODE**. Put G1098edc/Get G1098ff4 use the UserDB namespace
plus **BATTLE_AUTOCOMBAT**; MODE1 uses the base key, other modes append their
decimal mode value. The field is exact **enable**. This is client-local
per-mode persistence, not an account server-profile grant or a global rule
that all battle families share the same selected state.

ReqMonsterRefCB G9c9ae4 checks HasBattleAutoCombat at G9c9c84, initializes
an absent setting to0 at G9c9c98, reads it at G9c9ca8 and shows the matching
panel in its 0/1/2 branches G9c9d96/G9c9e0c/G9c9dd2.
No single direct current-mode word in CSRGameBase was closed by this audit.

There is another, older implementation: CSRPopUpGameBase.OnButtonClick
Gc3cf40 cycles BT_AUTO with `(toggle+1)%3`; it stores its value at
**that popup+0x658**. CSRGameUI.SetAutoToggle Ga326e0 drives LY_MANUAL,
LY_AUTO_TAB and LY_AUTO_ALL. Those fields/layers are not a valid shortcut
readout for the current ordinary/Mirage CSRGameBase.OnTouch implementation.
Do not read game+0x658 as a mode or apply the older click order.

## Source display readout for a future qualified HUD probe

The independent read-only art lane identified original UI_XML_RO row468,
KO/SR_INGAME/UI_LYR_NM, raw XML SHA256
`d7b4d78385751bcc1cc1b131825f0c4c0c9013abb84e4ddb0b9f1291dad6a908`:

Source owners are Server
`resources/reference/recovered-data/leveldb-tables/all-tables.json` and
read-only DataDump
`sources/client-tables/recovered-data/leveldb-tables/all-tables.json`.
Their whole-file bytes match SHA256
`f166f857d45c6dd68e97bd4b8f055be795796400fa10ba9f040aaa1b1d8f0a78`.

- UI_NORMAL/AUTO_TOGGLE/PA_AUTO_ALL uses rotating AUTO2_T and textbox
  AUTO_AUTO; its EN UI_JSON text is **AUTO**,14px.
- PA_AUTO_DASH uses the **same** rotating AUTO2_T and textbox AUTO_TAP;
  its EN UI_JSON text is **TAP**,16px.
- PA_AUTO_OFF uses static AUTO2_F and no textbox.

Original INGAME_NM row462, raw SHA256
`cbaa8506d069cd102fdb9d42473ae51562bb3139622f84902b8bbafd5f714e16`,
supplies the UI anchor rect VIEWER→panel UICamera→rect UI_ROOT
(visible=true)→rect UI (visible=false). This is not the fever path
MainCamera/RUNNER_ROOT. Runtime attachment of UI_LYR_NM's fragment beneath
that anchor was not directly verified, so a future observer must qualify the
actual child chain and unique names rather than concatenate guessed pointers.

For qualified panels, report both effective/inherited hidden byte+0x270 and
local-hidden byte+0x271, plus ancestor visibility. SetVisible G7882a0 writes
the local byte+0x271 at G7882c8; effective visibility can settle later in the
frame. InvalidateVisible G78891e computes byte270 from parent270 OR local271;
DrawAll G7861f8 returns when270 is nonzero. Do not infer a mode from one stale byte, a hidden ancestor or only a
caption. A stable exclusive ALL/DASH/OFF panel selection, matching native
setting/behavior where qualified, is stronger evidence. Root did not see TAP
or verify DASH during this turn.

## Manual heal versus manual swap

Skill activation is **one press/DOWN on the actual opaque skill bubble**.
CSRGameUIIconSkill.OnProcessCursorPress Ga3c178 requires press=true,
enabled byte+0x6c, intersection with drawable+0x60 bounds and dispatches
opacity-derived byte at Ga3c1c4. Actor listener G9f7604 requires actor+0xa7d
enabled and received byte exactly255 at G9f7640–G9f764a. No hold duration
is tested in this activation path. Holding is not a source-backed remedy for
a missed or dim icon, and body dragging is a different action.

Bomber/support roles3/4 use skills from an eligible bench/airship position.
Front-related states3/4/8 cause alpha128 at G97d7b0–G97d7ce; that fails
the listener's 255 check. A healer moved to the front is not a valid manual
bench-heal target merely because its portrait or a translucent bubble exists.
Offense/Defense skill taps may exchange the clicked Hunter to the front before
reserving the skill; do not confuse that skill-induced exchange with a drag.

Other admission remains real: funded native Rage, nonempty effects, source
stun/cooldown, visible live opposing actor, game-state bit4 and no incompatible
reserve/background pause. Correction to older notes: Supporter skips the
**additional same-camp front-stun** check (G9f78a6–G9f78b8); source stun
is still unconditional. A normal paused icon snapshot is not input-time proof
of these conditions. Do not alter costs, flags or HP to force admission.

Manual exchange instead captures a bench actor body on phase1 through
CatchActor G9db698, moves that same pointer using its captured offset, then
uses ExchangeActor G9db990 on the same-contact release, subject to the actual
opened exchange target and source/front eligibility. Skill bubble bounds do
not establish body capture bounds or a valid drop zone. Confirm the resulting
front/bench identities and catch cleanup; a visible drag alone proves neither.

The next bounded control should qualify mode and bench healer before resuming,
use a fresh actual bubble hit point with one ordinary paired tap when funded,
and verify skill acceptance/Rage debit/application while keeping attacks
prompt. Long observer pauses or historical/scaled coordinates are not a fast
reaction strategy. No new native control success is claimed by this document.
