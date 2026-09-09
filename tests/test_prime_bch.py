"""Fast standalone checks; the larger oracle suite is vm/test-prime-bch.py."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    'prime_bch', Path(__file__).resolve().parents[1] / 'vm/prime_bch.py')
bch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bch)


class BCHTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec = bch.BCH(13, 8, 0x201b)
        cls.data = bytes(i % 256 for i in range(512))

    def test_uboot_parity_vector(self):
        self.assertEqual(self.codec.encode(self.data).hex(), 'a9bcebb1e14d242bbe4146b3d4')

    def test_correct_data_and_parity_without_error_hint(self):
        parity = self.codec.encode(self.data)
        positions = (0, 17, 1023, 2048, 4095, 4096, 4150, 4199)
        wire = bytearray(self.data + parity)
        for bit in positions:
            wire[bit // 8] ^= 1 << (7 - bit % 8)
        fixed, ecc, errors = self.codec.decode(bytes(wire[:512]), bytes(wire[512:]))
        self.assertEqual((fixed, ecc, errors), (self.data, parity, positions))

    def test_padding_is_not_a_transmitted_bit(self):
        codec = bch.BCH(5, 2, 0x25)
        parity = codec.encode(b'hi')
        padded = parity[:-1] + bytes([parity[-1] | ((1 << codec.padding) - 1)])
        self.assertEqual(codec.decode(b'hi', padded), (b'hi', padded, ()))

    def test_reject_bad_inputs(self):
        with self.assertRaises(ValueError):
            self.codec.encode(bytes(1024))
        with self.assertRaises(ValueError):
            self.codec.decode(self.data, b'')
        with self.assertRaises(ValueError):
            bch.BCH(5, 2, 0x21)


if __name__ == '__main__':
    unittest.main()
