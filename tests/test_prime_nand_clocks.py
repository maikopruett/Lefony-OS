import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prime_g2_nand_clocks import decode


class NANDClockTests(unittest.TestCase):
    def setUp(self):
        self.capture = json.loads((ROOT / 'hardware/prime_g2/reference/rom-clock-nand-status-20260907.json').read_text())

    def setreg(self, name, value):
        self.capture['clock_registers'][name]['value'] = hex(value)

    def test_captured_roots(self):
        result = decode(self.capture)
        for root in result['roots'].values():
            self.assertEqual(root['configured_hz'], {'numerator': 198000000, 'denominator': 1})
            self.assertEqual(root['selected_pfd'], 2)
            self.assertEqual(root['pfd_fraction'], 24)
            self.assertEqual(root['post_divisor'], 2)
            self.assertEqual(root['ccgr4_gate_encoding'], 3)
            self.assertEqual(root['ccgr6_gate_encoding'], 3)

    def test_independent_parent_selectors_and_all_dividers(self):
        self.setreg('CCM_CSCMR1', 1 << 19)
        for divisor in range(1, 9):
            self.setreg('CCM_CSCDR1', (divisor - 1) << 22)
            result = decode(self.capture)['roots']
            from fractions import Fraction
            rate = Fraction(352000000, divisor)
            self.assertEqual(result['gpmi']['configured_hz'], {'numerator': rate.numerator, 'denominator': rate.denominator})
            self.assertEqual(result['bch']['configured_hz'], {'numerator': 396000000, 'denominator': 1})

    def test_unknown_parent_is_not_zero_or_default_clock(self):
        self.setreg('ANATOP_PLL_SYS', 0x80016001)
        self.assertIsNone(decode(self.capture)['roots']['gpmi']['configured_hz'])
        self.setreg('ANATOP_PLL_SYS', 0x80012001)
        self.assertEqual(decode(self.capture)['roots']['gpmi']['configured_hz'], {'numerator': 9000000, 'denominator': 1})

    def test_bch_mux_and_pll_480mhz_selection(self):
        self.setreg('CCM_CSCMR1', 1 << 18)
        self.setreg('CCM_CSCDR1', 0)
        result = decode(self.capture)['roots']
        self.assertEqual(result['bch']['configured_hz']['numerator'], 352000000)
        self.assertEqual(result['gpmi']['configured_hz']['numerator'], 396000000)
        self.setreg('ANATOP_PLL_SYS', 0x80002000)
        result = decode(self.capture)['roots']
        self.assertEqual(result['gpmi']['configured_hz']['numerator'], 360000000)
        self.assertEqual(result['bch']['configured_hz'], {'numerator': 320000000, 'denominator': 1})

    def test_gated_disabled_powered_down_and_invalid_fraction(self):
        for pll in (0x80000001, 0x80003001):
            self.setreg('ANATOP_PLL_SYS', pll)
            self.assertEqual(decode(self.capture)['roots']['gpmi']['configured_hz']['numerator'], 0)
        self.setreg('ANATOP_PLL_SYS', 0x80002001)
        self.setreg('ANATOP_PFD_528', 0x50d8505b)
        self.assertEqual(decode(self.capture)['roots']['gpmi']['configured_hz']['numerator'], 0)
        for fraction in (0, 11, 36, 63):
            self.setreg('ANATOP_PFD_528', fraction << 16)
            self.assertIsNone(decode(self.capture)['roots']['gpmi']['configured_hz'])

    def test_missing_register_and_bad_oscillator_are_rejected(self):
        for value in (0, -1, True, 24.0):
            with self.assertRaises(ValueError):
                decode(self.capture, value)
        del self.capture['clock_registers']['ANATOP_PLL_SYS']
        with self.assertRaises(KeyError):
            decode(self.capture)

    def test_gates_and_stability_are_not_silently_ignored(self):
        self.setreg('CCM_CCGR4', 1 << 28)
        self.setreg('CCM_CCGR6', 2 << 8)
        self.setreg('ANATOP_PFD_528', 24 << 16)
        result = decode(self.capture)['roots']['gpmi']
        self.assertEqual(result['ccgr4_gate_encoding'], 1)
        self.assertEqual(result['ccgr6_gate_encoding'], 2)
        self.assertFalse(result['pfd_stable_flag'])


if __name__ == '__main__':
    unittest.main()
