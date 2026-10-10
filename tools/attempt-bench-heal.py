"""One normal-input attempt after caller verifies paused CB0602 and C004 bench.

No JDWP, game-memory writes or acceptance inference. The caller must first
verify living C004/1000005 on the bench and living Nene/1000004 at the front.
The detector proves only a retained visible heart/cost4 in the bounded region.
"""
import argparse
import importlib.util
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bench_finder', ROOT / 'tools/find-bench-heart.py')
FINDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINDER)
CAPTURES = ROOT / 'local/captures/testing'


def checked_center(result):
    center = result.get('safe_center')
    if result.get('visible_button') is not True or type(center) is not list or len(center) != 2:
        return None
    x, y = center
    if type(x) is not int or type(y) is not int or not (250 <= x <= 390 and 1300 <= y <= 1550):
        return None
    return x, y


class Android:
    def __init__(self, pid):
        self.pid = pid
        self.prefix = [str(ROOT / 'local/toolchains/android-sdk/platform-tools/adb.exe'),
                       '-s', '127.0.0.1:5555']

    def run(self, *args):
        # subprocess.run waits for and terminates this exact child on timeout;
        # no detached pending helper and no retry is created.
        return subprocess.run(self.prefix + list(args), check=True, capture_output=True, timeout=5).stdout

    def confirm(self):
        actual = self.run('shell', 'pidof', 'com.vshower.prd_sr.instrumented').decode().strip()
        if actual != self.pid:
            raise RuntimeError('Client identity changed; stop inputs')
        foreground = self.run('shell', 'dumpsys', 'activity', 'activities').decode(errors='replace')
        import re
        if not re.search(r'mResumedActivity: ActivityRecord\{[^}]*com\.vshower\.prd_sr\.instrumented/com\.vshower\.instrumented\.InstrumentedActivity', foreground):
            raise RuntimeError('Instrumented activity is not resumed; stop inputs')


def attempt(android, folder, inspect=FINDER.inspect, sleep=time.sleep):
    proof = dict(expected_combat='CB0602', expected_client=android.pid, source_serial=1000005,
                 receiver_serial=1000004, skill_contact_sent=False, observer='none',
                 native_acceptance='unproved', caller_native_precondition='required')
    started = time.perf_counter()
    resumed = False
    try:
        android.confirm()
        # Mark before input: if its completion is uncertain, cleanup still
        # verifies identity before requesting normal Back pause.
        resumed = True
        android.run('shell', 'input', 'tap', '540', '875')
        sleep(.8)
        for frame in range(3):
            path = folder / f'before-contact-{frame:02}.png'
            captured_at = time.perf_counter()
            path.write_bytes(android.run('exec-out', 'screencap', '-p'))
            result = inspect(path, 5)
            (folder / f'button-guard-{frame:02}.json').write_text(json.dumps(result, indent=2) + '\n')
            proof['visible_frames_checked'] = frame + 1
            center = checked_center(result)
            if center is not None:
                android.confirm()
                proof['capture_to_contact_seconds'] = time.perf_counter() - captured_at
                if proof['capture_to_contact_seconds'] > 2:
                    proof['decline_reason'] = 'capture_age_exceeds_two_seconds'
                    break
                x, y = map(str, center)
                proof['point'] = list(center)
                proof['skill_contact_attempted'] = True
                android.run('shell', 'input', 'swipe', x, y, x, y, '200')
                proof['skill_contact_sent'] = True
                break
            sleep(.1)
    except Exception as error:
        proof['input_error'] = str(error)
    finally:
        if resumed:
            try:
                android.confirm()
                android.run('shell', 'input', 'keyevent', '4')
                proof['normal_pause_requested'] = True
            except Exception as error:
                proof['pause_error'] = str(error)
        proof['elapsed_seconds'] = time.perf_counter() - started
        (folder / 'play-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-client-pid', required=True)
    parser.add_argument('--evidence-dir', required=True, type=Path)
    parser.add_argument('--verified-paused-cb0602-c004-bench-nene-front', required=True, action='store_true',
                        help='Caller attests a fresh native precondition; pixels do not establish it')
    args = parser.parse_args()
    if not args.expected_client_pid.isascii() or not args.expected_client_pid.isdigit() or int(args.expected_client_pid) <= 0:
        parser.error('Expected PID must be a positive decimal integer')
    folder = args.evidence_dir.resolve()
    if not folder.is_relative_to(CAPTURES.resolve()) or folder == CAPTURES.resolve():
        parser.error('Evidence must be a fresh descendant of local/captures/testing')
    if folder.exists():
        parser.error('Use a fresh evidence directory')
    folder.mkdir(parents=True)
    proof = attempt(Android(args.expected_client_pid), folder)
    print(json.dumps(proof), flush=True)
    return 1 if 'input_error' in proof or 'pause_error' in proof else 0


if __name__ == '__main__':
    raise SystemExit(main())
