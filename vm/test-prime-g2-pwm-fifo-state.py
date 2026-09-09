#!/usr/bin/env python3
"""Nominal PWM FIFO consumption/repeat/reset/migration; no physical access."""
import importlib
from pathlib import Path
import tempfile

state = importlib.import_module('test-prime-g2-gpt-state')
PWM = 0x020f8000
CCGR6 = 0x020c4080


def run(repeat, scenario):
    with tempfile.TemporaryDirectory(prefix='pg2pwmqueue-') as folder:
        folder = Path(folder)
        vms = []
        try:
            vm = state.VM(folder, 'source', None)
            vms.append(vm)
            q = vm.q
            vm.qmp.execute('cont')
            q.writel(0x020c401c, (q.readl(0x020c401c) & ~0x7f) | 0x40)
            gates = q.readl(CCGR6) | (3 << 30)
            q.writel(CCGR6, gates)
            q.writel(PWM, 8)
            q.writel(PWM + 16, 23998)  # 1 ms at 24 MHz
            for sample in (100, 200, 300, 400, 500):
                q.writel(PWM + 12, sample)
            assert q.readl(PWM + 4) & 0x47 == 0x44
            q.writel(PWM + 4, 0x40)
            assert q.readl(PWM + 4) & 0x47 == 4
            cr = (2 << 16) | (repeat.bit_length() - 1) << 1 | 1
            q.writel(PWM, cr)
            q.command('clock_step 1000000')

            def check(sample, count):
                assert q.readl(PWM + 12) == sample, (repeat, scenario, 'sample', sample)
                assert q.readl(PWM + 4) & 7 == count, (repeat, scenario, 'count', count)

            check(100, 3)
            if scenario == 'refill':
                q.writel(PWM + 12, 600)  # reuse the vacated ring-buffer slot
                check(100, 4)
                assert not q.readl(PWM + 4) & 0x40
                for sample, remaining in ((200, 3), (300, 2), (400, 1), (600, 0)):
                    q.command(f'clock_step {repeat * 1000000}')
                    check(sample, remaining)
                print(f'PASS PWM FIFO ring refill repeat={repeat}')
                return
            if scenario == 'migration':
                q.command('clock_step 500000')
                check(100, 3)
                vm.qmp.execute('stop')
                destination = state.VM(folder, 'destination', None, incoming=True)
                vms.append(destination)
                destination.q.command('clock_step 1500000')
                uri = 'unix:' + str(folder / 'migration.sock')
                destination.qmp.execute('migrate-incoming', {'uri': uri})
                vm.qmp.execute('migrate', {'uri': uri})
                state.wait_migration(vm)
                state.wait_migration(destination)
                vm, q = destination, destination.q
                check(100, 3)
                vm.qmp.execute('cont')
                q.command(f'clock_step {repeat * 1000000 - 500000}')
                check(200, 2)
            elif scenario == 'gate':
                q.writel(CCGR6, gates & ~(3 << 30))
                q.command('clock_step 10000000')
                check(100, 3)
                q.writel(CCGR6, gates)
                q.command(f'clock_step {repeat * 1000000}')
                check(200, 2)
            elif scenario in ('reset', 'system-reset'):
                if scenario == 'reset':
                    q.writel(PWM, 8)
                else:
                    vm.qmp.execute('system_reset')
                    q.writel(0x020c401c, (q.readl(0x020c401c) & ~0x7f) | 0x40)
                    q.writel(CCGR6, gates)
                    q.writel(PWM + 16, 23998)
                check(0, 0)
                assert not q.readl(PWM + 4) & 0x78
                q.writel(PWM, cr)
                q.command('clock_step 10000000')
                check(0, 0)
                print(f'PASS PWM FIFO {scenario} repeat={repeat}')
                return
            else:
                if repeat > 1:
                    q.command(f'clock_step {(repeat - 1) * 1000000}')
                    check(100, 3)
                q.command('clock_step 1000000')
                check(200, 2)
            q.command(f'clock_step {repeat * 1000000}')
            check(300, 1)
            q.command(f'clock_step {repeat * 1000000}')
            check(400, 0)  # overflowed 500 must never replace a queued value
            q.command('clock_step 1000000000')
            check(400, 0)
            print(f'PASS PWM FIFO {scenario} repeat={repeat}, order and final sample retained')
        finally:
            for vm in reversed(vms):
                vm.close()


if __name__ == '__main__':
    for repeat in (1, 2, 4, 8):
        for scenario in ('consume', 'gate', 'reset', 'system-reset', 'migration', 'refill'):
            run(repeat, scenario)
