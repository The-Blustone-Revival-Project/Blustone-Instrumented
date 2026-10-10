"""Fail-closed visual match for retained native skill-button appearances.

This does not identify an actor, read Rage, or prove native skill eligibility.
It requires a caller-approved physical point and expected cost. Templates retain
circle context and the cost glyph; unfamiliar rendering is deliberately denied.
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('battle_hud_guard', HERE / 'battle-hud-guard.py')
HUD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HUD)
TEMPLATES = {3: ('shield3', 'sword3'), 4: ('heart4', 'heart4-front', 'heart4-front-hit', 'heart4-bench', 'heart4-bench-live')}
SIZE = 137

def white_mask(image):
    # Solid icon/cost fill, not pale translucent circle or scene brightness.
    return Image.eval(image.convert('RGB').convert('L'), lambda v: 255 if v >= 235 else 0)

def overlap(a, b):
    aa = a.histogram()[255]
    bb = b.histogram()[255]
    common = ImageChops.multiply(a, b).histogram()[255]
    return 2 * common / (aa + bb) if aa + bb else 0

def inspect(path, x, y, cost, expected_enemies, rage=None):
    result = {'visible_button': False, 'visible_skill_button': False, 'point': [x, y], 'expected_cost': cost,
              'actor_identity': 'unproved', 'native_eligibility': 'unproved',
              'funding': 'unproved', 'reason': 'unsupported_request'}
    if (cost not in TEMPLATES or type(x) is not int or type(y) is not int
            or expected_enemies not in range(1, 6) or not (100 <= x <= 980 and 350 <= y <= 1600)):
        return result
    if rage is not None:
        if not isinstance(rage, (int, float)) or not math.isfinite(rage) or rage < 0:
            return result
        result['funding'] = 'caller_supplied_sufficient' if rage >= cost else 'caller_supplied_insufficient'
        if rage < cost:
            result['reason'] = 'insufficient_caller_supplied_rage'
            return result
    hud = HUD.inspect(path, expected_enemies)
    result['battle_hud'] = hud['battle_hud']
    if not hud['battle_hud']:
        result['reason'] = 'battle_hud_not_confirmed'
        return result
    with Image.open(path) as original:
        image = original.convert('RGB')
    annulus = Image.new('L', (SIZE, SIZE))
    draw = ImageDraw.Draw(annulus)
    draw.ellipse((3, 3, 133, 133), fill=255)
    draw.ellipse((13, 13, 123, 123), fill=0)
    samples = annulus.histogram()[255]
    digit_box = (76, 63, 116, 110)
    candidates = []
    for name in TEMPLATES[cost]:
        # The front skill circle sits against the battle backdrop. Its retained
        # context cannot authorize a rear button against the airship backdrop.
        if name.startswith('heart4-front') and y > 700:
            continue
        if name.startswith('heart4-bench') and y < 1300:
            continue
        with Image.open(HERE / 'skill-button-templates' / (name + '.png')) as source:
            template = source.convert('RGB')
        template_white = white_mask(template)
        digit = template_white.crop(digit_box)
        for dy in range(-32, 33):
            for dx in range(-32, 33):
                cx, cy = x + dx, y + dy
                patch = image.crop((cx-68, cy-68, cx+69, cy+69))
                mask = white_mask(patch)
                glyph_overlap = overlap(mask.crop(digit_box), digit)
                if glyph_overlap < .90:
                    continue
                icon_overlap = overlap(mask, template_white)
                if icon_overlap < .88:
                    continue
                difference = ImageChops.multiply(ImageChops.difference(patch, template).convert('L'), annulus)
                error = sum(i*n for i, n in enumerate(difference.histogram())) / samples
                if error <= 18:
                    candidates.append((name, cx, cy, glyph_overlap, icon_overlap, error))
    if not candidates:
        result['reason'] = 'retained_button_appearance_not_confirmed'
        return result
    # Multiple neighboring alignments are one match; distant matches are ambiguous.
    best = max(candidates, key=lambda c: c[3] + c[4] - c[5]/255)
    # Retained front heart contexts are appearances of the same heart/cost,
    # while shield and sword remain distinct icon classes.
    kind = lambda name: 'heart4' if name.startswith('heart4-') else name
    if any(kind(c[0]) != kind(best[0]) or (c[1]-best[1])**2 + (c[2]-best[2])**2 > 16**2 for c in candidates):
        result['reason'] = 'ambiguous_button_match'
        return result
    result.update(visible_button=True, visible_skill_button=True, reason='retained_button_appearance',
                  template=best[0], matched_center=list(best[1:3]),
                  measurements={'cost_fill_overlap': best[3], 'icon_fill_overlap': best[4],
                                'circle_context_luminance_error': best[5]})
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('x', type=int)
    parser.add_argument('y', type=int)
    parser.add_argument('cost', type=int)
    parser.add_argument('expected_enemies', type=int)
    parser.add_argument('--rage', type=float)
    args = parser.parse_args()
    print(json.dumps(inspect(args.image, args.x, args.y, args.cost, args.expected_enemies, args.rage)))
