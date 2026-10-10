"""Annotated native frames: gameplay, loading, preparation, loss, win and menus."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hud_guard", ROOT / "tools/battle-hud-guard.py")
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class NativeFrameGate(unittest.TestCase):
    def test_arena_badge_geometry_and_non_gameplay_controls(self):
        folder = ROOT / "local/fixtures/testing/arena-stage-001"
        active = folder / "first-burst/009.png"
        self.assertFalse(GUARD.inspect(active, 1)["battle_hud"], "standard badge placement is not Arena geometry")
        for frame in ("first-burst/009.png", "first-burst/010.png", "first-burst/013.png"):
            with self.subTest(frame=frame):
                self.assertTrue(GUARD.inspect(folder / frame, 1, "arena")["battle_hud"])
        for frame in ("first-burst/001.png", "07-preparation-fee.png", "08-after-guard-pause.png", "09-after-start-current.png"):
            with self.subTest(frame=frame):
                self.assertFalse(GUARD.inspect(folder / frame, 1, "arena")["battle_hud"])
        self.assertFalse(GUARD.inspect(active, 1, "unknown")["battle_hud"])

    def test_annotated_native_frames(self):
        records = json.loads((ROOT / "local/fixtures/testing/episode04-002/visual-guard-validation.json").read_text())
        self.assertGreaterEqual(len(records), 24)
        for record in records:
            with self.subTest(path=record["path"].replace("analysis/testing", "local/fixtures/testing")):
                actual = GUARD.inspect(ROOT / record["path"].replace("analysis/testing", "local/fixtures/testing"))
                self.assertEqual(actual["battle_hud"], record["expected_battle_hud"])

    def test_episode05_low_enemy_health_and_transitions(self):
        frames = {
            "local/fixtures/testing/episode05-005/cb0501/013.png": True,
            "local/fixtures/testing/episode05-005/cb0501/014.png": True,  # enemy25HP
            "local/fixtures/testing/episode05-005/cb0501-resume/001.png": False,  # win dialogue
            "local/fixtures/testing/episode05-005/16-cb0501-pause.png": False,
            "local/fixtures/testing/episode05-005/15-cb0501-prep.png": False,
            "local/fixtures/testing/episode05-005/05-story03-final.png": False,
        }
        for path, expected in frames.items():
            with self.subTest(path=path):
                self.assertEqual(GUARD.inspect(ROOT / path)["battle_hud"], expected)

    def test_expected_roster_defeat_crosses(self):
        frames = [
            ("local/fixtures/testing/episode05-005/cb0501/013.png", 5, True),
            ("local/fixtures/testing/episode05-005/cb0501/014.png", 5, True),
            ("local/fixtures/testing/episode05-005/cb0502/016.png", 1, True),
            ("local/fixtures/testing/episode05-005/cb0502/017.png", 1, False),
            ("local/fixtures/testing/episode05-005/cb0502/018.png", 1, False),
            ("local/fixtures/testing/episode05-005/33-cb0502-current.png", 1, False),
            ("local/fixtures/testing/episode04-002/visual-battle/020.png", 2, False),
        ]
        for path, enemies, expected in frames:
            with self.subTest(path=path):
                result = GUARD.inspect(ROOT / path, enemies)
                self.assertEqual(result["battle_hud"], expected)
                if path.endswith("cb0502/017.png"):
                    self.assertEqual(result["reason"], "all_expected_portraits_crossed")

    def test_episode06_red_and_yellow_attribute_badges(self):
        for name in ("24-cb0601-current.png", "25-cb0601-current.png"):
            with self.subTest(frame=name):
                result = GUARD.inspect(ROOT / "local/fixtures/testing/episode06-001" / name, 3)
                self.assertTrue(result["battle_hud"])
                self.assertGreaterEqual(result["left_warm_badge_pixels"], 300)
                self.assertGreaterEqual(result["right_warm_badge_pixels"], 300)
        result = GUARD.inspect(ROOT / "local/fixtures/testing/episode06-cb0601-001/020.png", 3)
        self.assertFalse(result["battle_hud"])

    def test_episode06_native_winning_retry(self):
        folder = ROOT / "local/fixtures/testing/episode06-cb0601-002"
        self.assertTrue(GUARD.inspect(folder / "027.png", 3)["battle_hud"])
        result = GUARD.inspect(folder / "035.png", 3)
        self.assertFalse(result["battle_hud"])
        self.assertEqual(result["crossed_portraits"], 3)
        self.assertEqual(result["reason"], "all_expected_portraits_crossed")

    def test_episode06_bibi_cutins_and_loss(self):
        folder = ROOT / "local/fixtures/testing/episode06-cb0602-001"
        for name in ("024.png", "035.png", "048.png"):
            with self.subTest(frame=name):
                self.assertFalse(GUARD.inspect(folder / name, 5)["battle_hud"])
        self.assertTrue(GUARD.inspect(folder / "040.png", 5)["battle_hud"])

    def test_player_skill_diagonal_transition_with_exposed_hud(self):
        folder = ROOT / "local/fixtures/testing/skill-ancestry-001/resume"
        result = GUARD.inspect(folder / "002.png", 5)
        # This captured cut-in exposed enough timer/HP/cyan to pass the old
        # gate. Reject the actual overlay, not by raising low-HP thresholds.
        self.assertGreaterEqual(result["timer_pixels"], 500)
        self.assertGreaterEqual(result["enemy_bar_pixels"], 10)
        self.assertGreaterEqual(result["cyan_badge_pixels"], 400)
        self.assertTrue(result["diagonal_skill_overlay"])
        self.assertFalse(result["battle_hud"])
        self.assertEqual(result["reason"], "hud_not_confirmed")
        for name in ("001.png", "004.png"):
            with self.subTest(frame=name):
                active = GUARD.inspect(folder / name, 5)
                self.assertFalse(active["diagonal_skill_overlay"])
                self.assertTrue(active["battle_hud"])

    def test_speed_line_skill_view_with_exposed_hud(self):
        folder = ROOT / "local/fixtures/testing/episode06-heal-001/resume"
        result = GUARD.inspect(folder / "002.png", 5)
        self.assertGreaterEqual(result["timer_pixels"], 500)
        self.assertGreaterEqual(result["enemy_bar_pixels"], 10)
        self.assertGreaterEqual(result["cyan_badge_pixels"], 400)
        self.assertFalse(result["diagonal_skill_overlay"])
        self.assertTrue(result["speed_line_skill_overlay"])
        self.assertFalse(result["battle_hud"])
        self.assertEqual(result["reason"], "hud_not_confirmed")
        for name in ("001.png", "003.png", "004.png"):
            with self.subTest(frame=name):
                actual = GUARD.inspect(folder / name, 5)
                self.assertFalse(actual["speed_line_skill_overlay"])
                self.assertTrue(actual["battle_hud"])

    def test_right_diagonal_enemy_skill_view_with_exposed_hud(self):
        folder = ROOT / "local/fixtures/testing/episode06-heal-002/finish"
        result = GUARD.inspect(folder / "002.png", 5)
        self.assertGreaterEqual(result["timer_pixels"], 500)
        self.assertGreaterEqual(result["enemy_bar_pixels"], 10)
        self.assertGreaterEqual(result["cyan_badge_pixels"], 400)
        self.assertTrue(result["diagonal_skill_overlay"])
        self.assertEqual(result["diagonal_skill_overlay_side"], "right")
        self.assertFalse(result["battle_hud"])
        self.assertTrue(GUARD.inspect(folder / "001.png", 5)["battle_hud"])

    def test_partial_left_speed_line_heal_transition(self):
        folder = ROOT / "local/fixtures/testing/support-stun-001/heal-resume"
        for name in ("002.png", "003.png"):
            with self.subTest(frame=name):
                result = GUARD.inspect(folder / name, 5)
                self.assertTrue(result["speed_line_skill_overlay"])
                self.assertFalse(result["battle_hud"])
        partial = GUARD.inspect(folder / "003.png", 5)
        self.assertIn("left", partial["speed_line_overlay_regions"])
        self.assertNotIn("whole", partial["speed_line_overlay_regions"])
        self.assertGreaterEqual(partial["timer_pixels"], 500)
        self.assertGreaterEqual(partial["cyan_badge_pixels"], 400)
        for name in ("001.png", "004.png"):
            with self.subTest(frame=name):
                self.assertTrue(GUARD.inspect(folder / name, 5)["battle_hud"])

    def test_enemy_only_frame_and_near_zero_front_with_live_reserves(self):
        enemy_only = GUARD.inspect(ROOT / "local/fixtures/testing/exchange-geometry-001/09-cleanup-pause.png", 5)
        self.assertGreaterEqual(enemy_only["timer_pixels"], 500)
        self.assertGreaterEqual(enemy_only["enemy_bar_pixels"], 10)
        self.assertGreaterEqual(enemy_only["cyan_badge_pixels"], 400)
        self.assertFalse(enemy_only["friendly_health_visible"])
        self.assertFalse(enemy_only["battle_hud"])
        # Actual2HP front fill has vanished, but live reserves retain bars.
        near_zero = GUARD.inspect(ROOT / "local/fixtures/testing/support-stun-001/heal-resume/004.png", 5)
        self.assertEqual(near_zero["friendly_front_bar_pixels"], 0)
        self.assertGreater(near_zero["friendly_rear_bar_pixels"], 0)
        self.assertTrue(near_zero["battle_hud"])


if __name__ == "__main__":
    unittest.main()
