# Ordinary campaign control and earned levels

The controller narrowly supports n_01_01 with exactly one expected enemy and
ordinary attack/pause only. Root must verify the live stage, preparation and party;
the pixel guard cannot identify native stage IDs or prove an outcome. Ordinary
preparation has separate Dispatch/Begin buttons: observed Begin is800,1820, while
the Episode center point540,1820 is the gap on this layout.

The initial Episode HUD guard correctly refused the campaign's different layout
and sent zero bursts. The separate campaign-hud-guard checks the observed top blue
enemy HP strip, white HP digits, orange enemy badge, living front's green bar and
lower HUD. It explicitly rejects the pink pause button. Pause/resume can leave
the bench closed during active native combat: the verified white stopwatch is an
alternative to the bench door appearance. Native read-only frame confirmed that
closed-bench case at CSRSceneGame/mode0/pause0/state0. Neither HUD variation
changes native eligibility or the meaning of the displayed100x100 label.

Five tests cover actual open/closed-bench combat, native pause, preparation,
Village/maps, Episode cut-in and both retained campaign result controls; removal
of required signals refuses. Independent review found no retained false positive.
Low HP or unfamiliar rendering may still conservatively stop the controller.

A screenshot helper timed out with localPID8724. Root verified that process was
missing before starting any new controller. Its partial PNG was invalid and was
not used as evidence. Normal pause was then confirmed visually and natively.
This was not a retry based solely on a timeout. The recovered campaign controller
sent one12-pair ordinary burst, stopped at the native Mowgli Victory dialogue and
no further combat inputs were sent to results. Accepted completion awarded10EXP
to all four party participants and one Search capsule.

Native Build Team after reload showed Mowgli6, Nene6, Lantern7 and Tyltyl12,
strength26243 versus26130 before. Private evidence is under
local/captures/testing/campaign-levels-001; raw captures and saves stay ignored.
The server's campaign-origin-fix-2026-10-11.md documents the duplicate origin
binding, incidental erroneous origin rewards, correction and pending native return
verification. Do not classify those origin rewards as replay payout.

Current runtime after correction: Server10020/55192/current-e6/139groups1634683,
client25370/+15; no active battle or input helper. Bench-heal delivery remains
verified, E6Story04 remains uncleared and E7 inactive. Further inputs are held
until the minimized BlueStacks window can provide a fresh reliable visible state.
No APK rebuild/install/release or DataDump/original-folder edits occurred.
