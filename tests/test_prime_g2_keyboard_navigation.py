import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[1]
KEYMAP = REPO / "ports/lefony-prime-g2/ion/src/prime_g2/keymap.inc"
PATCH = REPO / "ports/lefony-prime-g2/patches/prime-g2-dedicated-navigation.patch"
ALPHA_PATCH = REPO / "ports/lefony-prime-g2/patches/prime-g2-alpha-layout.patch"
KEYBOARD_PATCH = REPO / "ports/lefony-prime-g2/patches/prime-g2-keyboard-layout.patch"
SHIFT_PATCH = REPO / "ports/lefony-prime-g2/patches/prime-g2-shift-shortcuts.patch"
BUILD = REPO / "scripts/build_lefony_prime_g2.sh"
TOUCH = REPO / "ports/lefony-prime-g2/ion/src/prime_g2/touch.cpp"
EMULATOR = REPO / "ports/lefony-prime-g2/ion/src/prime_g2/emulator.cpp"


class PrimeG2KeyboardNavigationTest(unittest.TestCase):
    def test_prime_matrix_positions_match_the_verified_hardware_table(self):
        keymap = KEYMAP.read_text()
        self.assertIn("PRIME_G2_KEY(home,       125, Home,              4,   3)", keymap)
        self.assertIn("PRIME_G2_KEY(cas,         29, CAS,               5,   1)", keymap)
        self.assertIn("PRIME_G2_KEY(apps,       139, Apps,              4,   4)", keymap)
        self.assertIn("PRIME_G2_KEY(toolbox,     48, Toolbox,           2,   7)", keymap)

    def test_dedicated_events_have_global_prime_navigation_semantics(self):
        patch = PATCH.read_text()
        self.assertIn("Home=6,  OnOff=7,  CAS=8,     Apps=9", patch)
        self.assertIn('"Home", "OnOff", "CAS", "Apps"', patch)
        self.assertIn(
            "event == Ion::Events::Home || event == Ion::Events::CAS", patch
        )
        self.assertIn("switchTo(appSnapshotAtIndex(1))", patch)
        self.assertIn(
            "event == Ion::Events::Apps || event == Ion::Events::Back", patch
        )
        self.assertIn("switchTo(appSnapshotAtIndex(0))", patch)

    def test_native_build_applies_navigation_patch(self):
        self.assertIn("prime-g2-dedicated-navigation.patch", BUILD.read_text())

    def test_prime_alpha_layout_matches_the_printed_key_legends(self):
        keymap = KEYMAP.read_text()
        for entry in (
            "PRIME_G2_KEY(units,       46, PrimeAlphaC,       2,   2)",
            "PRIME_G2_KEY(fraction,    18, PrimeAlphaE,       2,   4)",
            "PRIME_G2_KEY(plusminus,   50, PrimeAlphaM,       3,   0)",
            "PRIME_G2_KEY(space,       57, PrimeAlphaSpace,   1,   6)",
        ):
            self.assertIn(entry, keymap)

        alpha = ALPHA_PATCH.read_text()
        for row in (
            'T("q"), T("r"), T("s"), T("n"), U(), T("m")',
            'T("u"), T("v"), T("w"), T("x"), T("t"), T(" ")',
            'T("y"), T("z"), T("#"), T(";"), T(":"), U()',
            'T("\\\""), U(), T("p"), U(), U(), U()',
        ):
            self.assertIn(row, alpha)

    def test_native_build_applies_alpha_layout_patch(self):
        self.assertIn("prime-g2-alpha-layout.patch", BUILD.read_text())

    def test_all_six_prime_application_keys_are_mapped(self):
        keymap = KEYMAP.read_text()
        for entry in (
            "PRIME_G2_KEY(symb,        59, PrimeSymb,          4,   2)",
            "PRIME_G2_KEY(plot,        60, PrimePlot,          4,   1)",
            "PRIME_G2_KEY(num,         61, PrimeNum,           4,   0)",
            "PRIME_G2_KEY(help,        62, PrimeHelp,          5,   7)",
            "PRIME_G2_KEY(view,        63, PrimeView,          5,   3)",
            "PRIME_G2_KEY(menu,        64, PrimeMenu,          5,   2)",
        ):
            self.assertIn(entry, keymap)

    def test_prime_shift_layout_replaces_numworks_shortcuts(self):
        keyboard = KEYBOARD_PATCH.read_text()
        self.assertIn(
            "constexpr Event Exp = Event::ShiftKey(Keyboard::Key::Ln);", keyboard
        )
        for mapping in (
            'T("[\\x11]")',
            'T("{\\x11}")',
            'T("√(\\x11)")',
            'T("𝐢")',
            'T("π")',
            'T("ans")',
        ):
            self.assertIn(mapping, keyboard)
        self.assertIn("#if !defined(PLATFORM_PRIME_G2)", keyboard)
        self.assertIn("PrimeDelete", keyboard)
        for semantic in (
            "PrimeList", "PrimeMatrix", "PrimeProgram", "PrimeBase", "PrimeNotes"
        ):
            self.assertIn(semantic, keyboard)
        self.assertIn("switchTo(appSnapshotAtIndex(4))", keyboard)

    def test_native_build_applies_complete_keyboard_patch(self):
        self.assertIn("prime-g2-keyboard-layout.patch", BUILD.read_text())

    def test_shift_corrections_apply_after_original_layout(self):
        build = BUILD.read_text()
        self.assertLess(build.index("prime-g2-keyboard-layout.patch"),
                        build.index("prime-g2-shift-shortcuts.patch"))
        patch = SHIFT_PATCH.read_text()
        for entry in ("PrimeUnits", "PrimeCalculus", "PrimeMathTemplates",
                      "PrimeListsUnavailable", "event == Ion::Events::ShiftOK"):
            self.assertIn(entry, patch)

    def test_category_opening_does_not_reenter_modal_appearance(self):
        patch = SHIFT_PATCH.read_text()
        self.assertIn("MathToolbox::didBecomeFirstResponder()", patch)
        self.assertNotIn("MathToolbox::viewWillAppear()", patch)
        self.assertIn("rootModel()->childAtIndex(row)->label() == requested", patch)
        self.assertIn("s_primeCategory = I18n::Message::Default", patch)

    def test_touch_uses_coordinates_instead_of_global_edge_keys(self):
        self.assertIn("return Ion::Events::Touch;", TOUCH.read_text())
        self.assertNotIn("return Ion::Events::Apps;", TOUCH.read_text())
        self.assertNotIn("return Ion::Events::OK;", TOUCH.read_text())

    def test_warm_reset_retains_launcher_behavior(self):
        source = EMULATOR.read_text()
        self.assertIn("sPendingEvent = Ion::Events::Apps;", source)
        self.assertNotIn("sPendingEvent = Ion::Events::Home;", source)


if __name__ == "__main__":
    unittest.main()
