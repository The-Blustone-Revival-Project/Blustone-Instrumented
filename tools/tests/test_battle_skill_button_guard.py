"""Retained native frames test a bounded visual aid, not native eligibility."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('skill_guard', ROOT / 'tools/battle-skill-button-guard.py')
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)
BASE = ROOT / 'local/fixtures/testing/episode6-complete-001'

class VisibleSkillButton(unittest.TestCase):
    def test_retained_physical_points(self):
        cases = [(10,930,1370,3,False), (15,300,535,3,True),
                 (15,450,535,3,False), (15,345,1385,4,True),
                 (20,345,1385,4,False), (20,947,1390,3,True),
                 (21,345,1385,4,False), (21,947,1390,3,True),
                 (25,450,535,3,False), (26,450,535,3,False),
                 (16,300,535,3,False), (47,947,1390,3,False)]
        for frame,x,y,cost,expected in cases:
            with self.subTest(frame=frame, point=(x,y), cost=cost):
                result = GUARD.inspect(BASE / 'fight' / f'{frame:03}.png', x,y,cost,5)
                self.assertEqual(result['visible_skill_button'], expected)
                self.assertEqual(result['visible_button'], expected)
                self.assertEqual(result['actor_identity'], 'unproved')
                self.assertEqual(result['native_eligibility'], 'unproved')
                self.assertEqual(result['funding'], 'unproved')

    def test_nonbattle_and_wrong_cost(self):
        for path in [BASE/'05-story.png', BASE/'09-map.png']:
            self.assertFalse(GUARD.inspect(path,300,535,3,5)['visible_skill_button'])
        for cost in [2,4]:
            self.assertFalse(GUARD.inspect(BASE/'fight/015.png',300,535,cost,5)['visible_skill_button'])
        self.assertFalse(GUARD.inspect(BASE/'fight/015.png',345,1385,3,5)['visible_skill_button'])

    def test_optional_explicit_funding(self):
        image = BASE/'fight/015.png'
        self.assertEqual(GUARD.inspect(image,300,535,3,5,2)['reason'], 'insufficient_caller_supplied_rage')
        self.assertTrue(GUARD.inspect(image,300,535,3,5,3)['visible_skill_button'])
        for invalid in [float('nan'), float('inf'), -1]:
            self.assertFalse(GUARD.inspect(image,300,535,3,5,invalid)['visible_skill_button'])

    def test_cost_or_circle_context_removal_denies(self):
        # These are deliberate corruptions of retained pixels, not extra native evidence.
        for box in [(302,509,342,556), (226,446,363,583)]:
            with tempfile.TemporaryDirectory() as directory:
                image = Image.open(BASE/'fight/015.png').convert('RGB')
                ImageDraw.Draw(image).rectangle(box, fill=(0,0,0))
                path=Path(directory)/'changed.png'
                image.save(path)
                self.assertFalse(GUARD.inspect(path,300,535,3,5)['visible_skill_button'])

    def test_circle_annulus_required_with_intact_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Image.open(BASE/'fight/015.png').convert('RGB')
            drawing = ImageDraw.Draw(image)
            drawing.ellipse((229,449,359,579), outline=(0,0,0), width=10)
            path=Path(directory)/'annulus.png'
            image.save(path)
            self.assertFalse(GUARD.inspect(path,300,535,3,5)['visible_button'])

    def test_unsupported_geometry(self):
        self.assertFalse(GUARD.inspect(BASE/'fight/015.png',1000,150,3,5)['visible_skill_button'])
        self.assertFalse(GUARD.inspect(BASE/'fight/015.png',300,535,3,0)['visible_skill_button'])

if __name__ == '__main__':
    unittest.main()
