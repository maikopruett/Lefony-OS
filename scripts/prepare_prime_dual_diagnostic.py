#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Instrument a separate RAM-only dual build; never install this in NAND."""
import argparse
from pathlib import Path
import shutil
from prepare_prime_bootmenu import ROOT,replace
from prepare_prime_phase6_recovery import force_ram_recovery


def prepare(tree):
    force_ram_recovery(tree)
    board=tree/'board/hp/mx6ull_prime'
    replace(board/'mx6ull_prime.c','env_set("bootdelay", "-2");',
            'env_set("bootdelay", "-1"); /* explicit RAM diagnostic */')
    replace(board/'Makefile','obj-y += hp_ram.o hp_nand_info.o dual_boot.o',
            'obj-y += hp_ram.o hp_nand_info.o dual_boot.o hp_transfer_info.o\n'
            'CFLAGS_dual_boot.o += -DLEFONY_DUAL_RAM_DIAGNOSTIC=1')
    shutil.copyfile(ROOT/'native/prime_g2/hp_handoff/hp_transfer_info.c',board/'hp_transfer_info.c')
    replace(board/'hp_nand_info.c','(u8 *)0x84000000, *hashes','(u8 *)0x84200000, *hashes')
    replace(tree/'configs/mx6ull_prime_defconfig','-lefony-dual5-candidate1','-lefony-dual-ram-diagnostic')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path)
    prepare(p.parse_args().tree)
