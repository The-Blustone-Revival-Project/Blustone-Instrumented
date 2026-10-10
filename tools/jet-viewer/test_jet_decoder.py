from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jet_decoder import inflate_jet, inspect_bytes  # noqa: E402


class JetDecoderTests(unittest.TestCase):
    def test_embedded_mp4_keeps_box_size_before_ftyp(self) -> None:
        mp4 = struct.pack(">I4s4s", 19, b"ftyp", b"mp42") + b"payload"
        analysis, variants = inspect_bytes(b"custom-jet-header" + mp4, "sample.jet")
        self.assertEqual(analysis["media"][0]["mime"], "video/mp4")
        self.assertEqual(variants["media-raw-0"], mp4)

    def test_jet_zlib_layer_is_inflated(self) -> None:
        inflated = b"RWM\x00\x00\x00<motion name=\"RunCharacter\"/>"
        raw = b"header" + b"\x00" * 18 + zlib.compress(inflated)
        offset, decoded = inflate_jet(raw)
        self.assertEqual(offset, 24)
        self.assertEqual(decoded, inflated)
        analysis, variants = inspect_bytes(raw, "motion.jet")
        self.assertIn("inflated-0", variants)
        self.assertIn("RunCharacter", analysis["text"])

    def test_real_mp4_asset_is_detected(self) -> None:
        path = Path(__file__).resolve().parents[2] / "analysis" / "extracted" / "assets" / "MP4_GACHA.jet"
        if not path.exists():
            self.skipTest("APK asset corpus is not present")
        analysis, variants = inspect_bytes(path.read_bytes(), path.name)
        self.assertTrue(any(item["mime"] == "video/mp4" for item in analysis["media"]))
        self.assertTrue(variants["media-raw-0"].startswith(b"\x00\x00\x00\x18ftyp"))

    def test_real_snd_asset_is_detected_as_mp3(self) -> None:
        path = Path(__file__).resolve().parents[2] / "analysis" / "extracted" / "assets" / "C001_SND.jet"
        if not path.exists():
            self.skipTest("APK asset corpus is not present")
        analysis, variants = inspect_bytes(path.read_bytes(), path.name)
        audio = next(item for item in analysis["media"] if item["mime"] == "audio/mpeg")
        self.assertEqual(audio["offset"], 34)
        self.assertTrue(variants[audio["id"]].startswith(b"\xff\xfb"))

    def test_real_motion_asset_is_readable_after_inflation(self) -> None:
        path = Path(__file__).resolve().parents[2] / "analysis" / "extracted" / "assets" / "MOTION.jet"
        if not path.exists():
            self.skipTest("APK asset corpus is not present")
        analysis, _variants = inspect_bytes(path.read_bytes(), path.name)
        self.assertIn("RunCharacter", analysis["text"] or "")

    def test_real_i2_asset_is_reconstructed_as_png(self) -> None:
        path = Path(__file__).resolve().parents[2] / "analysis" / "extracted" / "assets" / "UI_MAIN.jet"
        if not path.exists():
            self.skipTest("APK asset corpus is not present")
        analysis, variants = inspect_bytes(path.read_bytes(), path.name)
        atlas = next(item for item in analysis["media"] if item["mime"] == "image/png")
        self.assertEqual(atlas["mime"], "image/png")
        self.assertTrue(variants[atlas["id"]].startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertTrue(any((layer.get("i2") or {}).get("width") == 1250 and (layer.get("i2") or {}).get("height") == 892 for layer in analysis["layers"]))

    def test_concatenated_cut_resources_all_render(self) -> None:
        path = Path(__file__).resolve().parents[2] / "analysis" / "extracted" / "assets" / "CUT_001.jet"
        if not path.exists():
            self.skipTest("APK asset corpus is not present")
        analysis, _variants = inspect_bytes(path.read_bytes(), path.name)
        self.assertEqual(analysis["resourceCount"], 6)
        self.assertEqual(sum(item["mime"] == "image/png" for item in analysis["media"]), 6)

    def test_rw_font_shader_and_leveling_resources_are_readable(self) -> None:
        root = Path(__file__).resolve().parents[2] / "analysis" / "extracted" / "assets"
        font, _ = inspect_bytes((root / "Font.jet").read_bytes(), "Font.jet")
        glsl, _ = inspect_bytes((root / "GLSL.jet").read_bytes(), "GLSL.jet")
        leveling, _ = inspect_bytes((root / "LEVELING.jet").read_bytes(), "LEVELING.jet")
        self.assertTrue(any(item["mime"] == "font/ttf" for item in font["media"]))
        self.assertIn("uniform mat4", glsl["text"] or "")
        shader_layers = [layer for layer in glsl["layers"] if layer.get("shader")]
        self.assertTrue(shader_layers)
        self.assertNotIn("Src:GL_SRC_ALPHA", shader_layers[0]["shader"]["fragment"])
        self.assertIn('"BeforeAppInit"', leveling["text"] or "")

    def test_character_package_exposes_atlases_and_spine_resources(self) -> None:
        path = Path(__file__).resolve().parents[2] / "analysis" / "extracted" / "assets" / "C001.jet"
        if not path.exists():
            self.skipTest("APK asset corpus is not present")
        analysis, _variants = inspect_bytes(path.read_bytes(), path.name)
        self.assertEqual(sum(item["mime"] == "image/png" for item in analysis["media"]), 2)
        spine_layers = [layer for layer in analysis["layers"] if layer.get("spine")]
        self.assertEqual(len(spine_layers), 2)

    def test_uncompressed_i2_resource_is_reconstructed(self) -> None:
        root = Path(__file__).resolve().parents[2] / "analysis" / "extracted" / "assets"
        paths = {name: root / name for name in ("PK_NEW.jet", "QUIZ.jet", "UI_FLAG.jet")}
        if not all(path.exists() for path in paths.values()):
            self.skipTest("APK asset corpus is not present")
        expected_counts = {"PK_NEW.jet": 123, "QUIZ.jet": 113, "UI_FLAG.jet": 248}
        for name, path in paths.items():
            analysis, variants = inspect_bytes(path.read_bytes(), path.name)
            self.assertEqual(analysis["resourceCount"], expected_counts[name])
            image = next(item for item in analysis["media"] if item["mime"] == "image/png")
            self.assertTrue(variants[image["id"]].startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
