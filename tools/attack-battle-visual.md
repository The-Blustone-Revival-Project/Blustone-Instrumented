# Continuous visual battle fallback

Root must hold exclusive BlueStacks control and freshly identify the expected
preparation or active battle. This controller checks the exact instrumented
PID/foreground and a captured 1080×1920 HUD before each bounded12-touch burst
at695,900. It uses the existing shell RapidTouch.jar, with no JDWP attachment,
APK change, native calls or memory writes. Evidence must be a fresh directory
under analysis/testing. Other resolutions are rejected.

```powershell
& tools/attack-battle-visual.ps1 -ExpectedCombatId CB0401 -ExpectedEnemyCount 2 -ExpectedClientPid 16117 -BeginBattle -MaxBursts 150 -EvidenceDir "$PWD/analysis/testing/fresh-replay"
```

Those encounter/PID values are an example from a completed run. Refresh them
from the live client and preparation before another run. ExpectedCombatId is
caller identification recorded as evidence; pixels do not verify native ID,
owner, pause, input list, modal hierarchy or armed state. Do not run another
input controller concurrently. Omit BeginBattle when resuming an already
visually confirmed active battle, and use a new evidence directory.

ExpectedEnemyCount is mandatory (1..5); verify it against the fresh preparation
roster. The gate excludes frames with defeat crosses on all expected enemy
portraits, including death effects that resemble a red health bar. It matches
both diagonal strokes and rejects solid red portrait regions. Count/portrait
placement is caller-verified calibration, not native enemy ownership or outcome
proof; other layouts/attributes can reject real combat.

The gate requires observed timer, red enemy-health bar and calibrated attribute
badge signatures: the prior cyan signature or red/yellow hand glyphs in BOTH
front badge interiors. Other attributes/positions/visual changes can still
reject a real battle. E06's winning retry accepted Lantern's red badge and
stopped immediately with all three Bear portraits crossed (30 bursts/35 frames).
That retry sampled no midbattle missing HUD; subsequent CB0602 evidence below
verifies cut-in waiting. See analysis/research/battle-hud-attribute-calibration.md.
All text and capture helpers use bounded waits. A timeout records its PID,
start time and operation in pending-helper.json; inspect that exact live handle
before another controller. The record is a historical observation, not current
liveness proof. No client restart follows an observation timeout.
A failed gate stops inputs, not the game, and is never labeled win/loss.
Initial Begin loading has a bounded no-input wait. After attacks have started,
up to six consecutive missing-HUD captures are observed without input, allowing
temporary skill cut-ins to finish. A fresh passing HUD resumes attacks; all
expected defeat crosses stop immediately. This does not classify a missing HUD
as a skill or an outcome, and menus/results receive no clicks during that wait.
For an already identified encounter temporarily obscured by a known skill,
`-InitialHudWaitFrames 1..12` permits bounded no-input observation at startup
without Begin. Default0 still stops immediately. This option has not been used
in a live resume yet. It never bypasses the HUD or all-enemy-cross gates.
CB0602 sampled cut-ins024/035 were rejected without bursts, then025/036 resumed
ordinary attacks; loss042..048 stayed rejected. The midbattle wait now has live
evidence, distinct from the untested startup option.
On a stop or burst bound,
inspect the fresh frame and live state before continuing. Read original win
dialogue and verify native Read/persisted clear separately.

Regression: tools/python-venv/Scripts/python.exe tools/tests/test_battle_hud_guard.py
checks34 distinct annotated actual frames (37 inspections), including low
enemy25HP, Nene's death while Karl remains alive, preparation,
intro/loading, launcher, menus, pause, loss and both-defeated/win dialogue.
Timer digits are isolated at(0,175)-(180,215), white>=500; red stripe>=10 and
cyan badge signature>=400. Lowering red alone falsely accepted chapter titles;
the narrowed timer box rejects those retained frames. Caller roster crosses
reject the actual Karl-defeated frame with blood/blue effects. Current rejection
on the live Karl victory dialogue sent0bursts. Cross branch itself is tested on
captures and the E06 three-Bear live victory; no universal UI safety claim.
CB0401 live replay completed14 bounded bursts/20 captured frames, stopped
with both enemy defeat crosses, then original EP0903B and savedE04_S03 clear.
No precise native terminal counter or final enemy HP snapshot was taken.

`-SkillPlanFile <json>` optionally schedules at most four single normal button
attempts, each after a unique integer `after_bursts` milestone below MaxBursts
and spaced by at least four ordinary bursts. Allowed scalar integer points are
front `(300,535)` or observed moving-front `(450,535)`, and rear support
`(345,1385)`. Plan example: `[{"after_bursts":10,"x":345,"y":1385}]`.
The full plan is validated before creating evidence or touching ADB. Each
attempt requires a fresh passing HUD, gets a separate skill-attempt record,
and skips the ordinary burst on that frame. Subsequent input requires another
fresh frame. Client enabled/opacity/cost/target checks remain authoritative;
an absent, moved or dim icon can miss or refuse. No automatic retry or native
eligibility classifier is supplied. Default no-plan behavior is unchanged.

Two live CB0602 trials recorded four attempts each and native losses. No
player skill activation or cost debit was verified. Bubble movement disproved
fixed-position readiness assumptions: even the rear heart moved vertically.
This option records bounded attempts without model/input gaps; it is not a
verified skill strategy. Do not repeat the failed schedules. See
analysis/research/battle-skill-plan-validation.md and episode06-003/report.md.

`-PauseAfterBursts N` is an explicit diagnostic option: after N ordinary bursts
and another fresh passing HUD, send one Android Back input and stop. N must
precede MaxBursts; default0 is disabled. Verify the actual Paused screen before
attaching any observer: the first capture can precede menu presentation. Live
CB0602 validation paused after six bursts and preserved timer283.1 through two
bounded read-only snapshots. Resume through the verified menu, then use a fresh
controller directory with InitialHudWaitFrames if needed; never treat the pause
request or elapsed observation time as a pause confirmation or outcome.

SDK25 client13845 previously died in libart JDWP CleanupMatchList on a JIT
thread during repeated read-only observer cycles. This fallback avoided those
cycles on the successful replay; the underlying ART failure is not fixed or
its exact cause established. Keep the bounded native reader for appropriate
diagnosis, but do not restart the app merely because an observer timed out.
