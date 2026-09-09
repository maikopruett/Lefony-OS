#!/usr/bin/env python3
"""PWM compare/rollover IRQ contracts, independent of PWM polling.

The modeled PWM lives in LCDIF's device container. Sysbus output 0 belongs
to LCDIF; PWM requires its own output 1 wired to GIC SPI 116.
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
    with tempfile.TemporaryDirectory(prefix='pg2pwmirq-') as folder:
        vm = state.VM(Path(folder), 'vm', None)
        destination = None
        try:
            q = vm.q
            if case != 'gic-route':
                q.command('irq_intercept_out /machine/soc/lcdif sysbus-irq')
            else:
                q.command('irq_intercept_in /machine/soc/a7mpcore/gic')
            vm.qmp.execute('cont')
            q.writel(0x020c401c, (q.readl(0x020c401c) & ~0x7f) | 0x40)
            q.writel(0x020c4080, q.readl(0x020c4080) | (3 << 30))
            q.writel(PWM, 8)
            q.writel(PWM + 16, 23998)  # 1 ms at 24 MHz
            q.writel(PWM + 12, 6000)  # quarter-period compare
            q.writel(PWM, (2 << 16) | 1)
            q.command('clock_step 1000000')
            assert q.readl(PWM + 12) == 6000, 'active FIFO sample was not installed'
            q.writel(PWM + 4, 0x78)

            def irq():
                q.readl(0x80000000)  # flush notifications WITHOUT reading PWM
                return q.levels.get(1, False)

            if case == 'gic-route':
                # Observe the real GIC input, not a replacement device output.
                # qtest MMIO is non-secure and cannot configure reset Group0
                # interrupts. CPU acknowledge/EOI needs a secure guest test;
                # this case deliberately verifies only the board's SPI wire.
                q.readl(0x80000000)
                before = q.levels.get(116, False)
                q.writel(PWM + 8, 4)
                q.command('clock_step 250000')
                q.readl(0x80000000)
                raised = sorted(n for n, level in q.levels.items() if level)
                q.writel(PWM + 4, 0x20)
                q.readl(0x80000000)
                after = q.levels.get(116, False)
                return {'actual': [before, raised, after],
                        'expected': [False, [116], False]}

            if case in ('soft-reset', 'system-reset'):
                q.writel(PWM + 8, 4)
                q.command('clock_step 250000')
                before = irq()
                if case == 'soft-reset':
                    q.writel(PWM, 8)
                else:
                    vm.qmp.execute('system_reset')
                after = irq()
                q.command('clock_step 1000000')
                return {'actual': [before, after, irq()], 'expected': [True, False, False]}
            if case.startswith('migration-'):
                pending = case == 'migration-pending'
                gated = case == 'migration-gated'
                q.writel(PWM + 8, 4)
                elapsed = 1250000 if pending else 1125000
                q.command(f'clock_step {elapsed - 1000000}')
                gates = q.readl(0x020c4080)
                if gated:
                    q.writel(0x020c4080, gates & ~(3 << 30))
                    q.command('clock_step 500000')
                    elapsed += 500000
                before = irq()
                vm.qmp.execute('stop')
                destination = state.VM(Path(folder), 'destination', None, incoming=True)
                destination.q.command('irq_intercept_out /machine/soc/lcdif sysbus-irq')
                destination.q.command(f'clock_step {elapsed}')
                uri = 'unix:' + str(Path(folder) / 'migration.sock')
                destination.qmp.execute('migrate-incoming', {'uri': uri})
                vm.qmp.execute('migrate', {'uri': uri})
                state.wait_migration(vm)
                state.wait_migration(destination)
                q = destination.q
                restored = irq()
                destination.qmp.execute('cont')
                if pending:
                    q.writel(PWM + 4, 0x20)
                    return {'actual': [before, restored, irq()], 'expected': [True, True, False]}
                if gated:
                    q.command('clock_step 1000000')
                    gated_level = irq()
                    q.writel(0x020c4080, gates)
                else:
                    gated_level = False
                q.command('clock_step 124999')
                early = irq()
                q.command('clock_step 1')
                return {'actual': [before, restored, gated_level, early, irq()],
                        'expected': [False, False, False, False, True]}

            if case in ('compare-masked', 'rollover-masked'):
                compare = case.startswith('compare')
                q.command(f'clock_step {250000 if compare else 1000000}')
                return {'actual': [bool(q.readl(PWM + 4) & (0x20 if compare else 0x10)), irq()],
                        'expected': [True, False]}
            if case in ('compare-asynchronous', 'rollover-asynchronous'):
                compare = case.startswith('compare')
                q.writel(PWM + 8, 4 if compare else 2)
                q.command(f'clock_step {249999 if compare else 999999}')
                before = irq()
                q.command('clock_step 1')
                after = irq()  # observed before any PWM status read
                status = bool(q.readl(PWM + 4) & (0x20 if compare else 0x10))
                return {'actual': [before, after, status], 'expected': [False, True, True]}
            if case == 'late-enable':
                q.command('clock_step 250000')
                q.writel(PWM + 8, 4)
                return {'actual': irq(), 'expected': True}
            if case == 'selective-ack':
                q.writel(PWM + 8, 6)
                q.command('clock_step 1000000')
                before = irq()
                q.writel(PWM + 4, 0x20)
                after_compare = irq()
                status = q.readl(PWM + 4) & 0x30
                q.writel(PWM + 4, 0x10)
                return {'actual': [before, after_compare, status, irq()],
                        'expected': [True, True, 0x10, False]}
            raise ValueError(case)
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
    for case in ('compare-masked', 'rollover-masked', 'compare-asynchronous',
                 'rollover-asynchronous', 'late-enable', 'selective-ack',
                 'soft-reset', 'system-reset', 'migration-active',
                 'migration-pending', 'migration-gated', 'gic-route'):
        result = run(case)
        result['passed'] = result['actual'] == result['expected']
        results[case] = result
        print(f'{"PASS" if result["passed"] else "FAIL"} {case}: {result}')
    passed = all(result['passed'] for result in results.values())
    report = {'audit_completed': True, 'conformance_passed': passed,
              'binary_sha256': hashlib.sha256(state.recovery.QEMU.read_bytes()).hexdigest(),
              'physical_access': False, 'full_hardware_parity': False,
              'tests': results,
              'scope': 'nominal compare/rollover events, device IRQ output and GIC SPI input wiring; CPU acknowledge/EOI, exception handling and physical timing remain unqualified'}
    if args.audit:
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(json.dumps(report, indent=2) + '\n')
    else:
        assert passed, report


if __name__ == '__main__':
    main()
