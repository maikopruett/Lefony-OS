#!/usr/bin/env python3
"""Observe APBH channel-zero completion IRQ masking and acknowledgement."""
import importlib
from pathlib import Path
import struct
import subprocess
import tempfile
import time

irq = importlib.import_module('test-prime-g2-bch-irq')
recovery = irq.recovery


def main():
    with tempfile.TemporaryDirectory(prefix='pg2apbh-') as folder:
        directory = Path(folder)
        sock, monitor = directory / 'qtest', directory / 'qmp'
        process = subprocess.Popen([
            str(recovery.QEMU), '-machine', 'hp-prime-g2', '-S',
            '-display', 'none', '-serial', 'none', '-monitor', 'none',
            '-qtest', f'unix:{sock},server=on,wait=off', '-qtest-log', '/dev/null',
            '-qmp', f'unix:{monitor},server=on,wait=off'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = qmp = None
        try:
            q, qmp = irq.IRQTest(sock), recovery.QMP(monitor)
            children = qmp.execute('qom-list', {'path': '/machine/unattached'})['return']
            name, = [c['name'] for c in children if c['type'] == 'child<prime-g2-gpmi-bch>']
            q.command(f'irq_intercept_out /machine/unattached/{name} sysbus-irq')

            def transfer(request=True):
                data = struct.pack('<3I', 0, 0x48 if request else 0x40, 0)
                q.command(f'write 0x80001000 12 0x{data.hex()}')
                q.writel(0x01804110, 0x80001000)
                q.writel(0x01804140, 1)
                assert q.readl(0x01804140) == 0

            def check(pending, enabled, level):
                ctrl = q.readl(0x01804010)
                assert bool(ctrl & 1) == pending, hex(ctrl)
                assert bool(ctrl & 0x10000) == enabled, hex(ctrl)
                assert q.levels.get(2, False) == level, q.events

            transfer()
            check(True, False, False)
            assert not [e for e in q.events if e[0] == 2], 'masked completion pulsed IRQ'
            q.writel(0x01804014, 0x10000)
            check(True, True, True)
            events = list(q.events)
            transfer(False)  # starting another chain cannot acknowledge the old IRQ
            check(True, True, True)
            assert q.events == events, 'new transfer glitched pending IRQ'
            q.writel(0x01804018, 0x10000)
            check(True, False, False)
            q.writel(0x0180401c, 0x10000)
            check(True, True, True)
            q.writel(0x01804018, 1)
            check(False, True, False)
            transfer(False)
            check(False, True, False)
            transfer()
            check(True, True, True)
            q.writel(0x01804010, 0x10000)
            check(False, True, False)
            # Other channels' enable/pending fields do not drive channel zero.
            q.writel(0x01804010, 0x20002)
            check(False, False, False)
            q.writel(0x01804010, 0x10001)
            check(True, True, True)
            qmp.execute('system_reset')
            deadline = time.monotonic() + 2
            while q.readl(0x01804010) and time.monotonic() < deadline:
                time.sleep(.01)
            check(False, False, False)
            print('PASS APBH actual IRQ: masked completion, pending enable, sticky status, '
                  'SET/CLR/TOG/direct acknowledgement, channel isolation and reset', flush=True)
        finally:
            if qmp:
                qmp.close()
            if q:
                q.close()
            process.terminate()
            try:
                _, errors = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                _, errors = process.communicate(timeout=5)
            if process.returncode not in (0, -15):
                raise RuntimeError(errors.decode(errors='replace'))


if __name__ == '__main__':
    main()
