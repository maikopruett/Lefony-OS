from pathlib import Path
import sys
import unittest

VM = Path(__file__).resolve().parents[1] / 'vm'
sys.path.insert(0, str(VM))
from prime_gpmi_bch import Layout


def layout(strength=8, first=512, count=4, metadata=10, page=2112, chunk=512, field=13):
    gf = int(field == 14) << 10
    return Layout(((count - 1) << 24) | (metadata << 16) | ((strength // 2) << 11)
                  | gf | (first // 4),
                  (page << 16) | ((strength // 2) << 11) | gf | (chunk // 4))


class GPMILayoutTests(unittest.TestCase):
    def setUp(self):
        self.geometry = layout()
        self.data = bytes(i % 251 for i in range(2048))
        self.metadata = b'\xffPRIME-ECC'

    def test_prime_register_units_and_marker(self):
        g = self.geometry
        self.assertEqual(g.payload_bytes, 2048)
        self.assertEqual(g.used_bits, 2110 * 8)
        self.assertEqual(g.status_offset, 12)
        self.assertEqual(g.marker_payload_bit(), 1999 * 8)
        raw_data, raw_meta = g.swap_marker(self.data, self.metadata)
        self.assertEqual(g.swap_marker(raw_data, raw_meta), (self.data, self.metadata))
        physical = g.encode(raw_data, raw_meta)
        self.assertEqual(physical[2048], 0xff)
        result = g.decode(physical)
        self.assertEqual(g.swap_marker(result.payload, result.metadata), (self.data, self.metadata))
        self.assertEqual(result.status, (0, 0, 0, 0))
        self.assertEqual(g.auxiliary(result)[12:], bytes(4))

    def test_captured_recovery_geometry(self):
        # Physical kobs.log from restore-a606-20260903T034645Z records
        # t=2, 2071 used bytes and a marker at payload byte 2028, bit 2.
        g = layout(strength=2, page=2071)
        self.assertEqual(g.used_bits, 2071 * 8)
        self.assertEqual(divmod(g.marker_payload_bit(), 8), (2028, 2))
        payload, meta = g.swap_marker(self.data, self.metadata)
        physical = g.encode(payload, meta)
        self.assertEqual(physical[2048], 0xff)
        result = g.decode(physical)
        self.assertEqual(g.swap_marker(result.payload, result.metadata), (self.data, self.metadata))

    def test_errors_in_metadata_payload_and_parity(self):
        g = self.geometry
        physical = bytearray(g.encode(self.data, self.metadata))
        for chunk in g.chunks:
            positions = [chunk.start_bit, chunk.start_bit + 10,
                         chunk.start_bit + chunk.message_bytes * 8, chunk.end_bit - 1]
            for bit in positions:
                physical[bit // 8] ^= 1 << (bit % 8)
        result = g.decode(bytes(physical))
        self.assertEqual((result.payload, result.metadata), (self.data, self.metadata))
        self.assertEqual(result.status, (4, 4, 4, 4))

    def test_nibble_aligned_chunks(self):
        g = layout(strength=6)
        self.assertEqual(g.chunks[1].start_bit % 8, 6)
        raw, meta = g.swap_marker(self.data, self.metadata)
        self.assertEqual(g.swap_marker(raw, meta), (self.data, self.metadata))
        physical = g.encode(raw, meta)
        self.assertEqual(physical[2048], 0xff)
        result = g.decode(physical)
        self.assertEqual(g.swap_marker(result.payload, result.metadata), (self.data, self.metadata))

    def test_metadata_separate_block_and_gf14(self):
        g = layout(first=0, count=3, chunk=1024, field=14)
        encoded = g.encode(self.data, self.metadata)
        result = g.decode(encoded)
        self.assertEqual((result.payload, result.metadata), (self.data, self.metadata))
        self.assertEqual(result.status, (0, 0, 0))

    def test_erased_and_selected_overload(self):
        g = self.geometry
        result = g.decode(b'\xff' * 2112)
        self.assertEqual(result.payload, b'\xff' * 2048)
        self.assertEqual(result.status, (0xff,) * 4)
        physical = bytearray(g.encode(self.data, self.metadata))
        physical[:4] = bytes(value ^ 0xff for value in physical[:4])
        result = g.decode(bytes(physical))
        self.assertTrue(result.failed)
        self.assertEqual(result.status, (0xfe, 0, 0, 0))

    def test_erased_threshold_preserves_damaged_dma_bytes(self):
        g = layout(strength=2)
        physical = bytearray(b'\xff' * 2112)
        # Metadata, payload, and parity in separate codewords, including a
        # non-byte-aligned boundary. The threshold is per chunk, not per page.
        for bit in (0, g.chunks[1].start_bit, g.chunks[2].end_bit - 1):
            physical[bit // 8] ^= 1 << (bit % 8)
        result = g.decode(bytes(physical), 1)
        self.assertEqual(result.status, (0xff,) * 4)
        self.assertEqual(result.erased_zero_count, 3)
        self.assertEqual(result.metadata[0], 0xfe)
        self.assertEqual(result.payload[512], 0xfe)
        self.assertEqual(g.decode(b'\xff' * 2112, 1).erased_zero_count, 0)
        self.assertNotEqual(g.decode(bytes(physical), 0).status, (0xff,) * 4)

    def test_programmed_ff_is_not_erased(self):
        g = self.geometry
        encoded = g.encode(b'\xff' * 2048, b'\xff' * 10)
        self.assertEqual(g.decode(encoded, 8).status, (0,) * 4)
        self.assertEqual(g.decode(encoded, 8).erased_zero_count, 0)

    def test_reject_impossible_layout_and_input(self):
        for threshold in (-1, 256):
            with self.assertRaises(ValueError):
                self.geometry.decode(b'\xff' * 2112, threshold)
        with self.assertRaises(ValueError):
            layout(strength=16)
        with self.assertRaises(ValueError):
            self.geometry.decode(bytes(2048))
        with self.assertRaises(ValueError):
            self.geometry.encode(self.data, bytes(11))


if __name__ == '__main__':
    unittest.main()
