#!/usr/bin/env python3
"""PWM7 live CCM clock contract using deterministic virtual time.

No physical access. These tests intentionally reject the fixed-66-MHz model.
"""
import importlib
from pathlib import Path
import subprocess
import tempfile

recovery = importlib.import_module('test-prime-g2-rom-recovery')
PWM = 0x020f8000
CSCMR1 = 0x020c401c
CCGR6 = 0x020c4080


def run(case):
    with tempfile.TemporaryDirectory(prefix='pg2pwmclk-') as folder:
        sock = Path(folder) / 'qt'
        process = subprocess.Popen([
            str(recovery.QEMU), '-machine', 'hp-prime-g2', '-accel', 'qtest',
            '-display', 'none', '-serial', 'none', '-monitor', 'none',
            '-qtest', f'unix:{sock},server=on,wait=off', '-qtest-log', '/dev/null'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = None
        try:
            q = recovery.QTest(sock)
            q.writel(CSCMR1, (q.readl(CSCMR1) & ~0x7f) | 0x40)  # OSC / 1
            gates = q.readl(CCGR6) & ~(3 << 30)
            q.writel(CCGR6, gates | (3 << 30))
            q.writel(PWM, 8)
            q.writel(PWM + 0x10, 0xfffe)
            q.writel(PWM, (2 << 16) | 1)

            def step(ns):
                q.command(f'clock_step {ns}')

            def count(expected):
                actual = q.readl(PWM + 0x14)
                assert actual == expected, (case, actual, expected)

            if case == 'osc':
                step(1000000)
                count(24000)
            elif case == 'divider':
                step(500000)
                q.writel(CSCMR1, (q.readl(CSCMR1) & ~0x3f) | 1)
                step(500000)
                count(18000)  # first 0.5 ms at 24 MHz, then at 12 MHz
            elif case in ('gate-off', 'gate-run', 'gate-reserved'):
                step(500000)
                mode = {'gate-off': 0, 'gate-run': 1, 'gate-reserved': 2}[case]
                q.writel(CCGR6, gates | (mode << 30))
                step(1000000)
                count(36000 if mode == 1 else 12000)
                q.writel(CCGR6, gates | (3 << 30))
                step(500000)
                count(48000 if mode == 1 else 24000)
            elif case == 'fractional-gate':
                step(1)  # 0.024 input cycles; must not be discarded
                q.writel(CCGR6, gates)
                step(1000000)
                count(0)
                q.writel(CCGR6, gates | (3 << 30))
                step(41)
                count(1)  # 42 ns total at 24 MHz
            elif case == 'unrelated-gate':
                step(500000)
                q.writel(CCGR6, q.readl(CCGR6) ^ (3 << 26))  # PWM5, not PWM7
                step(500000)
                count(24000)
            elif case in ('ipg', 'per-ipg'):
                # OSC -> periph_clk2 / 1 -> AHB / 3 -> IPG / 2 = 4 MHz.
                q.writel(0x020c4018, (q.readl(0x020c4018) & ~(3 << 12)) | (1 << 12))
                mask = (7 << 27) | (7 << 10) | (3 << 8)
                q.writel(0x020c4014, (q.readl(0x020c4014) & ~mask) |
                         (1 << 25) | (2 << 10) | (1 << 8))
                q.writel(CSCMR1, (q.readl(CSCMR1) & ~0x7f) | 3)  # perclk = IPG / 4
                q.writel(PWM, ((1 if case == 'ipg' else 2) << 16) | 1)
                step(1000000)
                count(4000 if case == 'ipg' else 1000)
            print(f'PASS PWM7 live clock {case}')
        finally:
            if q:
                q.close()
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)


def run_migration(gated):
    state = importlib.import_module('test-prime-g2-gpt-state')
    with tempfile.TemporaryDirectory(prefix='pg2pwm-mig-') as folder:
        folder = Path(folder)
        vms = []
        try:
            source = state.VM(folder, 'source', None)
            vms.append(source)
            source.qmp.execute('cont')
            q = source.q
            q.writel(CSCMR1, (q.readl(CSCMR1) & ~0x7f) | 0x40)
            gate_bits = q.readl(CCGR6) & ~(3 << 30)
            q.writel(CCGR6, gate_bits | (3 << 30))
            q.writel(PWM + 0x10, 0xfffe)
            q.writel(PWM, (2 << 16) | 1)
            q.command('clock_step 500001')
            if gated:
                q.writel(CCGR6, gate_bits)
            assert q.readl(PWM + 0x14) == 12000
            source.qmp.execute('stop')
            destination = state.VM(folder, 'destination', None, incoming=True)
            vms.append(destination)
            destination.q.command('clock_step 500001')
            uri = 'unix:' + str(folder / 'migration.sock')
            destination.qmp.execute('migrate-incoming', {'uri': uri})
            source.qmp.execute('migrate', {'uri': uri})
            state.wait_migration(source)
            state.wait_migration(destination)
            q = destination.q
            assert q.readl(PWM + 0x14) == 12000
            destination.qmp.execute('cont')
            if gated:
                q.command('clock_step 1000000')
                assert q.readl(PWM + 0x14) == 12000
                q.writel(CCGR6, gate_bits | (3 << 30))
            q.command('clock_step 41')
            assert q.readl(PWM + 0x14) == 12001, 'fractional PWM phase lost in migration'
            print(f'PASS PWM7 migration {"gated" if gated else "active"}, fractional phase retained')
        finally:
            for vm in reversed(vms):
                vm.close()


if __name__ == '__main__':
    failures = []
    for case in ('osc', 'divider', 'gate-off', 'gate-run', 'gate-reserved',
                 'fractional-gate', 'unrelated-gate', 'ipg', 'per-ipg'):
        try:
            run(case)
        except AssertionError as error:
            failures.append((case, str(error)))
    assert not failures, failures
    for gated in (False, True):
        run_migration(gated)
