# Opt-in Bright healer qualification

Host observer source only; compilation and native use remain pending with the
runtime owner. This adds no APK code, native call, memory write or input action.

After the runtime owner qualifies the instrumented process and its existing
JDWP forward, the exact host invocation is:

```text
java -cp local/verification/host-java InspectNativeInput 8701 --episode-skills --frame --heal-source-ref=C049 --heal-source-serial=1000018
```

Use it for a fresh paused CB0602 observation. `--episode-skills` retains its
existing all-actor material/skill snapshot, including recipient HP, then adds
the selected living healer's skill and unique friendly-group Rage snapshot.
The output's selectedCombatId must independently establish CB0602. Selection
does not claim that the healer is currently eligible or that healing occurred.

Both options are mandatory together, unique, and accepted only after exactly
`--episode-skills --frame`. References are closed to exact `C004` or `C049`;
the decimal serial must be positive, canonical, and at most4294967295 with high
word0. This permits explicit selection of a known owned instance, never a ref
scan or an arbitrary character class. The observer independently verifies that
the exact serial-map actor has that exact ref before returning output.

The existing `--episode-badge --frame` still uses C004/1000005 exactly. The
touch helper and `--episode-touch --source-serial` are unchanged. In particular,
this opt-in does not authorize any Bright touch or relax C004 badge guards.

The selected snapshot reuses the original bounded32-node serial-map search,
concrete emplaced Hunter control/vptr identity, nonexpired ownership, camp0,
positive finite HP, exact serial halves, stable re-read checks, and unique
exact source/control membership in the bounded friendly-group traversal. Group
Rage values remain finite/nonnegative checked. Existing scene/combat/modal
ownership and final stability guards enclose this additional snapshot.
Existing group-control allocation and native admission remain unproved, as
reported in the output. The new arguments do not prove a resource, input
hitbox, native skill acceptance, healing amount, or tick count.

`tools/tests/TestHealSourceSelection.java` is a pure host test prepared for the
runtime owner's compilation alongside `tools/NativeCampaignMarkers.java` and
`tools/InspectNativeInput.java`; run `TestHealSourceSelection` using that class
directory. It tests accepted closed selections, default isolation, missing or
duplicate options, wrong modes/frame, unknown refs/options, extra arguments,
canonical positive serials and low-word boundaries. It does not attach to a VM.
No compile or live test was performed by this change's author.

## Root host verification

Host javac of NativeCampaignMarkers, InspectNativeInput and both pure tests
succeeded. TestHealSourceSelection and TestNativeCampaignMarkers passed;
independent read-only review clear. No runtime VM attach or input occurred.
Windows control failed activation twice after reselection, so root held inputs
and requested a user window restore. Client7068 and server46444 are verified
live; all three games remain exact to the pre-trial backup. Native observation
and healing are pending; no process was restarted because capture failed.

## Native qualification after the user restored BlueStacks

Two paused CB0602 snapshots qualified C049/1000018, HP1720, exact native
serial-map/concrete Hunter ownership and friendly Rage SP2.916827/4.287144.
Observer exited normally before input. This supersedes the earlier attach
pending note. Actual healing remains unverified; see the companion
bright-e6-native-trials-2026-10-23.md for both outcomes and the separate
SetFeverLV null-visibility crash. Client recovered to Village23461; rebind
JDWP8701 before another observer. No APK rebuild or patch occurred.
