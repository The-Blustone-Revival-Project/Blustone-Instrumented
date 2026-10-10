"""Standalone ordinary campaign visual observer; never authorizes input or infers outcome.

Only calibrated for retained 1080x1920 native frames. All positive anchors plus a
horizontal friendly HP fill/track are required. Unknown modal/skill/terminal
states can retain these anchors: caller must resolve each frame visually.
"""
import argparse
import base64
import json
import struct
import zlib
from PIL import Image

# Sparse foreground masks sampled from actual retained native images. Coordinates
# preserve icon/arc/mountain geometry; digits, pin, scene and hunter art excluded.
# Positive source: campaign-exp-001/fight/013; negative text sources: r017, 06-prep.
MASK_DATA = {'crate': 'eJwl0ltPE0EUB/DzRYwPNJiGtNVyq9ISaE2XlpVaqm0Rw60RSmsbL1DDLTFi2rDBjsG1ZmvYCAs6oqtklMyD8Rbw9q38b3k6mTMzv3NOZshFmpL2kJu0w+M8eUlLLvmpkzTxq0gB0sYedlMIyWU/hUl70IiTQtrn30VSSYsveCiJkycFchHLr/ZBYZ+w5yV2x1SgsKM/JSis9HIQCis2I1AYExNQmPxXhsLyxiAUdvS3TGli/QkXMH2m4mD6m29OS3quHgGm8+95YPrrr/PA9MOTe8D0j8d3genvfjot6TdqQWD6wY8CMD004mDGaN4PzFh/dQ2YsfNlC5hR3U0DM6pWFlgrhJ1kFpixsT8GzNiWW8CM2l4WmNGrnAVmpordwMwNPgHMXH5eAGZqB1PATO3tJLBWCJ8Ghcz6hxww8z6bBWY+eT8NzDzFrESrM+vR3jgwa3g+AMx6vH8TmFWuXwFm3d5UgVlLzTQwq4ayKlmRKT8wq4pVmqye6BlgXJ11ML5iOmPy6HQXML7aGpNfnjwPjDv3wsRvrTvPyNd2M8B4aMwLjK/tZIDxQKwNmK3OOWPaC80kMDs87vwJe3E7BcweyHqA2f0ZHzB7YiUKzK6grEr2pWQHMLuyfR2YHRz1AROxuR5govBMBSaCKQ8wUWqMABMXk25gInC1A5jILEaAidKLBDDRHT8HTJQbCWCiL3UBmByY9AGT05sKMNk77AYmZ9gQMNk11A5MdirtwGSi3A9M5p7GgEnfYBswmWNxYNI/1P4f/GblhQ==',
 'coin': 'eJwlkO8rBFEUhs8/Yn7sLlL+TT5MaUpDTTRokosuupax1Cg+2BIftoQSkrLs7Jpld+deux+8h0+nZt7nOee9lJKXP03SOXnDD4vq5JnnMboib9S2qEHey8UU1cgv7i1Kye/MOEj6eoeTvtm3kPT1Jif9bMalW/JHLYuqFDBQo0BvjYELzLEF7m/U/8fV/2ggcuSAC/I5hx4oGGUW7VKY303CEvLHGoWcTCnsXk7AEvZbZVhC/VWC5W80EBnw9rA9a8MSdhZdWKJhk2+JjOJbou7NBCzRIGMgyubLAKIBqjxQ1FuxAcQa3asYygYQmz63jYu+i32x6brYF5tvF3jcqfO+WB8wHhcbfLUYNm3gothmXGRVF/tEc3ccFpHNskXkexVYxKeowCJ6ezYswpywRXyvOrDI12QaFtleKgGXxVkJuBx8MC7zay4ts1PuIHtrFnBpDhmXra0yOPXzxttVX/Cbqc8FG7jiO+v4d8ovr35SfnnF3C2p9rILXOlHF1zCHVJK3tfL4JLepg0u0ZK55Es44JKmrIBL9GPpF9uBCXc=',
 'victory_word': 'eJwtkl9nJEEUxfV5DMsQ8hqWEMJ8gCZP+xqGEELY1/k6YWiaomiapsgXCSEsS1j2NQ+9M9PTPdMzPX/23Dp5Oqruub9Tt6qSVzyfTqfkr+QTz02zwlSrV8zatmVtptqsWa3wjdI0GGG22WzojLU3ZMfjkc6s73taMnOOkMmSyZKb/EFuzk/JgHwYhuRoskeC3NBn0UlKlJHkXHIhuVLDteQH8rbtcKfaE/Ldboef2pwq9g1O6U6jOEvv4Cy9h+OYzHPL5ZJ5brvd4jI6MYY7HA5IJbexgUFOQVGmYr7Dc1omeDqZ4JXgNYqv639Em4VoqxEda6nkDn4+n2MCb4d/gt/v90R7oQuduhCzELOo65rMQszCbmKsWiqZxAZSClFKkw+UeoBSsFKwUgcsBStt2rFqqWQieRTlHRVvKfmFiscls9IBKzErPVxll3Wp1ViSSiao7HHuYzuZFaclLBjlN0LXdWQGfgYygzF71QYEa0gQFosFE4K+RtDXMCfzrA/ftXkjSSX3kgeE9XrNe/lavVD+AwKEv2M=',
 'prepare_word': 'eJwl069THDEYxvEn+RNq+h/UYNBVK6hoRTFoDKYC0wpOUNGaipqq7gxzgghiMnOTmRJReyfwJ66iGlwHyhxwe/sjy5v3Ud/JZZP9bHbPVKjHcTT7qO83rTlAncfRvkS97QZ7rHP2FHU/ZDvjaM6suK7CtORAY19g+u+hkeXTTdvLcv1xxsyZFRdUcFynOYRrusEcwbX9YD7ArTedmXDuG/MT7qntzQVHC2YJJ1zzh6Mb5kFjd3RP+xpu2w92D+72cWvfwhXZe84d88pTuPJ8Z3CP2064jlxHruaa69aymTgr+HKjN8w7Zp85hC+P8gle7id4T7zmAj7ngvfEe6o91f7/U2tf6UjUmj3dRZw6OoOXdyRAT6An0BOoabhZhUBLoCXciWWCsG46sQRawpCzuUTIep6BpEBSiVgCLYGWQIuOvjDfmRkzZ1bMNTerEGmJxTJBzHogkQjNJbNglsyNRhCxfFI7knUjlkhLpCXSEmmJPKUoH5GQIkmRpEhSmRNSIikV0mckebfmKxKPJ8nHYM6Z30jl6BZcsGTukOTo7C5S12exJFrSvby/j7rOniCV/9EPpGL5pVvbK47+MrdySR6fASI3FRc=',
 'begin_word': 'eJwlkqFWAkEYRs+ZDZMMGKRsYMuUCRIk+BwUi0EDBQMGCZItFIqZTLb4GhYLDyEHFkGW3Vm/mZvu+WZ+uN/+u9nEXrRtm72AVzC2l6QIM7TdiEewtt2w2WUmpawj1HXWI43AmMmhzfldwrPNQ/lrpsJma+Y6DMEsuHsXqrNZklbgQ5Pb0vwonWvTKB3+pI13mQUdcAV64EY4VeqS0yWnSxFxB+7BE5iBJViBT/AFvsHaFrFSKewP6lJQomAFKV0LTSN7gb3A7tiEQ+tYSMIUvAlayJy0sC7s9qrkqOSolFAKVSW7w+6wO+yOFSTcpv/MHqyrD0dVclRyVPJU8lTybRNUwofjSVqP1qP1aOOItB5tnJTWo/W8fo8hYaIR2Ue2z2Gfwz5PO4gfw0LYbHU34C7iH8pkT2s=',
 'paused_word': 'eJwlk61uG0EUheurgIKCAj9CQUCAgYFBH8DAwCDAwMAPUGBgYFAQYOAnMbAsK7KqUbWKRtGqGlUDBlgFAQEGAQEh/re8/umd+dCne+fsnrNz75YmMlqv16VHGV2v19Iv8Bs8gWfwJ0EGMjqfzzKkOZExj4+RJPxNUOUY5RjlFOUUyRTJFMkUyQzJDMkMyQzJDInZbDYqMUgSXsSciqL0Kma/35cWYrYqeaN6R/IBTgnyScxyuZQy1TdwKyYa3YlZrVZSQVIFNdBA2VS/00laYjSutGl2xFwuF+lS9UBfzG63k58aabuVB5oDMCTSRLJt+qKMG8z4sIzUGakzUmekzkidUAcNyQ6Hg4ZIVRcMJIuRhrxlIhYjy6Qtk7ZM2jJpSwiLu8Xd4m5xt7hb7szGm6hTdcAPsTv92i7VQCzzs4TICZEzuIRXsABv4B18gFOChsgJkeOeF0WhE0tVBVRBHTRAE9yDFmiDjuTH41FT51xdTuqc1DmpHYvpYvUPvIhTiQZ0BHQEdAR0ZHG6g7o9jkiO63HbdD0OI4eRw8hj5DHyGHmMPEYeIx+//av4gzqUadbAd87qVI30uPp5/DzL5/EL+AX8gi6R+gXmEBhAwDZgm3CjSrX9LCEafaFZBlUJ8T5rVA3QBB0JcV+6VD3Ql6A7oT9JKPS5B5pDbB9lrg4aaa7/kS7KPN7EQpvHoyab62+vkebxnTfpTEPEB3Q/E245u+OsAqo0m+CeZgu0afZAn+Ywvew/ByUeAA==',
 'resume_word': 'eJwlkq9uQjEUxmmLmOABJiYmJ/YAkxMTSMSy3CwLAtEsDWmWhjQ83hUIBALBAyAQCATZ+Hcv5d59p5/65bSnv+/c3qrSfLQpqRnQNGoOtK1aANekSvMp1ZIozZDVsK1rtWJVmhEXM9bEBrhUamtGzd9R7VBBtudeytAd7J0r3c0t+o7oEfdouTX6mZ0vxGu26Les1n0uDoCU9DvOnS664OI3MWbnD50THp9yiNJYwYyYEwtiDdRXjGs5rgAjWY5kOVJGH4CzkAO1/jK2+T0g3TLIMshR7eQKlsY1xzMSHGS4FyfXs2dLksUb7kUq3ItrqxqxjrGOsY6xea/A8cMJsY6xDv8PnylOpDume/4czw/zMlkvV1B7qj3VnmpPtafaU+3lhZQmUBYoE0AWKAsy/JNAnIHOQGegM9AZ6AwcMApWxAbAzW9Z7YAkzybKLSVU+JsdAAnd3IJnIy36gYuPcrxGemR6ZHpkemR6lPRxDsLTyC0TWqY56B+/kbJp'}

MASKS = {name: tuple(struct.iter_unpack(">HHBBB", zlib.decompress(base64.b64decode(data))))
         for name, data in MASK_DATA.items()}


# Paired foreground/background coordinates preserve ring arcs and mountain edge.
EDGE_DATA = {'auto': 'eJwd1PlLVFEYxvHzw/mzIpKQaN8IiWjfkIihsp2IELNsz7FpmqLStESkX9pcQkTEpQVCZLDNVIbhcmG4f0If/eHle57nvOfM3LnvM+Fw7AiH4v1wFI/gcTyGjdiIJ/AEnsSTmMMcnsLTeAab8Cyew72xEPbEh2E/7sODeAAP4yE8ikfwOB7DRmzEHObwFJ7GM9iEZ/EcnscLeBEv4WW8grtjMTTEvM8sWud9ftE6r6+oJ6+K+vKqGK7iVbyGu2Ip7HBHA+7C3diwcmdJzyNV0ldQpdCMzXgdt8dnYYs7duI2bMbr2II3sBXbcGt8HjY5sx23YAvewFZsw5t4GzfHl2GDM1txE7ZiG97E23gL7+LG2BXWxRf8Lv5zfle4h3fwAX997A71sVNft75Ofje/k/+a/0rv69CO62JvWBt76F66R09v6MD62Bfq4hu6j35D99N9dD/dp7c/FHBtfBtWW7djYaXnfVgV3+FH/IAD+MmZgfAEC/gU6+IQf5Aeogfpz/Qw/ZkepkfoEXqEHqFH6VF6lB6lx+gxeoweo8fpcXqcHqcn6El6gp6kp+hp32PK95jmT/Gn+V/4X/lf+Mv8ht891w/PNYMzOOv5Z8IafICPsB0fr/iz7ijzZ50t82fdXfa7lp2d87suez/tl+3P8ef4v/lz/N/exy93/PV+fun563390fOP/kP/o+fpRXMxr3fR+563t+R9z7tj0ZwsmJOKOVkwJxX7C+ahYs6WzFnVnC2Zs6r5rJjPxGxXzHliTivmNDHjVV5q3qvWqTmvmvFUZhJeTX4S65r8JtY1OUpkqKYS2aipxJnl/dR+Jt+pfGfyncp3Jt+pfGfyncp3JtupyvyHpCrzH5KqTNZTlcl7Ku+ZvKfynsl7Ku+ZvKfynv0HDRtbPQ==',
 'speed': 'eJwd1O9PklEUwPEX9/77rVHJGpWhkT/IzBgiEmPOGFMkQiJjZIpGhETkj8y13vSpF2ff53vOuQ/sPufeUI93Qj3eCg1sYBOb2MJ9rMV74nbYwR2sYx0b2MAmNrGF+1iOyVCKCWuSImFNUiSsSYqENUmR0J/UnwhtfIcdfI8H+AG72MNCvB/y8W4oYgFLWMQylrCF+9jB93iAH7CLPezhIR7iEeZjKuS8u4B5LGIhznhXyvOM/pTeGZHSPyNSoa+vj6e4Fh+G596Vwxf//9vD8BL7+BlP8QsO8CuuxtnwzNo1fP7/t2etS6nPqqfCEM9wJabDsjWr+AyHeIYj/IbZOB8W9K7gMo7wG45xiksxEzJxTl9G35x8Rn4uTPAcl+KC+hO+wJ/oWQrz8amepXCJmZgN6bgon5VflM/KL+rNhp+YiSvqy3yFL+tZDbOeL/EXzse18MjzJd5gOubCA8/z+Agv8QZ/4m9Mx7x6jud5jhf4Oi/wdV7kG7zIN3iJb/IS3+Rl/oqX+Sv/oRz+YDpW5CvyFfmKfEX+n2/xLb7F/3Ebt/VX9VfVq+pV+ap8Vb4mX5Ovydfka/I1+R35Xfkd+V1e53u8zvd4g7/hDf6GN/lb3uRv7UfLfrTtR8t+tHmbd3ibd+xzJzyOB/a5E64xI9Kxyw+8o+v7dK356Pt0rfnIe/wT7/FPvvOhNce+86E1x+bhSM+JeTjSc2J++noG5qevZ2DeTs3b0LydmrehOR2Y05H5HJjPkXkdmtexOR+a87E5H5rzsTkfmvOxszNSmzg7I8/fnZuRM/NdjPROnNOxs/XDeRw7Wz9CVe51vHAnTMSFu2AiLtwhE3GhPlW/cndMxZWeqbhyd0zFlfq5+rXaubhWOxfXfwGLw9g4',
 'distance': 'eJwNyiEOhDAUANGf/juswWDWrMFgMBgMF8JgMJiaGgyGFTQbGkKD4TRrMBhuwYjJM6Oj/HSUr0444YwzLrjgR1byPCt53XATb/6yU9C37BQ0wwxzzLHAAi1adOhwwEGCOeWgaC688MZbor7koKgJJphiiiWWWGGFNdbYYIMttthhhz32aNGiQyfxAaISRQc='}
EDGES = {name: tuple(struct.iter_unpack(">HHHH", zlib.decompress(base64.b64decode(data))))
         for name, data in EDGE_DATA.items()}

def inspect(path):
    try:
        with Image.open(path) as source:
            if source.size != (1080, 1920):
                return {"classification": "unconfirmed", "reason": "unsupported_resolution",
                        "input_authorized": False, "stage_identity_verified": False, "outcome": "unknown"}
            image = source.convert("RGB")
    except (OSError, ValueError):
        return {"classification": "unconfirmed", "reason": "unreadable_image",
                        "input_authorized": False, "stage_identity_verified": False, "outcome": "unknown"}
    pixels = image.load()

    def similarity(name, tolerance):
        mask = MASKS[name]
        return sum(max(abs(actual - expected) for actual, expected in
                       zip(pixels[x, y], (r, g, b))) <= tolerance
                   for x, y, r, g, b in mask) / len(mask)

    scores = {name: round(similarity(name, 35), 4) for name in ("crate", "coin")}
    for name, pairs in EDGES.items():
        scores[name] = round(sum(sum(pixels[x, y])/3 - sum(pixels[xo, yo])/3 > 5
                                 for x, y, xo, yo in pairs) / len(pairs), 4)
    # Retained ordinary impacts can saturate AUTO's upper arc and reverse the
    # translucent mountain's contrast against a bright background. Preserve
    # the full signed-edge path; this alternative requires the same mountain
    # geometry and almost all of AUTO's still-visible lower arc together.
    # It observes HUD pixels only, including effects; it cannot identify a
    # skill/modal state or authorize attacks during one.
    lower_arc = tuple(pair for pair in EDGES["auto"] if pair[1] >= 1200)
    alternatives = {
        "auto_lower_arc": round(sum(sum(pixels[x, y])/3 - sum(pixels[xo, yo])/3 > 5
                                    for x, y, xo, yo in lower_arc) / len(lower_arc), 4),
        "distance_unsigned": round(sum(abs(sum(pixels[x, y])/3 - sum(pixels[xo, yo])/3) > 5
                                      for x, y, xo, yo in EDGES["distance"])
                                   / len(EDGES["distance"]), 4),
    }
    # Positive recognition of the retained text states; absence of combat HUD
    # alone does not identify a menu, pause, death, win or loss.
    victory = similarity("victory_word", 25) >= .95
    paused = (similarity("paused_word", 25) >= .95
              and similarity("resume_word", 25) >= .95)
    preparation = (similarity("prepare_word", 25) >= .95
                   and similarity("begin_word", 25) >= .95)

    def green(pixel):
        r, g, b = pixel
        return 60 <= r <= 170 and 125 <= g <= 235 and 20 <= b <= 130 and g-r >= 45 and g-b >= 65

    # Require a coherent horizontal fill (>=24px), several adjacent rows and
    # a nearby gray/dark track. Portrait/exit-door green is not a health stripe.
    health = []
    for box in ((100, 1018, 600, 1051), (100, 1500, 1060, 1680)):
        x0, y0, x1, y1 = box
        for y in range(y0, y1-2):
            run = 0
            for x in range(x0, x1):
                if all(green(pixels[x, y+d]) for d in (0, 1, 2)):
                    run += 1
                else:
                    run = 0
                if run >= 24:
                    # Native bar edge is within 3px of its green fill. Use a
                    # narrow border, not a distant arbitrary scene dark patch.
                    left = x-run+1
                    border = [pixels[left+d, yy] for d in (3, 9, 15, 21)
                              for yy in (y-3, y+5) if 0 <= yy < 1920]
                    if sum(max(p)-min(p) < 32 and max(p) < 150 for p in border) >= 4:
                        health.append({"x": left, "y": y, "visible_fill_min": run})
                        break
            if health and health[-1]["y"] == y:
                break
    anchors = all(scores[name] >= (.88 if name in ("crate", "coin") else .70)
                  for name in scores)
    impact_anchors = (scores["crate"] >= .88 and scores["coin"] >= .88
                      and scores["speed"] >= .70
                      and alternatives["auto_lower_arc"] >= .95
                      and alternatives["distance_unsigned"] >= .70)
    if victory or preparation or paused:
        classification = "known_nonbattle"
        reason = ("recognized_retained_result_text" if victory else
                  "recognized_preparation_text" if preparation else "recognized_pause_text")
    elif (anchors or impact_anchors) and health:
        classification = "ordinary_hud_observed"
        reason = ("anchor_conjunction_and_friendly_health" if anchors else
                  "lower_arc_and_mountain_geometry_with_friendly_health")
    else:
        classification, reason = "unconfirmed", "ordinary_hud_not_confirmed"
    return {"classification": classification, "reason": reason, "anchor_scores": scores,
            "alternate_anchor_scores": alternatives,
            "friendly_health_stripes": health, "stage_identity_verified": False,
            "input_authorized": False, "outcome": "unknown"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    args = parser.parse_args()
    print(json.dumps(inspect(args.image)))
