#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Long-press drag, edge scrolling and NAND persistence through normal Goodix input."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from runner import Channel
from replay import Controls,control_session
from emulator_usb import PrimeUSBHost
from device import Client
from cli import package
from build import write_json,lock_value
from signing import sign
from PIL import Image

class Transport:
    def __init__(self,host):self.host=host
    def read(self,request,value=0,index=0,length=64):return self.host.control_in(0xc0,request,value,index,length)
    def write(self,request,data=b'',value=0,index=0):self.host.control_out(0x40,request,value,index,data)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,default=ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--output',type=Path,default=ROOT/'build/home-app-order-test')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    write_json(ROOT/'sdk/examples/counter/sdk.lock.json',lock_value(ROOT/'sdk',1))
    private=ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem';public=ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'
    signed=sign(package(ROOT/'sdk/examples/counter').read_bytes(),private)
    with tempfile.TemporaryDirectory(prefix='lf-order-',dir='/tmp') as directory:
        folder=Path(directory);overlay=folder/'nand.overlay';overlay.write_bytes(b'PG2OVL1\n')
        def run(round):
            uart=folder/f'uart{round}'
            command=[str(ROOT/'build/qemu-prime-g2/qemu-system-arm'),'-machine','mcimx6ul-evk','-m','256M','-display','none','-monitor','none',
                '-serial',f'file:{uart}','-serial','null','-chardev',f'socket,id=appcontrol,path={folder}/control,server=on,wait=off','-serial','chardev:appcontrol',
                '-qtest',f'unix:{folder}/qtest,server=on,wait=off','-qtest-log',os.devnull,'-qmp',f'unix:{folder}/qmp,server=on,wait=off',
                '-global','imx6ul-lcdif.prime-g2-panel=on','-global',f'prime-g2-gpmi-bch.stock-overlay={overlay}',
                '-chardev',f'socket,id=usbhost,path={folder}/usb,server=on,wait=off','-global','prime-g2-usbotg-device.chardev=usbhost',
                '-kernel',str(args.firmware),'-no-reboot']
            process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE);host=channel=None
            try:
                deadline=time.monotonic()+45
                while not uart.exists() or 'entering calculator runtime' not in uart.read_text(errors='replace'):
                    assert process.poll() is None and time.monotonic()<deadline,'VM did not boot'
                    time.sleep(.05)
                channel=Channel(folder/'control',process);host=PrimeUSBHost(folder/'usb');host.connect_and_enumerate();client=Client(Transport(host))
                def wait(ms):
                    start=int(channel.command('TIME GET').split()[1]);end=time.monotonic()+30
                    while int(channel.command('TIME GET').split()[1])-start<ms:
                        assert time.monotonic()<end,'guest clock stopped'
                        time.sleep(.01)
                def touch(text,ms=100):
                    assert channel.command('TOUCH FRAME '+text)=='OK';wait(ms)
                def app(index):
                    state=channel.command('STATE');assert state.startswith(f'STATE app={index} '),state
                with control_session(Controls(channel,args.output)) as ui:
                    def capture(label):
                        path=args.output/(label+'.ppm');ui.execute('screendump',{'filename':str(path.resolve())})
                        image=Image.open(path).convert('RGB');image.save(args.output/(label+'.png'));return image
                    def tap(x,y):touch(f'1 0 {x} {y}');touch('0',400)
                    wait(600);ui.key('back');wait(600);app(0)
                    if round==0:
                        before=capture('before')
                        # Home's labels should show selection only during keypad
                        # navigation. Even a clipped arrow restores the feedback.
                        label_strip=(0,98,312,124)
                        labels=lambda image:image.crop(label_strip).tobytes()
                        ui.key('left');wait(100)
                        assert labels(capture('key-highlight'))!=labels(before)
                        # Finger-down must hide both the old keypad selection
                        # and the table's temporary pressed-cell highlight.
                        touch('1 0 160 68',100)
                        assert labels(capture('touch-no-highlight'))==labels(before)
                        touch('2 0 160 68 1 240 68',100);touch('0',400)
                        assert labels(capture('cancel-no-highlight'))==labels(before)
                        ui.key('right');wait(100)
                        assert labels(capture('key-highlight-restored'))!=labels(before)
                        ui.key('left');wait(100)
                        # Release after a swipe must not restore the old
                        # selected label, including after cells are recycled.
                        touch('1 0 280 210',100);touch('1 0 280 40',100);touch('0',400)
                        app(0);capture('swipe-no-highlight')
                        touch('1 0 280 40',100);touch('1 0 280 210',100);touch('0',400)
                        assert labels(capture('swipe-return-no-highlight'))==labels(before)
                        # Continue with the existing drag, tap and persistence
                        # checks; selection visibility must not change them.
                        touch('1 0 160 68',1000);capture('held')
                        touch('1 0 52 68',400);capture('dragging')
                        touch('0',2000);app(0);after=capture('functions-first')
                        assert before.crop((24,40,82,95)).tobytes()!=after.crop((24,40,82,95)).tobytes()
                        # Tapping the new first icon resolves its original app identity.
                        tap(52,68);app(2);ui.key('apps');wait(400);app(0)
                        # A second contact cancels the preview and never launches.
                        touch('1 0 52 68',1000);touch('1 0 264 68',300)
                        touch('2 0 264 68 1 200 160',300);touch('0',600);app(0)
                        cancelled=capture('multitouch-cancelled')
                        assert cancelled.crop((24,40,82,95)).tobytes()==after.crop((24,40,82,95)).tobytes()
                        tap(52,68);app(2);ui.key('apps');wait(400);app(0)
                        client.install(signed,[public]);wait(2100)
                        # Ordinary swipe remains a scroll; long-press is required.
                        touch('1 0 280 210',100);touch('1 0 280 40',100);touch('0',400);app(0)
                        capture('scrolled')
                        # Pick up the last installed app, hold at the top edge to
                        # scroll through earlier rows, then drop in the first slot.
                        touch('1 0 264 204',1000);capture('installed-held')
                        touch('1 0 52 26',2300);capture('edge-scrolling')
                        touch('1 0 52 68',300);touch('0',2100);app(0)
                        capture('counter-first')
                        tap(52,68);app(12);ui.key('back');wait(400);app(0)
                        wait(2100)
                    else:
                        restored=capture('cold-boot')
                        expected=Image.open(args.output/'counter-first.png').convert('RGB')
                        assert restored.crop((24,40,82,95)).tobytes()==expected.crop((24,40,82,95)).tobytes(),'Order did not survive a cold boot'
                        tap(52,68);app(12);ui.key('back');wait(400);app(0)
            finally:
                if host:host.close()
                if channel:channel.close()
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                if process.stderr:process.stderr.close()
        run(0);run(1)
    report={'status':'passed','qualification':'emulator only','firmware_sha256':hashlib.sha256(args.firmware.read_bytes()).hexdigest(),
            'checks':['keypad-only selection feedback','touch down and cancellation hide highlights','swipe release keeps highlights hidden',
                      'long-press and drag built-in app','tap launches reordered identity','multitouch cancels preview','ordinary swipe scrolls',
                      'drag installed app across rows with edge scrolling','drop does not launch','cold NAND persistence']}
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
