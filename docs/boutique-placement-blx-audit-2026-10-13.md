# Boutique guard placement audit: BLX coverage

The read-only UInt32 Boutique guard proposal previously omitted Thumb BLX
immediate branches and ignored the ARM BLX H bit. Its no-reference result was
therefore incomplete for those encodings. The audit now includes Thumb BLX's
word-aligned PC base and low immediate constraints, and retains ARM's H bit in
the signed displacement. Embedded data is still overapproximated as candidate
instructions; a reference into the proposed gap refuses placement.

Two synthetic branch tests independently confirm the opcode and target with
Capstone before checking the audit result. The existing actual Thumb/VFP
Unicorn tests still prove unchanged reachable positive behavior and finite
zero width for the unsigned zero denominator. The pinned retained image's
static layout/symbol/relocation/reference gates continue to pass with no new
immediate references into the24-byte extab/rodata gap at ELF1d52928.

```powershell
& local/toolchains/python-venv/Scripts/python.exe -B -m unittest discover -s tools/tests -p test_boutique_zero_width_guard_u32.py
```

All6 tests pass. Retained library SHA256 remains
759481add6592a6e46a692d37e263cef791151a4897a8f98d9eff5ba3f0b6a34.
No native library is written or patched. The proposal remains an unapproved
bounded candidate: dynamic indirect execution and live Boutique behavior are
unverified. No APK build, installation, device input or release occurred.
