import importlib.util
from pathlib import Path
import tempfile
import unittest
import re

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prime_settings", ROOT / "scripts/prepare_prime_settings.py")
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)


class SettingsIdentityTests(unittest.TestCase):
    def test_about_battery_uses_platform_estimate(self):
        source = (ROOT / "ports/lefony-prime-g2/apps/settings/sub_menu/about_controller.cpp").read_text()
        self.assertIn("PrimeG2::Services::batteryPercent()", source)
        self.assertIn("batteryEstimateIsCalibrated()", source)
        self.assertNotIn("(Ion::Battery::voltage() - 3.6) * 166", source)
        self.assertNotIn('setAccessoryText("1%")', source)

    def test_status_bar_battery_is_icon_only(self):
        source = (ROOT / "ports/lefony-prime-g2/apps/battery_view.cpp").read_text()
        self.assertNotIn("drawString", source)
        self.assertNotIn("percentage", source)
        self.assertIn("KDSize(k_batteryWidth, 14)", source)
        self.assertIn("constexpr KDCoordinate x = 0", source)
        for flag in ("m_isCharging", "m_chargerFault", "m_batteryPresent"):
            self.assertIn(flag, source)

    def test_usb_page_has_green_heading_and_no_idle_full_redraw(self):
        page = (ROOT / "ports/lefony-prime-g2/apps/lefony_usb_page.h").read_text()
        self.assertIn("0x466645", page)
        self.assertNotIn("0x195cba", page)
        self.assertNotIn('drawString("LEFONY OS"', page)
        self.assertIn('"USB connected"', page)
        self.assertIn('"Ready for the Lefony OS installer"', page)
        self.assertIn("KDFont::SmallFont, KDColorBlack, KDColorWhite", page)
        self.assertIn("percent != m_percent", page)
        self.assertIn("if (changed) markRectAsDirty", page)
        self.assertIn("return changed;", page)
        self.assertNotIn("return m_page.shown;", page)

    def test_usb_snapshot_text_fits_single_prime_screen(self):
        page = (ROOT / "ports/lefony-prime-g2/apps/settings/sub_menu/lefony_usb_controller.h").read_text()
        rows = []
        for row, a, b in re.findall(r'pair\(ctx, (\d+), "([^"]+)", [^,]+, "([^"]+)"', page):
            text = f"{a} 00000000  {b} 00000000"
            self.assertLess(len(text), 40)  # includes trailing NUL in buffer
            self.assertLessEqual(4 + len(text) * 7, 320)
            rows.append(int(row))
        for row, text in re.findall(r'line\(ctx, (\d+), "([^"]+)"', page):
            self.assertLessEqual(4 + len(text) * 7, 320)
            rows.append(int(row))
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual(max(rows), 14)
        self.assertLessEqual(4 + max(rows) * 14 + 14, 222)

    def test_preparation_is_idempotent_and_identity_is_embedded(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            app = source / "apps/settings"
            (app / "sub_menu").mkdir(parents=True)
            (source / "ion/src/prime_g2").mkdir(parents=True)
            (app / "main_controller.h").write_text("extern tree s_modelAboutChildren[10];")
            (app / "main_controller.cpp").write_text(
                "tree s_modelAboutChildren[10] = {SettingsMessageTree(I18n::Message::Contributors, s_contributorsChildren)};")
            (app / "base.universal.i18n").write_text('UsbSetting = "USB"\n')
            first = settings.prepare(source, "260909-010000")
            second = settings.prepare(source, "260909-010000")
            self.assertEqual(first, second)
            self.assertLessEqual(len(first["build_id"]), 20)
            self.assertIn(first["build_id"], (source / "ion/src/prime_g2/lefony_build_identity.h").read_text())
            self.assertEqual((app / "main_controller.cpp").read_text().count("I18n::Message::LefonyBuildId"), 1)
            self.assertIn("s_modelAboutChildren[13]", (app / "main_controller.h").read_text())
            self.assertEqual((app / "main_controller.cpp").read_text().count("I18n::Message::LefonyUsbStatus"), 1)
            self.assertNotIn("\n\n", (app / "base.universal.i18n").read_text())
            # The already installed Settings candidate has twelve model rows.
            header = app / "main_controller.h"
            model = app / "main_controller.cpp"
            header.write_text(header.read_text().replace("[13]", "[12]"))
            model.write_text(model.read_text().replace("[13]", "[12]").replace(
                "SettingsMessageTree(I18n::Message::LefonyUsbStatus), ", ""))
            settings.prepare(source, "260909-010000")
            self.assertIn("s_modelAboutChildren[13]", header.read_text())
            self.assertEqual(model.read_text().count("I18n::Message::LefonyUsbStatus"), 1)

    def test_usb_status_refresh_is_read_only(self):
        source = (ROOT / "ports/lefony-prime-g2/apps/settings/sub_menu/about_controller.cpp").read_text()
        refresh = source.split("if (childLabel == I18n::Message::LefonyUsbStatus", 1)[1].split("return true;", 1)[0]
        self.assertIn("displayModalViewController(&m_usbController", refresh)
        self.assertNotIn("USBDiagnostics::init", refresh)
        self.assertNotIn("shutdown", refresh)
        self.assertIn("USBDiagnostics::firstErrorStep()", source)
        page = (ROOT / "ports/lefony-prime-g2/apps/settings/sub_menu/lefony_usb_controller.h").read_text()
        draw = page.split("void drawRect", 1)[1].split("private:", 1)[0]
        self.assertNotIn("debugSnapshot()", draw)
        for label in ("FLAGS", "REQ", "SETUPS", "RESET", "PRIME", "RAW0", "RAW1"):
            self.assertIn('"' + label + '"', draw)
        self.assertIn("dismissModalViewController()", page)

    def test_recovery_requires_popup_confirmation(self):
        base = ROOT / "ports/lefony-prime-g2/apps/settings/sub_menu"
        about = (base / "about_controller.cpp").read_text()
        popup = (base / "lefony_recovery_controller.h").read_text()
        self.assertIn("displayModalViewController(&m_recoveryController", about)
        self.assertNotIn("rebootToROMRecovery()", about)
        self.assertIn("Invocation(", popup)
        self.assertEqual(popup.count("rebootToUBootRecovery()"), 1)
        self.assertIn("bootloaderRecoveryVersion() != 1", about)
        self.assertIn("LEFONY_OS_VERSION", about)
        self.assertIn("LEFONY_BUILD_ID", about)
