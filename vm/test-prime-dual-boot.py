#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual ARM dual-layout NAND loaders, menu and rejection checks in QEMU.

RAM entry uses the paired DCD; --rom uses NAND ROM startup. Optional
--archive verifies migrated files through HP APIs. Private fixture required.
"""
import argparse
import importlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_hp_prime_compatibility import private_output
r=importlib.import_module('test-prime-g2-rom-recovery')


class VM:
    def __init__(self,a,name,overlay,held=False):
        self.out=a.output/name;self.out.mkdir(parents=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='hp-handoff-dual5-',dir='/tmp');self.p=Path(self.tmp.name)
        self.log=self.out/'serial.log';self.err=(self.out/'stderr.log').open('w')
        binary=a.uboot.read_bytes();imx=a.ddr_image.read_bytes()
        ident=b'\x7fELF'+bytes([1,1,1])+bytes(9)
        head=struct.pack('<16sHHIIIIIHHHHHH',ident,2,40,1,0x87800000,52,0,0x05000000,52,32,1,0,0,0)
        segment=struct.pack('<8I',1,0x1000,0x87800000,0x87800000,len(binary),len(binary),7,0x1000)
        elf=self.out/'uboot.elf';elf.write_bytes((head+segment).ljust(0x1000,b'\0')+binary)
        cmd=[str(r.QEMU),'-machine','hp-prime-g2','-cpu','cortex-a7','-m','256M',
             '-global','prime-g2-mmdc.preinitialized=off',
             '-global','cortex-a7-arm-cpu.cntfrq=8000000',
             '-global','imx6ul-lcdif.prime-g2-panel=on','-global','prime-g2-pf1550.external-power=on',
             '-global','prime-g2-goodix-gt5688.drive-irq=off',
             '-global','prime-g2-gpmi-bch.physical-pages=on',
             '-global','prime-g2-gpmi-bch.trace-writes=on',
             '-global',f'prime-g2-gpmi-bch.stock-nand={a.fixture.resolve()}',
             '-global',f'prime-g2-gpmi-bch.stock-overlay={overlay.resolve()}',
             '-kernel',str(elf),'-S','-no-reboot','-display','none','-monitor','none',
             '-serial',f'file:{self.log}','-qmp',f'unix:{self.p}/qmp,server=on,wait=off',
             '-qtest',f'unix:{self.p}/qt,server=on,wait=off','-qtest-log','/dev/null',
             '-gdb',f'unix:{self.p}/gdb,server=on,wait=off',
             '-chardev',f'socket,id=usb,path={self.p}/usb,server=on,wait=off',
             '-global','prime-g2-usbotg-device.chardev=usb',
             '-d','guest_errors,unimp','-D',str(self.out/'qemu.log')]
        if a.rom:
            index=cmd.index('-kernel');del cmd[index:index+2]
        if getattr(a,'keep_on_shutdown',False):
            cmd.append('-no-shutdown')
        if getattr(a,'allow_reboot',False):
            cmd.remove('-no-reboot')
        self.proc=subprocess.Popen(cmd,stdout=self.err,stderr=self.err)
        self.q=r.QTest(self.p/'qt');self.mp=r.QMP(self.p/'qmp')
        self.q.socket.settimeout(5);self.mp.socket.settimeout(5)
        if not a.rom:
            header=struct.unpack_from('<8I',imx)
            assert imx[header[1]-header[5]:header[1]-header[5]+len(binary)]==binary
            pos=header[3]-header[5];assert imx[pos]==0xd2
            end=pos+int.from_bytes(imx[pos+1:pos+3],'big');pos+=4
            while pos<end:
                tag,length,parameter=struct.unpack_from('>BHB',imx,pos)
                assert tag==0xcc and parameter==4 and length>=12 and (length-4)%8==0 and pos+length<=end
                for at in range(pos+4,pos+length,8):self.q.writel(*struct.unpack_from('>II',imx,at))
                pos+=length
            for at in range(0,len(binary),65536):
                chunk=binary[at:at+65536]
                self.q.command(f'write {0x87800000+at:#x} {len(chunk)} 0x{chunk.hex()}')
        if getattr(a,'usb_powered_before_entry',False):
            # Real U-Boot arch_cpu_init samples USBPHY1_PWD.RXPWD1PT1.
            # A connected warm reset or ROM SDP can leave this PHY powered.
            self.q.writel(0x020c9000,0)
        if held:self.q.writew(0x020b8008,0x8700)
        self.mp.execute('cont')
    def wait(self,text,timeout=45,after=0):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            data=self.log.read_text(errors='replace') if self.log.exists() else ''
            if text in data[after:]:return data
            if self.proc.poll() is not None:break
            time.sleep(.05)
        raise AssertionError(f'missing {text}:\n{data[-4000:]}')
    def key(self,row,col):
        for down in (True,False):
            self.q.writew(0x020b8008,row<<8|col|(0x8000 if down else 0));time.sleep(.15)
    def release(self):self.q.writew(0x020b8008,0x0700);time.sleep(.2)
    def capture(self,name):
        self.mp.execute('screendump',{'filename':str((self.out/(name+'.ppm')).resolve())})
        from PIL import Image
        im=Image.open(self.out/(name+'.ppm'));im.save(self.out/(name+'.png'))
        assert len(im.getcolors(76800) or [])>10,'blank display'
    def capture_hp_logical(self):
        from PIL import Image
        ctrl,size,framebuffer=(self.q.readl(a) for a in (0x021c8000,0x021c8030,0x021c8040))
        assert size==(240<<16)|320 and (ctrl>>8)&3==3,'unexpected HP framebuffer layout'
        self.mp.execute('screendump',{'filename':str((self.out/'strict-panel.ppm').resolve())})
        target=self.out/'hp-logical.bin'
        self.mp.execute('human-monitor-command',{'command-line':f'pmemsave {framebuffer:#x} 0x4b000 "{target}"'})
        im=Image.frombytes('RGB',(320,240),target.read_bytes(),'raw','BGRX')
        im.save(self.out/'hp-logical.png')
        assert len(im.getcolors(76800) or [])>10,'blank HP logical framebuffer'
    def close(self):
        self.q.close();self.mp.close();self.proc.terminate()
        try:self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=5)
        self.err.close();self.tmp.cleanup()


def erased_blocks(path,blocks):
    with path.open('wb') as f:
        f.write(b'PG2RAW1\n')
        for b in blocks:f.write(struct.pack('<B3xI',2,b))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixture',type=Path,required=True)
    p.add_argument('--uboot',type=Path,required=True)
    p.add_argument('--ddr-image',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--archive',type=Path,help='verify every archived file through HP APIs')
    p.add_argument('--rom',action='store_true',help='use NAND ROM entry with no RAM code or DCD replay')
    p.add_argument('--usb-powered-before-entry',action='store_true',
                   help='exercise startup with inherited powered USB PHY')
    a=p.parse_args();a.output=private_output(a.output);a.output.mkdir(parents=True,exist_ok=False)
    a.fixture=a.fixture.resolve();a.uboot=a.uboot.resolve();a.ddr_image=a.ddr_image.resolve()
    vm=VM(a,'auto-lefony',a.output/'auto.overlay')
    try:
        vm.wait('Dual boot: countdown ready');vm.capture('startup')
        vm.wait('entering calculator runtime',75);time.sleep(6);vm.capture('lefony')
        assert vm.q.readl(0x87ffd000)==0x3548464c
    finally:vm.close()
    print('PASS signed NAND descriptor, relocated Lefony and valid layout handoff',flush=True)
    # Save HP as priority using normal GPIO keys; a new machine must read it.
    overlay=a.output/'priority.overlay'
    vm=VM(a,'set-hp-priority',overlay,held=True)
    try:
        vm.wait('screen=1 selected=0');vm.release()
        vm.key(4,5);vm.key(4,5);vm.key(7,0);vm.wait('screen=2')
        vm.key(4,5);vm.key(7,0);vm.wait('screen=1')
        vm.capture('hp-priority')
    finally:vm.close()
    vm=VM(a,'auto-hp',overlay)
    try:
        vm.wait('Dual boot: countdown ready');vm.wait('HP RAM: research-256 confinement applied')
        vm.wait('HP RAM: verified V15751 os');time.sleep(5)
        assert [vm.q.readl(0x807bdef8+o) for o in (0x14,0x18,0xf4,0xf8)]==[392,2047,392,2047]
        if a.archive:
            script=vm.out/'archive.gdb'
            helper=ROOT/'vm/prime_hp_archive_gdb.py'
            script.write_text('set pagination off\nset confirm off\nset architecture arm\n'+
                'file '+json.dumps(str(vm.out/'uboot.elf'))+'\ntarget remote '+str(vm.p/'gdb')+'\npython\nARCHIVE='+repr(str(a.archive.resolve()))+
                '\nEXPECTED_END=2047\nexec(compile(open('+repr(str(helper))+').read(), "archive-check", "exec"))\nend\ndetach\nquit\n')
            with (vm.out/'archive.log').open('w') as log:
                subprocess.run(['arm-none-eabi-gdb','-q','-nx','-batch','-x',str(script)],
                               stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
            assert 'phase5-logical: {"result": "PASS"' in (vm.out/'archive.log').read_text()
            vm.mp.execute('cont')
        vm.capture_hp_logical()
    finally:vm.close()
    print('PASS cold saved HP priority, NAND HP image and runtime confinement bounds',flush=True)
    vm=VM(a,'one-time-lefony',overlay,held=True)
    try:
        vm.wait('screen=1');vm.release();vm.key(5,4);vm.key(7,0)
        vm.wait('entering calculator runtime',75)
    finally:vm.close()
    print('PASS HP priority overridden by Enter menu selection of Lefony',flush=True)
    vm=VM(a,'priority-unchanged',overlay)
    try:
        vm.wait('HP RAM: verified V15751 os')
    finally:vm.close()
    vm=VM(a,'set-lefony-priority',overlay,held=True)
    try:
        vm.wait('screen=1');vm.release()
        vm.key(4,5);vm.key(7,0);vm.wait('screen=2')
        vm.key(5,4);vm.key(7,0);vm.wait('screen=1')
    finally:vm.close()
    vm=VM(a,'cold-lefony-priority',overlay)
    try:vm.wait('entering calculator runtime',75)
    finally:vm.close()
    print('PASS one-time selection retains HP priority; changed Lefony priority persists cold',flush=True)
    for name,blocks in [('missing-layout' ,[256,257]),('missing-hp',[2048]),('missing-lefony',[2128])]:
        target=a.output/(name+'.overlay');erased_blocks(target,blocks)
        vm=VM(a,name,target,held=name=='missing-hp')
        try:
            if name=='missing-layout':vm.wait('Dual boot: recovery required')
            elif name=='missing-hp':
                vm.wait('screen=1');vm.release();vm.key(4,5);vm.key(7,0)
                vm.wait('loading OS 1');time.sleep(1)
                assert 'HP RAM: verified' not in vm.log.read_text()
                vm.capture('rejected')
            else:
                vm.wait('loading OS 0');time.sleep(1)
                assert 'Starting kernel' not in vm.log.read_text()
                vm.capture('rejected')
        finally:vm.close()
        print('PASS '+name+' fails closed',flush=True)
    (a.output/'qualification.json').write_text(json.dumps({'result':'PASS tested NAND loaders and menu',
        'scope':('NAND ROM cold boots' if a.rom else 'RAM-started U-Boot with paired DCD')+('; restored archive verified through HP APIs' if a.archive else '; logical restore not asserted'),
        'physical_installed':False,
        'usb_powered_before_entry':a.usb_powered_before_entry,
        'logical_archive_verified':bool(a.archive),
        'hashes':{name:__import__('hashlib').sha256(path.read_bytes()).hexdigest()
                  for name,path in [('nand',a.fixture),('uboot',a.uboot),('ddr_image',a.ddr_image),('qemu',r.QEMU)]}},indent=2)+'\n')


if __name__=='__main__':main()
