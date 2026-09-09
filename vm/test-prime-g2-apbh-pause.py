#!/usr/bin/env python3
"""APBH channel-zero gate/freeze must hold dispatch independently of GPMI."""
import importlib
from pathlib import Path
import struct
import tempfile

migration = importlib.import_module('test-prime-g2-nand-migration')
CTRL, FREEZE, NEXT, SEMA = 0x01804000, 0x01804030, 0x01804110, 0x01804140
HEAD, TERMINAL = 0x80001000, 0x80001040


def run(case):
    with tempfile.TemporaryDirectory(prefix='pg2pause-') as folder:
        directory = Path(folder)
        vm = migration.VM(directory, 'src', migration.physical.overlay(directory / 'src.overlay', {}),
                          timed_clock=198000000)
        try:
            q = vm.q
            waiting = case in ('ready', 'timeout')
            records = [(HEAD, [0, 0x2048, 0, 0, 0x12345678])]
            if waiting:
                records = [(HEAD, [TERMINAL, 0x10a4, 0, 0x03800000]),
                           (TERMINAL, [0, 0x2048, 0, 0, 0x12345678])]
                q.command(f'set_irq_in {vm.nand_path} nand-ready 0 0')
                q.writel(0x01806080, 2 << 16)
                q.writel(0x01806064, 1 << 20)
            for address, words in records:
                data = struct.pack('<' + 'I' * len(words), *words)
                q.command(f'write 0x{address:x} {len(data)} 0x{data.hex()}')
            q.writel(0x01804014, 1 << 16)
            q.writel(NEXT, HEAD)
            # PHORE is read-only; zero INCREMENT cannot launch an idle channel.
            if case == 'zero':
                for value in (0, 0x00ff0000, 0xffffff00):
                    q.writel(SEMA, value)
                    assert q.readl(SEMA) == 0
                    assert q.readl(0x01804100) == 0
                    assert q.readl(0x01806010) == 0
                    assert not q.levels.get(2, False)
                print('PASS APBH zero increment and read-only PHORE cannot start DMA', flush=True)
                return
            register = CTRL if case == 'gate' else FREEZE
            if not waiting:
                q.writel(register + 4, 1)
            q.writel(SEMA, 1)
            if waiting:
                q.writel(register + 4, 1)
            if case == 'both':
                q.writel(CTRL + 4, 1)
                q.writel(FREEZE + 8, 1)
                register = CTRL

            def pending():
                assert q.readl(SEMA) == 0x10000
                assert q.readl(0x01804100) == (HEAD if waiting else 0)
                assert q.readl(0x01806010) == 0
                assert not q.levels.get(2, False)

            pending()
            vm.qmp.execute('cont')
            if case == 'ready':
                q.command(f'set_irq_in {vm.nand_path} nand-ready 0 1')
            q.command('clock_step 1000000000')
            pending()
            if waiting:
                assert bool(q.levels.get(0)) == (case == 'timeout')
            # Other channels' gate/freeze writes must not release channel zero.
            q.writel(register + 4, 2)
            q.writel(register + 8, 2)
            pending()
            if case == 'reset':
                vm.qmp.execute('system_reset')
                q.readl(SEMA)
                assert q.readl(SEMA) == 0
                q.writel(register + 8, 1)
                assert q.readl(0x01806010) == 0
                assert not q.levels.get(2, False)
                print('PASS APBH pause reset cancels queued dispatch', flush=True)
                return
            if case == 'migrate':
                destination = migration.VM(directory, 'dst',
                    migration.physical.overlay(directory / 'dst.overlay', {}),
                    incoming=True, timed_clock=198000000)
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
                pending()
                assert q.readl(register) & 1
            if case == 'toggle':
                q.writel(register + 12, 1)
            elif case == 'direct':
                q.writel(register, 0)
            else:
                q.writel(register + 8, 1)
            assert q.readl(SEMA) == 0
            assert q.readl(0x01804100) == (TERMINAL if waiting else HEAD)
            assert q.readl(0x01806010) == 0x12345678
            assert q.levels.get(2, False)
            print(f'PASS APBH {case}: held dispatch and one completion after release', flush=True)
        finally:
            vm.close()


if __name__ == '__main__':
    for case in ('gate', 'freeze', 'both', 'toggle', 'direct', 'ready', 'timeout', 'reset', 'migrate', 'zero'):
        run(case)
