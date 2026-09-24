#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise real guest ChipIdea DMA, RAM staging and legacy fallback. No hardware."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from emulator_usb import PrimeUSBHost,USBError,ion_crc32
from bulk_transfer import upload,status,MAGIC,available


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu',type=Path,default=ROOT/'build/qemu-prime-g2/qemu-system-arm')
    parser.add_argument('--firmware',type=Path,default=ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
    args=parser.parse_args();report={'qualification':'emulator only; no physical throughput claim'}
    with tempfile.TemporaryDirectory(prefix='lf-bulk-',dir='/tmp') as folder:
        folder=Path(folder);uart=folder/'uart';usb=folder/'usb';host=None
        command=[str(args.qemu),'-machine','mcimx6ul-evk','-m','256M','-display','none','-monitor','none',
            '-serial',f'file:{uart}','-chardev',f'socket,id=usbhost,path={usb},server=on,wait=off',
            '-global','prime-g2-usbotg-device.chardev=usbhost','-kernel',str(args.firmware),'-no-reboot']
        process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+45
            while not uart.exists() or 'entering calculator runtime' not in uart.read_text(errors='replace'):
                if process.poll() is not None or time.monotonic()>deadline:raise AssertionError('VM failed to boot')
                time.sleep(.05)
            host=PrimeUSBHost(usb);host.connect_and_enumerate()
            assert available(host.control_in(0x80,6,0x200,0,32))
            def read(request,value=0,index=0,length=64):return host.control_in(0xc0,request,value,index,length)
            def write(request,data=b'',value=0,index=0):host.control_out(0x40,request,value,index,data)
            def arg(request,value):write(request,value=value&65535,index=value>>16)
            def send(data):
                for offset in range(0,len(data),16384):host.endpoint_out(1,data[offset:offset+16384])
            def rejected(request,data=b'',value=0):
                try:write(request,data,value=value)
                except USBError:return
                raise AssertionError('Malformed/stale command was accepted')
            profile=read(0x56,length=392)
            assert struct.unpack_from('<5I',profile)==(0x3150464c,1,392,3000000,9)
            assert struct.unpack_from('<I',profile,24)==(0,) # VM is never physical evidence.
            rejected(0x56) # Timings are read-only; no reset/erase/write command.
            runtime=read(0x57,length=64)
            assert struct.unpack_from('<3I',runtime)==(0x5452464c,1,64)
            assert not any(struct.unpack_from('<3I',runtime,52))
            rejected(0x57)
            for value,index,length in ((1,0,64),(0,1,64),(0,0,63),(0,0,65)):
                try:read(0x57,value=value,index=index,length=length)
                except USBError:pass
                else:raise AssertionError('Malformed runtime report query accepted')
            payload=bytearray(bytes(range(251))*263);payload=payload[:65549]
            struct.pack_into('<I',payload,0x24,0x016F2818);struct.pack_into('<I',payload,0x2c,len(payload))
            crc=ion_crc32(payload)
            for fast in (False,True):
                arg(0x44,len(payload));start=time.monotonic()
                if fast:upload(read,write,send,1,payload)
                else:
                    for offset in range(0,len(payload),512):write(0x45,payload[offset:offset+512],offset&65535,offset>>16)
                report['bulk_seconds' if fast else 'legacy_seconds']=time.monotonic()-start
                arg(0x46,crc)
                recovery=struct.unpack('<8I',read(0x43,length=32));assert recovery[2]==2 and recovery[5:7]==(len(payload),crc)
                write(0x47)
            # Full 512-byte USB packets must not prematurely complete a 16 KiB dTD.
            arg(0x44,len(payload));write(0x59,struct.pack('<6I',MAGIC,1,1,len(payload),0,0))
            for offset in range(0,len(payload),512):host.endpoint_out(1,payload[offset:offset+512])
            s=status(read);assert s[2]==2 and s[6]==len(payload);arg(0x5a,s[3]);assert status(read)[2]==4
            arg(0x46,crc);write(0x47)
            # Interrupted DMA is flushed, never applied, and cannot be resumed by
            # an old session token. Replacement SETUP must not imply commit.
            arg(0x44,len(payload));write(0x59,struct.pack('<6I',MAGIC,1,1,len(payload),0,0));s=status(read)
            assert len(read(0x56,length=392))==392 # Counters remain readable during staging.
            rejected(0x56)
            host.endpoint_out(1,payload[:16384]);rejected(0x5a,value=s[3])
            arg(0x5b,s[3]);assert status(read)[2]==0;rejected(0x5a,value=s[3]);write(0x47)
            # A short bulk packet terminates early and must fail the whole stage.
            arg(0x44,len(payload));write(0x59,struct.pack('<6I',MAGIC,1,1,len(payload),0,0))
            host.endpoint_out(1,b'bad');assert status(read)[2]==5;write(0x47)
            arg(0x44,len(payload));rejected(0x59,struct.pack('<6I',MAGIC,1,1,33554433,0,0));write(0x47)
            report['status']='passed';report['checks']=['legacy CRC','chained DMA CRC','512-byte packet accumulation','early apply rejection','cancel and stale token','short payload rejection','capacity bound']
        finally:
            if host:host.close()
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            if process.stderr:process.stderr.close()
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
