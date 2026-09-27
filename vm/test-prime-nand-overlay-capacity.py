#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise >128 MiB of distinct NAND overlay pages without a private image."""
import importlib
import subprocess
r=importlib.import_module('test-prime-g2-rom-recovery')
# Inside the modeled good region, above the default synthetic bad block.
first=392*64
commands=[]
for page in range(first,first+65537):
    commands.extend((f'writel 0x01806104 {page}', 'writel 0x01806100 0x80',
                     'writel 0x01806108 0x5a', 'writel 0x01806100 0x10'))
commands.extend(('readl 0x01806160','readl 0x01806164','readl 0x0180616c',
                 'writel 0x01806100 0x60',f'writel 0x01806104 {first}',
                 'writel 0x01806100 0xd0','readl 0x01806160',
                 'writel 0x01806100 0x00',f'writel 0x01806104 {first+65536}',
                 'readl 0x01806108'))
p=subprocess.Popen([str(r.QEMU),'-machine','hp-prime-g2','-display','none',
                    '-monitor','none','-serial','none','-qtest','stdio',
                    '-qtest-log','/dev/null'],stdin=subprocess.PIPE,
                   stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:
    try:out,err=p.communicate('\n'.join(commands)+'\n',timeout=30)
    except subprocess.TimeoutExpired:
        p.terminate();out,err=p.communicate(timeout=5)
    assert p.returncode in (0,-15),(p.returncode,err[-2000:])
    values=[int(line.split()[1],16) for line in out.splitlines() if line.startswith('OK ')]
    assert values==[65537,0,0,65537-64,0x5a],values
    print('PASS 65,537 distinct pages, no false program failures, high page survives low block erase')
finally:
    if p.poll() is None:p.kill();p.wait(timeout=5)
