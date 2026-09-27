#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add the isolated Phase 3 command after the normal menu preparation.
Embedded U-Boot changes retain GPL-2.0-or-later.
"""
import argparse
from pathlib import Path
import shutil
from prepare_prime_bootmenu import ROOT, replace

# Original HP G2 DDR configuration, physically checked with the unchanged RAM
# menu and V15751 image. In particular MDASP must cover HP's 0x90000000 alias.
# Apply only at ROM DCD startup; never reconfigure live DDR from code in DDR.
HP_DDR_VALUES = (
    ('020E0288', '000C0030', '00000030'),
    ('021B000C', '3F4354F3', '676B52F3'),
    ('021B0018', '00211740', '00201740'),
    ('021B0030', '00431023', '006B1023'),
    ('021B0040', '00000047', '0000005F'),
    ('021B0000', '83180000', '85180000'),
    ('021B0890', '00400A38', '00400000'),
    ('021B0020', '00007800', '00000800'),
    ('021B0004', '0002556D', '0002552D'),
)


def prepare(tree):
    board = tree / 'board/hp/mx6ull_prime'
    for address, original, hp in HP_DDR_VALUES:
        replace(board / 'imximage.cfg',
                f'DATA 4 0x{address} 0x{original}',
                f'DATA 4 0x{address} 0x{hp}')
    replace(board / 'Makefile',
            'obj-y += boot.o hardware.o menu.o render.o preferences.o',
            'obj-y += boot.o hardware.o menu.o render.o preferences.o\nobj-y += hp_ram.o hp_menu.o hp_nand_info.o')
    for name in ('hp_ram.c', 'hp_menu.c', 'hp_nand_info.c', 'hp_confinement.h'):
        shutil.copyfile(ROOT / 'native/prime_g2/hp_handoff' / name, board / name)
    replace(board / 'mx6ull_prime.c', 'env_set("bootcmd", "lfboot");',
            'env_set("bootcmd", "lfboot");\n\tenv_set("bootdelay", "-1"); /* explicit RAM experiment */')
    config = tree / 'configs/mx6ull_prime_defconfig'
    replace(config, 'CONFIG_LOCALVERSION="-lefony-menu1"',
            'CONFIG_LOCALVERSION="-lefony-hp-ram-experiment7"\nCONFIG_SHA256=y')
    # A stock raw trial must not create U-Boot flash BBT records in HP's last
    # NAND blocks. Scan markers into the RAM table, like manufacturing Linux.
    replace(tree / 'drivers/mtd/nand/mxs_nand.c',
            'nand->bbt_options = NAND_BBT_USE_FLASH | NAND_BBT_NO_OOB;',
            'nand->bbt_options = 0; /* isolated stock trial: RAM BBT only */')
    # The isolated raw-restore trial can transfer a full device twice. Retain a
    # finite window; never apply this change to the ordinary installed loader.
    sdp = tree / 'drivers/usb/gadget/f_sdp.c'
    replace(sdp, 'get_timer(lefony_sdp_start) >= 180000',
            'get_timer(lefony_sdp_start) >= 5400000')
    replace(sdp, 'get_timer(lefony_sdp_start) < 180000)',
            'get_timer(lefony_sdp_start) < 5400000)')
    replace(sdp, '180 second recovery window', '5400 second RAM research window')
    # Upstream retains the rejected IMX-header status even when a legacy script
    # succeeds. Report the actual script outcome so the next SDP read is aligned.
    replace(sdp, 'source(sdp_func->jmp_address, "script@1");',
            'status = source(sdp_func->jmp_address, "script@1") ? SDP_ERROR_IMXHEADER : 0;')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    prepare(parser.parse_args().tree)
