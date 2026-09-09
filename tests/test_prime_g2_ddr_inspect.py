import importlib
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
inspect = importlib.import_module('inspect_prime_g2_ddr').inspect
from test_prime_g2_ddr_audit import fixture


class DDRInspectTests(unittest.TestCase):
    def test_padded_and_unpadded_have_same_sequence(self):
        image = fixture()
        full, trimmed = inspect(image), inspect(image[0x400:])
        self.assertEqual(full['mmdc_sequence_sha256'], trimmed['mmdc_sequence_sha256'])
        self.assertEqual(full['dcd_sha256'], trimmed['dcd_sha256'])
        self.assertNotEqual(full['image_sha256'], trimmed['image_sha256'])

    def test_command_decode(self):
        image = fixture()
        struct.pack_into('>I', image, 0x43c, 0x02008032)
        command = inspect(image)['mmdc_writes'][0]
        self.assertEqual(command['register'], 'MDSCR')
        self.assertTrue(command['configuration_request'])
        self.assertEqual((command['command'], command['chip_select'], command['bank'], command['mode_data']),
                         (3, 0, 2, 0x200))

    def test_non_mmdc_difference_excluded(self):
        image = fixture()
        before = inspect(image)
        image[0x447] ^= 1
        after = inspect(image)
        self.assertNotEqual(before['dcd_sha256'], after['dcd_sha256'])
        self.assertEqual(before['mmdc_sequence_sha256'], after['mmdc_sequence_sha256'])

    def test_mmdc_difference_detected(self):
        image = fixture()
        before = inspect(image)
        image[0x43f] ^= 1
        self.assertNotEqual(before['mmdc_sequence_sha256'], inspect(image)['mmdc_sequence_sha256'])

    def test_bad_bounds(self):
        image = fixture()
        image[0x431:0x433] = b'\xff\xff'
        with self.assertRaises(ValueError):
            inspect(image)

    def test_boot_extent_and_trimmed_prefix(self):
        image = fixture()
        struct.pack_into('<I', image, 0x410, 0x80000420)
        struct.pack_into('<III', image, 0x420, 0x80000000, len(image), 0)
        for data in (image, image[0x400:]):
            extent = inspect(data)['boot_extent']
            self.assertTrue(extent['valid_pointer'])
            self.assertEqual(extent['bytes_beyond_artifact'], 0)
            self.assertEqual(extent['end_file_offset'], len(data))
        struct.pack_into('<I', image, 0x424, len(image) + 0x4000)
        self.assertEqual(inspect(image)['boot_extent']['bytes_beyond_artifact'], 0x4000)

    def test_unavailable_boot_data_is_not_claimed_valid(self):
        image = fixture()
        self.assertFalse(inspect(image)['boot_extent']['valid_pointer'])
        struct.pack_into('<I', image, 0x410, 0xffffffff)
        self.assertFalse(inspect(image)['boot_extent']['valid_pointer'])

    def test_reset_clock_write_order(self):
        image = fixture()
        struct.pack_into('>I', image, 0x440, 0x020c4004)
        self.assertFalse(inspect(image)['reset_clock_writes'][0]['before_first_mmdc'])
        first, second = bytes(image[0x438:0x440]), bytes(image[0x440:0x448])
        image[0x438:0x448] = second + first
        self.assertTrue(inspect(image)['reset_clock_writes'][0]['before_first_mmdc'])


if __name__ == '__main__':
    unittest.main()
