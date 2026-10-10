"""Conservative pixel gate for the observed 1080x1920 battle HUD.

This is a visual fallback, not native combat identity, pause or outcome proof.
Caller must identify the expected encounter and hold exclusive emulator control.
"""
import json
import sys
from PIL import Image


def inspect(path, expected_enemies=None, layout="standard"):
    if layout not in ("standard", "arena"):
        return {"battle_hud": False, "reason": "unsupported_hud_layout"}
    if expected_enemies is not None and expected_enemies not in range(1, 6):
        return {"battle_hud": False, "reason": "unsupported_enemy_count"}
    with Image.open(path) as source:
        if source.size != (1080, 1920):
            return {"battle_hud": False, "reason": "unsupported_resolution"}
        image = source.convert("RGB")
    pixels = image.load()

    def count(box, predicate):
        x0, y0, x1, y1 = box
        return sum(predicate(*pixels[x, y]) for y in range(y0, y1) for x in range(x0, x1))

    # Isolate the lower-left large timer digits. The old box overlapped chapter
    # titles, allowing preparation/dialogue frames when the red threshold fell.
    timer = count((0, 175, 180, 215), lambda r, g, b: min(r, g, b) >= 220 and max(r, g, b) - min(r, g, b) <= 25)
    enemy_bar = count((0, 1020, 1080, 1050), lambda r, g, b: 145 <= r <= 245 and 20 <= g <= 110 and 20 <= b <= 115 and r - g >= 65 and r - b >= 65)
    def friendly_green(r, g, b):
        return (60 <= r <= 170 and 125 <= g <= 235 and 20 <= b <= 130
                and g - r >= 45 and g - b >= 65)

    friendly_front_bar = count((100, 1020, 580, 1050), friendly_green)
    # Rear health bars can preserve the positive signal when the front's
    # fill is subpixel or its actor is changing. Exclude the central glowing
    # exit panel, whose green decoration persists on enemy-only frames.
    friendly_rear_bar = sum(
        friendly_green(*pixels[x, y])
        for y in range(1450, 1680) for x in range(1080)
        if not (400 <= x <= 680 and y < 1500)
    )
    friendly_health_visible = friendly_front_bar + friendly_rear_bar > 0
    cyan_badge = count((0, 1005, 1080, 1055), lambda r, g, b: r < 120 and 65 <= g <= 220 and 65 <= b <= 230 and g - r >= 30 and b - r >= 30 and abs(g - b) <= 60)
    # Attribute hand glyphs can be red (Lantern) or yellow (Karl/bears), not
    # just cyan. Restrict the warm-colour alternative to BOTH fixed front
    # badge interiors, excluding the adjacent HP stripes and most body art.
    # Retained E06 active frames have 409/459 and 452/482 glyph pixels;
    # the full-screen bear skill cut-in has zero in both boxes.
    def warm_attribute(r, g, b):
        red_hand = (r >= 180 and 65 <= g <= 160 and 40 <= b <= 130
                    and r - g >= 65 and r - b >= 85)
        yellow_hand = (r >= 160 and g >= 135 and b <= 100
                       and r - b >= 90 and g - b >= 75 and abs(r - g) <= 85)
        return red_hand or yellow_hand

    # Original LEVELING_B arena positioning puts the left badge around205,
    # versus the Episode badge around170. Explicit layout selection only;
    # keep the same signal threshold and both-front requirement.
    left_badge_box = (175, 1010, 230, 1050) if layout == "arena" else (145, 1010, 200, 1050)
    left_warm_badge = count(left_badge_box, warm_attribute)
    right_warm_badge = count((665, 1010, 720, 1050), warm_attribute)
    attribute_badges = cyan_badge >= 400 or (left_warm_badge >= 300 and right_warm_badge >= 300)
    # A skill can leave timer/enemy HP exposed while its diagonal panel
    # enters from either lower side. Background cyan then passes the old
    # badge branch. Require a long coherent black edge with a bright inner
    # face, crossing both battle and airship regions, to reject this overlay.
    # This is calibrated visual evidence, not a native pause/skill flag.
    diagonal_skill_overlay = False
    diagonal_skill_overlay_side = None
    for side in ("left", "right"):
        for start in range(-80, 81, 10):
            for slope_step in range(10, 21):
                dark = bright_inside = valid = 0
                for y in range(1120, 1841, 20):
                    edge = round(start + (y - 1120) * slope_step / 20)
                    x = edge if side == "left" else 1080 - edge
                    if 25 <= x < 1050:
                        valid += 1
                        dark += max(pixels[x, y]) <= 35
                        inside_x = x - 25 if side == "left" else x + 25
                        bright_inside += min(pixels[inside_x, y]) >= 140
                if valid >= 30 and dark >= 28 and bright_inside >= 15:
                    diagonal_skill_overlay = True
                    diagonal_skill_overlay_side = side
                    break
            if diagonal_skill_overlay:
                break
        if diagonal_skill_overlay:
            break
    # A second observed skill-view style replaces the upper scene with a
    # dark backdrop and widely separated horizontal cyan speed streaks while
    # leaving timer/HP exposed. Require both features, rather than rejecting
    # ordinary cyan scenery or dark arena backgrounds by colour alone.
    # Test each half as well as the whole scene: a skill-view can be halfway
    # through its wipe while the other half has returned to ordinary scenery.
    dark_samples = [0, 0, 0]
    total_samples = [0, 0, 0]
    streak_rows = [[], [], []]
    for y in range(300, 651, 4):
        streak_hits = [0, 0, 0]
        for x in range(0, 1080, 4):
            r, g, b = pixels[x, y]
            dark = r <= 45 and g <= 60 and b <= 90
            streak = (r <= 140 and g >= 150 and b >= 180
                      and g - r >= 55 and b - r >= 70
                      and max(pixels[x, y - 12]) <= 110
                      and max(pixels[x, y + 12]) <= 110)
            for region in (0, 1 if x < 540 else 2):
                total_samples[region] += 1
                dark_samples[region] += dark
                streak_hits[region] += streak
        for region, hits in enumerate(streak_hits):
            if hits >= 30:
                streak_rows[region].append(y)
    speed_line_overlay_regions = [
        name for i, name in enumerate(("whole", "left", "right"))
        if dark_samples[i] / total_samples[i] >= 0.70
        and len(streak_rows[i]) >= 3
        and streak_rows[i][-1] - streak_rows[i][0] >= 80
    ]
    speed_line_skill_overlay = bool(speed_line_overlay_regions)
    # CB0501's live25-HP enemy bar retains15 matching pixels. Requiring70
    # stopped prompt attacks before the native victory transition. Retain a
    # nonzero stripe requirement; actual zero-enemy/result frames stay rejected.
    def red(x, y):
        r, g, b = pixels[x, y]
        return r >= 170 and g <= 100 and b <= 110 and r - max(g, b) >= 70

    def defeat_cross(cx):
        # Match both diagonal strokes and reject solid red portrait clothing.
        # Small offsets cover the retained native portrait placement/animation.
        for ox in range(-20, 21, 4):
            for cy in range(172, 193, 4):
                x = cx + ox
                first = sum(red(x + d, cy + d + w) for d in range(-26, 27) for w in (-3, 0, 3))
                if first < 110:
                    continue
                second = sum(red(x + d, cy - d + w) for d in range(-26, 27) for w in (-3, 0, 3))
                if second < 110:
                    continue
                off = sum(red(x + d, cy) + red(x, cy + d)
                          for d in list(range(-26, -11)) + list(range(12, 27)))
                if off <= 10:
                    return True
        return False

    crossed = 0
    if expected_enemies is not None:
        centers = [540 + 120 * (i - (expected_enemies - 1) / 2) for i in range(expected_enemies)]
        crossed = sum(defeat_cross(int(cx)) for cx in centers)
    all_crossed = expected_enemies is not None and crossed == expected_enemies
    active = (timer >= 500 and enemy_bar >= 10 and attribute_badges
              and not all_crossed and not diagonal_skill_overlay
              and not speed_line_skill_overlay and friendly_health_visible)
    return {"battle_hud": active, "hud_layout": layout, "timer_pixels": timer, "enemy_bar_pixels": enemy_bar,
            "friendly_front_bar_pixels": friendly_front_bar,
            "friendly_rear_bar_pixels": friendly_rear_bar,
            "friendly_health_visible": friendly_health_visible,
            "cyan_badge_pixels": cyan_badge, "left_warm_badge_pixels": left_warm_badge,
            "right_warm_badge_pixels": right_warm_badge, "expected_enemies": expected_enemies,
            "diagonal_skill_overlay": diagonal_skill_overlay,
            "diagonal_skill_overlay_side": diagonal_skill_overlay_side,
            "speed_line_skill_overlay": speed_line_skill_overlay,
            "speed_line_overlay_regions": speed_line_overlay_regions,
            "crossed_portraits": crossed,
            "reason": "all_expected_portraits_crossed" if all_crossed else
                      ("observed_hud" if active else "hud_not_confirmed")}


if __name__ == "__main__":
    print(json.dumps(inspect(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None,
                             sys.argv[3] if len(sys.argv) > 3 else "standard")))
