"""Regressions from annotated native screenshots, never fabricated battle states."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ordinary_hud", ROOT / "tools/verify-ordinary-hud.py")
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class OrdinaryNativeFrames(unittest.TestCase):
    def assert_observation(self, path, classification):
        result = GUARD.inspect(ROOT / path)
        self.assertEqual(result["classification"], classification, path)
        # Every retained screenshot remains insufficient to authorize input,
        # establish a stage identity, or settle a battle.
        self.assertFalse(result["input_authorized"])
        self.assertFalse(result["stage_identity_verified"])
        self.assertEqual(result["outcome"], "unknown")
        return result

    def test_normal_ordinary_fighting_and_enemy_disappearance(self):
        for name in ("09-paused.png", "10-result.png", "12-pause.png"):
            with self.subTest(frame=name):
                # Visual annotation overrides misleading historical filenames:
                # there is no Paused/result overlay in any of these images.
                self.assert_observation("local/fixtures/testing/campaign-exp-001/" + name,
                                        "ordinary_hud_observed")
        for index in range(5, 14):
            with self.subTest(frame=index):
                self.assert_observation(f"local/fixtures/testing/campaign-exp-001/fight/{index:03d}.png",
                                        "ordinary_hud_observed")

    def test_native_impact_streaks_remain_observable(self):
        for name in ("07-fight.png", "08-paused.png", "11-current.png"):
            with self.subTest(frame=name):
                result = self.assert_observation("local/fixtures/testing/campaign-exp-001/" + name,
                                                 "ordinary_hud_observed")
                self.assertTrue(result["friendly_health_stripes"])

    def test_historical_locked_controls_and_actual_result(self):
        self.assert_observation("local/fixtures/r016-02-BATTLE-SCENE-RENDERED.png", "ordinary_hud_observed")
        self.assert_observation("local/fixtures/r017-03-AFTER-EXIT-8s.png", "known_nonbattle")

    def test_village_area_map_and_preparation(self):
        for name in ("01-current.png", "02-current.png", "03-airport.png", "04-areas.png",
                     "05-map.png", "13-current.png"):
            with self.subTest(frame=name):
                self.assert_observation("local/fixtures/testing/campaign-exp-001/" + name, "unconfirmed")
        self.assert_observation("local/fixtures/testing/campaign-exp-001/06-prep.png", "known_nonbattle")
        for name in ("01-current.png", "03-areas-settled.png", "05-aurora-settled.png"):
            with self.subTest(current=name):
                self.assert_observation("local/fixtures/testing/campaign-receipt-001/" + name, "unconfirmed")
        self.assert_observation("local/fixtures/testing/campaign-receipt-001/07-preparation-settled.png",
                                "known_nonbattle")

    def test_native_entry_warning_and_uninitialized_scene(self):
        for index in (2, 3, 4):
            with self.subTest(frame=index):
                self.assert_observation(f"local/fixtures/testing/campaign-exp-001/fight/{index:03d}.png",
                                        "unconfirmed")
        self.assert_observation("local/fixtures/testing/campaign-exp-001/fight/001.png", "known_nonbattle")

    def test_episode_mode_actual_paused_and_skill_views(self):
        self.assert_observation("local/fixtures/testing/episode05-005/16-cb0501-pause.png", "known_nonbattle")
        for path in ("episode05-005/cb0501/013.png", "episode06-cb0602-001/024.png",
                     "episode06-cb0602-001/048.png", "episode06-heal-001/resume/002.png",
                     "skill-ancestry-001/resume/002.png"):
            with self.subTest(frame=path):
                self.assert_observation("local/fixtures/testing/" + path, "unconfirmed")

    def test_new_live_ordinary_and_natural_win_receipts(self):
        for name in ("10-first-hud.png", "17-current.png"):
            self.assert_observation("local/fixtures/testing/campaign-receipt-001/" + name,
                                    "ordinary_hud_observed")
        for name in ("12-hud.png", "15-current.png", "38-20-frame.png"):
            self.assert_observation("local/fixtures/testing/campaign-receipt-001/" + name,
                                    "known_nonbattle")
        # These native impacts retain the lower AUTO arc and mountain geometry,
        # though upper-arc saturation and contrast reversal defeat old anchors.
        for name in ("11-hud.png", "14-hud.png"):
            result = self.assert_observation("local/fixtures/testing/campaign-receipt-001/" + name,
                                             "ordinary_hud_observed")
            self.assertLess(result["anchor_scores"]["distance"], .70)
            self.assertEqual(result["alternate_anchor_scores"]["auto_lower_arc"], 1.0)
            self.assertGreaterEqual(result["alternate_anchor_scores"]["distance_unsigned"], .70)
            self.assertEqual(result["reason"], "lower_arc_and_mountain_geometry_with_friendly_health")

    def test_impact_alternative_still_requires_each_visible_geometry(self):
        # Negative ablations of actual retained pixels are not new positive
        # battle fixtures. Removing one required anchor must defeat the fallback.
        removals = {
            "mountain": (700, 150, 950, 190),
            "lower_auto_arc": (60, 1200, 160, 1270),
            "crate": (30, 130, 95, 195),
            "coin": (165, 130, 235, 195),
            "speed": (920, 1160, 1025, 1280),
            "friendly_health": (100, 1018, 1060, 1680),
        }
        with tempfile.TemporaryDirectory() as directory:
            for name in ("11-hud.png", "14-hud.png"):
                with Image.open(ROOT / "local/fixtures/testing/campaign-receipt-001" / name) as source:
                    for removed, box in removals.items():
                        with self.subTest(frame=name, removed=removed):
                            frame = source.convert("RGB")
                            ImageDraw.Draw(frame).rectangle(box, fill=(80, 80, 80))
                            path = Path(directory) / "ablated.png"
                            frame.save(path)
                            result = GUARD.inspect(path)
                            self.assertEqual(result["classification"], "unconfirmed")
                            self.assertFalse(result["input_authorized"])
                            self.assertFalse(result["stage_identity_verified"])
                            self.assertEqual(result["outcome"], "unknown")

    def test_missing_or_truncated_capture_fails_closed(self):
        result = GUARD.inspect(ROOT / "local/fixtures/testing/does-not-exist.png")
        self.assertEqual(result["classification"], "unconfirmed")
        with tempfile.TemporaryDirectory() as directory:
            incomplete = Path(directory) / "incomplete.png"
            incomplete.write_bytes(b"\x89PNG\r\n\x1a\n")
            self.assertEqual(GUARD.inspect(incomplete)["classification"], "unconfirmed")


if __name__ == "__main__":
    unittest.main()
