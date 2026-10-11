# Boutique guard placement: context-specific24-byte candidate

No library or APK was modified. The original28-byte signed-zero proposal stays
separate. This new24-byte variant is valid only at the pinned original UInt32
denominator conversion site; it does not claim general negative-zero handling.
Future application still needs root review, native validation and the required
instrumented APK release.

## Current artifact and rejected first candidate

The final retained override and APK native entry share SHA-256
`759481add6592a6e46a692d37e263cef791151a4897a8f98d9eff5ba3f0b6a34`.
Its RX extent is0x210d4d0. This is retained build-output identity, not a fresh
measurement of the running installed library.

The original .plt→.text gap0x612c88..0x612cc0 has56 zero bytes, but current
gym/Search patches already occupy0x612c90..0x612cc0. Only8 bytes remain free,
so the previously examined28-byte candidate there is rejected. The older
df49f1... stage copy predates those stubs and cannot prove current placement.
The explicitly unsafe assertion-trace cave0x10da720 is never used.

##24-byte context proof

At ELF1041b46, the unchanged `vcvt.f32.u32 s4,s4` converts the target count to
positive finite float or positive zero. Only a drawable-pointer load and the
numerator multiplication follow before the VDIV hook1041b50; nothing changes
s4. Negative zero is unreachable through this pinned instruction path.

Removing the earlier sign-stripping LSL therefore saves4 bytes without changing
any reachable native behavior. The20-byte body preserves r2, SP/LR/APSR and
other VFP registers; a4-byte return branch produces a24-byte stub. Positive
denominators run the exact original VDIV. Positive zero yields finite width0
without a manufactured bonus row.

## Bounded executable padding evidence

The candidate is ELF/file0x1d52928..0x1d52940, exactly24 zero bytes between
.ARM.extab's end and .rodata's32-byte-aligned start. Neither neighboring section
is code, so there is no sequential instruction fallthrough into the gap.
It is already inside the unchanged RX PT_LOAD; no program header, section,
relocation, address, page mapping or symbol-table extension is needed. Hook and
return are both within Thumb B.W range.

For the exact current artifact:

- No section or dynamic symbol, including zero-sized/data symbols, overlaps.
- All24 bytes remain zero; current patch payloads do not occupy the span.
- No absolute ARM/Thumb pointer word at any byte offset targets the span.
- Overapproximated ARM and Thumb direct branch scans of .text/.plt find no
  targets, including32-bit conditional branches and CBZ/CBNZ.
- Independent ARM PC-relative ADR and bounded Thumb literal-plus-PC address
  scans found no derived address/data references.
- No loader relocation writes overlap, and no resolved local relocation target
  reaches the candidate. The exact artifact's only relocation kinds are
  ARM_RELATIVE23(128620), GLOB_DAT21(32), ABS32(13), JUMP_SLOT22(379).
- ARM exception-table pointer scans find no genuine relative reference.

A whole-word PREL31 overapproximation reports one apparent target1d52930 from
word1d4df30. Its owning generic extab record starts1d4df20. After personality
and unwind words, bytes`ff ff 01 26` at1d4df2c mean omitted landing-pad base,
omitted type table, ULEB call-site encoding and38-byte table length. The next
bytes`00 4a 00 00` decode call-site start0, length74, landing-pad0, action0.
That word is a call-site tuple, not a PREL31 pointer. The tool pins this exact
classification and refuses any additional or changed relative hit.

These are bounded static gates, not universal proof against arbitrary computed
indirect jumps or malicious memory corruption. Runtime Houdini execution and
native UI rendering remain unverified. The tool never marks the cave approved
for live execution.

## Proposal tool and tests

New files are `boutique-zero-width-guard-u32.s`,
`prepare-boutique-zero-width-guard-u32.py` and their separate unittest. The tool
accepts only the pinned final artifact, validates exact surrounding context and
padding structure/xrefs, assembles the20-byte body and emits proposal JSON to
stdout. It has no library-write interface and sets native_library_modified and
cave_proven_for_live_execution false.

Body:`04b412ee102a12b900ee102a01e080ee020a04bc`.
At the proposed addresses, hook B.W:`10f1ea96`; return B.W:`eff60a91`.
Both are decoded back to their requested addresses immediately.

Four tests pass with actual Unicorn Thumb/VFP execution. They execute the
original UInt32→F32 conversion and numerator multiplication before the hook,
compare36 positive combinations across three FPSCR settings and two simulated
ASLR bases, and check zero-result/register/flags behavior. Current-artifact
SHA/context/static-placement gates pass; original input SHA remains unchanged
and modified input refuses. The earlier four28-byte tests also remain separate.

Before any application, review this bounded proof and final patch diff, verify
the running baseline identity, integrate only the intended hook/cave bytes into
an instrumented copy, publish a new regular Latest APK release, and perform
native Boutique/positive-progress/save-preservation validation with explicitly
authorized game control. No fake bonus, costume grant or price is needed.
