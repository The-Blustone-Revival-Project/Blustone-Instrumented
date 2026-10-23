# Read-only Episode battle-control snapshot

`InspectNativeInput --episode-controls --frame` selects a bounded UI-only
observer. It reads the current AUTO/OFF/DASH panels without traversing combat
models, actors, skills, modal lists or background state. It performs no native
getter calls, input, setting changes or APK patch. This is a host-tool change;
the installed +15 instrumented client remains unchanged.

## Why a separate mode

The existing full Episode observer is useful for combat diagnosis but reads
too much for a quick control check. More importantly, static normal-expedition
UI paths and tiny AUTO captions do not prove the selected Episode HUD mode.
Episode uses CSRFCUIBase and UI_BATTLE, not CSRGameUIStage/UI_NORMAL.

The source-backed current cycle is OFF0→ALL2→DASH1→OFF0. Full AUTO2 installs
skill/exchange AI. DASH1 separates automatic ordinary attacks from manual skills
and swaps. A source caption is not a live mode observation; see
[the native control report](battle-auto-manual-skill-controls-2026-10-23.md).

## Ownership and interpretation

The new mode first qualifies the existing CSRSceneGame mode7 wrapper and its
exact Episode child emplace owner. Other scene families, including Mirage,
refuse at this boundary. Sharing a UI implementation does not justify treating
a Mirage wrapper as an Episode wrapper.

It then qualifies game+20c/+210 as the exact CSRFCUIBase emplace pair and
component+44/+48 as the exact selected CMDrawable UI_BATTLE emplace pair.
Instead of concatenating a static XML path, it follows actual parent/control
pairs back to the game's owned SR_INGAME/INGAME_NM root, bounded to12 nodes.
Every edge requires matching unique child-list membership and an unadjusted,
allowlisted CMUpdatable base. Cycles, unknown types, duplicate names, missing
owners or inconsistent list counts refuse.

Source-backed children are UI_BATTLE/BATTLE_ROOT, then two separate branches:

- AUTO_TOGGLE contains PA_AUTO_ALL, PA_AUTO_DASH and PA_AUTO_OFF.
- AUTO_LOCK contains PA_AUTO_LOCK. Lock is not a fourth sibling of those modes.

For each branch the reader captures local-hidden271, effective-hidden270 and
the complete actual ancestor chain. The pure `NativeBattleControls` helper
checks the parent-OR-local visibility rule separately for AUTO and LOCK.
Exactly one visible normal panel produces setting2/1/0. A visible lock produces
LOCKED only with all normal panels hidden. Hidden ancestry, no visible mode,
multiple visible modes, normal-plus-lock visibility and contradictory bytes
do not become an inferred active mode. All observed words, names, owner pairs,
pause and game MODE are rechecked before output.

For a visible panel, the existing qualified cached-rectangle reader supplies
diagnostic bounds only when its native rectangle consumers match. That does
not establish a current screen-coordinate transform or authorize a click.
Concrete allocation identities of descendant XML nodes remain unproved; the
exact FC component/selected fragment allocations are qualified separately.

## Build and run

From this checkout, with its configured JDK/ADB on PATH:

```powershell
. .\tools\env.ps1
javac -d local/verification/battle-controls-host tools/InspectNativeInput.java tools/NativeCampaignMarkers.java tools/NativeBattleControls.java

$blustonePid = (adb -s 127.0.0.1:5555 shell pidof com.vshower.prd_sr.instrumented).Trim()
if ($blustonePid -notmatch '^[1-9][0-9]*$') { throw 'Expected one live instrumented PID' }
adb -s 127.0.0.1:5555 forward tcp:8701 "jdwp:$blustonePid"
java -cp local/verification/battle-controls-host InspectNativeInput 8701 --episode-controls --frame
```

Only the exact three arguments PORT/--episode-controls/--frame are admitted.
Malformed or misplaced controls flags refuse before VM attachment rather than
falling back to touch-triggered mode. The command takes one render-frame
snapshot and disposes the debugger connection in its existing finally path.
It does not wait for or inject a game touch. Rebind to a freshly verified
instrumented PID after a client restart; never target the original app/phone.

Prefer a normally paused battle for this diagnostic. A paused observation
does not prove skill admission or permit toggling AUTO: ordinary OnTouch has
its own pause gate. Prepare the next action, resume through the visible UI,
then verify the admitted transition on a fresh HUD while keeping attacks
prompt. No long source/log work belongs in an unpaused fight. This tool never
fills Rage, sets mode, heals or changes pause masks.

## Verification and remaining native gate

Compilation and pure host tests passed for strict CLI admission, three normal
panels plus separate lock ancestry, inherited visibility, ambiguity/refusal
cases and absence of an inferred setting for hidden/locked/unknown states.
Existing fever and selected-healer CLI/ownership tests also passed after the
integration. Independent native-source review found no actionable issue in
the reader's ownership, attachment, separation or stability checks.

On the actual instrumented client4750 in Village, the new frame observer
refused before UI reads: six memory reads/24bytes, snapshot0.236455seconds.
The server save SHA256 was exact before/after. No battle was started for that
negative control. The retained ignored log is
`local/verification/battle-controls-village.log`.

## Subsequent positive paused Episode observation

After Windows restoration, native CB0602 was entered and normally paused.
The new reader verified the full actual FC component, selected UI_BATTLE,
attachment chain and both control branches. All ancestors through BATTLE_ROOT
were effective/local0/0; AUTO_TOGGLE and AUTO_LOCK were both1/1. Their children
were ALL1/1, DASH1/1, OFF1/0 and LOCK1/0. The correct result was
**ANCESTOR_HIDDEN / setting unavailable**, not an inferred OFF or DASH mode.
This positive traversal used1121 reads/4820bytes and3.243602seconds. It is a
paused diagnostic, not a measured fast unpaused input loop.

The recovered producer explains the observation: Episode.InitBeforeOpen calls
EnableIngameUIState(2) at Gb23da4–Gb23da6, leaving the timer enabled while
hiding AUTO, lock and speed parents. The FC default0x16 and Mirage's initializer
are separate; this result must not be generalized to Mirage. The exact source
is added to the linked control report. No missing artwork or forced visibility
fix is justified. The local OFF child alone does not prove stored AI mode.

A separate paused selected-healer read verified living Bright/C049 serial
1000018 with HP1720 and group Rage2.609351; current front Nene was601.408020.
That snapshot took1.773802seconds. It does not prove an input-time eligible
healing bubble under pause. After resume, a Captain swap was visible, but a
Karl skill contact did not establish activation and no heal was verified.
The attempt was lost. Input gaps remained too long; do not repeat that pacing
or report this as successful manual skill control. Prepare the exact next
action before resuming and keep analysis/tool-request overhead minimal during
an unpaused fight; pause again before any source or log inspection.

The third loss-dialogue option returned safely to the E6 map. Story4 remains
uncleared. All three saved games and all account fields were exact against the
pretrial backup, including the older abandoned Mirage journal. Retained ignored
logs are `local/verification/battle-controls-episode-paused.log` and
`local/verification/episode-controls-bright-paused.log`; the paused screenshot
is in Server's `local/native-validation-20261023/episode-controls/`.

No native DASH selection or manual heal is proved. No host-authenticated live
gameplay request, private-save edit, original/DataDump/phone change,
Docker/collector operation, APK rebuild/install or instrumented release occurred.
