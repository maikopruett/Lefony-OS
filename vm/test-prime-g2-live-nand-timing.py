#!/usr/bin/env python3
"""Drive real CCM registers mid-wait and verify remaining NAND clock cycles."""
import importlib
import json
from pathlib import Path
import struct
import tempfile

migration = importlib.import_module('test-prime-g2-nand-migration')
ROOT = Path(__file__).resolve().parents[1]


def run(case):
    capture = json.loads((ROOT / 'hardware/prime_g2/reference/rom-clock-nand-status-20260907.json').read_text())
    with tempfile.TemporaryDirectory(prefix='pg2liveclk-') as folder:
        directory = Path(folder)
        vm = migration.VM(directory, 'vm', migration.physical.overlay(directory / 'nand.overlay', {}),
                          timed_clock=0)  # no explicit-rate override; use live CCM
        try:
            q = vm.q
            for name in ('ANATOP_PLL_SYS', 'ANATOP_PFD_528', 'CCM_CSCMR1',
                         'CCM_CSCDR1', 'CCM_CCGR4', 'CCM_CCGR6'):
                item = capture['clock_registers'][name]
                q.writel(int(item['address'], 16), int(item['value'], 16))
            for address, words in ((0x80001000, [0x80001020, 0x10a4, 0, 0x03800000]),
                                   (0x80001020, [0x80001040, 7, 0x80001060]),
                                   (0x80001040, [0, 0x48, 0]), (0x80001060, [0, 0x48, 1])):
                data = struct.pack('<' + 'I' * len(words), *words)
                q.command(f'write 0x{address:x} {len(data)} 0x{data.hex()}')
            q.command(f'set_irq_in {vm.nand_path} nand-ready 0 0')
            q.writel(0x01806080, 2 << 16)  # 8192 cycles
            q.writel(0x01806064, 1 << 20)
            vm.qmp.execute('cont')
            q.writel(0x01804110, 0x80001000)
            q.writel(0x01804140, 1)

            def pending():
                assert q.readl(0x01804140) == 0x10000
                assert q.readl(0x01804100) == 0x80001000
                assert not q.readl(0x01806060) & (1 << 9)
                assert not q.levels.get(0, False)

            def completed(failed=True):
                assert q.readl(0x01804140) == 0
                assert q.readl(0x01804100) == (0x80001060 if failed else 0x80001040)
                assert bool(q.readl(0x01806060) & (1 << 9)) == failed
                assert q.levels.get(0, False) == failed

            def checkpoint(now):
                nonlocal vm, q
                destination = migration.VM(directory, 'restored',
                    migration.physical.overlay(directory / 'restored.overlay', {}),
                    incoming=True, timed_clock=0)
                try:
                    vm.qmp.execute('stop')
                    assert int(destination.q.command(f'clock_step {now}').split()[1]) == now
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
                pending()
                vm.qmp.execute('cont')

            pending()
            q.command('clock_step 10000')  # exactly 1980 cycles at 198 MHz
            pending()
            remaining, rate = 8192 - 1980, 198000000
            if case == 'reset-wait':
                q.writel(0x01806004, 1 << 31)
                assert q.readl(0x01806000) == 0xc0000000
                q.command('clock_step 1000000000')
                pending()
                q.writel(0x01806008, 0xc0000000)
                q.command(f'set_irq_in {vm.nand_path} nand-ready 0 1')
                q.command('clock_step 1000000000')
                pending()
                print('PASS GPMI reset cancels wait continuation without a late IRQ or implicit DMA restart', flush=True)
                return
            if case in ('slower', 'faster-twice', 'migrate-slower'):
                cscdr1 = q.readl(0x020c4024)
                q.writel(0x020c4024, (cscdr1 & ~(7 << 22)) | (3 << 22))
                rate = 99000000
                if case in ('faster-twice', 'migrate-slower'):
                    q.command('clock_step 10000')  # 990 further cycles
                    pending()
                    remaining -= 990
                    if case == 'migrate-slower':
                        checkpoint(20000)
                        q.writel(0x020c4024, cscdr1)
                        rate = 198000000
                    else:
                        q.writel(0x020c4024, cscdr1 & ~(7 << 22))
                        rate = 396000000
            else:
                local = case in ('local-gate', 'local-ready', 'local-migrate')
                if local:
                    address, mask = 0x01806000, 1 << 30
                    original = q.readl(address)
                    q.writel(address + 4, mask)
                elif case == 'pfd-gate':
                    address, mask = 0x020c8100, 1 << 23
                    original = q.readl(address)
                    q.writel(address + 4, mask)
                else:
                    address, mask = (0x020c4078, 3 << 28) if case == 'io-gate' else (0x020c4080, 3 << 8)
                    original = q.readl(address)
                    q.writel(address, original & ~mask)
                period = vm.qmp.execute('qom-get', {'path': vm.nand_path + '/gpmi',
                                                  'property': 'qtest-clock-period'})['return']
                assert (period != 0) if local else (period == 0), 'wrong upstream clock state'
                q.command('clock_step 1000000000')
                pending()
                if case in ('migrate-gated', 'local-migrate'):
                    checkpoint(1000010000)
                if case in ('ready-while-gated', 'local-ready'):
                    q.command(f'set_irq_in {vm.nand_path} nand-ready 0 1')
                    pending()
                q.writel(address, original)
                if case in ('ready-while-gated', 'local-ready'):
                    completed(False)
                    q.command('clock_step 1000000')
                    completed(False)
                    print('PASS live NAND clock: ready edge waits for ungating', flush=True)
                    return
            delay = (remaining * 1000000000 + rate - 1) // rate
            q.command(f'clock_step {delay - 1}')
            pending()
            q.command('clock_step 1')
            completed()
            print(f'PASS live NAND clock: {case} preserves {remaining} remaining cycles', flush=True)
        finally:
            vm.close()


if __name__ == '__main__':
    for case in ('slower', 'faster-twice', 'core-gate', 'io-gate', 'pfd-gate',
                 'ready-while-gated', 'migrate-slower', 'migrate-gated',
                 'local-gate', 'local-ready', 'local-migrate', 'reset-wait'):
        run(case)
