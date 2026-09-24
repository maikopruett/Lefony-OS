#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""SDK launcher test through normal key dispatch and Goodix touch frames."""
import json
from pathlib import Path
import socket
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from cli import package
from build import lock_value,write_json
from runner import exercise


def main():
    # This checked-in platform fixture always exercises the current SDK.
    write_json(ROOT/'sdk/examples/counter/sdk.lock.json',lock_value(ROOT/'sdk',1))
    output=ROOT/'build/sdk-ui'; output.mkdir(parents=True,exist_ok=True)
    def controls(channel):
        monitor=socket.socket(socket.AF_UNIX); monitor.settimeout(5)
        monitor.connect(str(Path(channel.socket.getpeername()).parent/'qmp'))
        matrix=socket.socket(socket.AF_UNIX); matrix.settimeout(5)
        matrix.connect(str(Path(channel.socket.getpeername()).parent/'qtest'))
        matrix_stream=matrix.makefile('rwb',buffering=0)
        def press(row,col):
            for down in (True,False):
                matrix_stream.write(f"writew 0x020b8008 {((row<<8)|col|(0x8000 if down else 0)):#x}\n".encode())
                while True:
                    reply=matrix_stream.readline()
                    if reply.startswith(b'IRQ'): continue
                    assert reply.startswith(b'OK'),reply
                    break
                time.sleep(.25)
        stream=monitor.makefile('rwb',buffering=0)
        json.loads(stream.readline())
        def qmp(name,args=None):
            stream.write((json.dumps({'execute':name,'arguments':args or {}})+'\n').encode())
            while True:
                reply=json.loads(stream.readline())
                if 'event' in reply: continue
                assert 'error' not in reply,reply
                return reply
        def capture(name):
            time.sleep(.3)
            file=output/(name+'.ppm')
            qmp('screendump',{'filename':str(file)})
            return file.read_bytes()
        def raw(command):
            assert channel.command(command)=='OK',command
            time.sleep(.3)
        try:
            qmp('qmp_capabilities')
            initial=capture('initial')
            press(7,0)
            keyboard=capture('keyboard')
            assert initial!=keyboard,'Native app did not handle Confirm from normal key dispatch'
            raw('TOUCH FRAME 1 0 200 160'); raw('TOUCH FRAME 0')
            reset=capture('reset')
            assert keyboard!=reset,'Native Reset button did not receive Goodix touch'
            raw('TOUCH FRAME 1 0 60 160'); raw('TOUCH FRAME 0')
            added=capture('added')
            assert reset!=added,'Native Add button did not receive Goodix touch'
            press(4,6)
            assert channel.command('PING')=='PONG'
            back=capture('back')
            assert back!=added,'Back did not return to the OS launcher'
            raw('APP LAUNCH')
            assert capture('resumed')==added,'Returning to the app reset its state'
        finally:
            stream.close(); monitor.close(); matrix_stream.close(); matrix.close()
    result=exercise(package(ROOT/'sdk/examples/counter'),ROOT/'build/qemu-prime-g2/qemu-system-arm',ROOT/'dist/lefony-os-prime-g2-vm-native.elf',controls=controls)
    assert result['result']==1
    print('PASS: SDK launcher, normal keys, Goodix touch buttons, OS responsive')


if __name__=='__main__': main()
