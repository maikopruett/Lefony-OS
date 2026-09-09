import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hp_prime_stock_transition", ROOT / "vm/hp_prime_stock_transition.py"
)
transition = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(transition)


class HPPrimeStockTransitionTests(unittest.TestCase):
    def test_mode_three_is_start_updater_packet(self):
        self.assertEqual(
            transition.stock_reset_packet(1, transition.RESET_START_UPDATER),
            bytes.fromhex("e8 01 00 00 00 05 00 00 00 00 03"),
        )

    def test_hid_report_has_sequence_packet_and_padding(self):
        report = transition.stock_reset_hid_report(7, sequence=2)
        self.assertEqual(len(report), transition.HID_REPORT_BYTES)
        self.assertEqual(report[0], 2)
        self.assertEqual(
            report[1:12], transition.stock_reset_packet(7, 3)
        )
        self.assertEqual(report[12:], bytes(52))

    def test_invalid_values_are_rejected(self):
        for version in (-1, 256):
            with self.subTest(version=version), self.assertRaises(ValueError):
                transition.stock_reset_packet(version, 3)
        for mode in (-1, 4):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                transition.stock_reset_packet(1, mode)
        with self.assertRaises(ValueError):
            transition.stock_reset_hid_report(1, sequence=255)
        with self.assertRaises(ValueError):
            transition.stock_reset_hid_report(1, report_bytes=11)


if __name__ == "__main__":
    unittest.main()
