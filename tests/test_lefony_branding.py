import json
import pathlib
import unittest

from PIL import Image


REPO = pathlib.Path(__file__).resolve().parents[1]
LOGO = REPO / "assets/lefony-logo.png"
THEME = REPO / "ports/lefony-prime-g2/themes/themes/local/lefony_light.json"
ICONS = THEME.with_suffix("")


class LefonyBrandingTest(unittest.TestCase):
    def test_native_boot_has_no_splash_stage(self):
        display = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/display.cpp").read_text()
        board = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/board.cpp").read_text()
        self.assertNotIn("lefony_splash.h", display)
        self.assertNotIn("showBootSplash", display)
        self.assertNotIn("showBootSplash", board)

    def test_palette_uses_exact_logo_green_and_white_canvas(self):
        palette = json.loads(THEME.read_text())
        colors = palette["colors"]
        self.assertEqual(palette["name"], "Lefony Light")
        self.assertEqual(colors["Toolbar"][""], "466645")
        self.assertEqual(colors["Home"]["CellBackgroundActive"], "466645")
        self.assertEqual(colors["Background"]["Hard"], "ffffff")
        self.assertEqual(colors["Home"]["Background"], "ffffff")

        logo = Image.open(LOGO).convert("RGBA")
        pixels = logo.load()
        opaque = [
            pixels[x, y][:3]
            for y in range(logo.height)
            for x in range(logo.width)
            if pixels[x, y][3] == 255
        ]
        dominant = max(set(opaque), key=opaque.count)
        self.assertEqual(dominant, (0x46, 0x66, 0x45))

    def test_software_color_inversion_is_explicitly_disabled_by_default(self):
        branding = (
            REPO / "ports/lefony-prime-g2/patches/lefony-branding.patch"
        ).read_text()
        self.assertIn("+invertEnabled(false)", branding)
        self.assertIn("+rootContext(nullptr)", branding)

    def test_app_icon_theme_has_green_accents_without_yellow_fringe(self):
        icon_files = sorted(ICONS.rglob("*.png"))
        self.assertEqual(len(icon_files), 43)
        green_pixels = 0
        yellow_pixels = 0
        for path in icon_files:
            image = Image.open(path).convert("RGBA")
            pixels = image.load()
            for y in range(image.height):
                for x in range(image.width):
                    red, green, blue, alpha = pixels[x, y]
                    if alpha == 0:
                        continue
                    if (red, green, blue) == (0x46, 0x66, 0x45):
                        green_pixels += 1
                    maximum = max(red, green, blue)
                    minimum = min(red, green, blue)
                    if (
                        maximum - minimum >= 18
                        and red >= green > blue
                        and red > 150
                        and 0.28 <= green / max(red, 1) <= 0.9
                    ):
                        yellow_pixels += 1
        self.assertGreater(green_pixels, 5_000)
        self.assertEqual(yellow_pixels, 0)

    def test_user_visible_native_identity_is_lefony(self):
        platform = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/platform.cpp").read_text()
        runtime = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/boot/runtime.cpp").read_text()
        branding = (REPO / "ports/lefony-prime-g2/patches/lefony-branding.patch").read_text()
        self.assertIn('return "Lefony OS 1.0.0"', platform)
        self.assertIn("Lefony OS: entering calculator runtime", runtime)
        self.assertIn('+AppsCapital = "LEFONY"', branding)
        self.assertIn('+UpsilonVersion = "Lefony OS version"', branding)


if __name__ == "__main__":
    unittest.main()
