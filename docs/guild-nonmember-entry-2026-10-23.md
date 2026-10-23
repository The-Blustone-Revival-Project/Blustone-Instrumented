# Guild entry: original level gate and zero-detail query hazard

Source-only audit of the immutable final ARM ELF SHA256
`c4646ac3817b0008b6ea387fde9c8279fd439343ccc272acdc5883fab9d00eec`.
Addresses below use Ghidra coordinates (file/code offsets plus0x10000).
No runtime/device input, private save access, APK patch or Server policy edit
was performed by this audit. Root owns the separate native observations.

## Village entry admission

Original UI_XML_RO contains BT_GUILD in KO/SR_MAIN/0_SR_MN_BG and
KO/SR_N_MAIN/NEW_MAIN_2. Its CRC32 is0x60ee2579. Village OnButtonClick
matches that value at Gdaf624–Gdaf630, calls GetUserLevel at Gdaf63c and
compares with4 at Gdaf640; BHI at Gdaf642 admits level5 or higher.
The denied path loads exact localized key `길드_입장조건_미달_토스트`
using LDR Gdaf64a / ADD Gdaf650. Original EN text:
“Only those at level 5 or higher can enter.”

Above that gate, it gets current GVG phase at Gdaf766–Gdaf76e and compares
against cached Village+0x674. Equality calls EnterHouse(scene0x66) at
Gdaf77e–Gdaf782; a changed phase refreshes through RequestInst. Its exact
route literal is `/gvg/GetInst` at Ga9f8ba, so that read can precede entry.
No chapter/progress/tutorial check occurs in this inspected normal Guild
button branch. This does not exclude a separate introduction/tutorial flow.
BT_GVG_DESC is a distinct button (CRC0x2f90521c), with a different level5
and tutorial-type0x26 path; do not conflate it with BT_GUILD.

The gate uses TEAM/account level, not Hunter level. The published original
account EXP thresholds remain unknown. Root's opt-in LOCAL linear curve
reinterprets already-earned1500EXP as level16 without granting EXP; that is
not original threshold evidence.

## Nonmember discovery resources and reads

CSRPopUpGuild.OnInit Gc60b64 loads exact `GUILD/G_T_SCENE` via literal
Gc60b68. CSRTabGuildApply.Init Gfac414 loads `GUILD/G_T_APPLY` via
Gfac42e, calls LoadView at Gfac4ec and RequestRecommandList at Gfac5d8.
The latter sends `/guild/GetRecommendations` with auth fields only. The exact
read response is success1 with `ret_data:{guilds:[]}` for an empty corpus,
not a bare array or null. Original empty-result localization at Gfacfa4 is
`협회를 찾을 수 없습니다.` → EN “Guild cannot be found.”

The personal lobby data must remain explicit no-affiliation
`my_guild:{guild_id:0,status:0,newbie:0,role:0,contribution:0}`. Null does not
establish a cleared native cache. Recommendations/ranking and existing
original GUILD art do not create membership or authorize Found/Apply/payment.
The factory's complete tab-mask selection was not closed by this bounded
audit; the Apply initialization/request chain above is exact once selected.

## Native source can request the no-association ID0

The previous Server detail parser's positive-only IDs are replica policy,
not a native RequestInfo validation rule. A concrete zero producer is
CSRTabGuildInfo.UpdateData Gfb766c. It calls
CSRGuild.GetMyGuildPlayData at Gfb7748/Gfb774c, loads its guild_id lowword
at Gfb7750, forces the highword0 at Gfb777c, then calls LoadAsync at
Gfb7780. There is no zero-ID check on that path. Info.Init itself calls
UpdateData at Gfb7434.

CSRGuild.LoadAsync Ga68b84 retains its uint64 input as sb/r8 and constructs
a singleton list at Ga68d40–Ga68d52, storing both words into node+8 at
Ga68d4e. It calls RequestInfo at Ga68d7e. RequestInfo Ga68e94 serializes
that list into a JSON array string under singular form key `guild_id`, then
posts `/guild/GetDetailInfo` (see Server guild-detail native contract).
Thus UpdateData with no-affiliation0 can produce `[0]`; an original zero
request is not evidence of a Guild instance whose identity is0.

Other LoadAsync callers also exist, including Guild thumbnails and selected
rows. This source proof does not claim a decoded root-owned live request
uniquely identified UpdateData as its emitter. It proves the exact own-zero
producer and transport path needed to explain a no-member preload.

## Empty success is not a harmless no-member acknowledgment

The exact RequestInfo callback accepts success1 plus `ret_data.guilds:[]`
and emits an empty INFO list. That alone does not prove the transitive caller
is safe. LoadAsync's `$_5` callback is linked through primary vtable0x214eb74,
callable slot+0x18→ELF0xa730a5/Ga830a4. It zero-initializes a complete INFO
at Ga830c8–Ga8313e. It copies the first returned INFO only when status1
**and list count is nonzero**, Ga83140–Ga8314c. Empty success keeps the
default INFO while preserving success1. Ga83244–Ga83256 dispatches that
status and INFO to registered waiting callbacks.

GuildInfo.UpdateData's waiting callback is linked through primary
vtable0x217f7cc, slot+0x18→ELF0xfb2f99/Gfc2f98. It accepts status1 at
Gfc2fc6–Gfc2fc8, copies the default INFO at Gfc2fdc, then calls SetGuildRole,
SetSortType and ArrangeData at Gfc2fec/Gfc2ff6/Gfc3002. It subsequently
calculates Guild level and performs native local Guild-level bookkeeping.
Failure instead takes the error/toast branch Gfc3064 onward.

ArrangeData calls CalcLevel, adds1 and unconditionally calls GetGuildLevelRef
at Gfba568–Gfba582. Existing recovered GetGuildLevelRef Ga7fe00 copies the
numeric reference list head before any empty-list check at Ga7fe2a–Ga7fe46.
With an empty Guild level reference table, that head is the sentinel rather
than valid LEVEL storage. Therefore success with emptyguilds can enter
Guild INFO rendering and a known invalid-reference boundary; it is not a
proved native-safe no-association completion. No crash from this hypothetical
success response was induced by this audit.

Decision: **retain zero-query refusal**. Do not broaden all Guild IDs to0,
fabricate INFO0, fabricate a level table, or replace this failure with empty
success without closing every transitive no-member callback. A later fix must
address native no-association semantics and reference safety together.

## Root-owned native result and remaining scope

Root reports the exact level5 toast was observed, then native MyInfo level16
under the explicit local curve. Original Guild bar, Join Guild empty discovery
and ranking all rendered. The observed GetRecommendations/Ranking reads
succeeded with empty collections; detail query refused. Only tutorial33 and
AP/BP clocks changed; affiliation, fees, wallet, progress and roster did not.
These are root-owned observations, not additional inputs by this author.
Joined Guild INFO, creation, payment and original level/benefit data remain
separate unresolved work.
