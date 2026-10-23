# Mirage Village entry: exact bindings and cache lifecycle

2026-10-23 source-only correction. Original ELF SHA256:
`c4646ac3817b0008b6ea387fde9c8279fd439343ccc272acdc5883fab9d00eec`.
G addresses below are file/code offsets plus0x10000. No current Mirage
activation, input, private-save access, APK patch or DataDump write occurred.
Root reports the new validation is waiting for a usable restored window.

## Original Village button and exact title-child gate

The original upper-house handler is `CSRPopUpVillage::OnButtonUpperHouse`
Gdafa7c. Its Mirage candidate compares **BT_RD**, CRC32 **0x3ea2b713**,
with high hash word0. It tests the rectangle of the cast at Village+0x7f8
against the stored touch coordinate+0x8cc. An inside overlap blocks only
when that cast's byte+0x270 is0. It then requires
`IsNameTagVisible(BUTTON3)` to return nonzero before calling
`EnterHouse(type0xb9)`. This is not a coordinate recipe.

The separate `MainTabUpVillage` Gea42c4 also recognizes BT_RD. It finds
**BT_TEMPLE** as the overlap-blocking cast, not as proof that BT_TEMPLE is
the Mirage destination. Do not infer a Mirage button from the anvil, a
question mark or an overlapping building's name.

The earlier source note left the title child's identity unresolved. Fresh
original Thumb inspection closes it: BUTTON `IsNameTagVisible` Gdb042c
selects the house pair at `Village+0x770+BUTTON*8`, then loads exact
**PA_TITLE** with LDR Gdb044c and the associated PC-relative ADD. It reads
that child's byte+0x270 at Gdb0462, returning `CLZ(byte)>>5` at
Gdb04a6–Gdb04aa: exactly1 for byte0, otherwise0. It does not read the
separately recovered local-hidden byte+0x271. The meaning of effective
visibility must not be generalized beyond this original byte predicate.

The TU_TYPE overload Gdb0da4 is a different helper: it returns1 for tutorial
state>=2, otherwise tests `GetStageAchieveCnt(TU_TYPE)` for nonzero. That
does not replace the BUTTON3 predicate in the reviewed upper-house branch.
`EnterHouse` Gdb0200 plays FX_WALKING and delegates scene change. The
complete scene-factory identity for0xb9 was not independently closed here.

## TU37 is a selector, not a literal mission number

MainTabUpVillage's stage test passes TU_TYPE **0x25 /37**. The original
`CSRStaticData::GetStageID` Gf42820 compares the selector with0x30 and
uses TBB at Gf4282a. Its table starts at **Gf4282e**; index37 selects
arm **Gf428ba**, whose LDR/ADD resolves exact **n_01_10**.
As an independent indexing control, index35 selects Gf428d0→n_02_03,
matching the previously recovered Episode prerequisite.

Therefore this native selector maps to **Snowfield10**, not mission37.
Original help record CONTENTS9_8 independently says normal stage27 in
KO/JA/SC/TC, while its current desc1.EN is missing. That text does not
override the directly recovered native selector. This audit does not explain
the version/path discrepancy or assert one universal gate for every entrance.
No manual tutorial/achievement rewrite is justified.

## Strongest prior native navigation evidence

DataDump `findings/hunters/mirage-village-door-review-20261010.md` records
root-owned native navigation: ordinary Search opens the red NPC0023;
after advancing/settling dialogue, the third option explicitly says
“I want to challenge the Mirage Ruins!” and opens native Mirage Floor0.
Home returned to Village, with all three saved games unchanged in that
historical test. This is prior native evidence, not a fresh input or proof
that historical coordinates still match the current window.

That recorded NPC choice is stronger practical navigation evidence than an
unverified current building coordinate. Select a fresh visible matching
choice; do not substitute a direct scene jump or a guessed anvil/question
mark hitbox.

## Current resource readiness and separate local policy

The reviewed170-group compatible restoration profile includes MIRAGE.jet,
ST002.jet, LEVELING.jet, C003/C003_Q/C003_EFT/C003_SND and CFE_PUB.jet.
Server's enabled/restored Mirage run preflight checks original resource
sizes/hashes, package layout and coherent stamps. Merely selecting art does
not enable a Mirage policy or establish native rendering.

MIRAGE_BG_G is the separate lobby background field. Battle environment
selection matches postfix002 against digits in original STI002 ENV prefixes
(keys2/15), subject to an actual stage-row override. Original COMMON supplies
D/C/B/A/E layer prefixes; their ST002 AT→S2→I2 dependencies are pinned.
MRG+002 independently supplies the stair UI resource MRG002. Do not equate
the lobby bg_res string with the battle environment selector.

Root's proposed floor1/three-stair policy, enemy003 rank3/EXP0 and skill
levels1/1/1/0/0, grade0, balance10000, gold0, empty dialogue and no rotation
bonus are explicit **LOCAL content**, not original floor/balance/reward data.
No such policy was activated by this source audit.

## Native cache chain and durable GetInfo caveat

`CSRExploreMirageInfo::RequestInfo` G92b30c sends `/mirage/GetInfo`.
The ordinary entry caller can request reset0/stay0/mask31; existing native
cache owners can toggle already-loaded section bits. GetInfo success parses
entry/base/enemy/stair/hero independently. The configured Server's first
valid nonreset call can **persist a run and enrollment**, choosing supported
existing char_id families under explicit rank/EXP/ID local policy, assigning
carried HP10000 and unentered sentinel−1, with an initially empty Mirage deck.
This is durable gameplay commitment, not a read-only empty lobby or a grant
of Hunters, rank, EXP or currency.

RegisterDeck G92fed0 posts `inst_list`, a JSON string of ordered full64 owned
IDs, omitting zero slots. The supported UI has five slots, living-gauge and
duplicate-char_id-family checks. Success ret_data is a **bare numeric ID
array**; it does not enroll or heal Hunters. The real registered Mirage
party remains separate from ordinary formation.

Confirm BT_NEXT at Gc033dc checks nonzero owned deck IDs and remaining HP,
then enters native scene0x81 at Gc03640/Gc0364e directly. This bounded path
does **not** issue a `/mirage/Begin` request. `MakeStageInst` G925798 consumes
the cached party, enemy and selected stair; balance10000 scales to1.0 using
the native divisor10000. Absence of Begin is expected, not a stalled server.

Configured End binds the captured floor/stair/party/camps and persists carry;
victory enables the explicit Reward step. Reward with configured gold0 still
advances the stair and supplies its next enemy/cache data. Completion releases
the captured party only through the supported lifecycle. Do not publish empty
entry/deck, use reset fallback, or overwrite carried HP merely to leave a scene:
Parse_Entry arrays actively reset native owned Mirage HP before applying rows.

Acceptance remains native entry, enrollment/deck qualification, actual cached
battle, carried-HP settlement, zero-gold advancement and eventual release.
No successful current Mirage battle or restored original economics is claimed.
