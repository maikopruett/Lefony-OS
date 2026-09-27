#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Single-OS shared bootloader: real ARM NAND-ROM, menu and wake checks.

Uses only the first MiB (FCB/DBBT geometry) of a private known-good single-OS
capture. Re-encodes boot and OS pages into a disposable erased emulator image.
This is not a device flash image or physical qualification.
"""
import argparse, importlib, json, struct, time
from pathlib import Path
from prime_nand_image import decode_fcb, encode_fcb, checksum, fcb_layout
from prime_dual_migration import NativeBCH, ECC, private_output, file_hash
m=importlib.import_module('test-prime-dual-boot')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('control-source','uboot','ddr-image','capsule','dtb','output'):
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();a.output=private_output(a.output);a.output.mkdir(parents=True,exist_ok=False)
    a.fixture=a.output/'nand.raw';a.rom=True;a.allow_reboot=True
    with a.control_source.open('rb') as f:controls=f.read(512*2112)
    assert len(controls)==512*2112
    boot=bytes(1024)+a.ddr_image.read_bytes();boot=boot.ljust((len(boot)+2047)//2048*2048,b'\xff')
    with a.fixture.open('wb') as f:
        for _ in range(4096):f.write(b'\xff'*(64*2112))
        f.seek(0);f.write(controls)
        with NativeBCH() as native:
            fcb,_=decode_fcb(controls[:2112]);codec=fcb_layout(fcb)
            for block in range(4):
                old=controls[block*64*2112:block*64*2112+2112]
                fc,errors=decode_fcb(old);assert not any(errors)
                fc=bytearray(fc);struct.pack_into('<4I',fc,0x68,512,1280,len(boot)//2048,len(boot)//2048)
                struct.pack_into('<I',fc,0,checksum(fc));f.seek(block*64*2112)
                f.write(encode_fcb(fc,covered_metadata=old[:32]))
            for first,data,encoding in ((512,boot,codec),(1280,boot,codec),
                    (0x400000//2048,a.capsule.read_bytes(),ECC),(0xc00000//2048,a.dtb.read_bytes(),ECC)):
                for at in range(0,len(data),2048):
                    payload,aux=encoding.swap_marker(data[at:at+2048].ljust(2048,b'\xff'),b'\xff'*encoding.metadata_bytes)
                    f.seek((first+at//2048)*2112);f.write(encoding.encode(payload,aux,native))
    vm=m.VM(a,'automatic',a.output/'auto.overlay')
    try:
        vm.wait('countdown ready');vm.capture('progress')
        vm.wait('entering calculator runtime',75);time.sleep(6);vm.capture('lefony')
        assert vm.q.readl(0x87ffd000)!=0x3548464c,'simple profile supplied dual handoff'
        start=len(vm.log.read_text())
        vm.q.writew(0x020b8008,0x8306);time.sleep(.2)
        vm.q.writel(0x020cc0fc,1);time.sleep(.3);vm.q.writel(0x020cc0fc,0)
        vm.q.writew(0x020b8008,0x0306);time.sleep(3)
        assert not vm.q.readl(0x021c8000)&1,'Off did not stop display'
        vm.q.writel(0x020cc0fc,1);time.sleep(.3);vm.q.writel(0x020cc0fc,0)
        vm.wait('countdown ready',75,after=start);vm.key(7,0)
        vm.wait('screen=1',after=start);vm.capture('wake-menu')
        assert vm.q.readl(0x020cc068)==0,'wake token not consumed'
    finally:vm.close()
    print('PASS: NAND ROM -> countdown -> Lefony; Off/On -> countdown -> Enter menu',flush=True)
    vm=m.VM(a,'navigation',a.output/'menu.overlay',held=True)
    try:
        vm.wait('screen=1 selected=0');vm.release()
        for row,col,position in [(4,5,1),(4,5,2),(5,4,1),(5,4,0),(7,1,1),(1,7,0)]:
            start=len(vm.log.read_text());vm.key(row,col);vm.wait(f'screen=1 selected={position}',after=start)
        vm.key(4,5);vm.key(7,0);time.sleep(1)
        assert 'loading OS 1' not in vm.log.read_text(),'HP activated on simple installation'
        vm.capture('hp-unavailable');vm.key(5,4);vm.key(7,0)
        vm.wait('entering calculator runtime',75)
    finally:vm.close()
    print('PASS: all arrows; HP disabled; Enter boots Lefony',flush=True)
    # A layout-5 capsule at the legacy offset must not be reinterpreted.
    poisoned=bytearray(a.capsule.read_bytes()[:2048]);struct.pack_into('<I',poisoned,0x30,0x354c464c)
    with NativeBCH() as native:
        payload,aux=ECC.swap_marker(poisoned,b'\xff'*ECC.metadata_bytes)
        raw=ECC.encode(payload,aux,native)
    overlay=a.output/'wrong-layout.overlay'
    overlay.write_bytes(b'PG2RAW1\n'+struct.pack('<B3xI',1,0x400000//2048)+raw)
    vm=m.VM(a,'wrong-layout',overlay)
    try:
        vm.wait('loading OS 0');vm.wait('screen=1');time.sleep(1)
        assert 'entering calculator runtime' not in vm.log.read_text()
        vm.capture('rejected-shared-capsule')
        for _ in range(3):vm.key(4,5)
        vm.key(7,0);vm.wait('screen=3');vm.key(4,5);vm.key(7,0);vm.wait('SDP: initialize')
    finally:vm.close()
    print('PASS: shared capsule rejected at legacy offset; recovery accessible',flush=True)
    (a.output/'qualification.json').write_text(json.dumps({'result':'PASS','physical_qualification':False,
        'scope':'single-OS NAND ROM, countdown, Enter, four arrows, disabled HP, native Off/On',
        'hashes':{n:file_hash(getattr(a,n)).hex() for n in ('uboot','ddr_image','capsule','dtb')}},indent=2)+'\n')


if __name__=='__main__':main()
