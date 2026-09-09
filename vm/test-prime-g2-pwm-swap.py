#!/usr/bin/env python3
"""32-bit PWM sample write ordering; no physical access or narrow-access claim."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import tempfile

state = importlib.import_module('test-prime-g2-gpt-state')
PWM = 0x020f8000


def run(mode, migrate=False):
    with tempfile.TemporaryDirectory(prefix='pg2pwmswap-') as directory:
        folder = Path(directory)
        vm = state.VM(folder, 'source', None)
        destination = None
        try:
            q = vm.q
            vm.qmp.execute('cont')
            q.writel(0x020c401c, (q.readl(0x020c401c) & ~0x7f) | 0x40)
            q.writel(0x020c4080, q.readl(0x020c4080) | (3 << 30))
            q.writel(PWM, 8)
            q.writel(PWM + 16, 23998)
            cr = 1 | (mode << 20)  # no counter source while loading FIFO
            q.writel(PWM, cr)
            words = [0x12345678, 0x89abcdef, 0xaabbccdd, 0x01020304]
            expected = []
            for word in words:
                half = word >> 16 if mode & 1 else word & 0xffff
                expected.append(((half & 255) << 8 | half >> 8) if mode & 2 else half)
                q.writel(PWM + 12, word)
            count = q.readl(PWM + 4) & 7
            q.writel(PWM + 12, 0xffffffff)
            overflow = q.readl(PWM + 4) & 0x47
            # Swapping applies on insertion, not consumption/readback. Change
            # controls after queuing and confirm existing words do not change.
            q.writel(PWM, 1 | (2 << 16))
            q.command('clock_step 500000')
            if migrate:
                vm.qmp.execute('stop')
                destination = state.VM(folder, 'destination', None, incoming=True)
                destination.q.command('clock_step 500000')
                uri = 'unix:' + str(folder / 'migration.sock')
                destination.qmp.execute('migrate-incoming', {'uri': uri})
                vm.qmp.execute('migrate', {'uri': uri})
                state.wait_migration(vm)
                state.wait_migration(destination)
                q = destination.q
                destination.qmp.execute('cont')
            values = []
            for i in range(4):
                q.command(f'clock_step {500000 if i == 0 else 1000000}')
                values.append(q.readl(PWM + 12))
            return {'actual': [count, overflow, values, q.readl(PWM + 4) & 7],
                    'expected': [4, 0x44, expected, 0]}
        finally:
            if destination:
                destination.close()
            vm.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path)
    args = parser.parse_args()
    if args.audit and args.audit.exists():
        parser.error('audit output already exists')
    results = {}
    for mode in range(4):
        for migration in (False, True):
            name = f'mode-{mode}-migration-{migration}'
            result = run(mode, migration)
            result['passed'] = result['actual'] == result['expected']
            results[name] = result
            print(f'{"PASS" if result["passed"] else "FAIL"} {name}: {result}')
    report = {'audit_completed': True,
              'conformance_passed': all(r['passed'] for r in results.values()),
              'binary_sha256': hashlib.sha256(state.recovery.QEMU.read_bytes()).hexdigest(),
              'physical_access': False, 'full_hardware_parity': False,
              'tests': results}
    if args.audit:
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(json.dumps(report, indent=2) + '\n')
    else:
        assert report['conformance_passed'], report


if __name__ == '__main__':
    main()
