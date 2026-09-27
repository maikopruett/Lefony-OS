#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""ARM ROM-boot rejection/fallback checks with valid physical BCH codewords."""
import argparse
import importlib
import json
from pathlib import Path
import struct
import zlib
from prime_dual_migration import payload,ECC,read_block,NativeBCH,private_output,file_hash
from prime_dual_boot_contract import record

m=importlib.import_module('test-prime-dual-boot')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','uboot','ddr-image','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.rom=True;a.output=private_output(a.output);a.output.mkdir(parents=True,exist_ok=False)
    hashes={name:file_hash(path).hex() for name,path in
            [('nand',a.fixture),('uboot',a.uboot),('imx',a.ddr_image),('qemu',m.r.QEMU)]}
    with NativeBCH() as native:
        original=payload(read_block(a.fixture,256)[:2112],native)
        def overlay(name,pages,erased=()):
            path=a.output/(name+'.overlay')
            with path.open('wb') as f:
                f.write(b'PG2RAW1\n')
                for block in sorted(set(pages)|set(erased)):
                    f.write(struct.pack('<B3xI',2,block))
                    if block in pages:
                        data,aux=ECC.swap_marker(bytes(pages[block]),b'\xff'*10)
                        f.write(struct.pack('<B3xI',1,block*64));f.write(ECC.encode(data,aux,native))
            return path
        tested=[]
        for name,at in [('bad-signature',364),('wrong-layout',96),('wrong-profile',128),('bad-crc',2044)]:
            data=bytearray(original);data[at]^=1
            if name!='bad-crc':struct.pack_into('<I',data,2044,zlib.crc32(data[:2044]))
            vm=m.VM(a,name,overlay(name,{256:data,257:data}))
            try:vm.wait('Dual boot: recovery required');assert 'loading OS' not in vm.log.read_text()
            finally:vm.close()
            tested.append(name);print('PASS',name,flush=True)
        data=bytearray(original);data[20]^=1;struct.pack_into('<I',data,2044,zlib.crc32(data[:2044]))
        recovery=record(2,'recovery',original[20:52])
        for name,pages in [('conflicting-transactions',{256:data}),('newer-recovery-record',{256:recovery})]:
            vm=m.VM(a,name,overlay(name,pages))
            try:vm.wait('Dual boot: recovery required')
            finally:vm.close()
            tested.append(name);print('PASS',name,flush=True)
        vm=m.VM(a,'single-layout-copy',overlay('single-layout-copy',{},[256]))
        try:vm.wait('entering calculator runtime',75)
        finally:vm.close()
        tested.append('single-layout-copy');print('PASS single-layout-copy',flush=True)
        # Exercise actual ROM fallback, rather than the host route validator.
        for name,blocks in [('missing-primary-boot',range(240,248)),
                            ('missing-secondary-boot',range(248,256)),
                            ('last-fcb-copy',[0,1,2])]:
            vm=m.VM(a,name,overlay(name,{},blocks))
            try:vm.wait('entering calculator runtime',75)
            finally:vm.close()
            tested.append(name);print('PASS',name,flush=True)
        prefs={}
        for block in (260,261):
            data=bytearray(payload(read_block(a.fixture,block)[:2112],native))
            struct.pack_into('<I',data,8,1) # old preference profile
            struct.pack_into('<I',data,60,zlib.crc32(data[:60]))
            prefs[block]=data
        vm=m.VM(a,'legacy-preferences',overlay('legacy-preferences',prefs))
        try:vm.wait('Dual boot: menu ready');assert 'countdown ready' not in vm.log.read_text()
        finally:vm.close()
        tested.append('legacy-preferences');print('PASS legacy-preferences',flush=True)
    for name,path in [('nand',a.fixture),('uboot',a.uboot),('imx',a.ddr_image),('qemu',m.r.QEMU)]:
        assert file_hash(path).hex()==hashes[name],'qualification input changed'
    (a.output/'qualification.json').write_text(json.dumps({'result':'PASS','cases':tested,'hashes':hashes,
        'scope':'actual ARM bootloader from NAND ROM; no physical installation'},indent=2)+'\n')


if __name__=='__main__':main()
