import random
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vm'))
from prime_nand_image import checksum, decode_fcb, encode_fcb, fcb_layout, recover_fcb


def make_fcb():
    fcb = bytearray(1024)
    values = {4: 0x20424346, 8: 0x01000000, 0x14: 2048, 0x18: 2112,
              0x1c: 64, 0x2c: 1, 0x30: 512, 0x34: 512, 0x38: 1,
              0x3c: 10, 0x40: 3, 0x68: 512, 0x6c: 1280,
              0x70: 190, 0x74: 190, 0x78: 256, 0x7c: 2028,
              0x80: 2, 0x84: 2048}
    for offset, value in values.items():
        struct.pack_into('<I', fcb, offset, value)
    # Exercise projection across every FCB block, not only zero-filled tails.
    fcb[180:] = random.Random(606).randbytes(1024 - 180)
    struct.pack_into('<I', fcb, 0, checksum(fcb))
    return bytes(fcb)


class NANDImageTests(unittest.TestCase):
    def test_fcb_encode_decode_and_geometry(self):
        fcb = make_fcb()
        physical = encode_fcb(fcb)
        decoded, corrections = decode_fcb(physical)
        self.assertEqual(decoded, fcb)
        self.assertEqual(corrections, [0] * 8)
        self.assertEqual(physical[2048:2050], b'\xff\xff')
        self.assertEqual(fcb_layout(fcb).marker_payload_bit(), 2028 * 8 + 2)

    def test_recover_linux_projected_fcb(self):
        fcb = make_fcb()
        physical = bytearray(encode_fcb(fcb))
        physical[0], physical[2048] = physical[2048], physical[0]
        word = int.from_bytes(physical, 'little')
        payload = bytearray()
        oob = int.from_bytes(physical[:10], 'little')
        wire, ecc = 80, 80
        for _ in range(4):
            payload += ((word >> wire) & ((1 << 4096) - 1)).to_bytes(512, 'little')
            wire += 4096
            oob |= ((word >> wire) & ((1 << 26) - 1)) << ecc
            wire += 26
            ecc += 26
        record = bytes(payload) + oob.to_bytes(64, 'little')
        self.assertEqual(recover_fcb(record), (fcb, [0] * 8))

    def test_40_errors_in_last_fcb_block(self):
        fcb = make_fcb()
        physical = bytearray(encode_fcb(fcb))
        for index in range(32 + 7 * 193, 37 + 7 * 193):
            physical[index] ^= 255
        decoded, corrections = decode_fcb(physical)
        self.assertEqual(decoded, fcb)
        self.assertEqual(corrections, [0] * 7 + [40])

    def test_reject_invalid_checksum_and_marker(self):
        fcb = bytearray(make_fcb())
        fcb[20] ^= 1
        with self.assertRaises(ValueError):
            encode_fcb(fcb)
        fcb = bytearray(make_fcb())
        struct.pack_into('<I', fcb, 0x7c, 2038)
        with self.assertRaises(ValueError):
            fcb_layout(fcb)
        with self.assertRaises(ValueError):
            recover_fcb(bytes(100))


if __name__ == '__main__':
    unittest.main()
