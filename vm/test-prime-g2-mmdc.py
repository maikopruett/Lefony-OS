#!/usr/bin/env python3
"""Nominal MMDC command-state/reset/migration tests, not PHY timing proof."""
import importlib
from pathlib import Path
import tempfile

state = importlib.import_module('test-prime-g2-gpt-state')
BASE = 0x021b0000
COMMANDS = [0x02008032, 0x00008033, 0x00048031, 0x15208030, 0x04008040]


def initialize(q):
    """Explicit nominal command setup for tests that require available DDR."""
    q.writel(BASE + 0x1c, 1 << 15)
    q.writel(BASE, 0x83180000)
    for command in COMMANDS:
        q.writel(BASE + 0x1c, command)
    q.writel(BASE + 0x1c, 0)


def ready(vm):
    return vm.qmp.execute('qom-get', {'path': '/machine/soc/mmdc',
                                    'property': 'initialized'})['return']


def run(case):
    with tempfile.TemporaryDirectory(prefix='pg2mmdc-') as directory:
        folder = Path(directory)
        source = state.VM(folder, 'source', None)
        destination = None
        vm = source
        try:
            assert not ready(vm)
            q = vm.q
            q.writel(BASE + 0x1c, 1 << 14)
            assert not q.readl(BASE + 0x1c) & (1 << 14), 'software forged CON_ACK'
            q.writel(BASE + 0x1c, 1 << 15)
            assert q.readl(BASE + 0x1c) & (1 << 14), 'CON_REQ not acknowledged'
            q.writel(BASE, 0x83180000 if case != 'no-chip-select' else 0x03180000)
            if case == 'lpddr2':
                q.writel(BASE + 0x18, 8)
            for i, command in enumerate(COMMANDS):
                if case == f'missing-{i}':
                    continue
                if case == 'no-request':
                    command &= ~(1 << 15)
                if case == 'wrong-rank':
                    command |= 8
                if case == 'different-mode-values' and i < 4:
                    command ^= 1 << 18  # No exact-image allowlist
                q.writel(BASE + 0x1c, command)
                if case in ('migration-partial', 'migration-complete') and i == (2 if case == 'migration-partial' else 4):
                    source.qmp.execute('stop')
                    destination = state.VM(folder, 'destination', None, incoming=True)
                    uri = 'unix:' + str(folder / 'migration.sock')
                    destination.qmp.execute('migrate-incoming', {'uri': uri})
                    source.qmp.execute('migrate', {'uri': uri})
                    state.wait_migration(source)
                    state.wait_migration(destination)
                    vm = destination
                    q = vm.q
                assert not ready(vm), 'configuration request still active'
            q.writel(BASE + 0x1c, 0)
            assert q.readl(BASE + 0x1c) & (1 << 14) == 0
            expected = case in ('complete', 'different-mode-values', 'system-reset',
                                'migration-partial', 'migration-complete')
            assert ready(vm) == expected, (case, ready(vm), expected)
            if case == 'system-reset':
                vm.qmp.execute('system_reset')
                assert not ready(vm), 'cold model reset retained command state'
                assert q.readl(BASE + 0x1c) == 0
                q.writel(BASE, 0x83180000)
                q.writel(BASE + 0x1c, 0)
                assert not ready(vm), 'old mode/ZQ state replayed after reset'
            print('PASS MMDC', case)
        finally:
            if destination:
                destination.close()
            source.close()


def main():
    for case in ('complete', 'different-mode-values', 'no-chip-select',
                 'no-request', 'wrong-rank', 'lpddr2', 'system-reset',
                 'migration-partial', 'migration-complete',
                 *(f'missing-{i}' for i in range(5))):
        run(case)


if __name__ == '__main__':
    main()
