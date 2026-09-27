#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic observer check: log escapes and failed attempts, never block them."""
import importlib,json,subprocess,tempfile
from pathlib import Path
r=importlib.import_module('test-prime-g2-rom-recovery')
with tempfile.TemporaryDirectory(prefix='nand-trace-') as directory:
 p=Path(directory);log=p/'writes.log'
 command=[str(r.QEMU),'-machine','hp-prime-g2','-display','none','-monitor','none','-serial','none',
          '-global','prime-g2-gpmi-bch.trace-writes=on','-qtest','stdio','-qtest-log','/dev/null','-D',str(log)]
 commands=[
  # Deliberately write to Phase 4's protected region. Observer must allow it.
  'writel 0x01806104 0x20000','writel 0x01806100 0x80','writel 0x01806108 0xa5','writel 0x01806100 0x10',
  'writel 0x01806100 0x00','writel 0x01806104 0x20000','readl 0x01806108',
  'writel 0x01806100 0x60','writel 0x01806104 0x20000','writel 0x01806100 0xd0',
  'writel 0x01806100 0x00','writel 0x01806104 0x20000','readl 0x01806108',
  # Failed program on an injected defect still appears in the observer.
  'writel 0x01806128 400','writel 0x01806104 0x6400','writel 0x01806100 0x80','writel 0x01806100 0x10',
  # An out-of-chip address must also be observed rather than silently skipped.
  'writel 0x01806104 0x40000','writel 0x01806100 0x80','writel 0x01806100 0x10',
 ]
 proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:out,err=proc.communicate('\n'.join(commands)+'\n',timeout=3)
 except subprocess.TimeoutExpired:
  proc.terminate();out,err=proc.communicate(timeout=5)
 assert proc.returncode in (0,-15),(out,err)
 reads=[int(x.split()[1],16) for x in out.splitlines() if x.startswith('OK ')];assert reads==[0xa5,0xff],reads
 events=[json.loads(x.split(': ',1)[1]) for x in log.read_text().splitlines() if x.startswith('prime-nand-write: ')]
 assert [(e['operation'],e['block']) for e in events]==[('program',2048),('erase',2048),('program',400),('program',4096)],events
 print('PASS: observer records protected writes, erases, defect and out-of-chip attempts without blocking writes')
