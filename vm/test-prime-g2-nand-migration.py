#!/usr/bin/env python3
"""Cross-process NAND/DMA checkpoint test; no physical device is accessed."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

physical = importlib.import_module('test-prime-g2-physical-rom-boot')
recovery = importlib.import_module('test-prime-g2-rom-recovery')
irq = importlib.import_module('test-prime-g2-bch-irq')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_prime_g2_rom_dma import analyze
from prime_nand_image import decode_fcb, fcb_layout


class VM:
    def __init__(self, directory, name, overlay, incoming=False, timed_clock=None):
        self.q = self.qmp = None
        sock, monitor = directory / (name + '.qt'), directory / (name + '.qm')
        command = [str(recovery.QEMU), '-machine', 'hp-prime-g2', '-S',
                   '-display', 'none', '-serial', 'none', '-monitor', 'none',
                   '-global', 'prime-g2-gpmi-bch.physical-pages=on',
                   '-global', f'prime-g2-gpmi-bch.stock-nand={physical.PHYSICAL}',
                   '-global', f'prime-g2-gpmi-bch.stock-overlay={overlay}',
                   '-qtest', f'unix:{sock},server=on,wait=off',
                   '-qtest-log', '/dev/null',
                   '-qmp', f'unix:{monitor},server=on,wait=off']
        if incoming:
            command += ['-incoming', 'defer']
        if timed_clock is not None:
            command += ['-accel', 'qtest', '-global',
                        f'prime-g2-gpmi-bch.gpmi-clock-hz={timed_clock}']
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.q = irq.IRQTest(sock)
            self.qmp = recovery.QMP(monitor)
            children = self.qmp.execute('qom-list', {'path': '/machine/unattached'})['return']
            name, = [c['name'] for c in children if c['type'] == 'child<prime-g2-gpmi-bch>']
            self.nand_path = f'/machine/unattached/{name}'
            self.q.command(f'irq_intercept_out /machine/unattached/{name} sysbus-irq')
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.qmp:
            self.qmp.close()
        if self.q:
            self.q.close()
        physical.boot.stop(self.process)

    def read(self, address, length):
        return bytes.fromhex(self.q.command(f'read 0x{address:x} {length}').split()[1][2:])


def wait_migration(vm):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        state = vm.qmp.execute('query-migrate')['return']
        if state.get('status') == 'completed':
            return
        if state.get('status') in ('failed', 'cancelled'):
            raise AssertionError(state)
        time.sleep(.02)
    raise AssertionError(('migration timed out', state))


def run(parity_errors):
    capture = json.loads((ROOT / 'hardware/prime_g2/reference/rom-dma-buffers-20260907.json').read_text())
    candidate, = analyze(capture)['candidates']
    head = int(candidate['start_descriptor'], 16)
    payload = int(candidate['payload_address'], 16)
    aux = int(candidate['auxiliary_address'], 16)
    row = candidate['row_3byte']
    record = physical.read_record(row)
    if parity_errors:
        fcb, _ = decode_fcb(physical.read_record(0))
        chunk = fcb_layout(fcb).chunks[2]
        start = chunk.start_bit + chunk.message_bytes * 8
        for bit in range(start, start + 16):
            record[bit // 8] ^= 1 << (bit % 8)
    expected_status = bytes([0, 0, 0xfe if parity_errors else 0, 0])
    with tempfile.TemporaryDirectory(prefix='pg2mig-') as folder:
        directory = Path(folder)
        source = destination = None
        try:
            source = VM(directory, 'src', physical.overlay(directory / 'src.overlay', {row: record}))
            q = source.q
            for name, item in capture['dma_registers'].items():
                if name.startswith('OCRAM_'):
                    q.writel(int(item['address'], 16), int(item['value'], 16))
            for name in ('BCH_FLASH0LAYOUT0', 'BCH_FLASH0LAYOUT1'):
                item = capture['nand_registers'][name]
                q.writel(int(item['address'], 16), int(item['value'], 16))
            q.writel(0x01808020, 7)
            q.writel(0x01808004, 0x100)  # enabled completion IRQ remains pending
            q.writel(0x01804014, 0x10000)
            # Independently retain a pending/enabled GPMI timeout. This is
            # a register-state fixture; timed expiry is tested separately.
            q.writel(0x01806064, (1 << 20) | (1 << 9))
            q.writel(0x01804110, head)
            q.writel(0x01804140, 1)
            assert q.readl(0x01804120) == 0x48
            assert q.readl(0x01808000) & 0x101 == 0x101
            assert q.levels.get(1) and q.levels.get(2), q.events
            assert q.levels.get(0), q.events
            assert source.read(aux + 12, 4) == expected_status
            # Save in the middle of consuming the cached raw page, not just
            # at an idle boundary. The destination must resume at byte 37.
            q.writel(0x01806100, 0x00)
            q.writel(0x01806104, row)
            assert bytes(q.readl(0x01806108) for _ in range(37)) == record[:37]
            # A queued semaphore with no descriptor tests PHORE separately
            # from a completed chain, which normally leaves it zero.
            q.writel(0x01804110, 0)
            q.writel(0x01804140, 3)
            addresses = [0x01804100, 0x01804110, 0x01804120, 0x01804130,
                         0x01804140, 0x01804010, 0x01808000, 0x01808010,
                         0x01808020, 0x01808080, 0x01808090, 0x01808170, 0x01806060]
            saved_registers = {a: q.readl(a) for a in addresses}
            saved_ram = source.read(0x00901c08, 1024)
            saved_payload = source.read(payload, 2112)
            saved_aux = source.read(aux, 64)
            destination = VM(directory, 'dst', physical.overlay(directory / 'dst.overlay', {}), True)
            assert destination.q.readl(0x01804120) == 0, 'destination must start independently'
            uri = 'unix:' + str(directory / 'migration.sock')
            destination.qmp.execute('migrate-incoming', {'uri': uri})
            source.qmp.execute('migrate', {'uri': uri})
            wait_migration(source)
            wait_migration(destination)
            assert destination.qmp.execute('query-status')['return']['running'] is False
            for address, expected in saved_registers.items():
                actual = destination.q.readl(address)
                assert actual == expected, (hex(address), hex(actual), hex(expected))
            assert destination.read(0x00901c08, 1024) == saved_ram
            assert destination.read(payload, 2112) == saved_payload
            assert destination.read(aux, 64) == saved_aux
            assert destination.q.levels.get(1) and destination.q.levels.get(2), destination.q.events
            assert destination.q.levels.get(0), destination.q.events
            assert bytes(destination.q.readl(0x01806108) for _ in range(100)) == record[37:137]
            # Restored descriptors must still execute; three terminal reads
            # consume the saved PHORE without resetting any device state.
            for remaining in (2, 1, 0):
                destination.q.writel(0x01808008, 1)
                destination.q.writel(0x01804018, 1)
                assert not destination.q.levels.get(1) and not destination.q.levels.get(2)
                destination.q.writel(0x01804110, head)
                destination.q.writel(0x01804140, 0)
                assert destination.q.readl(0x01804140) == remaining << 16
                assert destination.q.readl(0x01804120) == 0x48
                assert destination.read(payload, 2112) == saved_payload
                assert destination.read(aux, 64) == saved_aux
                assert destination.q.readl(0x01808000) & 0x101 == 0x101
                assert destination.q.levels.get(1) and destination.q.levels.get(2)
                assert destination.q.levels.get(0), 'unrelated DMA must not acknowledge GPMI timeout'
            destination.q.writel(0x01806068, 1 << 9)
            assert not destination.q.levels.get(0)
            label = 'synthetic parity damage' if parity_errors else 'clean page'
            print(f'PASS cross-process NAND migration ({label}): CMD, PHORE, BCH pending state, '
                  'IRQ wire restoration, OCRAM, cached-page cursor and repeat reads', flush=True)
        finally:
            if destination:
                destination.close()
            if source:
                source.close()


if __name__ == '__main__':
    run(False)
    run(True)
