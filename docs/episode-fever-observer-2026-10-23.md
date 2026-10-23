# Read-only Episode fever-node qualification

The host observer adds one opt-in mode:

```text
java -cp local/verification/fever-host InspectNativeInput 8701 --episode-fever --frame
```

The runtime owner must first qualify the instrumented process/JDWP forward and
the expected Episode scene. The mode requires exactly `--frame`, rejects extra
arguments before attaching, and reuses existing Episode scene/combat/modal and
input snapshot guards. It performs no game-native calls, memory writes, touch
events, APK changes or profile operations. Other modes retain their defaults.

The exact original INGAME_NM XML path is UI root→VIEWER→MainCamera→RUNNER_ROOT,
then each of CFE4 and CFE3_B. The root at game+0x2c/+0x30 must be a nonexpired
strong pair, have a type in the existing161-class primary-vptr guard set,
preserve the recovered unadjusted CMUpdatable slot, and have exact runtime name
`SR_INGAME/INGAME_NM`. Its concrete allocator is explicitly **unproved**.
No guessed root concrete class or control-vptr is accepted as evidence.

Each exact child path uses the existing bounded64-sibling list helper with
count/name/duplicate/cycle refusal. Parent object/control backlinks at+0x54/+0x58
must match at each selected step. Both target image nodes require original
CSRUIImageNode primary ELF vptr0x213bd20, control primary0x213b5cc,
object=control+0x10 and a nonexpired strong count. This concrete owner comes
from `make_shared<CSRUIImageNode>` G7a6d58: allocation0x8d8 at G7a6d62,
control primary assignment and object+0x10 at G7a6d80–G7a6d86. The primary
control address is the original GOT pointee0x213b5c4 plus8. The immutable ELF
SHA256 is `c4646ac3817b0008b6ea387fde9c8279fd439343ccc272acdc5883fab9d00eec`.

All recorded root/path/owner/field reads and every observed UI name are checked
again before output; outer scene/combat stability checks still enclose the
snapshot. Missing nodes produce explicit refusal, not a partial success. The
mode reports cached fever rank game+0x208, phase+0x2ec, and target hidden bytes
at+0x270/+0x271. Those fields are observations, not proof of an accepted fever
transition. Resource drawing, animation completion and absence of a later
SetFeverLV crash remain unproved until native validation. This mode never
calls SetFeverLV or authorizes attacks.

Host compilation succeeded in separate ignored `local/verification/fever-host`
using NativeCampaignMarkers.java, InspectNativeInput.java and the two pure
tests. `TestEpisodeFever` passes frame-only/default-isolation cases and rejects
null/misaligned/wrong-offset/wrong-class/wrong-control/expired target owners.
Existing `TestHealSourceSelection` also passes. Neither test attaches to a VM.
`git diff --check` passes. No live observation was performed by this author;
the runtime owner controls subsequent qualification and native transition.

## Root native check after original package restoration

Client23967, 140groups/stamp1634691, paused CB0602: both CFE4 and CFE3_B
qualified as concrete CSRUIImageNode emplace owners under the expected path.
Cached rank0, phase7; both hidden bytes1/1. Observer exited normally after
858 reads, 2.98s. Ignored evidence: local/verification/fever140-episode-paused-20261023.txt.
After Resume, bounded ordinary attack bursts continued through visible FEVER
and a native LOSS; third option returned to E6map, same PID alive, no crash.
All three saved games exact. This does not capture the exact rank2 branch,
prove pixel drawing for these nodes, or establish Bright healing.
