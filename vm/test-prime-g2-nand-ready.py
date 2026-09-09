#!/usr/bin/env python3
"""Timed ready/busy waits and DMA_SENSE paths using an explicit GPMI clock."""
import importlib
from pathlib import Path
import struct
import subprocess
import tempfile
import time

recovery = importlib.import_module('test-prime-g2-rom-recovery')
irq = importlib.import_module('test-prime-g2-bch-irq')
boot = importlib.import_module('test-prime-g2-nand-rom-boot')


def run(rate):
    with tempfile.TemporaryDirectory(prefix='pg2ready-') as folder:
        directory = Path(folder)
        sock, monitor = directory / 'qtest', directory / 'qmp'
        process = subprocess.Popen([
            str(recovery.QEMU), '-machine', 'hp-prime-g2', '-accel', 'qtest',
            '-display', 'none', '-serial', 'none', '-monitor', 'none',
            '-global', f'prime-g2-gpmi-bch.gpmi-clock-hz={rate}',
            '-global', 'prime-g2-gpmi-bch.use-ccm-clock=off',
            '-qtest', f'unix:{sock},server=on,wait=off', '-qtest-log', '/dev/null',
            '-qmp', f'unix:{monitor},server=on,wait=off'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = qmp = None
        try:
            q, qmp = irq.IRQTest(sock), recovery.QMP(monitor)
            children = qmp.execute('qom-list', {'path': '/machine/unattached'})['return']
            name, = [c['name'] for c in children if c['type'] == 'child<prime-g2-gpmi-bch>']
            path = '/machine/unattached/' + name
            q.command(f'irq_intercept_out {path} sysbus-irq')

            def check_irq():
                ctrl = q.readl(0x01806060)
                expected = bool(ctrl & (1 << 9) and ctrl & (1 << 20))
                assert q.levels.get(0, False) == expected, (hex(ctrl), q.events)

            q.writel(0x01806010, 0xffff0001)  # COMPARE is data, not an IRQ trigger
            assert q.readl(0x01806010) == 0xffff0001
            # Exercise only this VM's synthetic NAND. Completion status must
            # not fabricate an ATA/device interrupt on the NAND-only board.
            q.writel(0x01806100, 0x80)
            q.writel(0x01806104, 512)
            q.writel(0x01806108, 0x5a)
            q.writel(0x01806100, 0x10)
            q.writel(0x01806100, 0x60)
            q.writel(0x01806104, 512)
            q.writel(0x01806100, 0xd0)
            check_irq()
            assert not [event for event in q.events if event[0] == 0]

            def ready(level):
                q.command(f'set_irq_in {path} nand-ready 0 {int(level)}')
                assert bool(q.readl(0x018060b0) & (1 << 24)) == level

            def descriptor(address, words):
                data = struct.pack('<' + 'I' * len(words), *words)
                q.command(f'write 0x{address:x} {len(data)} 0x{data.hex()}')

            # ROM-style WAIT, SENSE, normal terminal, alternate error terminal.
            descriptor(0x80001000, [0x80001020, 0x10a4, 0, 0x03800000])
            descriptor(0x80001020, [0x80001040, 7, 0x80001060])
            descriptor(0x80001040, [0, 0x48, 0])
            descriptor(0x80001060, [0, 0x48, 1])

            def start(ticks):
                q.writel(0x01806068, 1 << 9)
                q.writel(0x01806080, ticks << 16)
                q.writel(0x01804110, 0x80001000)
                q.writel(0x01804140, 1)

            def pending():
                assert q.readl(0x01804100) == 0x80001000
                assert q.readl(0x01804140) == 0x10000
                assert not q.readl(0x01806060) & (1 << 9)
                check_irq()

            def terminal(failed):
                current = q.readl(0x01804100)
                assert current == (0x80001060 if failed else 0x80001040), (
                    hex(current), hex(q.readl(0x01804110)), hex(q.readl(0x01804140)),
                    hex(q.readl(0x01806060)), hex(q.readl(0x01806080)))
                assert q.readl(0x01804130) == int(failed)
                assert q.readl(0x01804140) == 0
                assert bool(q.readl(0x01806060) & (1 << 9)) == failed
                assert bool(q.readl(0x018060b0) & (1 << 16)) == failed
                assert bool(q.readl(0x018060b0) & (1 << 8)) == failed
                check_irq()

            ready(True)
            start(1)
            terminal(False)
            ready(False)
            start(2)
            pending()
            if rate:
                ns = (2 * 4096 * 1000000000 + rate - 1) // rate
                q.command(f'clock_step {ns - 1}')
                pending()
                q.command('clock_step 1')
                terminal(True)
                assert not [event for event in q.events if event[0] == 0]
                q.writel(0x01806064, 1 << 20)  # enable an already pending timeout
                check_irq()
                q.writel(0x01806068, 1 << 20)
                check_irq()
                q.writel(0x0180606c, 1 << 20)
                check_irq()
                q.writel(0x01806068, 1 << 9)  # acknowledge, not a status read
                check_irq()
                q.writel(0x01806064, 1 << 9)
                check_irq()
                q.writel(0x01806060, 1 << 20)  # direct write also acknowledges
                check_irq()
                # STAT is read-only, including otherwise unused alias offsets.
                saved_stat = q.readl(0x018060b0)
                for offset in (0xb0, 0xb4, 0xb8, 0xbc):
                    q.writel(0x01806000 + offset, 0xffffffff)
                    assert q.readl(0x018060b0) == saved_stat
                for ticks in (0, 65535):
                    start(ticks)
                    ns = (ticks * 4096 * 1000000000 + rate - 1) // rate
                    if ns:
                        q.command(f'clock_step {ns - 1}')
                        pending()
                    q.command('clock_step 1')
                    terminal(True)
                # A later successful wait must replace the failed sense result.
                ready(True)
                start(2)
                terminal(False)
                ready(False)
                start(3)
                q.command(f'clock_step {4096 * 1000000000 // rate}')
                pending()
                ready(True)
                terminal(False)
                q.command(f'clock_step {10 * 4096 * 1000000000 // rate}')
                terminal(False)  # cancelled timer cannot later take error path
            else:
                q.command('clock_step 1000000000')
                pending()  # no invented clock or timeout when unconnected
                ready(True)
                terminal(False)
            ready(False)
            start(2)
            pending()
            qmp.execute('system_reset')
            deadline = time.monotonic() + 2
            while q.readl(0x01804140) and time.monotonic() < deadline:
                time.sleep(.01)
            assert q.readl(0x01804140) == 0
            q.command('clock_step 1000000000')
            assert q.readl(0x01804100) == 0, 'cancelled reset wait resumed DMA'
            check_irq()
            timing = 'zero/max/exact timeout boundaries' if rate else 'unconnected clock remains pending'
            print(f'PASS NAND ready wait at {rate} Hz: readiness, {timing}, '
                  'SENSE terminal, cancellation and reset', flush=True)
        finally:
            if qmp:
                qmp.close()
            if q:
                q.close()
            boot.stop(process)


if __name__ == '__main__':
    for rate in (99000000, 198000000, 0):
        run(rate)
