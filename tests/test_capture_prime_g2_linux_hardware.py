import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "capture_prime_g2_linux_hardware",
    ROOT / "scripts" / "capture_prime_g2_linux_hardware.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CapturePrimeG2LinuxHardwareTests(unittest.TestCase):
    def test_register_addresses_are_unique_and_aligned(self):
        seen = set()
        for group, registers in MODULE.REGISTER_GROUPS.items():
            self.assertTrue(registers, group)
            for name, address, width in registers:
                self.assertNotIn(address, seen, name)
                seen.add(address)
                self.assertIn(width, (16, 32))
                self.assertEqual(address % (width // 8), 0, name)

    def test_capture_commands_do_not_contain_destructive_tools(self):
        commands = "\n".join(command for _, command in MODULE.CAPTURES)
        commands += "\n" + MODULE.register_command(
            entry for entries in MODULE.REGISTER_GROUPS.values() for entry in entries
        )
        for forbidden in ("nandwrite", "flash_erase", "i2cdetect", "i2cset", "devmem 0x00000000"):
            self.assertNotIn(forbidden, commands)

    def test_expected_emulator_reference_groups_exist(self):
        self.assertEqual(
            {"ccm", "src", "lcdif", "pwm7", "gpio", "kpp", "iomuxc_display"},
            set(MODULE.REGISTER_GROUPS),
        )

    def test_interrupted_capture_can_be_sealed_offline(self):
        with tempfile.TemporaryDirectory() as temporary:
            capture = Path(temporary) / "20260831T000000Z"
            capture.mkdir()
            (capture / "system.txt").write_text("Linux\n")
            target = MODULE.write_offline_manifest(capture, "test interruption")
            manifest = json.loads(target.read_text())
            self.assertEqual("incomplete", manifest["status"])
            self.assertEqual("test interruption", manifest["incomplete_reason"])
            self.assertEqual("system.txt", manifest["files"][0]["file"])
            self.assertEqual(6, manifest["files"][0]["bytes"])

    def test_watchdog_lease_is_bounded_and_cleanly_disarmed(self):
        source = (ROOT / "scripts" / "capture_prime_g2_linux_hardware.py").read_text()
        self.assertIn("until=$(cat", source)
        self.assertIn("printf V >&9", source)
        self.assertIn("--watchdog-safe", source)
        self.assertIn("timeout=5.0", source)


if __name__ == "__main__":
    unittest.main()
