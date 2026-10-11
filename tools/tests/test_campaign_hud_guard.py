"""Retained live campaign frames and counterexamples; no native outcome proof."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('campaign_guard', ROOT / 'tools/campaign-hud-guard.py')
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)
LIVE = ROOT / 'local/captures/testing/campaign-levels-001'


class CampaignHud(unittest.TestCase):
    def test_actual_active_and_pause(self):
        for index in (5, 9, 13):
            self.assertTrue(GUARD.inspect(LIVE / f'fight/{index:03}.png')['battle_hud'])
        self.assertFalse(GUARD.inspect(LIVE / '11-paused.png')['battle_hud'])
        self.assertTrue(GUARD.inspect(LIVE / 'recovered-fight/013.png')['battle_hud'])
        self.assertFalse(GUARD.inspect(LIVE / '13-recovery-paused.png')['battle_hud'])

    def test_native_menus_and_other_combat_layouts(self):
        for name in ('01-current.png', '02-village.png', '03-airport.png',
                     '04-area.png', '07-snowfield.png', '09-preparation.png'):
            self.assertFalse(GUARD.inspect(LIVE / name)['battle_hud'])
        episode = ROOT / 'local/captures/testing/bench-heal-live-002'
        for name in ('05-prep.png', '06-paused.png', '07-after-contact.png', '13-settled-map.png'):
            self.assertFalse(GUARD.inspect(episode / name)['battle_hud'])
        retained = ROOT / 'local/fixtures/testing/campaign-result-gate-001'
        for name in ('39-before-result-touch.png', '40-before-result-touch.png'):
            self.assertFalse(GUARD.inspect(retained / name)['battle_hud'])

    def test_each_required_hud_feature_removal_refuses(self):
        boxes = ((250, 330, 855, 390), (480, 330, 630, 385), (215, 330, 270, 390),
                 (300, 1020, 700, 1050))
        for box in boxes:
            with self.subTest(box=box), tempfile.TemporaryDirectory() as directory:
                image = Image.open(LIVE / 'fight/013.png').convert('RGB')
                ImageDraw.Draw(image).rectangle(box, fill=(0, 0, 0))
                path = Path(directory) / 'removed.png'
                image.save(path)
                self.assertFalse(GUARD.inspect(path)['battle_hud'])

    def test_lower_hud_alternatives_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Image.open(LIVE / 'fight/013.png').convert('RGB')
            drawing = ImageDraw.Draw(image)
            drawing.rectangle((475, 1350, 610, 1440), fill=(0, 0, 0))
            drawing.rectangle((720, 1840, 780, 1900), fill=(0, 0, 0))
            path = Path(directory) / 'removed.png'
            image.save(path)
            self.assertFalse(GUARD.inspect(path)['battle_hud'])

    def test_unsupported_layout_count_and_resolution(self):
        path = LIVE / 'fight/013.png'
        for count in (0, 2, True, '1'):
            self.assertFalse(GUARD.inspect(path, count)['battle_hud'])
        self.assertFalse(GUARD.inspect(path, 1, 'standard')['battle_hud'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'small.png'
            Image.new('RGB', (540, 960)).save(path)
            self.assertFalse(GUARD.inspect(path)['battle_hud'])


if __name__ == '__main__':
    unittest.main()
