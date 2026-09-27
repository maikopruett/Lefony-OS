#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private-fixture HP menu, calculation and cold saved-history regression.

Uses original ARM code and ordinary modeled keypad input. Compares logical
LCDIF pixels; does not qualify the physical panel or flashing/restore process.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from analyze_hp_prime_compatibility import private_output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--stock-physical', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--uboot', type=Path)
    parser.add_argument('--ddr-image', type=Path)
    args = parser.parse_args()
    out = private_output(args.output)
    out.mkdir(parents=True, exist_ok=False)
    backing_hash = hashlib.sha256(args.stock_physical.read_bytes()).hexdigest()
    common = [sys.executable, str(ROOT/'vm/probe-prime-hp-handoff.py'),
              '--image', str(args.image), '--stock-nand', str(args.stock_physical),
              '--physical-pages', '--menu', '--seconds', '24']
    if args.uboot:
        common += ['--uboot', str(args.uboot), '--ram-loader']
    if args.ddr_image:
        common += ['--ddr-image', str(args.ddr_image)]
    subprocess.run(common+['--output', str(out/'save'), '--keys',
                   'one,two,plus,three,ok', '--power-off'], check=True, timeout=180)
    subprocess.run(common+['--output', str(out/'cold'), '--overlay-from',
                   str(out/'save/nand.overlay')], check=True, timeout=180)
    first = json.loads((out/'save/observation.json').read_text())
    cold = json.loads((out/'cold/observation.json').read_text())
    assert first['samples'][1]['ecc_writes'] > first['samples'][0]['ecc_writes']
    assert first['hp_instruction_patches'] == cold['hp_instruction_patches'] == []
    assert first['image_sha256'] == cold['image_sha256']
    def pixels(path):
        # Exclude clock/battery header and soft-key bar; compare full history.
        return Image.open(path).convert('RGB').crop((0, 20, 320, 220)).tobytes()
    before = pixels(out/'save/before-keys.png')
    after = pixels(out/'save/after-keys.png')
    retained = pixels(out/'cold/lcdif-logical.png')
    assert before != after, 'modeled keypad did not change the calculation history'
    assert retained == after, 'cold HP history differs from its pre-shutdown pixels'
    assert hashlib.sha256(args.stock_physical.read_bytes()).hexdigest() == backing_hash
    (out/'qualification.json').write_text(json.dumps({
        'result': 'PASS original HP menu boot, keypad calculation, save and cold retained history',
        'logical_history_sha256': hashlib.sha256(retained).hexdigest(),
        'stock_physical_sha256': backing_hash,
        'hp_sha256': first['image_sha256'], 'uboot_sha256': first['uboot_sha256'],
        'ddr_setup': first['ddr'],
        'ddr_image_sha256': first['ddr_image_sha256'],
        'incompatible_ddr_rejected': first['incompatible_ddr_rejected'],
        'qemu_sha256': first['qemu_sha256'],
        'limits': ['DDR PHY timing not modeled', 'logical LCDIF pixels, not physical panel',
                   'private stock fixture with unchanged geometry', 'physical test still required'],
    }, indent=2)+'\n')
    print('PASS unmodified HP menu boot, GPIO keypad calculation, NAND save and cold retained history; backing unchanged')


if __name__ == '__main__':main()
