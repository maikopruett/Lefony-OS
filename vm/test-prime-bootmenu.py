#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run compiled boot-menu U-Boot with synthetic NAND and physical GPIO input.

No HP image, private dump or attached calculator is required. Captures come
from the modeled LCDIF/panel; this does not qualify electrical behavior.
"""
import argparse
import importlib
import json
import re
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import time
import zlib
r=importlib.import_module('test-prime-g2-rom-recovery')
ROOT=Path(__file__).resolve().parents[1]
def pref(generation=1,priority=0):
    b=bytearray(64);struct.pack_into('<4s4I',b,0,b'LFBP',1,1,generation,priority)
    struct.pack_into('<I',b,60,zlib.crc32(b[:60]));return bytes(b)
def fixture(path,capsule,dtb,valid=True):
    with path.open('wb') as f:
        f.write(b'PG2OVL1\n')
        inputs=[(0x400000,capsule),(0xc00000,dtb)]
        if valid:inputs.extend([(0xdc0000,pref()),(0xde0000,pref())])
        for offset,data in inputs:
            for at in range(0,len(data),2048):
                f.write(struct.pack('<B3xI',1,(offset+at)//2048))
                f.write(data[at:at+2048].ljust(2048,b'\xff')+b'\xff'*64)
class VM:
    def __init__(self,args,name,overlay,held=False,recovery=False):
        self.out=args.output/name;self.out.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='lfmenu-',dir='/tmp');self.root=Path(self.tmp.name)
        self.log=self.out/'serial.log';self.err=(self.out/'stderr.log').open('w')
        cmd=[str(r.QEMU),'-machine','hp-prime-g2','-global','prime-g2-mmdc.preinitialized=on',
             '-global','cortex-a7-arm-cpu.cntfrq=8000000',
             '-global','imx6ul-lcdif.prime-g2-panel=on','-global','prime-g2-pf1550.external-power=on',
             '-global',f'prime-g2-gpmi-bch.stock-overlay={overlay}',
             '-device',f'loader,file={args.uboot.resolve()},addr=0x87800000,force-raw=on,cpu-num=0',
             '-display','none','-monitor','none','-serial',f'file:{self.log}',
             '-d','guest_errors','-D',str(self.out/'guest.log'),
             '-qmp',f'unix:{self.root}/qmp,server=on,wait=off',
             '-qtest',f'unix:{self.root}/qt,server=on,wait=off','-qtest-log','/dev/null','-S',
             '-chardev',f'socket,id=usb,path={self.root}/usb,server=on,wait=off',
             '-global','prime-g2-usbotg-device.chardev=usb']
        self.console=None;self.prompt_count=0
        if args.command_prompt:
            index=cmd.index('-serial')
            cmd[index:index+2]=['-chardev',f'socket,id=console,path={self.root}/console,server=on,wait=off,logfile={self.log}', '-serial','chardev:console']
        self.proc=subprocess.Popen(cmd,stdout=self.err,stderr=self.err)
        if args.command_prompt:self.console=r.connect_socket(self.root/'console')
        self.q=r.QTest(self.root/'qt');self.mp=r.QMP(self.root/'qmp')
        self.q.writel(0x020a0000,0)
        self.q.writel(0x020a0004,2)  # column 0 drives low; all rows input
        assert self.q.readl(0x020a0008)&0x5554==0x5554
        self.q.writew(0x020b8008,0x8700)
        assert not self.q.readl(0x020a0008)&0x4000  # Enter closes row 7
        self.q.writel(0x020a0004,8)  # another column cannot read Enter
        assert self.q.readl(0x020a0008)&0x4000
        assert self.q.readl(0x020a0000)&2  # undriven column reads pulled-up pad
        self.q.writew(0x020b8008,0x0700)
        self.q.writel(0x020a0004,0)
        if held:self.q.writew(0x020b8008,0x8700)
        if recovery:self.q.writel(0x020cc068,0x3153464c)
        self.mp.execute('cont')
    def wait(self,text,timeout=35):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            s=self.log.read_text(errors='replace')
            prompts=s.count('=> ')
            if self.console and prompts>self.prompt_count:
                self.console.sendall(b'lfboot\n');self.prompt_count=prompts
            if text in s:return s
            if self.proc.poll() is not None:break
            time.sleep(.025)
        raise AssertionError(f'missing {text}:\n{s}\n{(self.out/"stderr.log").read_text()[-2000:]}')
    def capture(self,name):
        self.mp.execute('screendump',{'filename':str((self.out/(name+'.ppm')).resolve())})
        from PIL import Image
        image=Image.open(self.out/(name+'.ppm'));image.save(self.out/(name+'.png'))
        assert len(image.getcolors(320*240) or [])>10, 'blank panel'
    def key(self,row,col):
        for down in (True,False):
            self.q.writew(0x020b8008,(row<<8)|col|(0x8000 if down else 0));time.sleep(.15)
    def touch(self,x,y,end=None):
        # Write the model's existing ingress through I2C2 while the guest is
        # stopped between bus transactions. The guest consumes ordinary Goodix
        # reports, including its acknowledgement and release interrupt.
        end=end or (x,y)
        until=time.monotonic()+3
        while True:
            self.mp.execute('stop');control=self.q.readl(0x021a4008)
            if not control&0x20:break
            self.mp.execute('cont')
            if time.monotonic()>until:raise AssertionError('I2C2 never became idle')
            time.sleep(.01)
        try:
            self.q.writel(0x021a4008,0xb0)
            for byte in b'\x28\x90\x00'+struct.pack('<5H',x,y,*end,90):
                self.q.writel(0x021a4010,byte)
            self.q.writel(0x021a4008,0x80)
            self.q.writel(0x021a400c,0)
            self.q.writel(0x021a4008,control)
        finally:self.mp.execute('cont')
        time.sleep(.3)
    def close(self):
        self.q.close();self.mp.close();self.proc.terminate()
        try:self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=5)
        if self.console:self.console.close()
        self.err.close();self.tmp.cleanup()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--uboot',type=Path,default=ROOT/'build/lefony-uboot-bootmenu/u-boot-dtb.bin')
    p.add_argument('--capsule',type=Path,default=ROOT/'dist/lefony-os-prime-g2.zImage')
    p.add_argument('--dtb',type=Path,default=ROOT/'build/lefony-uboot-bootmenu/u-boot.dtb')
    p.add_argument('--output',type=Path,default=ROOT/'build/bootmenu-phase1/arm')
    p.add_argument('--command-prompt',action='store_true',help='explicitly run lfboot at each experimental loader prompt')
    p.add_argument('--recovery-timeout',action='store_true',help='also wait through the real 180-second recovery window')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    source=args.output/'base.overlay';fixture(source,args.capsule.read_bytes(),args.dtb.read_bytes())
    auto=args.output/'auto.overlay';shutil.copyfile(source,auto)
    vm=VM(args,'auto',auto)
    try:
        vm.wait('countdown ready');vm.capture('startup')
        vm.key(4,5);vm.touch(70,80)
        vm.wait('entering calculator runtime',60);time.sleep(20);vm.capture('lefony')
        assert 'screen=1' not in vm.log.read_text()
    finally:vm.close()
    print('PASS: automatic boot of actual Lefony capsule',flush=True)
    vm=VM(args,'pressed-enter',source)
    try:
        vm.wait('countdown ready');time.sleep(.4)
        vm.key(7,0);vm.wait('screen=1');vm.capture('pressed-enter')
        assert 'loading OS' not in vm.log.read_text()
        vm.key(7,0);vm.wait('entering calculator runtime',60)
    finally:vm.close()
    print('PASS: Enter pressed during the visible progress bar',flush=True)
    vm=VM(args,'all-arrows',source,held=True)
    try:
        vm.wait('screen=1 selected=0')
        vm.q.writew(0x020b8008,0x0700);time.sleep(.2)
        for row,col,selected in [(4,5,1),(4,5,2),(4,5,3),(4,5,3),
                                 (5,4,2),(5,4,1),(5,4,0),(5,4,0),
                                 (7,1,1),(7,1,2),(7,1,3),(7,1,3),
                                 (1,7,2),(1,7,1),(1,7,0),(1,7,0)]:
            vm.key(row,col)
            positions=re.findall(r'screen=(\d+) selected=(\d+)',vm.log.read_text())
            assert positions[-1]==('1',str(selected)),positions
        assert 'loading OS' not in vm.log.read_text()
        vm.capture('all-arrows');vm.key(7,0)
        vm.wait('entering calculator runtime',60)
    finally:vm.close()
    print('PASS: physical Up, Down, Left and Right GPIO switches navigate without activation',flush=True)
    manual=args.output/'manual.overlay';shutil.copyfile(source,manual)
    vm=VM(args,'manual',manual,held=True)
    try:
        vm.wait('screen=1');vm.capture('menu');time.sleep(.5)
        assert 'loading OS' not in vm.log.read_text()
        vm.q.writew(0x020b8008,0x0700);time.sleep(.2)
        vm.key(4,5);vm.key(7,0);vm.capture('hp-unavailable')
        assert 'loading OS' not in vm.log.read_text()
        vm.key(4,5);vm.key(7,0);vm.wait('screen=2');vm.capture('priority')
        vm.key(7,0);vm.capture('saved');vm.key(7,0)
        vm.wait('entering calculator runtime',60)
    finally:vm.close()
    print('PASS: held Enter, disabled HP, saved priority and manual Lefony boot',flush=True)
    # A new machine reads the preference saved by the previous run.
    vm=VM(args,'persisted',manual,held=True)
    try:
        vm.wait('generation=2 priority=0');vm.wait('screen=1')
        vm.q.writew(0x020b8008,0x0700);time.sleep(.15)
        vm.touch(70,80,(70,150))
        assert 'loading OS' not in vm.log.read_text()
        vm.touch(70,145);vm.capture('touch-disabled-hp')
        assert 'loading OS' not in vm.log.read_text()
        vm.touch(80,195);vm.wait('screen=2')
        vm.touch(70,80);time.sleep(.15);vm.capture('touch-saved')
        vm.touch(70,80);vm.wait('entering calculator runtime',60)
    finally:vm.close()
    print('PASS: cold preference read, Goodix swipe cancellation, disabled HP and touch boot',flush=True)
    invalid=args.output/'invalid.overlay'
    fixture(invalid,b'bad image',args.dtb.read_bytes(),valid=False)
    vm=VM(args,'invalid',invalid)
    try:
        vm.wait('preference unavailable');vm.capture('invalid-preference')
        writes=vm.q.readl(r.NAND_ECC_WRITES)
        time.sleep(.15);vm.key(4,5);vm.key(4,5);vm.key(7,0)
        vm.wait('screen=2');vm.key(7,0);vm.capture('save-rejected')
        assert vm.q.readl(r.NAND_ECC_WRITES)==writes
        vm.key(4,6);vm.key(7,0);vm.wait('loading OS 0');time.sleep(.5)
        vm.capture('invalid-image')
        assert 'Starting kernel' not in vm.log.read_text()
        vm.key(4,5);vm.key(4,5);vm.key(4,5);vm.key(7,0)
        vm.wait('screen=3');vm.key(4,5);vm.key(7,0)
        vm.wait('recovery requested');vm.capture('recovery')
        from prime_usb_host import PrimeUSBHost
        host=PrimeUSBHost(vm.root/'usb')
        try:
            device,_=host.connect_and_enumerate()
            assert device[8:12]==bytes.fromhex('feca5350')
        finally:host.close()
    finally:vm.close()
    print('PASS: invalid preferences/image, unprovisioned save rejection and USB recovery',flush=True)
    for timeout in ([False,True] if args.recovery_timeout else [False]):
        vm=VM(args,'recovery-timeout' if timeout else 'recovery-reset',source,recovery=True)
        try:
            vm.wait('consumed one-shot SDP request');vm.wait('SDP: initialize')
            assert vm.q.readl(0x020cc068)==0
            from prime_usb_host import PrimeUSBHost
            host=PrimeUSBHost(vm.root/'usb')
            try:
                device,_=host.connect_and_enumerate()
                assert device[8:12]==bytes.fromhex('feca5350')
                vm.capture('recovery')
                if not timeout:vm.mp.execute('system_reset')
                vm.wait('countdown ready',195 if timeout else 35)
                vm.wait('entering calculator runtime',60)
                assert vm.log.read_text().count('consumed one-shot SDP request')==1
            finally:host.close()
        finally:vm.close()
        print('PASS: one-shot recovery '+('timeout' if timeout else 'RESET')+' returns to actual Lefony boot',flush=True)
if __name__=='__main__':main()
