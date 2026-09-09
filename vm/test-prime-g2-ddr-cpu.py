#!/usr/bin/env python3
"""TCG OCRAM execution and external-memory aborts; no physical access."""
import importlib
import re
from pathlib import Path
import subprocess
import tempfile
import time

helper = importlib.import_module('test-prime-g2-pwm-cpu-irq')
recovery = helper.recovery


def main():
    with tempfile.TemporaryDirectory(prefix='pg2ddrcpu-') as directory:
        folder = Path(directory)
        payload = helper.payload(folder, helper.ROOT / 'vm/guest/prime-g2-ddr-gate.S')
        qt, qm = folder / 'qt', folder / 'qm'
        command = [str(recovery.QEMU), '-machine', 'hp-prime-g2', '-accel', 'tcg',
                   '-S', '-display', 'none', '-serial', 'none', '-monitor', 'none',
                   '-qtest-log', '/dev/null', '-qtest', f'unix:{qt},server=on,wait=off',
                   '-qmp', f'unix:{qm},server=on,wait=off',
                   '-device', f'loader,file={payload},addr=0x00910000,force-raw=on',
                   '-device', 'loader,addr=0x00910000,cpu-num=0']
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = qmp = None
        try:
            q = recovery.QTest(qt)
            qmp = recovery.QMP(qm)
            qmp.execute('cont')
            deadline = time.monotonic() + 10
            result = None
            while time.monotonic() < deadline:
                result = [q.readl(0x00920000 + 4 * i) for i in range(8)]
                if result[0]:
                    break
                time.sleep(0.01)
            assert result[0] == 1 and result[1] & 0x40f == 8, result
            assert result[2:] == [0x80001000, 0x1234abcd, 0x1234abcd,
                                  3, 0x02200001, 0x1234abcd], result
            print('PASS OCRAM guest: initialization/configuration/self-refresh CPU aborts and retained data after wake')
            qmp.execute('stop')
            def registers():
                response = qmp.execute('human-monitor-command', {'command-line': 'info registers'})['return']
                return {int(index): int(value, 16) for index, value in
                        re.findall(r'R(\d{2})=([0-9a-fA-F]+)', response)}

            before = registers()
            assert before.get(8) == 3 and 0x00910000 <= before.get(15, 0) < 0x00920000, before
            # Exercise SRC's CPU-only reset rather than QMP system_reset.
            # DDR controller state, supply and backing bytes must not reset.
            src = 0x020d8000
            q.writel(src, q.readl(src) | (1 << 13))
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and q.readl(src) & (1 << 13):
                time.sleep(0.01)
            assert not q.readl(src) & (1 << 13), 'CPU reset did not finish'
            after = registers()
            assert after.get(8) == 0 and after.get(15) == 0, after
            assert q.readl(0x80001000) == 0x1234abcd, 'CPU-only reset lost initialized DDR'
            assert q.readl(0x00920000) == 1, 'CPU-only reset erased OCRAM'
            print('PASS SRC CPU-only reset clears CPU registers while preserving initialized DDR and OCRAM')
            rail = {'path': '/machine/soc/mmdc', 'property': 'ddr-supply-present'}
            qmp.execute('qom-set', dict(rail, value=False))
            qmp.execute('qom-set', dict(rail, value=True))
            importlib.import_module('test-prime-g2-mmdc').initialize(q)
            assert q.readl(0x80001000) == 0, 'TCG power loss preserved DDR data'
            assert q.readl(0x00920000) == 1, 'DDR fault erased OCRAM mailbox'
            qmp.execute('cont')
            qmp.execute('stop')
            print('PASS paused TCG DDR rail loss invalidates memory without erasing OCRAM')
        finally:
            if q:
                q.close()
            if qmp:
                qmp.close()
            process.terminate()
            try:
                _, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                _, stderr = process.communicate(timeout=5)
            if process.returncode not in (0, -15):
                raise RuntimeError(stderr.decode(errors='replace'))


if __name__ == '__main__':
    main()
