#!/usr/bin/env python3
"""Migrate halfway through a NAND wait; preserve the original deadline."""
import importlib
from pathlib import Path
import struct
import tempfile

migration = importlib.import_module('test-prime-g2-nand-migration')


def run(outcome, phase='half'):
    rate = 198000000
    total = (2 * 4096 * 1000000000 + rate - 1) // rate
    elapsed = {'first': 1, 'half': total // 2, 'last': total - 1}[phase]
    with tempfile.TemporaryDirectory(prefix='pg2waitmig-') as folder:
        directory = Path(folder)
        source = destination = None
        try:
            source = migration.VM(directory, 'src',
                                  migration.physical.overlay(directory / 'src.overlay', {}),
                                  timed_clock=rate)
            q = source.q
            for address, words in (
                    (0x80001000, [0x80001020, 0x10a4, 0, 0x03800000]),
                    (0x80001020, [0x80001040, 7, 0x80001060]),
                    (0x80001040, [0, 0x48, 0]),
                    (0x80001060, [0, 0x48, 1])):
                data = struct.pack('<' + 'I' * len(words), *words)
                q.command(f'write 0x{address:x} {len(data)} 0x{data.hex()}')
            q.command(f'set_irq_in {source.nand_path} nand-ready 0 0')
            q.writel(0x01806080, 2 << 16)
            q.writel(0x01806064, 1 << 20)
            q.writel(0x01804014, 1 << 16)
            source.qmp.execute('cont')  # qtest accelerator executes no guest CPU
            q.writel(0x01804110, 0x80001000)
            q.writel(0x01804140, 1)
            assert int(q.command(f'clock_step {elapsed}').split()[1]) == elapsed
            assert q.readl(0x01804140) == 0x10000
            source.qmp.execute('stop')
            destination = migration.VM(directory, 'dst',
                                       migration.physical.overlay(directory / 'dst.overlay', {}),
                                       incoming=True, timed_clock=rate)
            assert destination.q.readl(0x018060b0) & (1 << 24)
            # qtest's externally driven clock counter is test infrastructure,
            # not migrated machine state. Align that counter before loading
            # any timers, while the incoming machine is still suspended.
            # The model's timer/deadline itself must come from migration.
            assert int(destination.q.command(f'clock_step {elapsed}').split()[1]) == elapsed
            uri = 'unix:' + str(directory / 'migration.sock')
            destination.qmp.execute('migrate-incoming', {'uri': uri})
            source.qmp.execute('migrate', {'uri': uri})
            migration.wait_migration(source)
            migration.wait_migration(destination)
            # Stop the source before observing any destination completion.
            source.close()
            source = None
            q = destination.q

            def pending():
                assert q.readl(0x01804100) == 0x80001000
                assert q.readl(0x01804140) == 0x10000
                assert not q.readl(0x018060b0) & (1 << 24)
                assert not q.readl(0x01806060) & (1 << 9)
                assert not q.levels.get(2, False)
                assert not q.levels.get(0, False)

            def completed(failed):
                assert q.readl(0x01804100) == (0x80001060 if failed else 0x80001040)
                assert q.readl(0x01804140) == 0
                assert q.readl(0x01804130) == int(failed)
                assert bool(q.readl(0x01806060) & (1 << 9)) == failed
                assert q.levels.get(2, False)
                assert q.levels.get(0, False) == failed

            pending()
            assert not destination.qmp.execute('query-status')['return']['running']
            destination.qmp.execute('cont')
            if total - elapsed > 1:
                q.command(f'clock_step {total - elapsed - 1}')
            pending()
            if outcome == 'timeout':
                q.command('clock_step 1')
                completed(True)
            elif outcome == 'ready':
                q.command(f'set_irq_in {destination.nand_path} nand-ready 0 1')
                completed(False)
                q.command(f'clock_step {total * 2}')
                completed(False)
            else:
                destination.qmp.execute('system_reset')
                q.command(f'clock_step {total * 2}')
                assert q.readl(0x01804100) == 0
                assert q.readl(0x01804140) == 0
                assert not q.levels.get(2, False)
                assert not q.levels.get(0, False)
            print(f'PASS active NAND-wait migration ({phase}): remaining deadline and {outcome} path', flush=True)
        finally:
            if destination:
                destination.close()
            if source:
                source.close()


if __name__ == '__main__':
    for outcome in ('timeout', 'ready', 'reset'):
        for phase in ('first', 'half', 'last'):
            run(outcome, phase)
