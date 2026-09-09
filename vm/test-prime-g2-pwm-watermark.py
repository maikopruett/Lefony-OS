#!/usr/bin/env python3
"""Audit the missing PWM FIFO-watermark threshold path.

Only nominal draining across each threshold is tested. This deliberately
does not choose sticky-versus-level reassertion, W1C race, or reset semantics.
Audit completion is not conformance: current implementations may fail.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import tempfile

state = importlib.import_module('test-prime-g2-gpt-state')
PWM = 0x020f8000


def run(watermark, enabled):
    with tempfile.TemporaryDirectory(prefix='pg2pwmwater-') as directory:
        vm = state.VM(Path(directory), 'vm', None)
        try:
            q = vm.q
            q.command('irq_intercept_out /machine/soc/lcdif sysbus-irq')
            vm.qmp.execute('cont')
            q.writel(0x020c401c, (q.readl(0x020c401c) & ~0x7f) | 0x40)
            q.writel(0x020c4080, q.readl(0x020c4080) | (3 << 30))
            q.writel(PWM, 8)
            q.writel(PWM, 1 | ((watermark - 1) << 26))
            q.writel(PWM + 16, 23998)
            for sample in (100, 200, 300, 400):
                q.writel(PWM + 12, sample)
            q.writel(PWM + 4, 0x78)
            q.writel(PWM + 8, int(enabled))
            q.writel(PWM, 1 | (2 << 16) | ((watermark - 1) << 26))
            actual = []
            for empty in range(1, 5):
                q.command('clock_step 1000000')
                q.readl(0x80000000)  # IRQ must arrive without PWM polling
                level = q.levels.get(1, False)
                status = q.readl(PWM + 4)
                actual.append([status & 7, bool(status & 8), level])
            expected = [[4 - empty, empty >= watermark,
                         enabled and empty >= watermark] for empty in range(1, 5)]
            return {'actual': actual, 'expected': expected}
        finally:
            vm.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path)
    args = parser.parse_args()
    if args.audit and args.audit.exists():
        parser.error('audit output already exists')
    results = {}
    for watermark in range(1, 5):
        for enabled in (False, True):
            name = f'empty-slots-{watermark}-irq-{enabled}'
            result = run(watermark, enabled)
            result['passed'] = result['actual'] == result['expected']
            results[name] = result
            print(f'{"PASS" if result["passed"] else "FAIL"} {name}: {result}')
    report = {'audit_completed': True,
              'conformance_passed': all(r['passed'] for r in results.values()),
              'binary_sha256': hashlib.sha256(state.recovery.QEMU.read_bytes()).hexdigest(),
              'physical_access': False, 'full_hardware_parity': False,
              'tests': results,
              'source': 'https://mcuxpresso.nxp.com/api_doc/dev/1244/group__pwm__driver.html',
              'unqualified': ['W1C/reassertion semantics', 'reset and enable edges',
                              'physical FIFO consumption timing']}
    if args.audit:
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(json.dumps(report, indent=2) + '\n')
    else:
        assert report['conformance_passed'], report


if __name__ == '__main__':
    main()
