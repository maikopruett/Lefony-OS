#!/usr/bin/env python3
"""Software self-refresh handshake/retention; not physical warm-reset proof."""
import importlib
from pathlib import Path
import tempfile

mmdc = importlib.import_module('test-prime-g2-mmdc')
power = importlib.import_module('test-prime-g2-ddr-power')
MAPSR = mmdc.BASE + 0x404
REQUEST = 1 << 21
ACK = 1 << 25
CELL = 0x80010000


def run(case):
    with tempfile.TemporaryDirectory(prefix='pg2ddrsr-') as directory:
        folder = Path(directory)
        source = mmdc.state.VM(folder, 'source', None)
        destination = None
        vm = source
        try:
            q = vm.q
            q.writel(MAPSR, ACK)
            assert not q.readl(MAPSR) & ACK, 'software forged DVACK'
            q.writel(MAPSR, REQUEST | 1)
            assert not q.readl(MAPSR) & ACK, 'uninitialized DDR acknowledged'
            mmdc.initialize(q)
            assert not mmdc.ready(vm), 'accepted MRS while self-refresh requested'
            q.writel(MAPSR, 1)
            mmdc.initialize(q)
            q.writel(CELL, 0x12345678)
            q.writel(MAPSR, REQUEST | 1)
            assert q.readl(MAPSR) == REQUEST | ACK | 1
            assert mmdc.ready(vm), 'self-refresh erased initialization'
            q.writel(CELL + 0x10000000, 0xbad00bad)
            assert q.readl(CELL) == 0, 'self-refresh allowed normal memory access'
            if case == 'migration':
                destination = mmdc.state.VM(folder, 'incoming', None, incoming=True)
                uri = 'unix:' + str(folder / 'migration.sock')
                destination.qmp.execute('migrate-incoming', {'uri': uri})
                source.qmp.execute('migrate', {'uri': uri})
                mmdc.state.wait_migration(source)
                mmdc.state.wait_migration(destination)
                vm, q = destination, destination.q
                assert q.readl(MAPSR) == REQUEST | ACK | 1
                assert q.readl(CELL) == 0
            if case == 'power-loss':
                power.supply(vm, False)
                assert not q.readl(MAPSR) & ACK
                power.supply(vm, True)
                assert not q.readl(MAPSR) & ACK
                assert not mmdc.ready(vm), 'power restoration resurrected mode state'
            if case == 'controller-reset':
                vm.qmp.execute('system_reset')
                assert q.readl(MAPSR) == 0
                assert not mmdc.ready(vm)
            q.writel(MAPSR, 1)
            assert q.readl(MAPSR) == 1, 'exit did not clear DVACK'
            if case in ('power-loss', 'controller-reset'):
                mmdc.initialize(q)
            expected = 0 if case == 'power-loss' else 0x12345678
            assert q.readl(CELL) == q.readl(CELL + 0x10000000) == expected
            print('PASS DDR self-refresh', case)
        finally:
            if destination:
                destination.close()
            source.close()


if __name__ == '__main__':
    for case in ('roundtrip', 'migration', 'power-loss', 'controller-reset'):
        run(case)
