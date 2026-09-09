#!/usr/bin/env python3
"""DDR gate/alias/reset/migration checks; not physical retention qualification."""
import importlib
from pathlib import Path
import tempfile

mmdc = importlib.import_module('test-prime-g2-mmdc')
state = mmdc.state


def run(case):
    with tempfile.TemporaryDirectory(prefix='pg2ddrgate-') as directory:
        folder = Path(directory)
        source = state.VM(folder, 'source', None)
        destination = None
        vm = source
        try:
            q = vm.q
            primary, alias = 0x80001000, 0x90001000
            q.writel(primary, 0x11223344)
            q.writel(alias, 0x55667788)
            assert q.readl(primary) == q.readl(alias) == 0
            mmdc.initialize(q)
            assert q.readl(primary) == 0, 'blocked write changed backing RAM'
            q.writel(primary, 0x1234abcd)
            assert q.readl(alias) == 0x1234abcd
            if case != 'migration-open':
                q.writel(mmdc.BASE + 0x1c, 1 << 15)
                q.writel(alias, 0xbad00bad)
                assert q.readl(primary) == q.readl(alias) == 0
            if case.startswith('migration-'):
                source.qmp.execute('stop')
                destination = state.VM(folder, 'destination', None, incoming=True)
                uri = 'unix:' + str(folder / 'migration.sock')
                destination.qmp.execute('migrate-incoming', {'uri': uri})
                source.qmp.execute('migrate', {'uri': uri})
                state.wait_migration(source)
                state.wait_migration(destination)
                vm = destination
                q = vm.q
                expected = 0x1234abcd if case == 'migration-open' else 0
                assert q.readl(primary) == expected, 'gate not restored'
            if case == 'controller-reset':
                vm.qmp.execute('system_reset')
                assert not mmdc.ready(vm)
                assert q.readl(primary) == q.readl(alias) == 0
                mmdc.initialize(q)
            else:
                q.writel(mmdc.BASE + 0x1c, 0)
            # Controller reset currently gates but does not erase backing RAM.
            # This is not a physical power-loss or warm-reset assertion.
            assert q.readl(primary) == q.readl(alias) == 0x1234abcd
            print('PASS DDR gate', case)
        finally:
            if destination:
                destination.close()
            source.close()


if __name__ == '__main__':
    for case in ('configuration-roundtrip', 'controller-reset',
                 'migration-open', 'migration-closed'):
        run(case)
