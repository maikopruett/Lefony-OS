from pathlib import Path
import copy
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_prime_g2_rom_dma import analyze


class ROMDMAAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.capture = json.loads((ROOT / 'hardware/prime_g2/reference/rom-dma-chain-20260907.json').read_text())

    def test_physical_retained_read(self):
        result = analyze(self.capture)
        self.assertEqual(len(result['candidates']), 1)
        read = result['candidates'][0]
        self.assertEqual(read['row_3byte'], 1280)
        self.assertEqual(read['column'], 0)
        self.assertEqual(read['additional_address_bytes'], '00 00')
        self.assertEqual(read['transfer_bytes'], 2071)
        self.assertEqual(read['chain'][-1], '0x00901f08')
        self.assertEqual(read['payload_address'], '0x00907000')
        self.assertEqual(read['auxiliary_address'], '0x0090b074')

    def test_missing_memory_does_not_invent_a_chain(self):
        capture = copy.deepcopy(self.capture)
        capture['dma_registers'].pop('OCRAM_00901ed8')
        self.assertEqual(analyze(capture)['candidates'], [])

    def test_normal_dma_terminal_is_separate_from_failed_bch(self):
        capture = json.loads((ROOT / 'hardware/prime_g2/reference/rom-dma-buffers-20260907.json').read_text())
        result = analyze(capture)
        completion = result['retained_completion']
        self.assertTrue(completion['consistent_with_normal_dma_terminal'])
        self.assertEqual(completion['sense_branches'], [{
            'descriptor': '0x00901e9c', 'normal_next': '0x00901ecc',
            'alternate_next': '0x00901f14', 'alternate_is_error_terminal': True}])
        self.assertEqual(result['retained_buffers']['chunk_status'][2], 254)

    def test_terminal_requires_consistent_live_registers(self):
        for name in ('APBH_CH0_CMD', 'APBH_CH0_BAR', 'APBH_CH0_NXTCMDAR'):
            for remove in (False, True):
                capture = copy.deepcopy(self.capture)
                if remove:
                    del capture['dma_registers'][name]
                else:
                    capture['dma_registers'][name]['value'] = '0xdeadbeef'
                completion = analyze(capture)['retained_completion']
                self.assertFalse(completion['consistent_with_normal_dma_terminal'])
                self.assertIn(name, completion['missing_registers' if remove else 'mismatched_registers'])

    def test_unknown_sense_target_is_not_called_error_handler(self):
        capture = copy.deepcopy(self.capture)
        capture['dma_registers']['OCRAM_00901ea4']['value'] = '0x80000000'
        completion = analyze(capture)['retained_completion']
        self.assertFalse(completion['consistent_with_normal_dma_terminal'])
        self.assertFalse(completion['sense_branches'][0]['alternate_is_error_terminal'])

    def test_active_channel_is_not_retained_idle_evidence(self):
        capture = copy.deepcopy(self.capture)
        capture['dma_registers']['APBH_CH0_SEMA']['value'] = '0x00010000'
        with self.assertRaises(ValueError):
            analyze(capture)

    def test_nonterminating_chain_rejected(self):
        capture = copy.deepcopy(self.capture)
        capture['dma_registers']['OCRAM_00901f08']['value'] = '0x00901e64'
        self.assertEqual(analyze(capture)['candidates'], [])

    def test_missing_readstart_rejected(self):
        capture = copy.deepcopy(self.capture)
        capture['dma_registers']['OCRAM_00901f34']['value'] = '0xa1360000'
        self.assertEqual(analyze(capture)['candidates'], [])

    def test_retained_buffers_identify_failed_chunk(self):
        capture = json.loads((ROOT / 'hardware/prime_g2/reference/rom-dma-buffers-20260907.json').read_text())
        result = analyze(capture)
        self.assertEqual(result['retained_buffers']['chunk_status'], [0, 0, 254, 0])
        self.assertEqual(len(result['retained_buffers']['payload_sha256']), 64)
        capture['dma_registers'].pop('PAYLOAD_00907000')
        with self.assertRaises(ValueError):
            analyze(capture)

    def test_no_layout_does_not_guess_status_offsets(self):
        capture = json.loads((ROOT / 'hardware/prime_g2/reference/rom-dma-buffers-20260907.json').read_text())
        capture.pop('nand_registers')
        buffers = analyze(capture)['retained_buffers']
        self.assertIn('payload_sha256', buffers)
        self.assertNotIn('chunk_status', buffers)


if __name__ == '__main__':
    unittest.main()
