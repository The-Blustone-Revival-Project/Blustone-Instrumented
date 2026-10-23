# E6 crash: missing CFE4 lookup in fever transition

Source-only diagnosis of the root-owned Bright bench trial. No APK patch,
runtime access, server/profile change or gameplay result is claimed here.

## Exact observed fault

`local/verification/bright-e6-exit-logcat-20261023.txt` lines336–339 reports
SIGSEGV fault0x271, ARM-PC module offset0x7782b1
`CMUpdatable::SetVisible`, ARM-LR offset0x9c298b
`CSRGameBase::SetFeverLV`, r0=0 and r1=0. The root observed no actors shortly
before exit. That visual observation does not alone identify UI teardown.

Immutable original ELF
`local/legacy-analysis/extracted/lib/armeabi-v7a/libnative_core.so` SHA256:
`c4646ac3817b0008b6ea387fde9c8279fd439343ccc272acdc5883fab9d00eec`.
Addresses prefixed G below are file/code offsets plus0x10000; Thumb PCs have
their low bit set. G7882b0 is `ldrb.w r0,[r0,#0x271]`, exactly explaining
fault0x271 for a null receiver. This is a read before SetVisible can write.

The return address pins the failing call to G9d2986, the first
`SetVisible(false)` in SetFeverLV's requested-level2 branch. G9d2982 loads
r0 from stack+0x30. That is the transient shared_ptr returned by a
`FindCastByName<CSRUIImageNode>` lookup at G9d28de, with literal **CFE4**
constructed using LDR G9d28ce / ADD G9d28d0. Its companion lookup at
G9d28b8 requests **CFE3_B** (LDR G9d28a8 / ADD G9d28ac) into stack+0x50.
Neither lookup is checked before the level2 false-visibility calls.

This is a missing CFE4 image-node lookup result, not a null Bright actor,
selected-healer record, or skill coefficient. The method had requested
level2 and entered its visual-update branch, which requires its second
argument to equal1 at G9d289c–G9d289e.

## Owner and lifetime boundaries

Both lookups search beneath `game+0x2c`, the UI root pointer; its shared control
is `game+0x30`. `CSRGameBase::OnInit` obtains `CMUIView::GetRoot` at G9c1866
and retains its object/control at G9c1884/G9c188c. Existing qualified host
observer source separately checks this root's runtime name as
`SR_INGAME/INGAME_NM` in `episodeExchangeUiSnapshot`.

`CSRGameBase::OnRefresh` G9d0ec4 compares UI `GetFeverRank` with cached
`game+0x208` and calls SetFeverLV on change, passing `(game+0x2ec != 1)`.
The retained source is DataDump
`sources/native/revival/ghidra-complete-12-dead-deadgroup.txt` lines572–577.
SetFeverLV stores the new cached rank only at G9d2a68, after these UI accesses.

The crash proves the name/type lookup returned null. It does not distinguish
an initially absent resource-created node from a previously removed node or
a wrong/currently clearing root. A dangling root would not itself be proved
by the null lookup result. No live root lifetime snapshot was taken by this
source audit.

## Concrete original-resource gap

The imported original UI_XML_RO rows461/462 are
`KO/SR_INGAME/INGAME_MR` and `KO/SR_INGAME/INGAME_NM`; both contain the
original CFE4 and CFE3_B animation declarations. The existing +15 source seed
`assets/instrumented-seed-episode-ui-delta-v1/UI_XML_RO.db/000031.ldb`
also contains `EN/SR_INGAME/INGAME_NM`, raw17709 bytes, SHA256
`8d528457f446be3ca1503948cb282d747bb400afabce3cfd296ca8de645ec1fe`, including:

```xml
<animation res-name="CFE3_B" play="2" visible="f"/>
<animation res-name="CFE4" play="2" pos="250,0" align="left, center" visible="false">
```

These were read with bounded host SST/WAL parsers without opening LevelDB.
The served Server UI tree's compressed records were skipped by that limited
parser, so this report does not claim to have read current native/live UI bytes.
The original and packaged-seed declarations rule out a source-seed omission
as the first explanation.

Both original AT resources are in **CFE_PUB.jet**, already imported publicly
under Server `resources/runtime/assets/`. Exact provenance ledger size281615,
SHA256 `bae718faf6aa7f1b5f6f868ea77db78e3fc8f0770999729fa64dc1b99e4b7f8b`.
The allowed read-only DataDump extracted asset is byte-identical. Strict JET
traversal reaches exact EOF281615. CFE4 has3 AT frames referencing
CFE_401/402/403 S2 resources, whose29 image entries all resolve within the
same pack with matching image hashes. CFE3_B has4 frames and4 corresponding
local S2/image joins, likewise verified.

At audit time, Server's exact139-group
`current-e6-materials-compatible-progression.json` does **not** select
CFE_PUB.jet and declares no folded extras. This is a concrete missing original
resource package capable of explaining a null resource-created image node.
It is stronger than attributing the crash to Bright healing or teardown alone.

## Minimal future fix and acceptance

Prefer a separately prepared Server resource profile adding the exact original
CFE_PUB package, retaining all prior groups/settings and advancing the three
coherent resource stamps beyond every existing profile. Verify emitted PKGI1,
MD5/SHA bytes and same-pack dependencies, then validate a fresh native boot
and the actual CFE4/CFE3_B nodes before a guarded fever-level2 transition.
Preserve saves, expected stage and prompt ordinary attack behavior.

Successful rendering/loading is not proof that the crash is fixed: repeat the
actual transition and inspect a terminal/no-crash outcome. If the lookup still
fails, qualify the current root and node lifetime/loader result before choosing
a patch. An APK null guard is not justified as the first repair while this
original-resource omission remains. No original ELF, seed, APK or runtime was
modified by this audit.
