#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Boot a verified desktop emulator session and check its reviewed priority.

Requires private Phase 5 inputs. Uses NAND ROM startup and normal menu keys.
Never attaches to USB hardware or marks physical installation as confirmed.
"""
import argparse
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prime_dual_installer import migration
from analyze_hp_prime_compatibility import private_output
m = importlib.import_module('test-prime-dual-boot')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--uboot', type=Path, required=True, help='matching U-Boot binary')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    session = private_output(args.session)
    review = json.loads((session / 'review.json').read_text())
    assert review['phase'] == 'verified' and review['execution'] == 'offline-emulator'
    output = private_output(args.output); output.mkdir(parents=True, exist_ok=False)
    a = SimpleNamespace(output=output, fixture=session/'migration/nand.raw', uboot=args.uboot.resolve(),
        ddr_image=Path(review['bundle']['uboot']), rom=True)
    priority = review['priority']
    expected = {'hp': 'HP RAM: verified V15751 os', 'lefony': 'entering calculator runtime'}
    with migration().NativeBCH() as native:
        for block in (260, 261):
            page = migration().payload(migration().read_block(a.fixture, block)[:2112], native)
            assert int.from_bytes(page[16:20], 'little') == int(priority == 'hp')
    overlay = output/'boot.overlay'
    vm = m.VM(a, 'reviewed-priority', overlay)
    try:
        vm.wait(expected[priority], 75)
    finally: vm.close()
    vm = m.VM(a, 'one-time-other', overlay, held=True)
    try:
        vm.wait('screen=1'); vm.release()
        vm.key(5, 4) if priority == 'hp' else vm.key(4, 5)
        vm.key(7, 0)
        vm.wait(expected['lefony' if priority == 'hp' else 'hp'], 75)
    finally: vm.close()
    vm = m.VM(a, 'priority-retained', overlay)
    try: vm.wait(expected[priority], 75)
    finally: vm.close()
    result = {'result': 'PASS', 'transaction': review['transaction'], 'priority': priority,
              'both_os_rom_boot': True, 'one_time_selection_retains_priority': True,
              'physical_installation': False}
    (output/'qualification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__': main()
