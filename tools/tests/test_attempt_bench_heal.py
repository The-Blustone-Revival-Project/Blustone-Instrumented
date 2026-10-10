"""Input sequencing/refusal tests; no Android or native acceptance claims."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('attempt', ROOT / 'tools/attempt-bench-heal.py')
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


class FakeAndroid:
    pid = '123'

    def __init__(self, changed=False, fail_contact=False):
        self.calls = []
        self.confirms = 0
        self.changed = changed
        self.fail_contact = fail_contact

    def confirm(self):
        self.confirms += 1
        if self.changed and self.confirms >= 2:
            raise RuntimeError('Client identity changed')

    def run(self, *args):
        self.calls.append(args)
        if self.fail_contact and 'swipe' in args:
            raise TimeoutError('contact completion uncertain')
        return b'fake screenshot'


class AttemptTests(unittest.TestCase):
    def run_attempt(self, android, results):
        queue = iter(results)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            result = HELPER.attempt(android, folder, inspect=lambda *_: next(queue), sleep=lambda _: None)
            self.assertEqual(json.loads((folder / 'play-proof.json').read_text()), result)
            return result

    def test_moving_point_is_used_once(self):
        android = FakeAndroid()
        result = self.run_attempt(android, [{'visible_button': False},
            {'visible_button': True, 'safe_center': [346, 1458]}])
        self.assertTrue(result['skill_contact_sent'])
        self.assertEqual(result['point'], [346, 1458])
        self.assertEqual([c for c in android.calls if 'swipe' in c],
                         [('shell', 'input', 'swipe', '346', '1458', '346', '1458', '200')])
        self.assertEqual(android.calls[-1], ('shell', 'input', 'keyevent', '4'))
        self.assertEqual(result['native_acceptance'], 'unproved')

    def test_declines_are_bounded_and_pause(self):
        android = FakeAndroid()
        result = self.run_attempt(android, [{'visible_button': False}] * 3)
        self.assertFalse(result['skill_contact_sent'])
        self.assertEqual(result['visible_frames_checked'], 3)
        self.assertFalse(any('swipe' in call for call in android.calls))
        self.assertTrue(result['normal_pause_requested'])

    def test_changed_client_prevents_contact_and_cleanup_input(self):
        android = FakeAndroid(changed=True)
        result = self.run_attempt(android, [{'visible_button': True, 'safe_center': [343, 1385]}])
        self.assertIn('input_error', result)
        self.assertIn('pause_error', result)
        self.assertFalse(result['skill_contact_sent'])
        self.assertFalse(any('swipe' in call or 'keyevent' in call for call in android.calls))

    def test_uncertain_contact_never_retries_or_claims_sent(self):
        android = FakeAndroid(fail_contact=True)
        result = self.run_attempt(android, [{'visible_button': True, 'safe_center': [343, 1385]}])
        self.assertTrue(result['skill_contact_attempted'])
        self.assertFalse(result['skill_contact_sent'])
        self.assertEqual(sum('swipe' in call for call in android.calls), 1)
        self.assertTrue(result['normal_pause_requested'])

    def test_malformed_center_refuses(self):
        for center in [[True, 1385], [343, 1385.0], [249, 1385], [391, 1385],
                       [343, 1299], [343, 1551], [343], '343,1385', (343, 1385), None]:
            with self.subTest(center=center):
                self.assertIsNone(HELPER.checked_center({'visible_button': True, 'safe_center': center}))
        self.assertIsNone(HELPER.checked_center({'visible_button': 1, 'safe_center': [343, 1385]}))

    def test_stale_capture_refuses_contact(self):
        android = FakeAndroid()
        with patch.object(HELPER.time, 'perf_counter', side_effect=[0, 1, 4, 5]):
            result = self.run_attempt(android, [{'visible_button': True, 'safe_center': [343, 1385]}])
        self.assertEqual(result['decline_reason'], 'capture_age_exceeds_two_seconds')
        self.assertFalse(result['skill_contact_sent'])
        self.assertFalse(any('swipe' in call for call in android.calls))
        self.assertTrue(result['normal_pause_requested'])


if __name__ == '__main__':
    unittest.main()
