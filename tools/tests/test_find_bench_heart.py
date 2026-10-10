"""Retained pixel controls for the bounded bench finder, not native admission."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('bench_finder', ROOT / 'tools/find-bench-heart.py')
FINDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINDER)
BASE = ROOT / 'local/fixtures/testing'


class BenchHeartFinder(unittest.TestCase):
    def test_retained_vertical_motion(self):
        cases = [('episode-bench-heal-002', 'before-contact-00.png', [343, 1385]),
                 ('episode-bench-heal-002', 'before-contact-01.png', [342, 1380]),
                 ('episode-bench-heal-003', 'before-contact-01.png', [346, 1458])]
        for directory, filename, center in cases:
            with self.subTest(filename=(directory, filename)):
                result = FINDER.inspect(BASE / directory / filename, 5)
                self.assertTrue(result['visible_button'])
                self.assertEqual(result['safe_center'], center)
                self.assertLessEqual(result['checked_alignments'], 100)
                self.assertEqual(result['actor_identity'], 'unproved')
                self.assertEqual(result['native_eligibility'], 'unproved')
                self.assertEqual(result['funding'], 'unproved')

    def test_retained_refusals(self):
        paths = [BASE / 'episode-bench-heal-002/03-pre-contact-pause.png',
                 BASE / 'episode-bench-heal-002/01-map.png',
                 BASE / 'episode-bench-heal-002/05-loss-options.png',
                 BASE / 'episode-bench-heal-003/before-contact-00.png']
        for path in paths:
            with self.subTest(path=path):
                result = FINDER.inspect(path, 5)
                self.assertFalse(result['visible_button'])
                self.assertIsNone(result['safe_center'])

    def test_explicit_funding_and_request_bounds(self):
        path = BASE / 'episode-bench-heal-002/before-contact-00.png'
        self.assertEqual(FINDER.inspect(path, 5, 3.99)['reason'], 'insufficient_caller_supplied_rage')
        self.assertTrue(FINDER.inspect(path, 5, 4)['visible_button'])
        for invalid in [float('nan'), float('inf'), -1, True]:
            self.assertFalse(FINDER.inspect(path, 5, invalid)['visible_button'])
        for invalid in [0, 6, True, '5']:
            self.assertFalse(FINDER.inspect(path, invalid)['visible_button'])

    def test_blank_wrong_icon_and_ambiguity(self):
        # Deliberate pixel controls preserve the real upper battle HUD. They
        # verify refusal semantics; they are not additional native observations.
        source = Image.open(BASE / 'episode-bench-heal-002/before-contact-00.png').convert('RGB')
        template = Image.open(ROOT / 'tools/skill-button-templates/heart4-bench.png').convert('RGB')
        sword = Image.open(ROOT / 'tools/skill-button-templates/sword3.png').convert('RGB')
        for kind in ['blank', 'sword', 'ambiguous', 'outside']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                image = source.copy()
                ImageDraw.Draw(image).rectangle((180, 1220, 459, 1640), fill=(0, 0, 0))
                if kind == 'sword':
                    image.paste(sword, (343 - 68, 1385 - 68))
                elif kind == 'ambiguous':
                    for cy in [1320, 1510]:
                        image.paste(template, (343 - 68, cy - 68))
                elif kind == 'outside':
                    image.paste(template, (210 - 68, 1385 - 68))
                path = Path(directory) / 'control.png'
                image.save(path)
                result = FINDER.inspect(path, 5)
                self.assertFalse(result['visible_button'])
                if kind == 'ambiguous':
                    self.assertEqual(result['reason'], 'ambiguous_button_match')


if __name__ == '__main__':
    unittest.main()
