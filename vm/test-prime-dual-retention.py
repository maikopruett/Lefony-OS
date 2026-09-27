#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Save HP history, cold-boot Lefony, then verify HP history through NAND ROM.

Uses ordinary modeled keypad input and one copy-on-write overlay across all
boots. No RAM payload/DCD injection or filesystem API writes. Logical LCDIF
pixels do not establish physical panel or electrical power-transition behavior.
"""
import argparse
import importlib
import json
from pathlib import Path
import re
import time

from PIL import Image
from prime_dual_migration import file_hash, private_output
from analyze_prime_hp_write_trace import analyze

m = importlib.import_module('test-prime-dual-boot')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('fixture', 'uboot', 'ddr-image', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    args.rom = True
    args.keep_on_shutdown = True
    args.output = private_output(args.output)
    args.output.mkdir(parents=True, exist_ok=False)
    hashes = {name: file_hash(path).hex() for name, path in (
        ('nand', args.fixture), ('uboot', args.uboot),
        ('imx', args.ddr_image), ('qemu', m.r.QEMU))}
    overlay = args.output / 'retention.overlay'
    keymap = {name: (int(row), int(col)) for name, row, col in re.findall(
        r'PRIME_G2_KEY\(\s*(\w+),\s*\d+,\s*\w+,\s*(\d+),\s*(\d+)\)',
        (m.ROOT / 'ports/lefony-prime-g2/ion/src/prime_g2/keymap.inc').read_text())}

    def history(vm, name):
        vm.capture_hp_logical()
        path = vm.out / (name + '.png')
        image = Image.open(vm.out / 'hp-logical.png').convert('RGB')
        image.save(path)
        return image.crop((0, 20, 320, 220)).tobytes()

    vm = m.VM(args, 'save-hp', overlay, held=True)
    try:
        vm.wait('screen=1 selected=0'); vm.release()
        # Saved HP priority, then select HP through the actual menu.
        vm.key(4, 5); vm.key(4, 5); vm.key(7, 0); vm.wait('screen=2')
        vm.key(4, 5); vm.key(7, 0); vm.wait('screen=1')
        vm.key(7, 0)
        vm.wait('HP RAM: verified V15751 os'); time.sleep(10)
        before = history(vm, 'before-input')
        programs = vm.q.readl(0x01806170)
        # Exclude earlier boot-menu preference commits from the HP-only trace.
        # Pause at record boundaries; both log and overlay belong to this VM.
        vm.mp.execute('stop')
        trace_offset = (vm.out / 'qemu.log').stat().st_size
        overlay_offset = overlay.stat().st_size
        vm.mp.execute('cont')
        for key in ('three', 'seven', 'plus', 'five', 'ok'):
            vm.key(*keymap[key])
        time.sleep(1)
        expected = history(vm, 'after-input')
        assert expected != before, 'ordinary keypad input did not change HP history'
        row, col = keymap['shift']
        vm.q.writew(0x020b8008, (row << 8) | col | 0x8000)
        time.sleep(.15)
        vm.q.writel(0x020cc0fc, 1); time.sleep(1)
        vm.q.writel(0x020cc0fc, 0)
        vm.q.writew(0x020b8008, (row << 8) | col)
        time.sleep(8)
        assert vm.q.readl(0x01806170) > programs, 'HP shutdown did not save NAND'
        vm.mp.execute('stop')
        (vm.out / 'hp-save.log').write_bytes((vm.out / 'qemu.log').read_bytes()[trace_offset:])
        (vm.out / 'hp-save.overlay').write_bytes(b'PG2RAW1\n' + overlay.read_bytes()[overlay_offset:])
        writes = analyze(vm.out / 'hp-save.log', vm.out / 'hp-save.overlay')
        assert not writes['escaped_attempts'] and not writes['escaped_commits'], 'HP save escaped confinement'
    finally:
        vm.close()
    print('PASS normal HP keypad calculation and Shift+On NAND save', flush=True)
    vm = m.VM(args, 'one-time-lefony', overlay, held=True)
    try:
        vm.wait('screen=1'); vm.release(); vm.key(5, 4); vm.key(7, 0)
        vm.wait('entering calculator runtime', 75); time.sleep(6)
        vm.capture('lefony')
        assert vm.q.readl(0x87ffd000) == 0x3548464c
    finally:
        vm.close()
    vm = m.VM(args, 'cold-hp', overlay)
    try:
        vm.wait('Dual boot: countdown ready')
        vm.wait('HP RAM: verified V15751 os'); time.sleep(10)
        retained = history(vm, 'retained-history')
        assert retained == expected, 'HP history changed across the Lefony boot'
    finally:
        vm.close()
    assert file_hash(args.fixture).hex() == hashes['nand'], 'backing NAND changed'
    for name, path in (('uboot', args.uboot), ('imx', args.ddr_image), ('qemu', m.r.QEMU)):
        assert file_hash(path).hex() == hashes[name], 'test executable changed'
    (args.output / 'qualification.json').write_text(json.dumps({
        'result': 'PASS', 'hashes': hashes,
        'scope': 'ARM NAND-ROM HP save -> one-time Lefony -> unattended HP; history pixels retained',
        'input': 'normal GPIO keypad, 37+5, Shift+On',
        'history_sha256': __import__('hashlib').sha256(retained).hexdigest(),
        'hp_save_writes': writes,
        'physical_qualification': False,
        'limits': ['Logical LCDIF pixels; physical panel is separate',
                   'Cold emulator boots; electrical power loss is not modeled'],
    }, indent=2) + '\n')
    print('PASS HP saved history survives intervening Lefony boot; HP priority unchanged', flush=True)


if __name__ == '__main__':
    main()
