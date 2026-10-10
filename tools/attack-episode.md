# Guarded Episode attack bursts

Root owns BlueStacks exclusively. Use only after a fresh screenshot confirms
the expected active Episode battle HUD, with the read-only observer compiled
and the existing RapidTouch shell JAR available. No APK rebuild or data edit.

Alternatively, `-BeginBattle` authorizes one Begin tap at540,1820 after root
visually verifies the expected native preparation screen. It waits2500ms,
then uses the same no-input frame snapshots and native combat/start/input
gates. This avoids an inference/tool-call gap after entering a fast fight.
Never use this switch from a menu, result, dialogue or unknown stage. It has
no input fallback if a native ownership check rejects the new scene.

`attack-episode.ps1 -CombatId CB0102 -MaxBursts 20 -EvidenceDir <fresh absolute
directory under analysis/testing>` checks the resumed instrumented activity
before each iteration. The original `com.vshower.rann.b.onDrawFrame` callback
supplies the existing JDWP read-only snapshot without a diagnostic touch.
Only exact matching combat ID, recovered started/input gates, a live owned
player Hunter with an input binding, pause0 and no modal authorize a12-touch/
50ms burst at550,800. It stops on terminal, modal or owner failure; temporarily
unarmed/paused states are polled without input within the same finite limit.
It never presses the exit door. `MaxBursts` bounds iterations (including waits),
maximum100/default20. Inspect a fresh screenshot between runs.

This is an Episode-specific alternative to manually inspecting every burst;
the native owner/identity/counter/modal check runs before each burst. A scene
can transition during the remaining half-second burst, so the finite bound
still matters. Native remaining counters may be-1 during a started fight:
the original OnRefresh rejects zero, not nonpositive values. Positive counts
were an incorrect earlier guard. The recovered started3d1/input flags/list/
Hunter ownership and binding now supply the armed predicate.
Observer timeout retains its process and stops further inputs, without killing
the client. Do not resume while a retained observer still owns JDWP.

Verified: JDK21 compilation, PowerShell parsing and native CB0102 loss-state
rejection (left0/right1 with dialogue modal), zero bursts and zero diagnostic
inputs with --frame. Native active CB0102 accepted four bursts (48 paired
touches), then stopped at original skill-animation pause2/state4; start-to-start
intervals2348..2484ms. Subsequent bounded no-input waiting through temporary
pause is source-updated but not yet measured in another active fight. Victory
remains pending. Initial startup polling bug on empty stdout
was corrected; failed observers timed out/disposed without game writes.
Injection acceptance alone does not prove attacks, actor defeat or a win.

`InspectNativeInput 8701 --episode-materials --frame` additionally walks bounded
owned group actors and the serial map using original getters/ownership layouts.
It reports source resource ID/body branch and actual serial-map target identity.
This diagnosed CB0102 enemy serial5 resolving to player C004 instead of M022;
it does not itself alter actor IDs, resources, stats or persistent state.

`InspectNativeInput 8701 --episode-skills --frame` adds diagnostic-only native
skill fields for owned player Hunters: icon emplace ownership, enabled/visible,
raw cached rectangle, dirty masks, opacity factors and resident drawable owner.
It does not compute physical coordinates or complete eligibility and never calls
lazy native getters. Actor/group/serial and owner/cache fields are rechecked.
Live CB0602 paused snapshots verified all five allied CSRUIScrollView emplace
drawables and expected enemy serials6..10. Ancestor attachment and renderer/Java
layout conversion remain unproved; do not generate input from these raw bounds.
Read analysis/testing/skill-targeting-002/report.md. Use bounded snapshots after
visually confirming pause; do not churn debugger attachments in active combat.

`InspectNativeInput 8701 --renderer-layout --frame` reads qualified native OES2
geometry and exact SDK25 Java layout/window fields in a safe menu. It invokes
only audited read-only Android framework property accessors; no game-native
getter or lazy cache refresh is called. `--touch-layout` instead waits for one
explicit safe-menu DOWN event at the original Activity callback, reporting
actual local/raw coordinates and reconstructed JNI/logical points. Never use
that mode to add diagnostic touches during a battle. Both modes repeat owner,
geometry/layout and relevant event/property values before output.

Live client19900 calibration: logical651×1135, renderer1080×1884, window1080×1920,
origin0, compatibilityscale1/no translator/scroll, translation0. Two empty-menu
touches had local==raw; no blanket36-pixel correction is valid for this session.
See analysis/testing/renderer-layout-001/report.md. These measurements do not
authorize stale actor-bound clicks or generalize to other layouts/devices.

Episode bursts now pass explicit695/900, the documented ordinary battle point.
RapidTouch accepts an optional x/y pair only within the central scene rectangle
x400..750/y700..1050; default550/800 remains for the fishing hook. APK unchanged.
BeginBattle macro waited through native loadingpause40/started0, then sent
10bursts120pairedtouches and stopped onloss0/1 beforemenus. NativeM022HP450
became298.560181, Gerard1000→944.800171: damage is observed, not all120hits or
anyenemydefeat. Source item/reward/stat data were unchanged. Victory pending.

Visible skill guard (2026-10-09): optional skill-plan fields require_visible_button:true,
expected_cost:3 or4, max_defer_bursts:0..3 invoke battle-skill-button-guard.py on the
fresh guarded frame. Missing matches defer while ordinary bursts continue; expiry
writes skill-skipped.json. PauseAfterSkill pauses normally after an attempt OR an
expired window, with the latter explicitly recording no skill input. Guarded
appearance matches are attempts only, not actor/funding/cooldown/eligibility proof.
Templates/provenance and limits: analysis/research/visible-skill-button-gate.md.
Seventeen native-frame tests passed. Live one guarded attempt/three skips still
ended in loss; no improved cast acceptance is claimed. See visible-skill-001/report.md.

Guarded plans may also set hold_ms to an integer50..250 for one same-point
Android contact. Omission preserves a tap. A200ms guarded Karl press produced a
player cut-in and nativefrontC012/HP1150 while normally paused; exact timing
causality and general reliability are unproved. See held-skill-001/report.md.
