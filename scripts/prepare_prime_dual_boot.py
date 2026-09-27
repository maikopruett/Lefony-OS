#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare a separate Phase 5 U-Boot candidate after the HP research preparation.
Embedded adaptations retain GPL-2.0-or-later. Never used by the normal builder.
"""
import argparse
from pathlib import Path
import shutil
from prepare_prime_bootmenu import ROOT, replace
from generate_prime_dual_boot import generate


def prepare(tree, public_key):
    board=tree/'board/hp/mx6ull_prime'
    replace(board/'Makefile','obj-y += hp_ram.o hp_menu.o hp_nand_info.o',
            'obj-y += hp_ram.o hp_nand_info.o dual_boot.o')
    shutil.copyfile(ROOT/'native/prime_g2/dual_boot/dual_boot.c',board/'dual_boot.c')
    (board/'dual_layout.h').write_text(generate(public_key))
    shutil.copyfile(ROOT/'native/prime_g2/dual_boot/hp_wake_menu.h',board/'hp_wake_menu.h')
    replace(board/'hp_ram.c','#include "hp_confinement.h"',
            '#define LEFONY_DUAL_WAKE_MENU 1\n#include "hp_confinement.h"')
    replace(board/'preferences.h','#define LF_PREF_LAYOUT 1','#define LF_PREF_LAYOUT 5')
    # Keep display shutdown/recovery helpers, but remove the legacy boot command.
    replace(board/'boot.c','U_BOOT_CMD(lfboot,1,0,do_lfboot,"Lefony graphical boot manager","");',
            '/* Legacy lfboot is not registered in the dual-layout candidate. */')
    replace(board/'hp_ram.c','U_BOOT_CMD(hpram, 4, 0, do_hpram, "experimental exact-image HP RAM handoff",\n'
            '           "os|updater <exact-hex-byte-count> [research-256] (image at 80000000)");',
            '/* Unrestricted hpram is not registered in the dual-layout candidate. */')
    replace(board/'mx6ull_prime.c','env_set("bootcmd", "lfboot");\n\tenv_set("bootdelay", "-1"); /* explicit RAM experiment */',
            'env_set("bootcmd", "lfdualboot");\n\tenv_set("bootdelay", "-2");')
    # This board owns recovery and the Enter-only graphical countdown. NXP's
    # generic USB manufacturing policy resets the environment and substitutes
    # bootcmd_mfg whenever the USB PHY was already powered (including a warm
    # NAND reset with a cable attached). Never let it replace lfdualboot.
    # -2 above also prevents pending UART input from bypassing the menu.
    autoboot=tree/'common/autoboot.c'
    text=autoboot.read_text()
    old='#if defined(is_boot_from_usb)'
    new=old+' && !defined(CONFIG_TARGET_MX6ULL_PRIME)'
    if text.count(old)!=2:
        raise ValueError('unexpected U-Boot USB manufacturing policy')
    if text.count(new)!=2:
        if new in text:
            raise ValueError('unexpected U-Boot USB manufacturing policy')
        autoboot.write_text(text.replace(old,new))
    replace(tree/'configs/mx6ull_prime_defconfig','CONFIG_LOCALVERSION="-lefony-hp-ram-experiment7"',
            'CONFIG_LOCALVERSION="-lefony-dual5-candidate1"\nCONFIG_RSA=y\nCONFIG_RSA_SOFTWARE_EXP=y')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path)
    p.add_argument('--public-key',type=Path,required=True);a=p.parse_args()
    prepare(a.tree,a.public_key)
