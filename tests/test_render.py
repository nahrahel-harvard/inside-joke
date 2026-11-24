"""Renderer and encoder, offline with placeholder art.

    .venv/bin/python -m unittest tests.test_render -v
"""
from __future__ import annotations

import copy
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]

from fixtures import PROSPECT, SAMPLE_TEXT, placeholder_arts  # noqa: E402
from PIL import Image, ImageChops, ImageFont  # noqa: E402

from inside_joke import config, render  # noqa: E402
from inside_joke.formats import ORDER  # noqa: E402

ONE_MB = 1024 * 1024


def encode(fmt, text, out: pathlib.Path, name=None, **kw):
    frames = render.render(fmt, placeholder_arts(fmt), text, PROSPECT)
    name = name or fmt
    gif, png = out / f"{name}.gif", out / f"{name}.png"
    info = render.encode(frames, gif, png, **kw)
    return info, gif, png


class RenderTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_all_formats_render_under_1mb(self):
        for fmt in ORDER:
            info, gif, png = encode(fmt, SAMPLE_TEXT[fmt], self.out)
            self.assertLess(gif.stat().st_size, ONE_MB, fmt)
            self.assertTrue(gif.read_bytes().startswith(b"GIF8"), fmt)
            self.assertTrue(png.exists(), fmt)
            self.assertGreater(info["frames"], 1, fmt)
            self.assertEqual(info["scale"], 1.0, fmt)

    def test_outlook_first_frame_is_complete_final_frame(self):
        for fmt in ORDER:
            _, gif, png = encode(fmt, SAMPLE_TEXT[fmt], self.out)
            with Image.open(gif) as im:
                im.seek(0)
                self.assertEqual(im.info.get("duration"), 20, fmt)
                first = im.convert("RGB")
                im.seek(im.n_frames - 1)
                last = im.convert("RGB")
            with Image.open(png) as p:
                poster = p.convert("RGB")
            self.assertEqual(first.size, poster.size, fmt)
            # Frame 1 and the last frame are the same final image with the same palette.
            self.assertIsNone(ImageChops.difference(first, last).getbbox(), fmt)
            # The PNG poster is that final image before GIF quantization, so allow
            # palette rounding only.
            diff = ImageChops.difference(first, poster).convert("L")
            mean = sum(i * n for i, n in enumerate(diff.histogram())) / (poster.width * poster.height)
            self.assertLess(mean, 4.0, fmt)

    def test_outlook_safe_off_skips_the_20ms_frame(self):
        _, gif, _ = encode("meme", SAMPLE_TEXT["meme"], self.out, outlook_safe=False)
        with Image.open(gif) as im:
            self.assertNotEqual(im.info.get("duration"), 20)

    def test_deterministic_bytes(self):
        for fmt in ORDER:
            _, g1, p1 = encode(fmt, SAMPLE_TEXT[fmt], self.out, name=f"{fmt}-a")
            _, g2, p2 = encode(fmt, SAMPLE_TEXT[fmt], self.out, name=f"{fmt}-b")
            self.assertEqual(g1.read_bytes(), g2.read_bytes(), fmt)
            self.assertEqual(p1.read_bytes(), p2.read_bytes(), fmt)

    def test_long_text_still_fits(self):
        thirty = " ".join(["forecast"] * 30)
        for fmt in ORDER:
            text = copy.deepcopy(SAMPLE_TEXT[fmt])
            for k, v in text.items():
                if k in ("prop", "stats"):
                    continue
                if isinstance(v, list):
                    text[k] = [thirty for _ in v]
                elif isinstance(v, dict):
                    text[k] = {kk: thirty for kk in v}
                else:
                    text[k] = thirty
            info, gif, _ = encode(fmt, text, self.out)
            self.assertLess(gif.stat().st_size, ONE_MB, fmt)

    def test_calendar_flip_invalid_month(self):
        for bad in ("XYZ", "", "Q2", "april"):
            text = {**SAMPLE_TEXT["reply"], "prop": "calendar_flip", "prop_value": bad}
            frames = render.render("reply", placeholder_arts("reply"), text, PROSPECT)
            self.assertGreater(len(frames), 3, bad)

    def test_other_props_render(self):
        for prop, val in (("progress_bar", "ERP migration"), ("stamp", "Q2 ready"), ("stamp", "")):
            text = {**SAMPLE_TEXT["reply"], "prop": prop, "prop_value": val}
            _, gif, _ = encode("reply", text, self.out, name=f"reply-{prop}")
            self.assertLess(gif.stat().st_size, ONE_MB)

    def test_bad_brand_color_falls_back(self):
        frames = render.render("card", placeholder_arts("card"), SAMPLE_TEXT["card"],
                               {**PROSPECT, "brand_color": "not-a-color"})
        self.assertTrue(frames)


class FontTest(unittest.TestCase):
    EXPECTED_STYLE = {
        "impact": ("Anton", "Regular"), "black": ("Archivo Black", "Regular"),
        "bold": ("Inter", "Bold"), "regular": ("Inter", "Regular"),
        "rounded": ("Nunito", "ExtraBold"), "serif_bold": ("Playfair Display", "Bold"),
        "serif_italic": ("Playfair Display", "Italic"), "didot": ("Playfair Display", "Bold"),
        "comic": ("Comic Neue", "Bold"), "mono": ("Courier Prime", "Bold"),
    }

    def test_same_ten_keys(self):
        self.assertEqual(set(config.FONTS), set(self.EXPECTED_STYLE))

    def test_bundled_fonts_load_at_the_right_weight(self):
        for key, (path, idx) in config.FONTS.items():
            self.assertTrue(path.startswith(str(config.FONT_DIR)), f"{key} is not using the bundled font")
            f = ImageFont.truetype(path, 24, index=idx)
            self.assertEqual(f.getname(), self.EXPECTED_STYLE[key], key)


if __name__ == "__main__":
    unittest.main()
