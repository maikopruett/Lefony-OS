#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Configure the shared loader's embedded DTB; no runtime layout guessing.

Embedded U-Boot configuration retains GPL-2.0-or-later. Run after the dual
preparation. Both output profiles must have byte-identical u-boot-nodtb.bin.
"""
import argparse
from pathlib import Path
from prepare_prime_bootmenu import replace


def prepare(tree, layout):
    if layout not in (1, 5):
        raise ValueError('unsupported boot layout')
    path = tree/'arch/arm/dts/imx6ull-prime.dts'
    text = path.read_text()
    marker = '\n/* Lefony shared boot profile: configuration, not a fallback. */\n'
    if marker in text:
        prefix, suffix = text.split(marker)
        if suffix not in ('/ { config { lefony,boot-layout = <1>; }; };\n',
                          '/ { config { lefony,boot-layout = <5>; }; };\n'):
            raise ValueError('unexpected shared boot configuration')
        text = prefix
    if text.count('model = "HP Prime G2 Calculator";') != 1 or 'lefony,boot-layout' in text:
        raise ValueError('unexpected Prime DTB')
    path.write_text(text+marker+f'/ {{ config {{ lefony,boot-layout = <{layout}>; }}; }};\n')
    replace(tree/'include/configs/mx6ull_prime.h',
            '\t"bootcmd=nand read ${loadaddr} 0x400000 0x800000;"\\\n'
            '\t\t"nand read ${fdt_addr} 0xc00000 0x100000;"\\\n'
            '\t\t"bootz ${loadaddr} - ${fdt_addr}\\0"',
            '\t"bootcmd=lfdualboot\\0"')
    replace(tree/'configs/mx6ull_prime_defconfig',
            'CONFIG_LOCALVERSION="-lefony-dual5-candidate1"',
            'CONFIG_LOCALVERSION="-lefony-boot2"')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree',type=Path);p.add_argument('--layout',type=int,choices=(1,5),required=True)
    a=p.parse_args();prepare(a.tree,a.layout)
