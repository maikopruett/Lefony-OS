#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional exact-HP wake hooks with explicitly modeled SNVS/WDOG registers.

No hardware I/O. This validates instruction flow and mailbox failure handling,
not electrical power behavior. Full ROM/input testing is a separate gate.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_hp_prime_compatibility import Machine, private_output, require
from prime_hp_confinement import apply_patches, patches as confinement
from prime_hp_wake_menu import patch_image, generate, HELPER, REQUEST
import unicorn as uc


def machine(data, case):
    m = Machine(data)
    m.u.mem_map(0x02000000, 0x100000)
    snvs = 0x020cc000
    values = {snvs: 0, snvs+0x34: 0, snvs+0x38: 0x100001,
              snvs+0x4c: 8 if case in ('pgd', 'pgd-stuck') else 0,
              snvs+0x68: 0x4b4f464c if case == 'lfok' else 0,
              0x020c4074: 0x00001234}
    if case == 'locked': values[snvs] = 32
    events = []

    def read(u, access, address, size, value, user):
        m.put(address, values.get(address, 0), size)

    def write(u, access, address, size, value, user):
        events.append((address, value))
        if address == snvs+0x4c:
            if case != 'pgd-stuck': values[address] &= ~value
        elif address != snvs+0x68 or case != 'request-stuck':
            values[address] = value

    m.u.hook_add(uc.UC_HOOK_MEM_READ, read, begin=0x02000000, end=0x020fffff)
    m.u.hook_add(uc.UC_HOOK_MEM_WRITE, write, begin=0x02000000, end=0x020fffff)
    return m, values, events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require((ROOT/'native/prime_g2/dual_boot/hp_wake_menu.h').read_text()==generate(),
            'checked-in U-Boot wake table differs from the instruction-tested patches')
    # Whole original hash plus atomic, non-overlapping power/storage patches.
    data = patch_image(args.image.read_bytes())
    data = apply_patches(data, confinement('HPPrime.img'))
    cases = []
    for case in ('ordinary', 'pgd', 'locked', 'lfok', 'pgd-stuck', 'request-stuck'):
        m, values, events = machine(data, case)
        sp = m.get('SP')
        for reg in range(1, 13): m.set('R'+str(reg), 0x12340000+reg)
        m.u.emu_start(HELPER | 1, 0x83fe0000, timeout=5_000_000, count=1_000_000)
        require(m.get('PC') == 0x83fe0000, 'mailbox loop was not bounded')
        expected = case in ('ordinary', 'pgd')
        require(m.get('R0') == int(expected), 'wrong mailbox result')
        require(m.get('SP') == sp and all(m.get('R'+str(r)) == 0x12340000+r
                for r in range(1, 13)), 'request clobbered caller state')
        require((values[0x020cc068] == REQUEST) == expected, 'wrong retained request')
        if case == 'lfok': require(values[0x020cc068] == 0x4b4f464c, 'boot confirmation overwritten')
        cases.append({'case': case, 'request': expected, 'instructions': m.count})
    m, values, events = machine(data, 'ordinary')
    sp = m.get('SP')
    m.run(0x803a4c1e)
    require(values[0x020cc068] == REQUEST and values[0x020cc038] == 0x100061,
            'original power-off command or unrelated LPCR bits changed')
    require(m.get('SP') == sp, 'power-off hook unbalanced stack')
    for case in ('ordinary', 'locked'):
        m, values, events = machine(data, case)
        restored = []
        m.hooks[0x802b370e] = lambda machine: restored.append(True)
        stop = []

        def reset(u, access, address, size, value, user):
            if address == 0x020bc000 and len([e for e in events if e[0] == address]) == 3:
                stop.append(True); u.emu_stop()

        m.u.hook_add(uc.UC_HOOK_MEM_WRITE, reset, begin=0x020bc000, end=0x020bc001)
        m.u.emu_start(0x8039df29, 0x8039df2c, timeout=5_000_000, count=1_000_000)
        require(restored == [True], 'original wake restoration skipped')
        if case == 'ordinary':
            require(stop and values[0x020cc068] == REQUEST and
                    values[0x020c4074] == 0x31234, 'wake did not request ordinary watchdog reset')
        else:
            require(not stop and m.get('PC') == 0x8039df2c, 'locked mailbox did not resume HP')
    out = private_output(args.output)
    out.mkdir(parents=True, exist_ok=False)
    (out/'qualification.json').write_text(json.dumps({
        'result': 'PASS', 'cases': cases,
        'power_off': 'request precedes original TOP command; unrelated bits preserved',
        'wake': 'original restoration then reset, or original resume on failed request',
        'limits': ['synthetic MMIO semantics', 'not physical wake qualification'],
    }, indent=2)+'\n')
    print('PASS exact HP wake hooks, mailbox ownership, bounded failures and original power-off', flush=True)


if __name__ == '__main__':
    main()
