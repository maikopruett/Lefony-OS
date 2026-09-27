#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""BCH DMA of sub-page payloads, using public generated codewords and canaries."""
import importlib
from pathlib import Path
import struct
import subprocess
import tempfile

from prime_gpmi_bch import Layout

irq = importlib.import_module('test-prime-g2-bch-irq')
r = irq.recovery


def main():
    geometry = Layout(0x0720a020, 0x0840a020)
    payload = bytes((i * 37 + 11) % 256 for i in range(1024))
    metadata = bytes(range(32))
    clean = geometry.encode(payload, metadata)
    corrected = bytearray(clean); corrected[72] ^= 1
    failed = bytearray(clean)
    for i in range(8):
        failed[72+i] ^= 255
    records = [clean, bytes(corrected), bytes(failed), bytes([255])*2112]
    with tempfile.TemporaryDirectory(prefix='bch-short-', dir='/tmp') as d:
        p = Path(d)
        overlay = p/'nand.overlay'
        overlay.write_bytes(b'PG2RAW1\n'+b''.join(struct.pack('<B3xI', 1, 16+i)+data for i,data in enumerate(records)))
        proc = subprocess.Popen([str(r.QEMU), '-machine', 'hp-prime-g2', '-S',
            '-display','none','-serial','none','-monitor','none',
            '-global','prime-g2-gpmi-bch.physical-pages=on',
            '-global','prime-g2-mmdc.preinitialized=on',
            '-global','prime-g2-gpmi-bch.use-ccm-clock=off',
            '-global',f'prime-g2-gpmi-bch.stock-overlay={overlay}',
            '-qtest',f'unix:{p}/qt,server=on,wait=off','-qtest-log','/dev/null',
            '-qmp',f'unix:{p}/qm,server=on,wait=off'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        q = mp = None
        try:
            q=irq.IRQTest(p/'qt');mp=r.QMP(p/'qm')
            children=mp.execute('qom-list',{'path':'/machine/unattached'})['return']
            name,=[c['name'] for c in children if c['type']=='child<prime-g2-gpmi-bch>']
            q.command(f'irq_intercept_out /machine/unattached/{name} sysbus-irq')
            def read(a,n):return bytes.fromhex(q.command(f'read {a:#x} {n}').split()[1][2:])
            q.writel(0x01808080,0x0720a020);q.writel(0x01808090,0x0840a020)
            q.writel(0x01804010,0x10000)
            for index in range(4):
                q.writel(0x01808000,0x100)
                q.writel(0x01804018,1)
                q.command('memset 0x80003000 2048 0xa5')
                q.command('memset 0x80004000 64 0x5a')
                q.writel(0x01806100,0);q.writel(0x01806104,16+index)
                words=[0,0x6048,0,1<<24,0,0x11ff,2112,0x80003000,0x80004000]
                q.command('write 0x80001000 36 0x'+struct.pack('<9I',*words).hex())
                q.writel(0x01804110,0x80001000);q.writel(0x01804140,1)
                assert q.readl(0x01804140)==0, 'short transfer stalled'
                assert q.readl(0x01808000)&1
                assert q.levels.get(1) and q.levels.get(2)
                assert read(0x80003400,1024)==bytes([0xa5])*1024,'DMA exceeded 1024-byte payload'
                status=read(0x80004020,8)
                if index in (0,1):
                    assert read(0x80003000,1024)==payload
                    assert read(0x80004000,32)==metadata
                    assert status==bytes([index])+bytes(7),status
                elif index==2:
                    assert status[0]==0xfe and status[1:]==bytes(7),status
                    assert q.readl(0x01808010)&4
                else:
                    assert status==bytes([255])*8,status
                    assert read(0x80003000,1024)==bytes([255])*1024
                print(f'PASS short BCH DMA case {index}: completion, IRQ, status and payload bounds',flush=True)
        finally:
            if q:q.close()
            if mp:mp.close()
            proc.terminate()
            try:_,err=proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill();_,err=proc.communicate(timeout=5)
            if proc.returncode not in (0,-15):raise RuntimeError(err.decode())


if __name__=='__main__':main()
