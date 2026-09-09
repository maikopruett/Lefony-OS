import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prime_g2_raw_read_plan import build_plan


class RawReadPlanTests(unittest.TestCase):
    def setUp(self):
        self.capture = json.loads((ROOT / 'hardware/prime_g2/reference/rom-dma-buffers-20260907.json').read_text())

    def test_bounded_raw_descriptor_and_backup(self):
        plan = build_plan(self.capture)
        self.assertEqual(plan['page'], 1280)
        self.assertEqual(plan['ram_backup_ranges'], [{'address': 0x00907000, 'bytes': 2112}])
        self.assertFalse(plan['hardware_qualified'])
        self.assertEqual([edit['after'] for edit in plan['descriptor_edits']],
                         [0x08403095, 0x00907000, 0x01800840, 0])

    def test_reject_mutated_pio_or_error_branch(self):
        for address, value in ((0x00901efc, 0x00800000), (0x00901f18, 0x00001096),
                               (0x00901e70, 0x08820008), (0x00901ed0, 0x00006096)):
            capture = copy.deepcopy(self.capture)
            capture['dma_registers'][f'OCRAM_{address:08x}']['value'] = hex(value)
            with self.assertRaises((ValueError, KeyError)):
                build_plan(capture)

    def test_reject_wrong_read_or_unbounded_buffer(self):
        for address, value in ((0x00901f30, 0x00000600), (0x00901ee8, 0x80000000),
                               (0x00901ee8, 0x00901e64)):
            capture = copy.deepcopy(self.capture)
            capture['dma_registers'][f'OCRAM_{address:08x}']['value'] = hex(value)
            with self.assertRaises(ValueError):
                build_plan(capture)


if __name__ == '__main__':
    unittest.main()
