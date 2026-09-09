#!/usr/bin/env python3
"""GPMI/BCH reset handshakes must clear only their controller state."""
import importlib
from pathlib import Path
import tempfile

migration = importlib.import_module('test-prime-g2-nand-migration')


def run(block, alias):
    with tempfile.TemporaryDirectory(prefix='pg2blockreset-') as folder:
        directory = Path(folder)
        vm = migration.VM(directory, 'src', migration.physical.overlay(directory / 'src.overlay', {}),
                          timed_clock=198000000)
        try:
            q = vm.q
            base = 0x01806000 if block == 'gpmi' else 0x01808000
            own = base + (0x10 if block == 'gpmi' else 0x80)
            other = 0x01808080 if block == 'gpmi' else 0x01806010
            q.writel(own, 0x12345678)
            q.writel(other, 0x33445566)
            # Keep an independent APBH pending IRQ through peripheral reset.
            q.writel(0x01804010, 0x10001)
            if block == 'gpmi':
                q.writel(base + 0x60, (1 << 20) | (1 << 9))
            else:
                q.writel(base, 0x101)
            irq = 0 if block == 'gpmi' else 1
            assert q.levels.get(irq)
            q.writel(0x01806128, 0)
            q.writel(0x01806100, 0x80)
            q.writel(0x01806104, 0)
            q.writel(0x01806100, 0x10)
            assert q.readl(0x0180610c) & 1
            q.writel(base + 8, 0x80000000)
            q.writel(base + 8, 0x40000000)
            q.writel(base + alias, 0x80000000)
            assert q.readl(base) == 0xc0000000
            assert q.readl(own) == 0
            assert not q.levels.get(irq, False)
            assert q.levels.get(2)
            assert q.readl(other) == 0x33445566
            assert q.readl(0x0180610c) & 1, 'controller reset changed NAND status'
            q.writel(own, 0xabcdef01)
            assert q.readl(own) == 0, 'configuration accepted while reset held'
            if alias == 12:
                destination = migration.VM(directory, 'dst',
                    migration.physical.overlay(directory / 'dst.overlay', {}),
                    incoming=True, timed_clock=198000000)
                try:
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
                assert q.readl(base) == 0xc0000000
                assert not q.levels.get(irq, False)
                assert q.levels.get(2)
                assert q.readl(other) == 0x33445566
            q.writel(base + 8, 0x80000000)
            assert q.readl(base) == 0x40000000
            q.writel(base + 8, 0x40000000)
            assert q.readl(base) == 0
            q.writel(own, 0x12345678)
            assert q.readl(own) == 0x12345678
            print(f'PASS {block} reset alias {alias}: acknowledgement, IRQ clearing, held writes and block/NAND isolation', flush=True)
        finally:
            vm.close()


if __name__ == '__main__':
    for block in ('gpmi', 'bch'):
        for alias in (0, 4, 12):
            run(block, alias)
