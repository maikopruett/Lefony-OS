#!/usr/bin/env python3
"""PWM7 counter contract; not a claim of FIFO, waveform or clock-tree parity."""
import importlib
from pathlib import Path
import subprocess
import tempfile

recovery = importlib.import_module('test-prime-g2-rom-recovery')
BASE = 0x020f8000


def run(case):
    with tempfile.TemporaryDirectory(prefix='pg2pwm-') as folder:
        sock = Path(folder) / 'qt'
        process = subprocess.Popen([
            str(recovery.QEMU), '-machine', 'hp-prime-g2', '-accel', 'qtest',
            '-display', 'none', '-serial', 'none', '-monitor', 'none',
            '-qtest', f'unix:{sock},server=on,wait=off', '-qtest-log', '/dev/null'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = None
        try:
            q = recovery.QTest(sock)
            q.writel(BASE, 8)
            q.writel(BASE + 0x10, 0xffff)
            if case == 'readonly':
                q.writel(BASE + 0x14, 0x1234)
                assert q.readl(BASE + 0x14) == 0, 'PWMCNR accepted a write'
            elif case == 'clock-off':
                q.writel(BASE, 1)
                q.command('clock_step 1000000')
                assert q.readl(BASE + 0x14) == 0, 'CLKSRC=0 still counts'
            else:
                divisor = {'prescaler': 8, 'prescaler-max': 4096}.get(case, 1)
                q.writel(BASE, (3 << 16) | ((divisor - 1) << 4) | 1)
                duration = 2000000000 if case == 'period-max' else 1000000000
                q.command(f'clock_step {duration}')
                expected = (32768 * duration // 1000000000 // divisor) % 65536
                assert q.readl(BASE + 0x14) == expected, (case, q.readl(BASE + 0x14), expected)
                if case == 'clock-switch':
                    q.writel(BASE, 1)  # disconnect the source, preserving phase
                    q.command('clock_step 1000000000')
                    assert q.readl(BASE + 0x14) == expected
                    q.writel(BASE, (3 << 16) | 1)
                    q.command('clock_step 500000000')
                    assert q.readl(BASE + 0x14) == expected + 16384
            print(f'PASS PWM7 {case}')
        finally:
            if q:
                q.close()
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)


if __name__ == '__main__':
    failures = []
    for case in ('readonly', 'clock-off', '32k', 'prescaler', 'prescaler-max', 'period-max', 'clock-switch'):
        try:
            run(case)
        except AssertionError as error:
            failures.append((case, str(error)))
    assert not failures, failures
