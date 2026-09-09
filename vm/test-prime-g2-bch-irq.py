#!/usr/bin/env python3
"""Observe the actual BCH sysbus IRQ wire, not a diagnostic status shortcut."""
import importlib
import struct
import subprocess
import tempfile
import time
from pathlib import Path

recovery = importlib.import_module('test-prime-g2-rom-recovery')


class IRQTest(recovery.QTest):
    def __init__(self, path):
        super().__init__(path)
        self.levels = {}
        self.events = []

    def command(self, command):
        self.socket.sendall((command + '\n').encode())
        while True:
            response = self.stream.readline().decode().strip()
            if response.startswith('IRQ '):
                _, state, index = response.split()
                self.levels[int(index)] = state == 'raise'
                self.events.append((int(index), state))
            elif response.startswith('OK'):
                return response
            else:
                raise RuntimeError((command, response))


def main():
    with tempfile.TemporaryDirectory(prefix='pg2irq-') as folder:
        directory = Path(folder)
        sock, qmp_sock = directory / 'test.sock', directory / 'qmp.sock'
        process = subprocess.Popen([
            str(recovery.QEMU), '-machine', 'hp-prime-g2', '-S',
            '-display', 'none', '-serial', 'none', '-monitor', 'none',
            '-global', 'prime-g2-gpmi-bch.physical-pages=on',
            '-qtest', f'unix:{sock},server=on,wait=off', '-qtest-log', '/dev/null',
            '-qmp', f'unix:{qmp_sock},server=on,wait=off'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = qmp = None
        try:
            q = IRQTest(sock)
            qmp = recovery.QMP(qmp_sock)
            children = qmp.execute('qom-list', {'path': '/machine/unattached'})['return']
            names = [child['name'] for child in children
                     if child['type'] == 'child<prime-g2-gpmi-bch>']
            assert len(names) == 1, children
            q.command(f'irq_intercept_out /machine/unattached/{names[0]} sysbus-irq')

            def write(address, data):
                q.command(f'write 0x{address:x} {len(data)} 0x{data.hex()}')

            def transfer(encode=False):
                q.writel(0x01806100, 0x80 if encode else 0)
                q.writel(0x01806104, 16)
                words = [0, 0x6048, 0, 0 if encode else 1 << 24,
                         0, 0x1000, 2112, 0x80003000, 0x80004000]
                write(0x80001000, struct.pack('<9I', *words))
                q.writel(0x01804110, 0x80001000)
                q.writel(0x01804140, 1)

            def check(pending, enabled, level):
                ctrl = q.readl(0x01808000)  # flush preceding IRQ notifications
                assert bool(ctrl & 1) == pending, hex(ctrl)
                assert bool(ctrl & 256) == enabled, hex(ctrl)
                assert q.levels.get(1, False) == level, q.events

            transfer()
            check(True, False, False)
            assert not [event for event in q.events if event[0] == 1], q.events
            q.writel(0x01808004, 256)  # enable a pending interrupt
            check(True, True, True)
            q.writel(0x01808008, 256)  # mask without discarding completion
            check(True, False, False)
            q.writel(0x0180800c, 256)  # toggle enable back on
            check(True, True, True)
            result_before = q.readl(0x01808010)
            for offset in (0x10, 0x14, 0x18, 0x1c):
                q.writel(0x01808000 + offset, 0xffffffff)
                assert q.readl(0x01808010) == result_before
                check(True, True, True)
            q.writel(0x01808008, 1)  # the driver's completion acknowledgement
            check(False, True, False)
            transfer(True)
            check(True, True, True)
            q.writel(0x01808000, 256)  # direct CTRL write also updates the wire
            check(False, True, False)
            transfer()
            check(True, True, True)
            qmp.execute('system_reset')
            deadline = time.monotonic() + 2
            while q.readl(0x01808000) and time.monotonic() < deadline:
                time.sleep(.01)
            check(False, False, False)
            for offset in (0x170, 0x174, 0x178, 0x17c):
                q.writel(0x01808000 + offset, 0xffffffff)
                assert q.readl(0x01808170) == 0
            for offset in (0x160, 0x164, 0x168, 0x16c):
                q.writel(0x01808000 + offset, 0xffffffff)
                assert q.readl(0x01808160) == 0x01000000
            q.writel(0x01808020, 0xffffffff)
            assert q.readl(0x01808020) == 255
            q.writel(0x01808028, 1)
            assert q.readl(0x01808020) == 254
            q.writel(0x0180802c, 0xffff0003)
            assert q.readl(0x01808020) == 253
            print('PASS BCH IRQ masking, pending enable, decode/encode completion, '
                  'CTRL SET/CLR/TOG/direct writes, read-only results and reset', flush=True)
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
