#!/usr/bin/env python3
"""Exercise U-Boot's APBH block-reset handshake and queued-DMA cancellation."""
import importlib
from pathlib import Path
import struct
import tempfile

migration = importlib.import_module('test-prime-g2-nand-migration')


def run(alias):
    with tempfile.TemporaryDirectory(prefix='pg2reset-') as folder:
        directory = Path(folder)
        vm = migration.VM(directory, 'src', migration.physical.overlay(directory / 'src.overlay', {}),
                          timed_clock=198000000)
        try:
            q = vm.q
            data = struct.pack('<5I', 0, 0x2048, 0, 0, 0x12345678)
            q.command(f'write 0x80001000 {len(data)} 0x{data.hex()}')
            q.writel(0x01806010, 0x11223344)
            q.writel(0x01808080, 0x030a0880)
            # A queued channel plus an existing completion IRQ must reset.
            q.writel(0x01804034, 1)
            q.writel(0x01804110, 0x80001000)
            q.writel(0x01804140, 1)
            q.writel(0x01804010, 0x10001)
            assert q.levels.get(2)
            q.writel(0x01804008, 0x80000000)
            assert not q.readl(0x01804000) & 0x80000000
            q.writel(0x01804008, 0x40000000)
            q.writel(0x01804000 + alias, 0x80000000)
            assert q.readl(0x01804000) == 0xc0000000
            assert not q.levels.get(2, False)
            for address in (0x01804010, 0x01804020, 0x01804030,
                            0x01804100, 0x01804110, 0x01804120, 0x01804130, 0x01804140):
                assert q.readl(address) == 0, hex(address)
            q.writel(0x01804110, 0x80001000)
            q.writel(0x01804140, 1)
            q.writel(0x01804010, 0x10001)
            assert q.readl(0x01804110) == 0 and q.readl(0x01804140) == 0
            assert not q.levels.get(2, False)
            # APBH reset must not reset NAND, GPMI or BCH configuration.
            assert q.readl(0x01806010) == 0x11223344
            assert q.readl(0x01808080) == 0x030a0880
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
                assert q.readl(0x01804000) == 0xc0000000
                assert q.readl(0x01804140) == 0
                assert not q.levels.get(2, False)
                assert q.readl(0x01806010) == 0x11223344
            q.writel(0x01804008, 0x80000000)
            assert q.readl(0x01804000) == 0x40000000
            q.writel(0x01804110, 0x80001000)
            q.writel(0x01804140, 1)
            assert q.readl(0x01804140) == 0x10000
            assert q.readl(0x01806010) == 0x11223344
            q.writel(0x01804008, 0x40000000)
            assert q.readl(0x01804140) == 0
            assert q.readl(0x01806010) == 0x12345678
            print(f'PASS APBH reset alias {alias}: handshake, cleared channel/IRQ, reset-held writes, block isolation and gated restart', flush=True)
        finally:
            vm.close()


if __name__ == '__main__':
    for alias in (0, 4, 12):
        run(alias)
