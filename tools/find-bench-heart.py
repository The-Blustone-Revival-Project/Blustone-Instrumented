"""Find a retained cost4 button inside the approved left-bench center region.

Connected white components propose alignments; acceptance uses the existing
skill guard's unchanged glyph/icon/circle thresholds. No input is sent. Actor,
funding (unless supplied), hitbox and native admission remain unproved.
"""
import argparse
import importlib.util
import json
import math
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('bench_skill_guard', HERE / 'battle-skill-button-guard.py')
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)
REGION = (250, 1300, 390, 1550)  # Inclusive permitted button centers only.
DIGIT_BOX = (76, 63, 116, 110)
NAMES = ('heart4', 'heart4-bench')


def components(mask):
    """Bounded eight-connected fill components, not OCR or actor identification."""
    width, height = mask.size
    values = mask.tobytes()
    visited = bytearray(len(values))
    result = []
    for first, value in enumerate(values):
        if not value or visited[first]:
            continue
        visited[first] = 1
        stack = [first]
        count = 0
        xmin = xmax = first % width
        ymin = ymax = first // width
        while stack:
            index = stack.pop()
            x, y = index % width, index // width
            count += 1
            xmin, xmax = min(xmin, x), max(xmax, x)
            ymin, ymax = min(ymin, y), max(ymax, y)
            for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < width and 0 <= yy < height:
                    neighbor = yy * width + xx
                    if values[neighbor] and not visited[neighbor]:
                        visited[neighbor] = 1
                        stack.append(neighbor)
        result.append((count, (xmin, ymin, xmax + 1, ymax + 1)))
    return result


def inspect(path, expected_enemies, rage=None):
    started = time.perf_counter()
    result = dict(visible_button=False, safe_center=None, center_region=list(REGION), expected_cost=4,
                  actor_identity='unproved', native_eligibility='unproved', native_hitbox='unproved',
                  funding='unproved', reason='unsupported_request')
    if type(expected_enemies) is not int or expected_enemies not in range(1, 6):
        return result
    if rage is not None:
        if type(rage) not in (int, float) or not math.isfinite(rage) or rage < 0:
            return result
        result['funding'] = 'caller_supplied_sufficient' if rage >= 4 else 'caller_supplied_insufficient'
        if rage < 4:
            result['reason'] = 'insufficient_caller_supplied_rage'
            return result
    hud = GUARD.HUD.inspect(path, expected_enemies)
    result['battle_hud'] = hud['battle_hud']
    if not hud['battle_hud']:
        result['reason'] = 'battle_hud_not_confirmed'
        return result
    with Image.open(path) as original:
        image = original.convert('RGB')
    # All possible cost-glyph pixels for centers in REGION and both retained
    # cost components. Proposal extraction never authorizes a center outside it.
    scan_box = (258, 1296, 430, 1600)
    found = components(GUARD.white_mask(image.crop(scan_box)))
    digit_components = [(n, box) for n, box in found
                        if 150 <= n <= 500 and 18 <= box[2] - box[0] <= 32
                        and 18 <= box[3] - box[1] <= 35]
    result['proposal_components'] = len(digit_components)
    if len(digit_components) > 32:
        result['reason'] = 'proposal_count_exceeded'
        return result
    annulus = Image.new('L', (GUARD.SIZE, GUARD.SIZE))
    drawing = ImageDraw.Draw(annulus)
    drawing.ellipse((3, 3, 133, 133), fill=255)
    drawing.ellipse((13, 13, 123, 123), fill=0)
    samples = annulus.histogram()[255]
    candidates = []
    checked = 0
    for name in NAMES:
        with Image.open(HERE / 'skill-button-templates' / (name + '.png')) as source:
            template = source.convert('RGB')
        template_white = GUARD.white_mask(template)
        digit = template_white.crop(DIGIT_BOX)
        # The cost4 is the separate small component inside the retained crop;
        # the larger heart must never become a proposal anchor.
        anchors = [(n, box) for n, box in components(template_white)
                   if 150 <= n <= 500 and box[0] >= DIGIT_BOX[0]
                   and box[1] >= DIGIT_BOX[1] and box[2] <= DIGIT_BOX[2]
                   and box[3] <= DIGIT_BOX[3]]
        if len(anchors) != 1:
            raise ValueError('Retained cost4 component provenance changed: ' + name)
        anchor = anchors[0][1]
        centers = set()
        for _, box in digit_components:
            sx = scan_box[0] + box[0] - anchor[0] + 68
            sy = scan_box[1] + box[1] - anchor[1] + 68
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    cx, cy = sx + dx, sy + dy
                    if REGION[0] <= cx <= REGION[2] and REGION[1] <= cy <= REGION[3]:
                        centers.add((cx, cy))
        for cx, cy in sorted(centers):
            checked += 1
            patch = image.crop((cx - 68, cy - 68, cx + 69, cy + 69))
            mask = GUARD.white_mask(patch)
            glyph = GUARD.overlap(mask.crop(DIGIT_BOX), digit)
            if glyph < .90:
                continue
            icon = GUARD.overlap(mask, template_white)
            if icon < .88:
                continue
            difference = ImageChops.multiply(ImageChops.difference(patch, template).convert('L'), annulus)
            error = sum(i * n for i, n in enumerate(difference.histogram())) / samples
            if error <= 18:
                candidates.append((name, cx, cy, glyph, icon, error))
    result['checked_alignments'] = checked
    result['elapsed_seconds'] = round(time.perf_counter() - started, 6)
    if not candidates:
        result['reason'] = 'retained_button_appearance_not_confirmed'
        return result
    best = max(candidates, key=lambda row: row[3] + row[4] - row[5] / 255)
    if any((row[1] - best[1]) ** 2 + (row[2] - best[2]) ** 2 > 16 ** 2 for row in candidates):
        result['reason'] = 'ambiguous_button_match'
        return result
    result.update(visible_button=True, safe_center=list(best[1:3]), template=best[0],
                  reason='retained_button_appearance',
                  measurements=dict(cost_fill_overlap=best[3], icon_fill_overlap=best[4],
                                    circle_context_luminance_error=best[5]))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('expected_enemies', type=int)
    parser.add_argument('--rage', type=float)
    args = parser.parse_args()
    print(json.dumps(inspect(args.image, args.expected_enemies, args.rage)))
