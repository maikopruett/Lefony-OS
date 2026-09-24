#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install progress via guest USB/storage and normal UI timers; synthetic NAND only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from cli import package
from build import lock_value,write_json
from lfapp import pack,unpack
from signing import sign,HEADER,MAGIC,public_der,openssl
from runner import Channel
from replay import Controls,control_session
from emulator_usb import PrimeUSBHost
from device import Client
from files_device import FileClient,IMPORT,WRITABLE,COMPLETE
from PIL import Image

class Transport:
    def __init__(self,host):self.host=host
    def read(self,request,value=0,index=0,length=64):return self.host.control_in(0xc0,request,value,index,length)
    def write(self,request,data=b'',value=0,index=0):self.host.control_out(0x40,request,value,index,data)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,default=ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--output',type=Path,default=ROOT/'build/app-install-progress-test')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    private=ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem'
    write_json(ROOT/'sdk/examples/counter/sdk.lock.json',lock_value(ROOT/'sdk',1))
    metadata,elf=unpack(package(ROOT/'sdk/examples/counter').read_bytes())
    metadata.update(id='progress-test',name='Counter',version='1.0.0')
    # Extra ELF file padding stretches real storage writes without changing code.
    signed=sign(pack(metadata,elf+bytes(512*1024)),private)
    with tempfile.TemporaryDirectory(prefix='lf-progress-',dir='/tmp') as name:
        folder=Path(name);uart=folder/'uart';overlay=folder/'nand.overlay'
        overlay.write_bytes(b'PG2OVL1\n')
        command=[str(ROOT/'build/qemu-prime-g2/qemu-system-arm'),'-machine','mcimx6ul-evk','-m','256M',
            '-display','none','-monitor','none','-serial',f'file:{uart}','-serial','null',
            '-chardev',f'socket,id=appcontrol,path={folder}/control,server=on,wait=off','-serial','chardev:appcontrol',
            '-qtest',f'unix:{folder}/qtest,server=on,wait=off','-qtest-log',os.devnull,
            '-qmp',f'unix:{folder}/qmp,server=on,wait=off','-global','imx6ul-lcdif.prime-g2-panel=on',
            '-global',f'prime-g2-gpmi-bch.stock-overlay={overlay}',
            '-chardev',f'socket,id=usbhost,path={folder}/usb,server=on,wait=off',
            '-global','prime-g2-usbotg-device.chardev=usbhost','-kernel',str(args.firmware),'-no-reboot']
        process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        channel=host=None
        try:
            deadline=time.monotonic()+45
            while not uart.exists() or 'entering calculator runtime' not in uart.read_text(errors='replace'):
                assert process.poll() is None and time.monotonic()<deadline,'VM failed to boot'
                time.sleep(.05)
            channel=Channel(folder/'control',process);host=PrimeUSBHost(folder/'usb');host.connect_and_enumerate()
            client=Client(Transport(host));assert client.status()['state']==2
            def wait_ms(ms):
                start=int(channel.command('TIME GET').split()[1]);deadline=time.monotonic()+30
                while int(channel.command('TIME GET').split()[1])-start<ms:
                    assert time.monotonic()<deadline,'UI timer did not advance'
                    time.sleep(.01)
            with control_session(Controls(channel,args.output)) as ui:
                def capture(label,delay=600):
                    wait_ms(delay);path=args.output/(label+'.ppm')
                    ui.execute('screendump',{'filename':str(path.resolve())})
                    image=Image.open(path).convert('RGB');image.save(args.output/(label+'.png'));return image
                def bar(image):
                    # RGB565 green progress track, 288 pixels wide on white.
                    rows=[]
                    for y in range(124,140):
                        n=sum(1 for x in range(16,304) if (lambda c: c[1]>c[0]+20 and c[1]>c[2]+20 and 50<c[1]<130)(image.getpixel((x,y))))
                        if n>=25:rows.append(n)
                    return max(rows,default=0)
                def gone(label):
                    frame=capture(label,2100)
                    assert bar(frame)<25,'App progress screen stayed open: '+label
                    return frame
                wait_ms(600);ui.key('back');baseline=capture('before')
                def upload(data,command=0x65,label='install',receive_capture=True):
                    client.write(0x63,argument=len(data))
                    midpoint=len(data)//1024*512
                    for offset in range(0,len(data),512):
                        client.write(0x64,data[offset:offset+512],offset)
                        if receive_capture and offset==midpoint:
                            frame=capture(label+'-receiving')
                            assert 130<=bar(frame)<=160,'Receiving bar does not show half progress'
                            assert sum(c==(255,255,255) for c in frame.getdata())>frame.width*frame.height*.65
                    client.write(command)
                    capture(label+'-writing',300)
                    assert client.wait()['state']==6
                upload(signed)
                gone('installed')
                entry=client.catalog()[0];assert entry['version']=='1.0.0'
                assert client.read_package(entry['slot'],len(signed))==signed
                metadata['version']='1.0.1';updated=sign(pack(metadata,elf+bytes(512*1024)),private)
                upload(updated,label='update');gone('updated')
                entry=client.catalog()[0];assert entry['version']=='1.0.1'
                assert client.read_package(entry['slot'],len(updated))==updated
                files=FileClient(client);data=bytes(range(256))*16
                state=files._begin(metadata['id'],IMPORT,'game.dat',identity=files.info(metadata['id']),length=len(data),digest=hashlib.sha256(data).digest())
                token=state['sequence'];offset=0
                while offset<len(data):
                    assert state['state']==WRITABLE
                    chunk=data[offset:offset+504];client.write(0x72,struct.pack('<II',token,offset)+chunk);offset+=len(chunk)
                    state=files._wait(sequence=token)
                    if offset==2016:assert 130<=bar(capture('app-data'))<=160
                client.write(0x74,argument=token);assert files._wait(sequence=token)['state']==COMPLETE
                gone('data-complete')
                files.export_file(metadata['id'],'game.dat',args.output/'game-readback.dat',replace=True)
                assert (args.output/'game-readback.dat').read_bytes()==data
                payload=b'LFICON1\0'+hashlib.sha256(updated).digest()+struct.pack('<II',55,56)+bytes(16)+bytes(55*56*2)
                header=HEADER.pack(MAGIC,1,len(payload),1,0,hashlib.sha256(public_der(private,private=True)).digest(),hashlib.sha256(payload).digest(),bytes(8))
                icon=header+openssl('dgst','-sha256','-sign',private,data=header)+payload
                upload(icon,0x6c,'icon');gone('icon-complete')
                client.write(0x63,argument=len(signed));client.write(0x64,signed[:512],0);capture('cancelling')
                client.write(0x67);gone('cancelled')
                client.write(0x63,argument=len(icon));bad=bytearray(icon);bad[-1]^=1
                for offset in range(0,len(bad),512):client.write(0x64,bytes(bad[offset:offset+512]),offset)
                client.write(0x6c);capture('invalid-signature',600)
                assert client.status()['state']==7;gone('failure-dismissed');client.write(0x67)
                client.write(0x63,argument=len(signed));client.write(0x64,signed[:512],0);capture('disconnecting')
                host.connect_and_enumerate();gone('disconnected')
                assert client.status()['state'] in (2,6)
                assert channel.command('PING')=='PONG'
        finally:
            if host:host.close()
            if channel:channel.close()
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            if process.stderr:process.stderr.close()
    report={'status':'passed','qualification':'emulator only','firmware_sha256':hashlib.sha256(args.firmware.read_bytes()).hexdigest(),
            'checks':['white screen and receiving progress','package install and update readback','file import progress and readback','icon install','completion dismissal','cancel dismissal','signature failure dismissal','disconnect dismissal']}
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
