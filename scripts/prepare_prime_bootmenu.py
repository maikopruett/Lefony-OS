#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply the Phase 1 boot manager to the pinned, one-shot-patched U-Boot tree.
Embedded U-Boot adaptations retain GPL-2.0-or-later.
"""
import argparse
from pathlib import Path
import shutil
from generate_bootmenu_font import generate
ROOT=Path(__file__).resolve().parents[1]
def replace(path,old,new):
    text=path.read_text()
    if new in text:return
    if text.count(old)!=1:raise ValueError(f'unexpected U-Boot context: {path.name}')
    path.write_text(text.replace(old,new))
def prepare(tree):
    board=tree/'board/hp/mx6ull_prime'
    replace(board/'Makefile','obj-y  := mx6ull_prime.o',
            'obj-y  := mx6ull_prime.o\nobj-y += boot.o hardware.o menu.o render.o preferences.o')
    replace(board/'mx6ull_prime.c', '\treturn 0;\n}\n\nu32 get_board_rev(void)',
            '\t/* Candidate boot policy: recovery above always takes precedence. */\n\tenv_set("bootcmd", "lfboot");\n\treturn 0;\n}\n\nu32 get_board_rev(void)')
    replace(board/'mx6ull_prime.c', '#include <command.h>',
            '#include <command.h>\nvoid lefony_recovery_screen(void);')
    replace(board/'mx6ull_prime.c', '\t\trun_command("sdp 0", 0);',
            '\t\tlefony_recovery_screen();\n\t\trun_command("sdp 0", 0);')
    replace(tree/'configs/mx6ull_prime_defconfig','CONFIG_LOCALVERSION="-lefony-sdp1"',
            'CONFIG_LOCALVERSION="-lefony-menu1"')
    for path in (ROOT/'native/prime_g2/bootmenu').iterdir():
        if path.suffix in ('.c','.h'):shutil.copyfile(path,board/path.name)
    generate(board/'font.h')
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('tree',type=Path)
    prepare(parser.parse_args().tree)
