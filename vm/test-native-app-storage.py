#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Native firmware/USB integration on synthetic NAND; never opens USB hardware."""
import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import socket
import json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from cli import package
from build import lock_value,write_json
from runner import Channel
from device import Client, FIRST_BLOCK
from signing import sign, HEADER, MAGIC, public_der, openssl
from lfapp import pack,unpack
from prime_usb_host import PrimeUSBHost, USBError
from PIL import Image
import io

class Transport:
    def __init__(self,host):self.host=host
    def read(self,request,value=0,index=0,length=64):return self.host.control_in(0xc0,request,value,index,length)
    def write(self,request,data=b'',value=0,index=0):self.host.control_out(0x40,request,value,index,data)

def marker():
    page=bytearray(b'\xff'*2048);page[:8]=b'LFAVOL1\0'
    struct.pack_into('<5I',page,8,1,FIRST_BLOCK,512,2048,64)
    page[32:64]=hashlib.sha256(b'synthetic pre-provisioned VM fixture').digest()
    page[-32:]=hashlib.sha256(page[:-32]).digest()
    return bytes(page)+b'\xff'*64

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--signing-key',required=True,type=Path)
    parser.add_argument('--public-key',required=True,type=Path)
    parser.add_argument('--preprovisioned',action='store_true',help='Also exercise an existing legacy volume')
    parser.add_argument('--many-apps',action='store_true',help='Install nine apps and launch the ninth from the normal menu');args=parser.parse_args()
    write_json(ROOT/'sdk/examples/counter/sdk.lock.json',lock_value(ROOT/'sdk',1))
    unsigned=package(ROOT/'sdk/examples/counter').read_bytes()
    signed=sign(unsigned,args.signing_key)
    screenshots=ROOT/'build/sdk-installed-counter';screenshots.mkdir(exist_ok=True)
    colors=(0xf800,0x07e0,0x001f,0xffe0)
    pixels=b''.join(struct.pack('<H',colors[(y>=28)*2+(x>=27)]) for y in range(56) for x in range(55))
    def signed_icon(binding,artwork=pixels):
        payload=b'LFICON1\0'+binding+struct.pack('<II',55,56)+bytes(16)+artwork
        der=public_der(args.signing_key,private=True)
        header=HEADER.pack(MAGIC,1,len(payload),1,0,hashlib.sha256(der).digest(),hashlib.sha256(payload).digest(),bytes(8))
        return header+openssl('dgst','-sha256','-sign',args.signing_key,data=header)+payload
    icon=signed_icon(hashlib.sha256(signed).digest())
    def check_icon(frame):
        image=Image.open(io.BytesIO(frame)).convert('RGB')
        counts=dict((rgb,n) for n,rgb in image.getcolors(image.width*image.height))
        for rgb in ((255,0,0),(0,255,0),(0,0,255),(255,255,0)):
            assert counts.get(rgb,0)>=700,(rgb,counts.get(rgb,0))
    saved_frame=None
    with tempfile.TemporaryDirectory(prefix='lf-app-usb-',dir='/tmp') as directory:
        directory=Path(directory);overlay=directory/'nand.overlay'
        overlay.write_bytes(b'PG2OVL1\n'+b''.join(struct.pack('<B3xI',1,(FIRST_BLOCK+i)*64)+marker() for i in range(2) if args.preprovisioned))
        def run(round):
            nonlocal saved_frame
            uart=directory/f'uart{round}';usb=directory/'usb'
            if usb.exists():usb.unlink()
            command=[str(ROOT/'build/qemu-prime-g2/qemu-system-arm'),'-machine','mcimx6ul-evk','-m','256M',
                     '-display','none','-monitor','none','-serial',f'file:{uart}',
                     '-qtest',f'unix:{directory}/qt{round},server=on,wait=off','-qtest-log','/dev/null',
                     '-serial','null','-chardev',f'socket,id=appcontrol,path={directory}/control{round},server=on,wait=off','-serial','chardev:appcontrol',
                     '-qmp',f'unix:{directory}/qmp{round},server=on,wait=off',
                     '-global','imx6ul-lcdif.prime-g2-panel=on',
                     '-global',f'prime-g2-gpmi-bch.stock-overlay={overlay}',
                     '-chardev',f'socket,id=usbhost,path={usb},server=on,wait=off',
                     '-global','prime-g2-usbotg-device.chardev=usbhost',
                     '-kernel',str(ROOT/'dist/lefony-os-prime-g2-vm-native.elf'),'-no-reboot']
            process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            host=None
            try:
                deadline=time.monotonic()+30
                while not uart.exists() or 'entering calculator runtime' not in uart.read_text(errors='replace'):
                    if process.poll() is not None or time.monotonic()>deadline:raise AssertionError('VM did not boot')
                    time.sleep(.05)
                qt=socket.socket(socket.AF_UNIX);qt.connect(str(directory/f'qt{round}'));stream=qt.makefile('rwb',buffering=0)
                def q(cmd):
                    stream.write((cmd+'\n').encode())
                    while True:
                        line=stream.readline().decode()
                        if line.startswith('OK'):return line.strip()
                channel=Channel(directory/f'control{round}',process)
                monitor=socket.socket(socket.AF_UNIX);monitor.connect(str(directory/f'qmp{round}'));qmp=monitor.makefile('rwb',buffering=0);json.loads(qmp.readline())
                def execute(name,args=None):
                    qmp.write((json.dumps({'execute':name,'arguments':args or {}})+'\n').encode())
                    while True:
                        reply=json.loads(qmp.readline())
                        if 'return' in reply:return reply
                        if 'error' in reply:raise AssertionError(reply)
                execute('qmp_capabilities')
                def wait_guest_ms(milliseconds):
                    # Home icon refresh runs on a 300 ms guest timer. Host
                    # sleeps alone can capture before that timer fires in TCG.
                    start=int(channel.command('TIME GET').split()[1])
                    deadline=time.monotonic()+10
                    while int(channel.command('TIME GET').split()[1])-start<milliseconds:
                        assert time.monotonic()<deadline,'guest timer stopped during storage UI check'
                        time.sleep(.01)
                def press(row,col):
                    # Observe normal event dispatch while holding a native-app
                    # key. A timer read alone does not prove keyboard delivery.
                    native='STATE app=12 ' in channel.command('STATE')
                    tracked=native and (row,col)==(7,0)
                    sequence=channel.command('APP DIAG 7') if tracked else None
                    try:
                        q(f'writew 0x020b8008 {((row<<8)|col|0x8000):#x}')
                        if tracked:
                            deadline=time.monotonic()+5
                            while channel.command('APP DIAG 7')==sequence:
                                assert time.monotonic()<deadline,'normal dispatch did not deliver Confirm'
                                time.sleep(.01)
                        else:
                            time.sleep(.25)
                    finally:
                        q(f'writew 0x020b8008 {((row<<8)|col):#x}')
                        time.sleep(.75) # Normal driver release/debounce.
                def capture(name):
                    wait_guest_ms(600);path=screenshots/(name+'.ppm');execute('screendump',{'filename':str(path)});return path.read_bytes()
                host=PrimeUSBHost(usb);host.connect_and_enumerate();client=Client(Transport(host))
                # Startup must finish before any host mount/provision command.
                connected=client.status();assert connected['state']==2 and connected['reserved']&2,connected
                storage=struct.unpack('<12I',client.read(0x6b,48))
                assert storage[:3]==(0x5341464c,2,64*1024*1024)
                assert storage[6]==round and storage[7]==131072,storage
                assert storage[5]>59*1024*1024 and storage[5]==storage[3]-storage[10],storage
                if round==0:print('PASS: OS reserved app space before USB; read-only inventory reports capacity',flush=True)
                assert connected['reserved']&8,'Firmware does not advertise icons'
                def upload_icon(value):
                    client.write(0x63,argument=len(value))
                    for offset in range(0,len(value),512):client.write(0x64,value[offset:offset+512],offset)
                    client.write(0x6c)
                if round==0:
                    assert client.catalog()==[]
                    client.write(0x63,argument=len(signed));client.cancel_upload()
                    assert client.connect()['state']==2 and client.catalog()==[]
                    print('PASS: cancelled upload returns to ready without remounting',flush=True)
                    # Missing backup receipt cannot provision an existing volume.
                    try:host.control_out(0x40,0x62,payload=bytes(32))
                    except USBError:pass
                    else:raise AssertionError('Provision without backup was accepted')
                    press(4,6);press(4,4);press(5,6) # Dismiss USB, Apps, then Settings via its menu shortcut.
                    before=capture('menu-before-install')
                    installed=client.install(signed,[args.public_key]);assert installed['id']=='counter'
                    assert client.read_package(installed['slot'],len(signed))==signed
                    print('PASS: signed ABI 1 upload, atomic commit and USB byte readback',flush=True)
                    wait_guest_ms(500);assert capture('menu-after-install')!=before,'Installed tile did not appear live'
                    corrupt=bytearray(icon);corrupt[-1]^=1
                    for invalid in (signed_icon(bytes(32)),bytes(corrupt)):
                        upload_icon(invalid)
                        try:client.wait()
                        except RuntimeError:pass
                        else:raise AssertionError('Invalid icon was accepted')
                        client.write(0x67)
                        assert client.read(0x6d,32,0)==bytes(32)
                    upload_icon(icon);assert client.wait()['state']==6
                    assert client.read(0x6d,32,0)==hashlib.sha256(icon).digest()
                    assert client.catalog()[0]['generation']==1
                    assert client.read_package(0,len(signed))==signed
                    print('PASS: icon signature and package binding; persisted readback; executable unchanged',flush=True)
                    press(1,0) # EE selects the twelfth tile: the installed Counter.
                    assert 'home_row=3 home_column=2' in channel.command('STATE')
                    check_icon(capture('menu-counter-selected'))
                    replacement=signed_icon(hashlib.sha256(signed).digest(),struct.pack('<H',0xf81f)*(55*56))
                    upload_icon(replacement);assert client.wait()['state']==6
                    frame=Image.open(io.BytesIO(capture('menu-icon-replaced'))).convert('RGB')
                    assert sum(1 for pixel in frame.get_flattened_data() if pixel==(255,0,255))>=3000,'Cached menu icon did not refresh without input'
                    upload_icon(icon);assert client.wait()['state']==6
                    check_icon(capture('menu-icon-restored'))
                    print('PASS: replacing a cached icon redraws the visible tile without user input',flush=True)
                    press(7,0);initial=capture('initial');wait_guest_ms(1000);press(7,0);saved_frame=capture('saved');assert initial!=saved_frame
                    press(4,6);client.wait();assert client.catalog()[0]['generation']==2
                    assert 'STATE app=0 ' in channel.command('STATE'),'Back did not return directly to the main menu'
                    print('PASS: normal launcher/key input commits app-private data on exit',flush=True)
                else:
                    entries=client.catalog();assert len(entries)==1 and entries[0]['id']=='counter'
                    assert client.read_package(entries[0]['slot'],len(signed))==signed
                    press(4,6);press(4,4);press(1,0)
                    assert 'home_row=3 home_column=2' in channel.command('STATE')
                    check_icon(capture('menu-after-restart'))
                    assert client.read(0x6d,32,0)==hashlib.sha256(icon).digest()
                    print('PASS: exact icon colors rendered through the home menu, including cold restart',flush=True)
                    # Goodix touch traverses the normal menu table/controller.
                    assert channel.command('TOUCH FRAME 1 0 265 180')=='OK';wait_guest_ms(250)
                    assert channel.command('TOUCH FRAME 0')=='OK';wait_guest_ms(500)
                    assert capture('restored')==saved_frame,'Saved app data did not survive cold restart'
                    press(4,6);client.wait()
                    client.remove('counter');assert client.catalog()==[]
                    wait_guest_ms(500);capture('menu-after-remove')
                    assert 'STATE app=0 home_row=3 home_column=1' in channel.command('STATE'),'Removed tile remained selected'
                    press(5,7) # Settings shortcut must never open the hidden runtime.
                    assert 'STATE app=11 ' in channel.command('STATE')
                    print('PASS: cold restart retains package and app data; removal clears catalog',flush=True)
                    if args.many_apps:
                        metadata,code=unpack(unsigned)
                        for i in range(9):
                            item=sign(pack({**metadata,'id':f'extra-{i:02}','name':f'Extra {i+1}'},code),args.signing_key)
                            assert client.install(item,[args.public_key])['id']==f'extra-{i:02}'
                            if (i+1)%3==0:print(f'Installed and verified {i+1} apps in shared storage',flush=True)
                        assert len(client.catalog())==9
                        metrics=struct.unpack('<12I',client.read(0x6b,48));assert metrics[6]==9 and metrics[5]>58*1024*1024,metrics
                        press(4,4) # Apps, retaining the Settings cell at row 3, column 1.
                        for _ in range(3):press(4,5)
                        assert 'home_row=6 home_column=1' in channel.command('STATE')
                        capture('ninth-app-selected');press(7,0)
                        assert 'STATE app=12 ' in channel.command('STATE'),'Ninth app was not launched'
                        before=capture('ninth-app');press(7,0);assert capture('ninth-app-counted')!=before
                        press(4,6);client.wait();assert client.catalog()[8]['generation']==2
                        client.remove('extra-00')
                        entries=client.catalog();assert len(entries)==8 and entries[-1]['id']=='extra-08' and entries[-1]['generation']==2
                        print('PASS: nine installed apps share storage; ninth launches and saves data; deletion reindexes catalog',flush=True)
                channel.close();qmp.close();monitor.close();stream.close();qt.close()
            finally:
                if host:host.close()
                process.terminate()
                try:_,error=process.communicate(timeout=5)
                except subprocess.TimeoutExpired:process.kill();_,error=process.communicate()
                if process.returncode not in (0,-15):print(error.decode(errors='replace')[-2000:],file=sys.stderr)
        run(0);run(1)

if __name__=='__main__':main()
