import importlib
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vm'))
audit = importlib.import_module('audit-prime-g2-ddr-boot')


def fixture():
    image = bytearray(0x480)
    image[0x400:0x404] = b'\xd1\x00\x20\x40'
    struct.pack_into('<I', image, 0x414, 0x80000400)
    struct.pack_into('<I', image, 0x40c, 0x80000430)
    image[0x430:0x438] = b'\xd2\x00\x18\x40\xcc\x00\x14\x04'
    struct.pack_into('>IIII', image, 0x438,
                     0x021b001c, 0x8000, 0x020c4068, 0xffffffff)
    return image


class DDRAuditTests(unittest.TestCase):
    def test_only_mmdc_address_changes_original_unchanged(self):
        original = fixture()
        snapshot = bytes(original)
        changed, evidence = audit.bypass_mmdc(original)
        self.assertEqual(bytes(original), snapshot)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]['address'], '0x21b001c')
        self.assertEqual(struct.unpack_from('>I', changed, 0x438)[0], 0x0093f000)
        changed[0x438:0x43c] = original[0x438:0x43c]
        self.assertEqual(changed, original)

    def test_rejects_invalid_ivt(self):
        image = fixture()
        image[0x400] = 0
        with self.assertRaises(ValueError):
            audit.bypass_mmdc(image)

    def test_rejects_dcd_outside_image(self):
        image = fixture()
        struct.pack_into('<I', image, 0x40c, 0x81000000)
        with self.assertRaises(ValueError):
            audit.bypass_mmdc(image)

    def test_rejects_unsupported_command(self):
        image = fixture()
        image[0x437] = 2
        with self.assertRaises(ValueError):
            audit.bypass_mmdc(image)

    def test_rejects_no_mmdc_writes(self):
        image = fixture()
        struct.pack_into('>I', image, 0x438, 0x020c4070)
        with self.assertRaises(ValueError):
            audit.bypass_mmdc(image)

    def test_rejects_truncated_ivt(self):
        with self.assertRaises(ValueError):
            audit.bypass_mmdc(fixture()[:0x418])

    def test_rejects_truncated_command(self):
        image = fixture()
        image[0x431:0x433] = b'\x00\x19'
        with self.assertRaises(ValueError):
            audit.bypass_mmdc(image)


if __name__ == '__main__':
    unittest.main()
