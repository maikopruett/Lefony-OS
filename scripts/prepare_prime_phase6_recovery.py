#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private RAM recovery transport additions; embedded U-Boot retains GPL-2.0+."""
import argparse
from pathlib import Path
import shutil
from prepare_prime_bootmenu import ROOT, replace


def force_ram_recovery(tree):
    board = tree / 'board/hp/mx6ull_prime'
    # This image is RAM-only recovery, never an installed boot manager. ROM
    # can acknowledge a write to a retained/locked SNVS GPR without changing
    # it. Do not depend on that token to enter this dedicated recovery image.
    replace(board/'mx6ull_prime.c',
            'int recovery = readl(request) == 0x3153464c; /* LFS1 */',
            'int recovery = 1; /* dedicated RAM-only recovery */')
    replace(board/'mx6ull_prime.c',
            'if (readl(request) != 0)\n\t\t\trecovery = 0;',
            '/* Token clearing is best effort; this RAM image always recovers. */')


def prepare(tree):
    force_ram_recovery(tree)
    board = tree / 'board/hp/mx6ull_prime'
    replace(board/'Makefile', 'obj-y += hp_ram.o hp_menu.o hp_nand_info.o',
            'obj-y += hp_ram.o hp_menu.o hp_nand_info.o hp_transfer_info.o')
    shutil.copyfile(ROOT/'native/prime_g2/hp_handoff/hp_transfer_info.c', board/'hp_transfer_info.c')
    # NAND hashing must not overwrite a verified upload while a journal update
    # or readback happens between staging and programming. READBACK already
    # belongs to this transport and is disjoint from STAGE and the command script.
    replace(board/'hp_nand_info.c', '(u8 *)0x84000000, *hashes', '(u8 *)0x84200000, *hashes')
    replace(tree/'configs/mx6ull_prime_defconfig', '-lefony-hp-ram-experiment7', '-lefony-recovery-experiment6')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    prepare(parser.parse_args().tree)
