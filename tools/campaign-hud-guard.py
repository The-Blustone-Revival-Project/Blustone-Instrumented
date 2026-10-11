"""Pixel gate for the observed n_01_01 campaign HUD; no native identity proof.

Unlike Episode combat, this scene has a top blue enemy HP strip and no large
upper-left countdown. Root must identify the stage/party before using this gate.
"""
import argparse
import json
from PIL import Image


def inspect(path, expected_enemies=1, layout='campaign'):
    if type(expected_enemies) is not int or expected_enemies != 1 or layout != 'campaign':
        return dict(battle_hud=False, reason='unsupported_campaign_request')
    with Image.open(path) as source:
        if source.size != (1080, 1920):
            return dict(battle_hud=False, reason='unsupported_resolution')
        image = source.convert('RGB')
    pixels = image.load()

    def count(box, predicate):
        return sum(predicate(*pixels[x, y]) for y in range(box[1], box[3])
                   for x in range(box[0], box[2]))

    blue = count((250, 330, 855, 390), lambda r, g, b:
                 25 <= r <= 90 and 40 <= g <= 130 and 130 <= b <= 230 and b - r >= 80)
    digits = count((480, 330, 630, 385), lambda r, g, b: min(r, g, b) >= 220)
    enemy_badge = count((215, 330, 270, 390), lambda r, g, b:
                        r >= 170 and 70 <= g <= 150 and 40 <= b <= 120)
    front_health = count((300, 1020, 700, 1050), lambda r, g, b:
                         60 <= r <= 170 and 125 <= g <= 235 and 20 <= b <= 130
                         and g - r >= 45 and g - b >= 65)
    airship = count((475, 1350, 610, 1440), lambda r, g, b:
                   g >= 170 and g - r >= 35 and g - b >= 70)
    # Normal pause/resume can leave the bench view closed while combat runs.
    # The retained white stopwatch stays in the lower HUD in that state.
    stopwatch = count((720, 1840, 780, 1900), lambda r, g, b:
                      min(r, g, b) >= 220 and max(r, g, b) - min(r, g, b) <= 25)
    pause_button = count((220, 810, 860, 940), lambda r, g, b:
                        r >= 200 and 25 <= g <= 100 and 60 <= b <= 150 and r - g >= 100)
    active = (blue >= 1500 and digits >= 150 and enemy_badge >= 200
              and front_health >= 100 and (airship >= 300 or stopwatch >= 150)
              and pause_button < 2000)
    return dict(battle_hud=active, hud_layout='campaign', enemy_blue_pixels=blue,
                enemy_hp_digit_pixels=digits, enemy_badge_pixels=enemy_badge,
                friendly_front_bar_pixels=front_health, airship_pixels=airship,
                stopwatch_pixels=stopwatch,
                pause_button_pixels=pause_button, native_identity='unproved',
                native_outcome='unproved', reason='observed_hud' if active else 'hud_not_confirmed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('expected_enemies', type=int)
    parser.add_argument('layout')
    args = parser.parse_args()
    print(json.dumps(inspect(args.image, args.expected_enemies, args.layout)))
