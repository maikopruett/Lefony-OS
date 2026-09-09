#!/usr/bin/env python3
"""Decode configured Prime NAND clock roots; no MMIO or hardware transport.

Rates are register-derived, not measurements. Power-mode gate semantics and
PLL/PFD settling must be handled by the eventual live clock-tree connection.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path


def decode(capture, oscillator_hz=24000000):
    if not isinstance(oscillator_hz, int) or isinstance(oscillator_hz, bool) or oscillator_hz <= 0:
        raise ValueError('An explicit positive oscillator frequency is required')
    source = capture['clock_registers']

    def reg(name):
        value = int(source[name]['value'], 16)
        if not 0 <= value <= 0xffffffff:
            raise ValueError('Register is not a 32-bit value: ' + name)
        return value

    pll = reg('ANATOP_PLL_SYS')
    pfd = reg('ANATOP_PFD_528')
    mux, divider = reg('CCM_CSCMR1'), reg('CCM_CSCDR1')
    ccgr4, ccgr6 = reg('CCM_CCGR4'), reg('CCM_CCGR6')
    reason = None
    if not pll & (1 << 13):
        parent = Fraction(0)
        reason = 'PLL2 output disabled'
    elif pll & (1 << 16):
        if (pll >> 14) & 3:
            parent = None
            reason = 'External PLL2 bypass input frequency not captured'
        else:
            parent = Fraction(oscillator_hz)
    elif pll & (1 << 12):
        parent = Fraction(0)
        reason = 'PLL2 powered down'
    else:
        parent = Fraction(oscillator_hz * (22 if pll & 1 else 20))

    roots = {}
    for name, mux_bit, div_bit, gate4_bit, gate6_bit in (
            ('gpmi', 19, 22, 28, 8), ('bch', 18, 19, 26, 6)):
        index = 0 if mux & (1 << mux_bit) else 2
        lane = (pfd >> (index * 8)) & 255
        fraction = lane & 63
        divisor = ((divider >> div_bit) & 7) + 1
        rate = None
        root_reason = reason
        if parent == 0 or lane & 128:
            rate = Fraction(0)
            root_reason = reason if parent == 0 else 'Selected PFD is gated'
        elif not 12 <= fraction <= 35:
            root_reason = 'Selected PFD fraction is outside supported range 12..35'
        elif parent is not None:
            rate = parent * 18 / fraction / divisor
        roots[name] = {
            'selected_pfd': index, 'pfd_fraction': fraction, 'post_divisor': divisor,
            'pfd_stable_flag': bool(lane & 64), 'pfd_gated': bool(lane & 128),
            'configured_hz': None if rate is None else {'numerator': rate.numerator, 'denominator': rate.denominator},
            'unknown_or_stopped_reason': root_reason,
            # Do not collapse RUN/WAIT encodings into an unconditional bool.
            'ccgr4_gate_encoding': (ccgr4 >> gate4_bit) & 3,
            'ccgr6_gate_encoding': (ccgr6 >> gate6_bit) & 3,
        }
    return {'oscillator_hz_assumed': oscillator_hz, 'pll2_locked_flag': bool(pll & (1 << 31)),
            'roots': roots,
            'qualification': 'Configured root rates, not measured/effective clocks. '
                             'Gate power modes, settling, bus clocks and live changes remain separate.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--oscillator-hz', type=int, default=24000000)
    args = parser.parse_args()
    print(json.dumps(decode(json.loads(args.capture.read_text()), args.oscillator_hz), indent=2))


if __name__ == '__main__':
    main()
