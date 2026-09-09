#!/usr/bin/env python3
"""NAND status read/compare drives APBH SENSE without a RAM transfer."""
import importlib
from pathlib import Path
import struct
import tempfile

migration = importlib.import_module('test-prime-g2-nand-migration')
HEAD, COMPARE, SENSE, GOOD, BAD = (0x80001000, 0x80001040, 0x80001080, 0x800010a0, 0x800010c0)


def run(case):
    with tempfile.TemporaryDirectory(prefix='pg2compare-') as folder:
        directory = Path(folder)
        vm = migration.VM(directory, 'src', migration.physical.overlay(directory / 'src.overlay', {}),
                          timed_clock=198000000)
        try:
            q = vm.q
            # Produce real modeled program failure, not a fabricated compare bit.
            failure = case in ('failure', 'masked', 'reference', 'migrate', 'refresh', 'paused')
            if failure:
                q.writel(0x01806128, 0)  # mark NAND block zero bad
                q.writel(0x01806100, 0x80)
                q.writel(0x01806104, 0)
                q.writel(0x01806100, 0x10)
                assert q.readl(0x0180610c) & 1
            mask = 0 if case == 'masked' else 1
            reference = 1 if case == 'reference' else 0
            expected = bool(failure and mask and not reference)
            if case in ('full-match', 'full-mismatch'):
                mask = 0xff
                reference = 0xe0 if case == 'full-match' else 0xe1
                expected = case == 'full-mismatch'
            split = case == 'migrate'
            compare_word = (mask << 16) | reference
            ctrl = {'multi-byte': 0x02800002, 'zero-count': 0x02800000,
                    'wide-bus': 0x02000001}.get(case, 0x02800001)
            for address, words in (
                (HEAD, [COMPARE, 0x00013096, 0x80001100, 0x08820001, 0, 0]),
                (COMPARE, [SENSE, 0x20c0 if split else 0x2084, 0x80001200, ctrl, compare_word]),
                (SENSE, [GOOD, 7, BAD]), (GOOD, [0, 0x48, 0]), (BAD, [0, 0x48, 1])):
                data = struct.pack('<' + 'I' * len(words), *words)
                q.command(f'write 0x{address:x} {len(data)} 0x{data.hex()}')
            q.command('write 0x80001100 1 0x70')
            q.command('memset 0x80001200 32 0xa5')
            q.writel(0x01804014, 1 << 16)
            q.writel(0x01806064, 1 << 20)
            if case == 'paused':
                q.writel(0x01804034, 1)
            q.writel(0x01804110, HEAD)
            q.writel(0x01804140, 1)
            if case in ('multi-byte', 'zero-count', 'wide-bus'):
                assert q.readl(0x01804100) == COMPARE
                assert q.readl(0x01804140) == 0x10000
                assert not q.levels.get(2, False)
                assert vm.read(0x80001200, 32) == bytes([0xa5]) * 32
                print(f'PASS unsupported {case} compare does not fabricate completion (not hardware parity)', flush=True)
                return
            if case == 'paused':
                assert q.readl(0x01804140) == 0x10000
                assert q.readl(0x01804100) == 0
                q.writel(0x01804038, 1)
            assert bool(q.readl(0x018060b0) & (1 << 8)) == expected
            assert not q.levels.get(0, False), 'compare must not synthesize timeout IRQ'
            assert not q.readl(0x01806060) & (1 << 9)
            assert vm.read(0x80001200, 32) == bytes([0xa5]) * 32
            if split:
                assert q.readl(0x01804100) == COMPARE
                assert q.readl(0x01804140) == 0
                assert not q.levels.get(2, False)
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
                assert q.readl(0x018060b0) & (1 << 8)
                q.writel(0x01804110, SENSE)
                q.writel(0x01804140, 1)
            assert q.readl(0x01804100) == (BAD if expected else GOOD)
            assert q.readl(0x01804130) == int(expected)
            assert q.readl(0x01804140) == 0
            assert q.levels.get(2, False)
            # Read-only STAT and COMPARE configuration alone do not clear the latch.
            q.writel(0x018060b0, 0)
            q.writel(0x01806010, 0)
            assert bool(q.readl(0x018060b0) & (1 << 8)) == expected
            if case == 'refresh':
                q.writel(0x01806100, 0xff)  # NAND reset restores successful status
                q.writel(0x01804018, 1)
                q.writel(0x01804110, HEAD)
                q.writel(0x01804140, 1)
                assert q.readl(0x01804100) == GOOD
                assert not q.readl(0x018060b0) & (1 << 8)
            vm.qmp.execute('system_reset')
            q.readl(0x018060b0)
            assert not q.readl(0x018060b0) & (1 << 8)
            print(f'PASS NAND read/compare {case}: masked status, SENSE branch, no RAM write or false timeout IRQ', flush=True)
        finally:
            vm.close()


if __name__ == '__main__':
    for case in ('failure', 'success', 'masked', 'reference', 'full-match', 'full-mismatch',
                 'paused', 'refresh', 'migrate', 'multi-byte', 'zero-count', 'wide-bus'):
        run(case)
