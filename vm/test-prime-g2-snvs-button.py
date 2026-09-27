#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""SNVS button pin, latched SPO status and IRQ acknowledgement contract.

Matches Linux's snvs_pwrkey.c register contract; no HP image is needed.
"""
import importlib
from pathlib import Path
import subprocess
import tempfile

irq = importlib.import_module('test-prime-g2-bch-irq')
r = irq.recovery


def main():
    with tempfile.TemporaryDirectory(prefix='snvs-button-', dir='/tmp') as d:
        p = Path(d)
        proc = subprocess.Popen([str(r.QEMU), '-machine', 'hp-prime-g2', '-S',
            '-display', 'none', '-serial', 'none', '-monitor', 'none',
            '-qtest', f'unix:{p}/qt,server=on,wait=off', '-qtest-log', '/dev/null',
            '-qmp', f'unix:{p}/qm,server=on,wait=off'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = mp = None
        try:
            q = irq.IRQTest(p/'qt'); mp = r.QMP(p/'qm')
            q.command('irq_intercept_out /machine/soc/snvs sysbus-irq')
            base = 0x020cc000
            q.writel(base+0x38, 0x20)
            q.writel(base+0xfc, 1)
            assert q.readl(base+0x14)&0x40
            assert q.readl(base+0x4c)&0x40000
            assert q.levels.get(0)
            q.writel(base+0x14, 0xffffffff)
            assert q.readl(base+0x14)&0x40, 'W1C cannot release physical button'
            q.writel(base+0x4c, 0x40000)
            assert not q.readl(base+0x4c)&0x40000
            assert not q.levels.get(0), 'SPO acknowledgement must lower IRQ while held'
            q.writel(base+0xfc, 1)
            assert not q.readl(base+0x4c)&0x40000, 'held key is not a second press'
            q.writel(base+0xfc, 0)
            assert not q.readl(base+0x14)&0x40
            q.writel(base+0xfc, 1);q.writel(base+0xfc, 0)
            assert q.readl(base+0x4c)&0x40000, 'release must retain pending event'
            q.writel(base+0x38, 0)
            assert not q.levels.get(0)
            q.writel(base+0x38, 0x20)
            assert q.levels.get(0)
            q.writel(base+0x4c, 0x40000)
            assert not q.levels.get(0)
            print('PASS SNVS button level, SPO latch/W1C, held/release behavior and IRQ enable')
        finally:
            if q:q.close()
            if mp:mp.close()
            proc.terminate()
            try:_,err=proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();_,err=proc.communicate(timeout=5)
            if proc.returncode not in (0,-15):raise RuntimeError(err.decode())


if __name__ == '__main__':main()
