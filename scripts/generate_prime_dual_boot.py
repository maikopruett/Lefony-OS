#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate layout constants and a public-only U-Boot verification key.

Generated U-Boot declarations are GPL-2.0-or-later. No key creation occurs.
"""
import argparse
from pathlib import Path
from prime_dual_boot_contract import load_layout, layout_digest, sha
from prime_hp_confinement import PROFILE
from prime_g2_update_key import modulus


def generate(public_key):
    doc, regions = load_layout()
    n = int.from_bytes(modulus(public_key), 'big')
    def array(name, value):
        return 'static const unsigned char '+name+'[] __aligned(8) = {'+','.join(hex(x) for x in value)+'};\n'
    text = '/* SPDX-License-Identifier: GPL-2.0-or-later */\n/* Generated; do not edit. */\n'
    text += '#define LF_DUAL_LAYOUT 5u\n'
    for name, region in regions.items():
        text += f'#define LF_DUAL_{name.upper()}_FIRST {region.first}u\n'
        text += f'#define LF_DUAL_{name.upper()}_BLOCKS {region.count}u\n'
    text += array('lf_dual_layout_sha', layout_digest())
    text += array('lf_dual_profile_sha', sha(PROFILE.encode()))
    text += array('lf_dual_modulus', n.to_bytes(256,'big'))
    text += array('lf_dual_rr', pow(2,4096,n).to_bytes(256,'big'))
    text += f'#define LF_DUAL_N0INV {(-pow(n,-1,2**32))%(2**32)}u\n'
    return text


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--public-key',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.write_text(generate(a.public_key))
