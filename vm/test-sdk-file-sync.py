#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Installed main/stdio live saves, forced exits, cold reopen and host oracle."""
import argparse
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, write_json
from cli import package
from replay import Controls
from runner import exercise
from workspace import opened


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-firmware', type=Path, help='Optional API 3/4 ELF for ENOSYS fallback')
    args = parser.parse_args()
    output = ROOT / 'build/sdk-file-sync/arm'
    output.mkdir(parents=True, exist_ok=True)
    cases = []
    modes = ['home', 'fault', 'exit', 'denied'] + (['unsupported'] if args.old_firmware else [])
    with tempfile.TemporaryDirectory(prefix='lefony-sync-') as temporary:
        helper = Path(temporary) / 'helper';helper.mkdir()
        reader = runpy.run_path(str(ROOT / 'vm/test-sdk-documents.py'))['fixture'](helper)
        for mode in modes:
            project = Path(temporary) / mode
            (project / 'src').mkdir(parents=True)
            shutil.copyfile(ROOT / 'tests/native/sdk_file_sync.c', project / 'src/main.c')
            metadata = {'abi':1, 'id':'file-sync', 'name':'File Sync', 'version':'1.0.0',
                'license':'GPL-3.0-or-later', 'schema':1, 'minimum_api':5,
                'required_capabilities':88, 'optional_capabilities':0, 'data_schema':0}
            if mode in ('denied', 'unsupported'):
                metadata.update(minimum_api=3, required_capabilities=24)
            write_json(project / 'app.json', metadata)
            retained = output / mode;retained.mkdir(exist_ok=True)
            for phase in (['write', 'cold'] if mode in ('home','fault','exit') else ['write']):
                write_json(project / 'project.json', {'schema':2, 'runtime':'foreground-newlib-1',
                    'sources':['src/main.c'], 'arguments':[mode]})
                app = package(project)
                symbols = subprocess.check_output(['arm-none-eabi-nm', str(project/'build/app-debug.elf')], text=True)
                expected_fault = next(int(line.split()[0],16) for line in symbols.splitlines()
                    if line.endswith(' lefony_sync_expected_fault'))
                evidence = retained / phase;evidence.mkdir(exist_ok=True)
                for name in ('app-debug.elf','app.elf','build.json',app.name):
                    shutil.copyfile(project / 'build' / name, evidence / name)
                for name in ('app.json','project.json','sdk.lock.json'):
                    shutil.copyfile(project / name, evidence / name)
                observed = {}
                def controls(channel):
                    normal = Controls(channel,evidence)
                    def value(index):
                        result=int(channel.command(f'APP DIAG {index}').split()[1])
                        return result-2**32 if result>=2**31 else result
                    try:
                        end=time.monotonic()+120
                        while True:
                            fault=value(9)
                            if phase=='write' and mode=='fault' and fault:
                                assert fault==-11 and value(10)==expected_fault
                                observed['expected_fault']=fault;observed['fault_pc']=value(10);break
                            assert fault==0, f'{mode}/{phase}: fault {fault} at {value(10):x}'
                            if phase=='write' and mode=='home':
                                frame=evidence/'staged.ppm'
                                normal.execute('screendump',{'filename':str(frame)})
                                with Image.open(frame) as image:
                                    if image.convert('RGB').getpixel((40,40))==(0,0,255):break
                            elif value(15):
                                status=value(21)
                                assert status==(7 if phase=='write' and mode=='exit' else 0)
                                observed['exit_status']=status;break
                            assert time.monotonic()<end, f'{mode}/{phase}: deadline'
                            time.sleep(.05)
                        normal.key('home')
                    finally:normal.close()
                with opened(project,'sync') as (workspace,_):
                    firmware=args.old_firmware if mode=='unsupported' else ROOT/'dist/lefony-os-prime-g2-vm-native.elf'
                    result=exercise(app, ROOT/'build/qemu-prime-g2/qemu-system-arm',
                        firmware, workspace=workspace, controls=controls)
                    if mode in ('home','fault','exit'):
                        exported=evidence/'checkpoint.bin'
                        subprocess.run([reader,'export-file',workspace/'nand.overlay','file-sync','checkpoint',exported],
                            check=True, stdout=subprocess.DEVNULL, timeout=30)
                        expected=bytearray(((i*131+(i>>8))^0x5d)&255 for i in range(8197))
                        expected[:4]=b'SAVE'
                        assert exported.read_bytes()==expected
                        observed['saved_sha256']=digest(exported)
                expected_result=-11 if mode=='fault' and phase=='write' else 1
                assert result['result']==expected_result and result['os_responsive'],result
                cases.append({'mode':mode,'phase':phase,'runtime':result,**observed})
                print('PASS:',mode,phase,flush=True)
    sources=['tests/native/sdk_file_sync.c','vm/test-sdk-file-sync.py','sdk/lib/newlib/files.c',
        'sdk/include/lefony/files_wire.h','ports/lefony-prime-g2/ion/src/prime_g2/app_file_session.cpp',
        'ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp']
    write_json(output/'report.json',{'schema':1,'status':'passed','physical':'not_tested',
        'cases':cases,'sources':{p:digest(ROOT/p) for p in sources}})


if __name__=='__main__':main()
