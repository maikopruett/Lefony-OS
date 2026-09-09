#!/usr/bin/env python3
"""Captured ROM DMA must not transfer while its GPMI/BCH clock is gated."""
import importlib
import json
from pathlib import Path
import tempfile

migration = importlib.import_module('test-prime-g2-nand-migration')
ROOT = Path(__file__).resolve().parents[1]


def run(case):
    capture = json.loads((ROOT / 'hardware/prime_g2/reference/rom-dma-buffers-20260907.json').read_text())
    clocks = json.loads((ROOT / 'hardware/prime_g2/reference/rom-clock-nand-status-20260907.json').read_text())
    candidate, = migration.analyze(capture)['candidates']
    head = int(candidate['start_descriptor'], 16)
    payload, aux = int(candidate['payload_address'], 16), int(candidate['auxiliary_address'], 16)
    with tempfile.TemporaryDirectory(prefix='pg2gate-') as folder:
        directory = Path(folder)
        vm = migration.VM(directory, 'src', migration.physical.overlay(directory / 'nand.overlay', {}), timed_clock=0)
        try:
            q = vm.q
            for name in ('ANATOP_PLL_SYS', 'ANATOP_PFD_528', 'CCM_CSCMR1', 'CCM_CSCDR1', 'CCM_CCGR4', 'CCM_CCGR6'):
                item = clocks['clock_registers'][name]
                q.writel(int(item['address'], 16), int(item['value'], 16))
            for name, item in capture['dma_registers'].items():
                if name.startswith('OCRAM_'):
                    q.writel(int(item['address'], 16), int(item['value'], 16))
            for name in ('BCH_FLASH0LAYOUT0', 'BCH_FLASH0LAYOUT1', 'BCH_MODE'):
                item = capture['nand_registers'][name]
                q.writel(int(item['address'], 16), int(item['value'], 16))
            q.command(f'memset 0x{payload:x} 2048 0xa5')
            q.command(f'memset 0x{aux:x} 64 0x5a')
            q.writel(0x01808000, 0x100)
            q.writel(0x01804010, 0x10000)
            if case == 'preconfigured':
                # Launch READ with one PIO word and previously configured
                # ECC/buffer registers; six PIO words are not mandatory.
                q.writel(0x01806100, 0)
                q.writel(0x01806104, candidate['row_3byte'])
                for address, value in ((0x01806020, 0x11ff), (0x01806030, 2071),
                                       (0x01806040, payload), (0x01806050, aux)):
                    q.writel(address, value)
                q.writel(0x00901ed0, 0x1094)
                head = 0x00901ecc
            gates = {'gpmi': (0x020c4080, 3 << 8), 'bch': (0x020c4080, 3 << 6),
                     'gpmi-io': (0x020c4078, 3 << 28),
                     'gpmi-local': (0x01806000, 1 << 30),
                     'bch-local': (0x01808000, 1 << 30),
                     'pll-disabled': (int(clocks['clock_registers']['ANATOP_PLL_SYS']['address'], 16), 1 << 13),
                     'pfd-gated': (int(clocks['clock_registers']['ANATOP_PFD_528']['address'], 16), 1 << 23),
                     'bch-io': (0x020c4078, 3 << 26), 'both': (0x020c4080, (3 << 6) | (3 << 8)),
                     'reset': (0x020c4080, 3 << 6), 'migrate': (0x020c4080, 3 << 6),
                     'bch-then-gpmi': (0x020c4080, 3 << 6), 'preconfigured': (0x020c4080, 3 << 6)}
            address, mask = gates[case]
            original = q.readl(address)
            q.writel(address, original | mask if case in ('pfd-gated', 'gpmi-local', 'bch-local') else original & ~mask)
            expected_stop = head if case in ('gpmi', 'gpmi-io', 'gpmi-local', 'pll-disabled', 'pfd-gated', 'both') else 0x00901ecc
            q.writel(0x01804110, head)
            q.writel(0x01804140, 1)

            def untouched():
                assert vm.read(payload, 2048) == bytes([0xa5]) * 2048
                assert vm.read(aux, 64) == bytes([0x5a]) * 64
                assert not q.levels.get(1, False) and not q.levels.get(2, False)

            def pending(stop):
                assert q.readl(0x01804100) == stop, hex(q.readl(0x01804100))
                assert q.readl(0x01804140) == 0x10000
                untouched()

            pending(expected_stop)
            vm.qmp.execute('cont')
            q.command('clock_step 1000000000')
            pending(expected_stop)
            if case == 'both':
                q.writel(address, original & ~(3 << 6))
                pending(0x00901ecc)
            if case == 'bch-then-gpmi':
                q.writel(address, original & ~((3 << 6) | (3 << 8)))
                q.writel(address, original & ~(3 << 8))
                pending(0x00901ecc)
                q.command('clock_step 1000000000')
                pending(0x00901ecc)
            if case == 'reset':
                vm.qmp.execute('system_reset')
                q.readl(0x01804140)
                untouched()
                assert q.readl(0x01804140) == 0
                q.writel(address, original)
                untouched()
                print('PASS reset cancels gated DMA without writing destination RAM', flush=True)
                return
            if case == 'migrate':
                destination = migration.VM(directory, 'dst', migration.physical.overlay(directory / 'dst.overlay', {}),
                                           incoming=True, timed_clock=0)
                try:
                    vm.qmp.execute('stop')
                    destination.q.command('clock_step 1000000000')
                    uri = 'unix:' + str(directory / 'migration.sock')
                    destination.qmp.execute('migrate-incoming', {'uri': uri})
                    vm.qmp.execute('migrate', {'uri': uri})
                    migration.wait_migration(vm)
                    migration.wait_migration(destination)
                except BaseException:
                    destination.close()
                    raise
                vm.close()
                vm, q = destination, destination.q
                pending(expected_stop)
            q.writel(address, original)
            assert q.readl(0x01804100) == 0x00901f08
            assert q.readl(0x01804140) == 0
            assert vm.read(aux + 12, 4) == bytes(4)
            expected_payload = migration.physical.read_record(candidate['row_3byte'])
            fcb, _ = migration.decode_fcb(migration.physical.read_record(0))
            decoded = migration.fcb_layout(fcb).decode(bytes(expected_payload))
            assert vm.read(payload, 2048) == decoded.payload
            assert q.levels.get(1) and q.levels.get(2)
            print(f'PASS gated DMA: {case} waits with unchanged RAM, then completes after ungating', flush=True)
        finally:
            vm.close()


if __name__ == '__main__':
    for case in ('gpmi', 'gpmi-io', 'gpmi-local', 'bch-local', 'pll-disabled', 'pfd-gated', 'bch', 'bch-io',
                 'both', 'bch-then-gpmi', 'preconfigured', 'reset', 'migrate'):
        run(case)
