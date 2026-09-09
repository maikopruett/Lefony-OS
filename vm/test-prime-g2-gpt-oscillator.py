#!/usr/bin/env python3
"""Check the physical GPT selector-5 clock without a device-tree substitute."""
import importlib
from pathlib import Path
import subprocess
import tempfile

recovery = importlib.import_module('test-prime-g2-rom-recovery')
IRQTest = importlib.import_module('test-prime-g2-bch-irq').IRQTest


def test_timer(index):
    with tempfile.TemporaryDirectory(prefix='pg2gpt-') as folder:
        sock = Path(folder) / 'qtest'
        process = subprocess.Popen([
            str(recovery.QEMU), '-machine', 'hp-prime-g2', '-accel', 'qtest',
            '-display', 'none', '-serial', 'none', '-monitor', 'none',
            '-qtest', f'unix:{sock},server=on,wait=off', '-qtest-log', '/dev/null'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = None
        try:
            q = IRQTest(sock)
            for base in [(0x02098000, 0x020e8000)[index]]:
                q.command(f'irq_intercept_out /machine/soc/gpt{index} sysbus-irq')
                for prescaler in (0, 1, 7):
                    q.writel(base, 1 << 15)  # soft reset
                    q.writel(base, 0)
                    q.writel(base + 4, prescaler)
                    q.writel(base, (5 << 6) | (1 << 9) | 3)
                    first = q.readl(base + 0x24)
                    q.command('clock_step 1000000')
                    actual = (q.readl(base + 0x24) - first) & 0xffffffff
                    expected = 3000 // (prescaler + 1)
                    assert abs(actual - expected) <= 1, (hex(base), prescaler, actual, expected)
                    q.writel(base, 0)
                    stopped = q.readl(base + 0x24)
                    q.command('clock_step 1000000')
                    assert q.readl(base + 0x24) == stopped
                # Output compare status must arrive at its tick, even masked.
                q.writel(base, 1 << 15)
                q.writel(base, 0)
                q.writel(base + 4, 0)
                q.writel(base + 0x10, 3000)
                q.writel(base + 0x14, 3000)
                q.writel(base + 0x18, 3000)
                q.writel(base + 0x0c, 0)
                q.writel(base, (5 << 6) | (1 << 9) | 3)
                q.command('clock_step 999000')
                assert not q.readl(base + 8) & 1
                q.command('clock_step 2000')
                assert q.readl(base + 8) & 7 == 7
                assert not q.levels.get(0, False)
                q.writel(base + 0x0c, 1)
                assert q.readl(base + 8) & 1
                assert q.levels.get(0, False), 'enabling pending compare must assert IRQ'
                q.writel(base + 0x0c, 0)
                assert q.readl(base + 8) & 1
                assert not q.levels.get(0, False), 'mask must lower IRQ, retaining status'
                q.writel(base + 0x0c, 1)
                q.writel(base + 8, 1)  # OF1 write-one-to-clear
                assert not q.readl(base + 8) & 1
                assert not q.levels.get(0, False), 'W1C must lower IRQ'
                assert q.readl(base + 8) & 6 == 6, 'OF1 ack must preserve OF2/OF3'
                q.writel(base, 0)
                q.writel(base, 1 << 15)
                q.writel(base, 0)
                q.writel(base + 4, 0)
                q.writel(base + 0x10, 3000)
                q.writel(base + 0x0c, 0)
                q.writel(base, (5 << 6) | 3)  # restart mode, masked
                q.command('clock_step 1001000')
                assert q.readl(base + 8) & 1
                assert abs(q.readl(base + 0x24) - 3) <= 1
                q.writel(base, 0)
            print(f'PASS GPT{index + 1} selector 5: 3 MHz, prescalers 1/2/8, stopped counters, masked compare/restart, IRQ masking and W1C')
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
    for timer in range(2):
        test_timer(timer)
