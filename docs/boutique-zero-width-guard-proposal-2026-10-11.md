# Conditional Boutique zero-width guard proposal

This is a host-tested byte proposal only. No code cave is approved, no native
library was modified, and no APK was rebuilt or installed. Root must resolve
placement, integration and native validation before enabling it. A future APK
rebuild requires the standing GitHub release publication.

## Original fault-producing arithmetic

Original `CSRTableSkinList::SetBonus` executes:

```text
ELF1041b3c  ldr r0,[sp,#0xc]      ; next/current target count
ELF1041b42  vmov s4,r0
ELF1041b46  vcvt.f32.u32 s4,s4
ELF1041b4c  vmul.f32 s0,s2,s0     ; progress width * owned count
ELF1041b50  vdiv.f32 s0,s0,s4
ELF1041b54  vstr s0,[sp,#0x40]
```

When no nondefault skin or bonus record exists, the UI fallback leaves both
numerator and denominator zero. Empty bonus getters are guarded and return
initialized neutral objects, but this UI division is not guarded. This proposal
avoids inventing a bonus threshold or purchased ownership merely to size a
progress bar.

The hook is exactly4 bytes, `80ee020a` at ELF1041b50. A36-byte surrounding
register/context window at1041b3a is pinned. The tool validates ELF32/ARM
executable mapping, full input SHA-256 and exact context. Accepted inputs are
the immutable original (`c4646ac3817b0008b6ea387fde9c8279fd439343ccc272acdc5883fab9d00eec`)
and a retained instrumented copy (`df49f1af3a4fdf3da5167446d9c6ffc19b3c7143588911cf92cbf6e24b3fdc16`).
The retained copy's context matches; its identity is not a claim about the
currently installed library.

## Conditional instruction plan

Replace only the original VDIV with B.W to a future proven28-byte cave. The
trampoline body is:

```asm
push {r2}
vmov r2,s4
lsl.w r2,r2,#1       // no S: preserve APSR; remove sign for ±zero
cbnz r2,positive    // flag-free branch
vmov s0,r2          // shifted zero bits become positive finite0
b restore
positive:
vdiv.f32 s0,s0,s4   // exact original instruction bytes
restore:
pop {r2}
b.w 0x1041b54
```

The body is24 bytes; the return branch adds4. It preserves all general
registers, SP, LR, APSR and other floating registers. Nonzero denominator runs
the exact original VDIV, including its FPSCR rounding/control/exception
behavior. No VFP comparison or VMRS is used, so the guard itself cannot
overwrite floating comparison flags or APSR. The zero case produces positive0
without raising a new invalid/divide-by-zero exception. Temporary scratch is
one push/pop word below SP; there are no calls or object writes.

Compiled body bytes:
`04b412ee102a4fea420212b900ee102a01e080ee020a04bc`.
Hook and return B.W encodings are relocation-dependent and immediately decoded
back to their requested addresses using the existing patcher's branch helpers.

## Tool and host proof

`tools/boutique-zero-width-guard.s` is assembled with the bundled ARM LLVM
toolchain. `tools/prepare-boutique-zero-width-guard.py` emits proposal JSON to
stdout; it has no output-library option or mutation API. Its default cave
address0x200000 is an arbitrary Unicorn simulation address, **not a location
approved inside the original library**. The output always states cave_proven
false and PROPOSAL_ONLY_NO_CAVE_APPROVED. Hook-context overlap and odd addresses
refuse.

Run offline:

```powershell
& local/toolchains/python-venv/Scripts/python.exe -B -m unittest tools/tests/test_boutique_zero_width_guard.py
```

Four tests pass. Actual Thumb/VFP execution in Unicorn checks18 positive-case
combinations across three FPSCR settings,8 signed-zero cases including NaN
numerators, register/flags preservation, exact resume PC and untouched memory
outside the scratch word. A positive control executes original0/0 as NaN.
Assembler output is disassembled to prove the LSL does not set flags and the
positive VDIV is byte-identical. Original SHA before/after is unchanged;
altered input, overlap and unaligned proposals refuse.

## Required placement and release gates

Existing animation/assertion patch caves are reserved or historically unsafe.
No unreferenced padding or bypassed function body is claimed safe here. Before
applying this candidate, prove an executable cave of sufficient size, its
existing bytes, absence of direct/indirect live entry, overlap with every
existing patch region, Thumb branch reach and runtime library identity. Preserve
all unrelated bytes and verify the exact final diff. A negative incoming-branch
scan can reject a cave but cannot alone prove it unused.

Then build only the instrumented copy, publish the required GitHub release,
verify installation/input hashes, and validate native Boutique entry and zero
progress width with original artwork. Recheck positive progress behavior and
saved ownership/bonuses. Host emulation does not prove Houdini rendering,
native callback timing or an end-to-end Boutique loop.
