#!/usr/bin/env python3
"""DDR3 startup command ordering, not electrical/timing qualification."""
import importlib
import itertools
from pathlib import Path
import tempfile

mmdc = importlib.import_module('test-prime-g2-mmdc')


def issue(vm, commands):
    vm.q.writel(mmdc.BASE, 0x83180000)
    for command in commands:
        vm.q.writel(mmdc.BASE + 0x1c, command)
    vm.q.writel(mmdc.BASE + 0x1c, 0)


def main():
    with tempfile.TemporaryDirectory(prefix='pg2ddrorder-') as directory:
        vm = mmdc.state.VM(Path(directory), 'order', None)
        try:
            for order in itertools.permutations(range(4)):
                vm.qmp.execute('system_reset')
                issue(vm, [mmdc.COMMANDS[i] for i in order] + [mmdc.COMMANDS[4]])
                assert mmdc.ready(vm) == (order == (0, 1, 2, 3)), order
            print('PASS all 24 startup MRS permutations (one valid)')
            invalid = {
                'dll-disabled': mmdc.COMMANDS[:2] + [mmdc.COMMANDS[2] | (1 << 16)] + mmdc.COMMANDS[3:],
                'no-dll-reset': mmdc.COMMANDS[:3] + [mmdc.COMMANDS[3] & ~(1 << 24)] + mmdc.COMMANDS[4:],
                'short-zq': mmdc.COMMANDS[:4] + [mmdc.COMMANDS[4] & ~(1 << 26)],
                'wrong-zq-bank': mmdc.COMMANDS[:4] + [mmdc.COMMANDS[4] | 1],
                'early-zq': [mmdc.COMMANDS[4]] + mmdc.COMMANDS[:4],
            }
            for name, commands in invalid.items():
                vm.qmp.execute('system_reset')
                issue(vm, commands)
                assert not mmdc.ready(vm), name
                # A complete new sequence recovers; no permanent fault latch.
                mmdc.initialize(vm.q)
                assert mmdc.ready(vm), (name, 'failed recovery')
                print('PASS startup rejection and recovery:', name)
            # Normal post-initialization MRS need not follow startup order.
            issue(vm, [mmdc.COMMANDS[0] ^ (1 << 19)])
            assert mmdc.ready(vm), 'runtime MRS forced a cold initialization'
            issue(vm, [mmdc.COMMANDS[3]])
            assert not mmdc.ready(vm), 'DLL reset retained old calibration'
            issue(vm, [mmdc.COMMANDS[4]])
            assert mmdc.ready(vm), 'ZQCL did not recover modeled calibration'
            print('PASS post-initialization MRS and DLL-reset/ZQ lifecycle')
            vm.qmp.execute('system_reset')
            issue(vm, [mmdc.COMMANDS[i] for i in (0, 1, 3, 2, 4)])
            destination = mmdc.state.VM(Path(directory), 'incoming', None, incoming=True)
            try:
                uri = 'unix:' + str(Path(directory) / 'migration.sock')
                destination.qmp.execute('migrate-incoming', {'uri': uri})
                vm.qmp.execute('migrate', {'uri': uri})
                mmdc.state.wait_migration(vm)
                mmdc.state.wait_migration(destination)
                assert not mmdc.ready(destination), 'migration qualified invalid startup'
                mmdc.initialize(destination.q)
                assert mmdc.ready(destination), 'valid startup failed after migration'
                print('PASS invalid startup migration and subsequent recovery')
            finally:
                destination.close()
        finally:
            vm.close()


if __name__ == '__main__':
    main()
