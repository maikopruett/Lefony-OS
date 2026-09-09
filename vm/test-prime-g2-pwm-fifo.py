#!/usr/bin/env python3
"""Black-box PWM FIFO contracts, including an evidence-only audit mode.

The counter source is disconnected while register access remains clocked,
so FIFO capacity checks do not assume an undocumented consumption edge.
No physical USB access. Failures are retained, never converted to passes.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import tempfile

state = importlib.import_module('test-prime-g2-gpt-state')
PWM = 0x020f8000


def run(case):
    with tempfile.TemporaryDirectory(prefix='pg2pwmfifo-') as folder:
        vm = state.VM(Path(folder), 'vm', None)
        try:
            q = vm.q
            q.writel(0x020c4080, q.readl(0x020c4080) | (3 << 30))
            q.writel(PWM, 8)
            q.writel(PWM, 1)  # EN=1, CLKSRC=0; no counter consumption
            before = q.readl(PWM + 4)
            samples = []
            if case == 'occupancy':
                for value in (100, 200, 300, 400):
                    q.writel(PWM + 12, value)
                    samples.append(q.readl(PWM + 4) & 7)
                return {'actual': samples, 'expected': [1, 2, 3, 4]}
            if case == 'overflow':
                for value in (100, 200, 300, 400, 500):
                    q.writel(PWM + 12, value)
                return {'actual': q.readl(PWM + 4) & 0x47, 'expected': 0x44}
            if case == 'occupancy-readonly':
                q.writel(PWM + 4, 7)
                return {'actual': q.readl(PWM + 4) & 7, 'expected': before & 7}
            if case == 'w1c-no-injection':
                q.writel(PWM + 4, 0x70)
                return {'actual': q.readl(PWM + 4) & 0x70, 'expected': 0}
            raise ValueError(case)
        finally:
            vm.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path,
                        help='write a new JSON evidence file; report failures without asserting parity')
    args = parser.parse_args()
    if args.audit and args.audit.exists():
        parser.error('audit output already exists')
    binary = state.recovery.QEMU
    results = {}
    for case in ('occupancy', 'overflow', 'occupancy-readonly', 'w1c-no-injection'):
        result = run(case)
        result['passed'] = result['actual'] == result['expected']
        results[case] = result
        print(f'{"PASS" if result["passed"] else "FAIL"} {case}: {result}')
    report = {
        'audit_completed': True,
        'conformance_passed': all(result['passed'] for result in results.values()),
        'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
        'physical_access': False, 'full_hardware_parity': False,
        'tests': results,
        'sources': ['https://mcuxpresso.nxp.com/api_doc/dev/4162/a00131.html',
                    'build/kernel-inspect/drivers/pwm/pwm-imx.c'],
        'unqualified': ['FIFO consumption edge and empty-FIFO update errata',
                        'physical PWM register differential and optical waveform'],
    }
    if args.audit:
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(json.dumps(report, indent=2) + '\n')
    else:
        assert all(result['passed'] for result in results.values()), report


if __name__ == '__main__':
    main()
