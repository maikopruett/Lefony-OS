from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PALETTE = ROOT / "ports/lefony-prime-g2/apps/prime_math_template_palette.h"
PATCH = ROOT / "ports/lefony-prime-g2/patches/prime-g2-math-template-palette.patch"


class PrimeMathTemplatePaletteTest(unittest.TestCase):
    def test_sixteen_supported_templates(self):
        source = PALETTE.read_text()
        entries = re.findall(r'\{"([^"\n]+)", "((?:\\.|[^"\\])*)"\}', source)
        self.assertEqual(len(entries), 16)
        self.assertEqual(dict(entries)["Square"], "^2")
        self.assertEqual(dict(entries)["Matrix"], "[")
        self.assertIn("\\x11", dict(entries)["Integral"])
        self.assertNotIn("Piecewise", dict(entries))

    def test_navigation_is_bounded_and_inserts_into_original_sender(self):
        source = PALETTE.read_text()
        for guard in ("selected % 4 != 0", "selected % 4 != 3",
                      "selected >= 4", "selected < 12"):
            self.assertIn(guard, source)
        self.assertIn("sender()->handleEventWithText(entry(selected).text)", source)
        self.assertIn("dismissModalViewController()", source)
        self.assertIn("void didBecomeFirstResponder() override {}", source)
        self.assertIn("void viewDidDisappear() override {}", source)

    def test_palette_is_only_the_bordered_grid(self):
        source = PALETTE.read_text()
        self.assertIn("KDSize(266, 146)", source)
        self.assertIn("int y = 1 + (i / 4) * 36;", source)
        self.assertNotIn('drawString("Math templates"', source)
        self.assertNotIn('drawString(entry(m_selected).label', source)
        self.assertNotIn('Arrows: choose', source)

    def test_only_plain_template_key_selects_palette(self):
        patch = PATCH.read_text()
        self.assertIn("m_primeTemplateRequested = event == Ion::Events::PrimeMathTemplates;", patch)
        self.assertIn("if (m_primeTemplateRequested) return &m_primeTemplatePalette;", patch)
        self.assertNotIn("event == Ion::Events::PrimeUnits", patch)
        build = (ROOT / "scripts/build_lefony_prime_g2.sh").read_text()
        self.assertLess(build.index("prime-g2-shift-shortcuts.patch"),
                        build.index("prime-g2-math-template-palette.patch"))

    def test_popup_special_templates_reload_without_a_keyboard_event(self):
        patch = (ROOT / "ports/lefony-prime-g2/patches/prime-g2-template-insertion-redraw.patch").read_text()
        self.assertIn("KDSize previousInsertionSize = minimalSizeForOptimalDisplay();", patch)
        self.assertIn("reload(previousInsertionSize);", patch)
        self.assertIn("cursor->hideEmptyLayoutIfNeeded();", patch)
        self.assertIn("insertLayoutAtCursor already reloads", patch)


if __name__ == "__main__":
    unittest.main()
