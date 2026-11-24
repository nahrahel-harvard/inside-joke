"""Regression test for the comic-grid safety net in art.looks_like_grid.

Real failure (2026-11-24): the image model drew a 2x2 comic grid inside a single
comic panel because the prompt said "panels". The detector should flag a grid
and leave a single busy scene alone."""
import random
import unittest

from PIL import Image, ImageDraw

from inside_joke.art import looks_like_grid


def busy(size, seed):
    rnd = random.Random(seed)
    img = Image.new("RGB", size, (240, 220, 200))
    d = ImageDraw.Draw(img)
    for _ in range(400):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        r = rnd.randrange(3, 14)
        d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(rnd.randrange(256) for _ in range(3)))
    return img


class GridDetectorTest(unittest.TestCase):
    def test_single_scene_is_not_a_grid(self):
        for seed in range(5):
            self.assertFalse(looks_like_grid(busy((400, 400), seed)), seed)

    def test_two_by_two_grid_is_flagged(self):
        img = Image.new("RGB", (400, 400), (255, 255, 255))
        for i, (x, y) in enumerate([(0, 0), (206, 0), (0, 206), (206, 206)]):
            img.paste(busy((194, 194), 10 + i), (x, y))
        self.assertTrue(looks_like_grid(img))

    def test_three_column_strip_is_flagged(self):
        img = Image.new("RGB", (400, 400), (20, 20, 20))
        for i, x in enumerate([0, 136, 272]):
            img.paste(busy((128, 400), 20 + i), (x, 0))
        self.assertTrue(looks_like_grid(img))


if __name__ == "__main__":
    unittest.main()
