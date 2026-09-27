import random
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vm'))
from prime_nand_image import checksum, decode_fcb, encode_fcb, fcb_layout, recover_fcb
from prime_gpmi_bch import Layout


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
    def test_hp_rom_marker_uses_fcb_metadata_byte_34(self):
        fcb = bytearray(make_fcb())
        for offset, value in {0x2c:2, 0x38:2, 0x3c:36, 0x7c:1992,
                              0x80:4, 0xb0:34}.items():
            struct.pack_into('<I', fcb, offset, value)
        geometry = fcb_layout(fcb)
        payload = random.Random(34).randbytes(2048)
        metadata = bytes(range(34)) + b'\xff\xa5'
        data, aux = geometry.swap_marker(payload, metadata)
        # Independent physical-ROM formula: splice metadata[34] into the
        # eight payload bits at byte 1992, bit 4, leaving adjacent bits intact.
        displaced = (int.from_bytes(payload[1992:1994], 'little') >> 4) & 255
        self.assertEqual(aux[34], displaced)
        self.assertEqual(aux[:34], metadata[:34])
        self.assertEqual(aux[35], metadata[35])
        raw = geometry.encode(data, aux)
        self.assertEqual(raw[2048], 255)
        decoded = geometry.decode(raw)
        restored = bytearray(decoded.payload)
        pair = int.from_bytes(restored[1992:1994], 'little')
        restored[1992:1994] = ((pair & ~0xff0) | decoded.metadata[34] << 4).to_bytes(2, 'little')
        self.assertEqual(bytes(restored), payload)
        self.assertEqual(geometry.swap_marker(decoded.payload, decoded.metadata), (payload, metadata))
        # The previous builder stored the byte in metadata[0]. Its ECC is
        # valid, but the ROM's specified restoration corrupts the payload.
        old = Layout(0x03241080, 0x08401080)
        wrong_data, wrong_aux = old.swap_marker(payload, b'\xff'*36)
        wrong = geometry.decode(old.encode(wrong_data, wrong_aux))
        self.assertNotEqual(geometry.swap_marker(wrong.payload, wrong.metadata)[0], payload)

    def test_fcb_rejects_out_of_range_marker_metadata(self):
        fcb = bytearray(make_fcb())
        for index in (10, 255, 0xffffffff):
            struct.pack_into('<I', fcb, 0xb0, index)
            with self.assertRaisesRegex(ValueError, 'marker metadata'):
                fcb_layout(fcb)

    def test_fcb_with_metadata_in_first_codeword(self):
        fcb = make_fcb()
        physical = bytearray(encode_fcb(fcb, covered_metadata=bytes(range(32))))
        self.assertEqual(decode_fcb(physical), (fcb, [0]*8))
        # Correct both a metadata bit and a first-payload bit.
        physical[3] ^= 1
        physical[41] ^= 4
        self.assertEqual(decode_fcb(physical), (fcb, [2]+[0]*7))
        for at in range(45,53):
            physical[at] ^= 255
        with self.assertRaises(ValueError):
            decode_fcb(physical)

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
