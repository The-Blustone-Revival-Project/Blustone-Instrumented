# Bench-heart declines after relocation (2026-10-11)

Read-only audit of `tools/find-bench-heart.py` against private live attempt 001 contact frames 01 and 02. No device input, native inspection, threshold changes, template changes, or DataDump/original-folder writes were performed.

The finder reaches the intended button: both frames pass the five-enemy battle HUD guard, produce one eligible cost-glyph component, and check 50 alignments. The cost components contain 328 and 326 white pixels respectively, within all existing size/count bounds. The glyph/heart gates pass; the circle-context gate rejects every otherwise eligible alignment.

Minimum context errors among alignments that already pass glyph >=0.90 and icon >=0.88:

- Frame 01, `heart4-bench`: center (330,1457), glyph 0.984472, icon 0.990468, context error 24.998164. Seven alignments passed glyph/icon.
- Frame 02, `heart4-bench`: center (331,1448), glyph 0.979876, icon 0.987717, context error 23.804040. Six alignments passed glyph/icon.
- Frame 01, `heart4`: center (330,1470), glyph 0.949333, icon 0.981525, context error 20.383788. Three alignments passed glyph/icon.
- Frame 02, `heart4`: center (331,1461), glyph 0.945551, icon 0.983015, context error 19.622770. Four alignments passed glyph/icon.

The unchanged context threshold is <=18. The declines are therefore retained-context mismatches, not failed proposals, wrong digit, missed motion, or HUD rejection. The bench-template alignment moves one pixel right and nine pixels up between these captures. The generic template aligns 13 pixels lower because its glyph has a different position within the retained crop; these crop anchors are not proof of the native button center or hitbox.

A wider read-only search over x300..360/y1430..1500 returned the same best-scoring alignments. Enlarging the proposal neighborhood cannot resolve the measured rejection. Both heart/cost fills closely match retained templates, while the surrounding airship/circle appearance differs enough to exceed the existing context gate. The screenshots alone do not establish why the contextual pixels differ, whether the button accepts input, which actor owns it, or native skill/funding eligibility.

Do not raise thresholds to make these captures pass. If adding a retained appearance later, use an independently reviewed private crop with provenance and held-out positive plus negative contexts, keeping all thresholds/region/HUD/pause/ambiguity checks intact. This audit did not add such an appearance.

Exact private measurements are retained at `local/verification/bench-decline-metrics.json` (wide diagnostic search) and `local/verification/bench-decline-gated-metrics.json` (actual proposal alignments). These JSON files contain measurements and local path references, no screenshots or account data. No raw private capture is included in this report.

## Follow-up: retained live appearance review

Root subsequently added `heart4-bench-live.png` using frame01 at (330,1457), plus provenance and a held-out frame02 test. Independent review verified the source SHA256, exact crop box and all 137x137 crop pixels. Thresholds remain 235/0.90/0.88/18; the finder region and all-candidate ambiguity check remain intact. The additional appearance is limited to bench y>=1300 in the point guard. Earlier-template preference preserves existing accepted points despite the previously measured 13-pixel crop-anchor discrepancy; distant candidates still refuse.

Independent rerun passed all 29 finder, button, HUD and sequencing tests in 42.019 seconds. The new test includes calibration frame01, held-out frame02 and underfunded frame00 refusal, while existing wrong-icon, paused/map/loss, out-of-region, blank and ambiguous controls remain in the suite. No actionable code defect found. This establishes retained visual recognition only; native acceptance remains pending root's device validation.
