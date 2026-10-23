# Fishing cache repair and practice-fish thumbnail boundary

Source-only investigation of original ARM ELF SHA256
`c4646ac3817b0008b6ea387fde9c8279fd439343ccc272acdc5883fab9d00eec`.
G addresses are file/code offsets plus0x10000. No implementation, game input,
runtime/private-save access, original/DataDump edit or APK build occurred.
This narrows the prior cold-cache-only statement; it does not establish full
native response-loss recovery or a newly recovered original fish catalogue.

## Why ordinary reads and view reloads cannot repair these caches

CSRMFishing's owned-count tree starts at model+0x04, count+0x0c; its record
tree starts at+0x10, count+0x18. GetInvenInfo Gb2ffcc and GetRecordInfo
Gb30008 expose each matched node's shared object/control at node+0x1c/+0x20.
The INVENTORY object has b/s/g counts at+0/+4/+8. RECORD has grade/length
at+0/+4. These are separate from general owned item-instance stacks.

GetInven's ParseInven Gb2d038 constructs a candidate and looks up its fish
key at Gb2d296. If that key already exists, Gb2d29e/Gb2d2a0 branches
to Gb2d2f2 without replacing the old value. GetRecord's ParseRecod
Gb2c5b8 likewise skips replacement at Gb2c7c8/Gb2c7ca→Gb2c820.
Empty replies clear neither map; duplicates are first-insert-wins.

There is also request suppression after a successful load: RequestRecord
checks model byte0 at Gb2beae–Gb2beb4; its success callback sets that byte1
at Gb2c482. RequestInven checks byte+0x46 at Gb2c92e–Gb2c934; its
success callback sets it1 at Gb2cf02. Merely clearing these flags would still
leave the insertion-only maps unchanged on the next response.

The bounded original ClearView Gb26ab0 releases cached view/list state;
ReloadView Gb2f18c reconstructs UI holders. ChangePlace Gb267f0 replaces
place settings then calls ResetFishing Gb2951c, which resets the current
minigame/task state. None of these inspected bodies clears both owned-count
and record trees. No existing UI cache-invalidation path was proved. A cold
native model remains a separate hydration option, not an in-session repair.

## Existing receiver seam: an explicitly partial End replay

Ordinary ReqEndCB Gb2a308 accepts success1, removes the **current** UserDB
consume marker at Gb2a33a–Gb2a34a, calls ParseEnd at Gb2a468, then
optionally calls ParseSell for nonnull `ret_data.sell` at Gb2a478–Gb2a47e.
Failure10203/10204 can clear consume but skips both parsers, explaining why
the existing terminal-cleanup response cannot repair missing cached results.

ParseEnd's true fish_id/grade/length invokes AddInven at Gb2ae3a and
UpdateRecord at Gb2ae46. UpdateRecord replaces grade and length only if
the incoming length is strictly longer; equality preserves both. ParseSell's
`sell_result` invokes UpdateInven at Gb2b2a2–Gb2b2ba, whose existing-key
path Gb2ee34–Gb2ee56 replaces all three counts absolutely.

These consumers permit a possible **LOCAL partial fish-count/record repair**
receipt for an already committed, exact owner/log outcome. It would retain
only that log's true fish/grade/length, omit additive user.item/card and other
progression changes, use consumed_inst_list:[], and attach a no-economic
sell subreceipt with item:[] and one complete **CURRENT** owner count row.
No sale, currency or stock settlement is performed by constructing this
projection. The transient AddInven+1 is then replaced by authoritative counts.

`user.item` is not mandatory: its null/nonempty guard starts at Gb2a9c6;
null or[] skips AddItem. Do not send the original positive `added` receipt or
original bait/removal deltas again. ParseSell initializes model+0x80 sale gain
to0; missing/null user.gold skips the absolute wallet update and delta
calculation through Gb2b122. Omitting that branch is safer than replaying an
old gold balance. Its item removal list is independently optional/empty-safe.

Required limits before implementing such a receipt:

- Use current b/s/g counts, including genuine sales since the original End.
  Old receipt counts can resurrect sold stock **in the native cache**.
- Replay the actual journaled length/grade. This repairs a missed record only
  when that true catch supplies the missing maximum. If the authoritative
  longest came from another older missed catch, replaying a later shorter
  catch does not repair it. Never invent a longer length or different grade.
- Native maximum updates cannot lower an already erroneous longer record.
  This is not authoritative replacement of arbitrary record corruption.
- Refuse a stale End while any newer cast is pending. Success removes the
  current consume marker, not a marker correlated to the response's log.
  Duplicate in-flight responses can still race with later casts; Server-only
  count idempotence does not prove native consume/order safety.
- There is no proved duplicate-result-popup suppression in this callback.
  Native RequestEnd with consume0 completes locally without HTTP; the usual
  lost-response case retains consume for a retry. Other overlapping/replayed
  UI paths still need native qualification.

**General inventory is not repaired by this projection.** Omitted AddItem
deltas avoid duplicate awards but do not restore a completely missed general
fish stack or bait quantity. Replaying AddItem/removal deltas can double-apply
them. General inventory requires a separately proven absolute inventory reload
such as the appropriate RefreshInven projection and native producer; no such
automatic follow-up was established here. The receipt therefore cannot be
reported as complete inventory, bait, wallet or response-loss success. Lost
standalone sale responses likewise remain outside this bounded End seam.

## Popup semantics and optional future client repair

The success popup does not test presence of `sell` to decide its fish label.
SetItemInfo Gd07620 selects the fish layout from use_type17 and loads exact
localized key `물고기를 판매하였습니다.` at Gd07dfa. It displays sale gain
from GetInfo+0x30/model+0x80 and uses model byte+1 for the new-record badge.
Thus a zero-economic subreceipt adds no newly recovered sale flag, but the
native popup's fixed sold wording is already a presentation limit for LOCAL
keep outcomes. A duplicated success callback may still redisplay a result.

A generic native repair would need an explicitly scoped client change:
existing-key parser branches above must update the existing shared objects'
numeric fields, preserving ownership/lifetime, and a proven refresh producer
must bypass the loaded flags. Clearing raw map headers is not safe ownership
cleanup. Such a change would require separate review/native validation and a
new instrumented APK release. No host memory write or APK patch is proposed
as an action by this document.

## Exact practice-fish thumbnail binding

Original CSRItemInfo.SetItem reads `thumbnail_id` at LDR Gaf00c8 /
ADD Gaf00cc, parses it at Gaf00d8/Gaf00e8 and writes the raw INFO string
at stack+0xe0. Raw INFO begins at stack+0xa8 (Gaefe88), establishing
thumbnail offset+0x38; its copy into published INFO is Gaf026e.

Success SetItemInfo loads that INFO+0x38 at Gd07c28/Gd07c2e, resolves
literal **_V** at LDR Gd07c32 / ADD Gd07c34, appends2 at Gd07c3c,
then passes the resulting name to LoadSprite. A blank thumbnail therefore
asks for `_V`, not a usable success fish sprite.
Root independently pinned the literal slot Gd07c44, word0x107cba0,
with ADD Gd07c34 resolving G1d847d8 `_V` on the same original ELF.

Bounded strict JET indexing independently verifies original FISH_LIST.jet:
562972bytes, exact EOF562972, SHA256
`ad5bedcc5cbea02dfe2a287374e70cd2261c2b5a212fdc124393ef908a19f18c`.
Both **FS001** and **FS001_V** are S2 resources with one local image whose
hash matches the referenced image. Their payload SHA256 values are respectively
`70eee5af4077a8843e333b88a6900907f7613a3f4040d34d31a8457e16730bf0`
and `b6c6e2f012e7e3ae320b54af5b7a264c85667fba3b746f0100e7c99d60a68d3e`.

An explicit LOCAL practice fish ID/name with thumbnail FS001 is therefore a
source-compatible art association after full metadata/policy validation. It is
not a recovered species→fish_id→thumbnail join, and says nothing about original
grade prices, pools, catch lengths, tuning or RNG.

## Independently recovered native casting context

Root independently verified the following original bytes against the same ELF
hash. CSRMFishing's constructor ChangePlace argument `common1` selects static
settings; it is not the actual Begin place_id. CSRSceneMFishing.OnReset
Ge6e0c8 loads exact **PLC001** using LDR Ge6e13e, literal slot Ge6e434,
word0xf1c41f and ADD Ge6e144, resolving G1d8a567. It calls SetPlaceID at
Ge6e150; setter Gb2f006 adds0x50 to select the current INFO.place_id string.
That producer supplies the practical exact server context identity without
inferring it from an NPC, static settings key or displayed place name.

StartFishing Gdf1e6c compares integer gauge values with
GetThrowDistance(1/2/3) thresholds and selects distance **1/2/3** at
Gdf237e/Gdf23bc/Gdf23fa when its corresponding valid branch is reached.
These are native selector values, not proved physical lengths, ranges in
meters, cast probabilities or a mapping from fish length to distance.

Together with the `_V` suffix and original FS001/FS001_V resources, these
facts permit a separately authored PLC001/distances1–3/LU003 practice recipe
to satisfy concrete native identity/art consumers. Every fish identity,
species label, membership, tuning, length/grade outcome and economy would
still require explicit LOCAL choices and validation. No public casting
configuration, native recipe activation or gameplay claim accompanies this doc.
