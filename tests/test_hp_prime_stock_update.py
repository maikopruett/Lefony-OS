import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vm"))

from hp_prime_stock_update import (  # noqa: E402
    REPORT_BYTES,
    REPORT_PAYLOAD_BYTES,
    flip_package_byte,
    iter_stock_update_reports,
    stock_crc16,
    stock_next_offset,
    stock_update_report,
)


class HPPrimeStockUpdateTests(unittest.TestCase):
    def test_crc_matches_reconstructed_connectivity_kit_algorithm(self):
        self.assertEqual(stock_crc16(bytes(REPORT_BYTES)), 0xA7DB)
        self.assertEqual(stock_crc16(bytes(range(REPORT_BYTES))), 0x8C2E)

    def test_report_contains_offset_crc_payload_and_padding(self):
        report = stock_update_report(123, b"abc")
        self.assertEqual(len(report), REPORT_BYTES)
        self.assertEqual(report[:4], b"{\x00\x00\x00")
        self.assertEqual(report[4:6], b"\xd7\x62")
        self.assertEqual(report[6:9], b"abc")
        self.assertEqual(report[9:], bytes(REPORT_BYTES - 9))

        with_crc_zeroed = report[:4] + b"\x00\x00" + report[6:]
        self.assertEqual(stock_crc16(with_crc_zeroed), 0x62D7)

    def test_report_iterator_preserves_offsets_and_tail(self):
        image = bytes(range(REPORT_PAYLOAD_BYTES + 3))
        reports = list(iter_stock_update_reports(image))
        self.assertEqual([offset for offset, _ in reports],
                         [0, REPORT_PAYLOAD_BYTES])
        self.assertEqual(reports[0][1][6:], image[:REPORT_PAYLOAD_BYTES])
        self.assertEqual(reports[1][1][6:9], image[-3:])

    def test_response_decodes_next_offset(self):
        self.assertEqual(stock_next_offset(b"\x7a\x00\x00\x00more"), 122)
        with self.assertRaisesRegex(ValueError, "next-offset"):
            stock_next_offset(b"\x00\x01\x02")

    def test_in_memory_signature_rejection_mutation_is_exact(self):
        original = bytes(range(16))
        mutated = flip_package_byte(original, 7)
        self.assertEqual(mutated[:7], original[:7])
        self.assertEqual(mutated[7], original[7] ^ 1)
        self.assertEqual(mutated[8:], original[8:])
        with self.assertRaisesRegex(ValueError, "outside"):
            flip_package_byte(original, len(original))

    def test_invalid_report_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            stock_update_report(-1, b"")
        with self.assertRaises(ValueError):
            stock_update_report(0, bytes(REPORT_PAYLOAD_BYTES + 1))

    def test_stock_probe_allows_slow_authentic_controller_startup(self):
        source = (ROOT / "vm" / "hp_prime_stock_update.py").read_text()
        self.assertIn("controller_timeout=30.0", source)

    def test_stock_probe_does_not_wait_for_per_report_acknowledgments(self):
        source = (ROOT / "vm" / "hp_prime_stock_update.py").read_text()
        send_loop = source[source.index("for offset, report") :]
        completion = send_loop.index("if sent == total_reports")
        self.assertNotIn("endpoint_in", send_loop[:completion])
        self.assertIn("endpoint_in(1, REPORT_BYTES)", send_loop[completion:])

    def test_bulk_endpoint_out_uses_fast_local_nak_retry(self):
        source = (ROOT / "vm" / "prime_usb_host.py").read_text()
        endpoint_out = source[source.index("def endpoint_out") :]
        endpoint_out = endpoint_out[:endpoint_out.index("def control_in")]
        self.assertIn("retry_interval=0.0001", endpoint_out)

    def test_final_report_can_be_paused_for_narrow_vm_tracing(self):
        source = (ROOT / "vm" / "hp_prime_stock_update.py").read_text()
        self.assertIn("--pause-before-final", source)
        self.assertIn("sent + 1 == total_reports", source)


if __name__ == "__main__":
    unittest.main()
