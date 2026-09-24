#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Public SDK file exchange over modeled USB, with cold data and error journeys."""
from pathlib import Path
import argparse
import hashlib
import shutil
import sys
import struct
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from cli import package
from device import DeviceError
from files_device import FileClient,IMPORT,WRITABLE
from replay import Controls
from runner import exercise
from workspace import opened


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,default=ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-file-exchange/arm')
    args=parser.parse_args();firmware=args.firmware.resolve();output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True);cases=[]
    for name in ('export.bin','preserved.bin','after-reset.bin','cold-export.bin'):
        (output/name).unlink(missing_ok=True)  # Only this harness's generated outputs.
    with tempfile.TemporaryDirectory(prefix='lefony-exchange-') as temp:
        project=Path(temp);(project/'src').mkdir()
        (project/'src/main.c').write_text('/* SPDX-License-Identifier: GPL-3.0-or-later */\nint main(void) {return 0;}\n')
        write_json(project/'app.json',{'abi':1,'id':'file-exchange','name':'File Exchange','version':'1.0.0',
            'license':'GPL-3.0-or-later','schema':1,'minimum_api':3,'required_capabilities':16,'optional_capabilities':0,'data_schema':0})
        write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c']})
        artifact=package(project)
        for name in ('app-debug.elf','app.elf','build.json',artifact.name):shutil.copyfile(project/'build'/name,output/name)
        source=output/'input.bin';source.write_bytes(bytes((i*37)&255 for i in range(128*1024+719)))
        replacement=output/'replacement.bin';replacement.write_bytes(b'new committed document\n')
        for cold in (False,True):
            def controls(channel):
                normal=Controls(channel,output)
                try:
                    deadline=time.monotonic()+30
                    while not int(channel.command('APP DIAG 15').split()[1]):
                        assert time.monotonic()<deadline;time.sleep(.025)
                    normal.key('home');client=channel.app_client;client.wait();files=FileClient(client)
                    info=files.info('file-exchange')
                    if cold:
                        report=files.export_file('file-exchange','document.bin',output/'cold-export.bin')
                        assert (output/'cold-export.bin').read_bytes()==replacement.read_bytes()
                        cases.append({'case':'cold-export','report':report});return
                    assert info['file_bytes']==0 and not info['pending_upgrade']
                    report=files.import_file('file-exchange','document.bin',source);cases.append({'case':'import','report':report})
                    exported=output/'export.bin';report=files.export_file('file-exchange','document.bin',exported)
                    assert exported.read_bytes()==source.read_bytes();cases.append({'case':'export','report':report})
                    listing=files.list('file-exchange');assert listing['entries']==[{'path':'document.bin','kind':'file','bytes':source.stat().st_size}]
                    try:files.import_file('file-exchange','document.bin',replacement)
                    except DeviceError as exc:assert 'exists' in str(exc)
                    else:raise AssertionError('replaced a file without explicit replace')
                    # Wait for cleanup of the rejected exclusive writer.
                    client.wait()
                    def cancelled():return True
                    try:files.import_file('file-exchange','document.bin',replacement,replace=True,cancelled=cancelled)
                    except DeviceError as exc:assert 'cancel' in str(exc)
                    else:raise AssertionError('cancelled import committed')
                    client.wait();preserved=output/'preserved.bin';files.export_file('file-exchange','document.bin',preserved)
                    assert preserved.read_bytes()==source.read_bytes()
                    # Deliberately bypass host hashing, so the actual guest must
                    # reject a wrong digest before publishing a replacement.
                    identity=files.info('file-exchange')
                    state=files._begin('file-exchange',IMPORT,'document.bin',identity=identity,length=0,digest=bytes(32),replace=True)
                    assert state['state']==WRITABLE;client.write(0x74,argument=state['sequence'])
                    try:files._wait(sequence=state['sequence'],operation=IMPORT)
                    except DeviceError as exc:assert 'hash mismatch' in str(exc)
                    else:raise AssertionError('wrong hash committed')
                    client.wait()
                    identity=files.info('file-exchange')
                    state=files._begin('file-exchange',IMPORT,'document.bin',identity=identity,length=5,digest=bytes(32),replace=True)
                    client.write(0x72,struct.pack('<2I',state['sequence'],0)+b'half')
                    files._wait(sequence=state['sequence'],operation=IMPORT)
                    client.transport.reset()
                    try:files._wait(sequence=state['sequence'],operation=IMPORT)
                    except DeviceError as exc:assert 'cancel' in str(exc)
                    else:raise AssertionError('USB reset retained an uncommitted session')
                    client.wait();normal.key('back')
                    after_reset=output/'after-reset.bin';files.export_file('file-exchange','document.bin',after_reset)
                    assert after_reset.read_bytes()==source.read_bytes()
                    cases.append({'case':'USB-reset-preserves-old-file','sha256':digest(after_reset)})
                    report=files.import_file('file-exchange','document.bin',replacement,replace=True)
                    cases.append({'case':'replace-after-errors','report':report})
                    assert files.info('file-exchange')['file_bytes']==replacement.stat().st_size
                    assert channel.command('PING')=='PONG'
                finally:normal.close()
            with opened(project,'exchange') as (workspace,_):
                result=exercise(artifact,ROOT/'build/qemu-prime-g2/qemu-system-arm',firmware,
                    workspace=workspace,controls=controls)
                assert result['result']==1 and result['os_responsive'];cases.append({'case':'runtime','cold':cold,'report':result})
            print('PASS: USB file exchange','cold' if cold else 'initial/error/retry',flush=True)
    sources=['vm/test-sdk-file-exchange.py','sdk/tools/files_device.py','sdk/tools/cli.py','sdk/tools/runner.py',
        *['ports/lefony-prime-g2/ion/src/prime_g2/'+p for p in
          ('app_file_exchange.cpp','app_file_exchange.h','app_file_session.cpp','app_management.cpp','usb_diagnostics.cpp')]]
    write_json(output/'report.json',{'schema':1,'status':'passed','physical':'not_tested','cases':cases,
        'sources':{p:digest(ROOT/p) for p in sources},'firmware_sha256':digest(firmware),
        'qemu_sha256':digest(ROOT/'build/qemu-prime-g2/qemu-system-arm')})


if __name__=='__main__':main()
