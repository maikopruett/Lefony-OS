#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A physical matrix switch must signal GPIO2 without CPU polling."""
import importlib
from pathlib import Path
import subprocess
import tempfile

irq = importlib.import_module('test-prime-g2-bch-irq')
r = irq.recovery


def main():
    with tempfile.TemporaryDirectory(prefix='key-irq-',dir='/tmp') as d:
        p=Path(d)
        proc=subprocess.Popen([str(r.QEMU),'-machine','hp-prime-g2','-S',
            '-global','imx6ul-lcdif.prime-g2-panel=on',
            '-display','none','-serial','none','-monitor','none',
            '-qtest',f'unix:{p}/qt,server=on,wait=off','-qtest-log','/dev/null',
            '-qmp',f'unix:{p}/qm,server=on,wait=off'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        q=mp=None
        try:
            q=irq.IRQTest(p/'qt');mp=r.QMP(p/'qm')
            q.command('irq_intercept_out /machine/soc/gpio1 sysbus-irq')
            gpio=0x020a0000;row=1<<14
            q.writel(gpio,0)
            q.writel(gpio+4,2) # Enter column drives low
            q.writel(gpio+12,3<<28) # falling edge for row 7
            q.writel(gpio+0x18,0xffffffff)
            q.writel(gpio+0x14,row)
            q.writew(0x020b8008,0x8700)
            # Read ISR, never DR/PSR: the event itself must raise the wire.
            assert q.readl(gpio+0x18)&row
            assert q.levels.get(0),q.events
            q.writel(gpio+0x18,row)
            assert not q.readl(gpio+0x18)&row
            q.writew(0x020b8008,0x700)
            assert not q.readl(gpio+0x18)&row
            # With column tri-stated, Enter cannot pull the row low.
            q.writel(gpio+4,0)
            q.writew(0x020b8008,0x8700)
            assert not q.readl(gpio+0x18)&row
            # Driving the already-held switch completes the same circuit.
            q.writel(gpio+4,2)
            assert q.readl(gpio+0x18)&row
            print('PASS GPIO keypad IRQ on switch closure and column drive; release and floating-column isolation')
        finally:
            if q:q.close()
            if mp:mp.close()
            proc.terminate()
            try:_,err=proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();_,err=proc.communicate(timeout=5)
            if proc.returncode not in (0,-15):raise RuntimeError(err.decode())


if __name__=='__main__':main()
