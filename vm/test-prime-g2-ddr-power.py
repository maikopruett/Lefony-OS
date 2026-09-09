#!/usr/bin/env python3
"""Explicit DDR rail-loss injection; not battery/PMIC wiring qualification."""
import importlib
from pathlib import Path
import tempfile

mmdc = importlib.import_module('test-prime-g2-mmdc')
PATH = '/machine/soc/mmdc'
CELLS = [0x80000000, 0x87fff000, 0x8ffffffc]


def supply(vm, present=None):
    if present is None:
        return vm.qmp.execute('qom-get', {'path': PATH, 'property': 'ddr-supply-present'})['return']
    vm.qmp.execute('qom-set', {'path': PATH, 'property': 'ddr-supply-present', 'value': present})


def run(case):
    with tempfile.TemporaryDirectory(prefix='pg2ddrpwr-') as directory:
        folder = Path(directory)
        preinitialized = case == 'preinitialized-reset-off'
        source = mmdc.state.VM(folder, 'source', None, preinitialized=preinitialized)
        destination = None
        vm = source
        try:
            q = vm.q
            mmdc.initialize(q)
            for i, address in enumerate(CELLS):
                q.writel(address, 0xc0de0000 + i)
            q.writel(0x00920000, 0x13579bdf)
            if case == 'reject-running':
                vm.qmp.execute('cont')
                try:
                    supply(vm, False)
                except RuntimeError as error:
                    assert 'pause the Prime VM' in str(error), error
                else:
                    raise AssertionError('running rail injection accepted')
                assert supply(vm) and mmdc.ready(vm)
                vm.qmp.execute('stop')
            supply(vm, False)
            assert not supply(vm) and not mmdc.ready(vm)
            assert q.readl(0x00920000) == 0x13579bdf, 'DDR-only fault erased OCRAM'
            mmdc.initialize(q)  # Device must not accept MRS/ZQ while unpowered.
            assert not mmdc.ready(vm)
            if case in ('controller-reset-off', 'preinitialized-reset-off'):
                vm.qmp.execute('system_reset')
                assert not supply(vm) and not mmdc.ready(vm), 'reset resurrected supply/state'
            if case.startswith('migration-'):
                if case == 'migration-restored':
                    supply(vm, True)
                    mmdc.initialize(q)
                destination = mmdc.state.VM(folder, 'destination', None, incoming=True)
                uri = 'unix:' + str(folder / 'migration.sock')
                destination.qmp.execute('migrate-incoming', {'uri': uri})
                source.qmp.execute('migrate', {'uri': uri})
                mmdc.state.wait_migration(source)
                mmdc.state.wait_migration(destination)
                vm = destination
                q = vm.q
                assert supply(vm) == (case == 'migration-restored')
                assert mmdc.ready(vm) == (case == 'migration-restored')
            if not supply(vm):
                supply(vm, True)
                assert not mmdc.ready(vm), 'rail restoration reused lost initialization'
            mmdc.initialize(q)
            assert mmdc.ready(vm)
            for address in CELLS:
                assert q.readl(address) == q.readl(address + 0x10000000) == 0, 'old powered-down data reappeared'
            q.writel(CELLS[0], 0x2468ace0)
            supply(vm, True)  # No edge: do not erase live memory.
            assert q.readl(CELLS[0]) == 0x2468ace0
            supply(vm, False)
            supply(vm, True)
            mmdc.initialize(q)
            assert q.readl(CELLS[0]) == 0, 'second loss did not invalidate data'
            print('PASS DDR supply', case)
        finally:
            if destination:
                destination.close()
            source.close()


if __name__ == '__main__':
    for case in ('loss-restore', 'reject-running', 'controller-reset-off',
                 'preinitialized-reset-off', 'migration-off', 'migration-restored'):
        run(case)
