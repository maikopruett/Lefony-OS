#!/usr/bin/env python3
"""GPT active/pending checkpoints and reset IRQ tests; no physical access."""
import importlib
from pathlib import Path
import subprocess
import tempfile

recovery = importlib.import_module('test-prime-g2-rom-recovery')
IRQTest = importlib.import_module('test-prime-g2-bch-irq').IRQTest
wait_migration = importlib.import_module('test-prime-g2-nand-migration').wait_migration


class VM:
    def __init__(self, folder, name, index, incoming=False, preinitialized=False, panel=False):
        sock, monitor = folder / (name + '.qt'), folder / (name + '.qm')
        self.q = self.qmp = None
        args = [str(recovery.QEMU), '-machine', 'hp-prime-g2', '-accel', 'qtest',
                '-S', '-display', 'none', '-serial', 'none', '-monitor', 'none',
                '-qtest', f'unix:{sock},server=on,wait=off', '-qtest-log', '/dev/null',
                '-qmp', f'unix:{monitor},server=on,wait=off']
        if preinitialized:
            args += ['-global', 'prime-g2-mmdc.preinitialized=on']
        if panel:
            args += ['-global', 'imx6ul-lcdif.prime-g2-panel=on']
        if incoming:
            args += ['-incoming', 'defer']
        self.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.q = IRQTest(sock)
            self.qmp = recovery.QMP(monitor)
            if index is not None:
                self.q.command(f'irq_intercept_out /machine/soc/gpt{index} sysbus-irq')
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.q:
            self.q.close()
        if self.qmp:
            self.qmp.close()
        self.process.terminate()
        try:
            self.process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.communicate(timeout=5)


def run(index, case):
    base = (0x02098000, 0x020e8000)[index]
    with tempfile.TemporaryDirectory(prefix='pg2gptstate-') as folder:
        folder = Path(folder)
        vms = []
        try:
            source = VM(folder, 'source', index)
            vms.append(source)
            q = source.q
            source.qmp.execute('cont')
            q.writel(base + 0x10, 3000)
            q.writel(base + 0x0c, 1)
            q.writel(base, (5 << 6) | (1 << 9) | 3)
            elapsed = 400000 if case == 'active' else 1001000
            q.command(f'clock_step {elapsed}')
            pending = case != 'active'
            if case == 'masked':
                q.writel(base + 0x0c, 0)
            asserted = pending and case != 'masked'
            assert bool(q.readl(base + 8) & 1) == pending
            assert q.levels.get(0, False) == asserted
            if case in ('soft-reset', 'system-reset'):
                if case == 'soft-reset':
                    q.writel(base, q.readl(base) | (1 << 15))
                else:
                    source.qmp.execute('system_reset')
                assert q.readl(base + 8) == 0
                assert q.readl(base + 0x0c) == 0
                assert not q.levels.get(0, False), 'reset left the GPT IRQ asserted'
                q.command('clock_step 2000000')
                assert q.readl(base + 8) == 0
                assert not q.levels.get(0, False), 'pre-reset compare fired later'
            else:
                source.qmp.execute('stop')
                saved = {off: q.readl(base + off) for off in (0, 4, 8, 12, 16, 0x24)}
                destination = VM(folder, 'destination', index, incoming=True)
                vms.append(destination)
                # qtest's externally driven clock is not part of migration.
                destination.q.command(f'clock_step {elapsed}')
                uri = 'unix:' + str(folder / 'migration.sock')
                destination.qmp.execute('migrate-incoming', {'uri': uri})
                source.qmp.execute('migrate', {'uri': uri})
                wait_migration(source)
                wait_migration(destination)
                q = destination.q
                for off, expected in saved.items():
                    assert q.readl(base + off) == expected, (off, expected)
                assert q.levels.get(0, False) == asserted, 'GPT IRQ state not restored'
                if case == 'masked':
                    q.writel(base + 0x0c, 1)
                    assert q.readl(base + 8) & 1
                    assert q.levels.get(0, False), 'restored masked event was lost'
                destination.qmp.execute('cont')
                if not pending:
                    q.command('clock_step 599000')
                    assert not q.readl(base + 8) & 1
                    q.command('clock_step 2000')
                    assert q.readl(base + 8) & 1
                    assert q.levels.get(0, False)
                q.writel(base + 8, 1)
                assert not q.readl(base + 8) & 1
                assert not q.levels.get(0, False)
            print(f'PASS GPT{index + 1} {case}')
        finally:
            for vm in reversed(vms):
                vm.close()


if __name__ == '__main__':
    for timer in range(2):
        for scenario in ('active', 'pending', 'masked', 'soft-reset', 'system-reset'):
            run(timer, scenario)
