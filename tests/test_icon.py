import tempfile
import unittest
from pathlib import Path

from PIL import Image

from silent_type import icon
from silent_type.icon import mark


class IconTests(unittest.TestCase):
    def test_states_draw_at_tray_and_shortcut_sizes(self):
        for size in (16, 32, 256):
            for state in ("ready", "recording", "working", "off"):
                image = mark(size, state)
                self.assertEqual(image.size, (size, size))
                self.assertIsNotNone(image.getbbox())

    def test_gold_badge_with_white_lips(self):
        image = mark(256)
        self.assertEqual(image.getpixel((128, 30))[:3], (0xAD, 0x83, 0x26))
        self.assertEqual(image.getpixel((128, 160))[:3], (255, 255, 255))
        self.assertEqual(image.getpixel((2, 2))[3], 0)

    def test_mouth_gap_stays_open_at_tray_size(self):
        column = [mark(16).getpixel((8, y))[:3] for y in range(16)]
        whites = [y for y, rgb in enumerate(column) if min(rgb) > 200]
        self.assertTrue(whites)
        gap = [y for y in range(whites[0], whites[-1]) if min(column[y]) < 200]
        self.assertTrue(gap, "upper and lower lips merged at 16 px")

    def test_off_is_gray_and_states_add_distinct_dots(self):
        r, g, b, _ = mark(64, "off").getpixel((32, 32))
        self.assertTrue(r == g == b)
        self.assertEqual(mark(64, "recording").getpixel((51, 51))[:3], (255, 255, 255))
        self.assertEqual(mark(64, "working").getpixel((51, 51))[:3], (0x17, 0x17, 0x17))

    def test_ico_holds_each_drawn_size(self):
        with tempfile.TemporaryDirectory() as folder:
            path = icon.write_ico(Path(folder) / "test.ico")
            with Image.open(path) as ico:
                self.assertIn((16, 16), ico.info["sizes"])
                ico.size = (16, 16)
                self.assertEqual(ico.convert("RGBA").tobytes(), mark(16).tobytes())

    def test_no_emoji_font_or_external_artwork(self):
        source = Path(icon.__file__).read_text(encoding="utf-8")
        self.assertNotIn("seguiemj", source.lower())
        self.assertNotIn("truetype", source.lower())


if __name__ == "__main__":
    unittest.main()
