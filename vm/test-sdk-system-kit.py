#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reproducible relocated source kit builds and runs an ordinary C system app."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json

SOURCE=r'''/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <lefony/system.h>
#include <lefony/foreground.h>
int main(void) {
  LefonySystemInfo info;
  if(lefony_system_info(&info)!=0 || info.size!=160 || info.schema!=1) return 1;
  if(info.utcOffsetMinutes!=LEFONY_UTC_OFFSET_UNKNOWN || !info.maximumBrightness) return 2;
  if(lefony_brightness(112)!=0) return 3;
  if(lefony_program_yield()!=0) return 4;
  if(lefony_system_info(&info)!=0 || info.brightness!=112 || info.actualBrightness!=112) return 5;
  if(lefony_restore_brightness()!=0) return 6;
  if(lefony_system_info(&info)!=0 || info.brightness!=240) return 7;
  return 0;
}
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-system/kit')
    parser.add_argument('--channel',action='store_true',help='Also exercise API 11 open/info/close in the relocated C app')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    archive=out/'source-with-newlib.tar.gz';qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm'
    command=[sys.executable,str(ROOT/'scripts/package_native_sdk.py'),'--newlib',str(ROOT/'build/sdk-newlib')]
    subprocess.run([*command,'--output',str(archive)],check=True)
    with tempfile.TemporaryDirectory(prefix='SDK system C é ') as folder:
        temporary=Path(folder);repeat=temporary/'repeat.tar.gz'
        subprocess.run([*command,'--output',str(repeat)],check=True)
        assert digest(archive)==digest(repeat),'source kit not reproducible'
        with tarfile.open(archive) as source:
            for item in source.getmembers():
                assert item.isfile() and item.name.startswith('lefony-native-sdk/') and '..' not in Path(item.name).parts
                target=temporary/item.name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(source.extractfile(item).read());target.chmod(item.mode)
        kit=temporary/'lefony-native-sdk';checksums={}
        for line in (kit/'SHA256SUMS').read_text().splitlines():
            sha,name=line.split('  ',1);assert digest(kit/name)==sha,name;checksums[name]=sha
        assert set(checksums)=={p.relative_to(kit).as_posix() for p in kit.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
        assert 'sdk/SYSTEM.md' in checksums and 'sdk/include/lefony/system.h' in checksums
        if args.channel:
            for name in ('sdk/CHANNEL.md','sdk/include/lefony/channel.h','sdk/include/lefony/channel_wire.h',
                         'sdk/tools/channel_device.py','sdk/tools/https_worker.py'):assert name in checksums,name
        project=temporary/'External C system app é';(project/'src').mkdir(parents=True);(project/'tests').mkdir()
        source=SOURCE
        if args.channel:
            source='#include <lefony/channel.h>\n'+source.replace('  return 0;', '''
  uint32_t session=0;LefonyChannelInfo channel;
  if(lefony_channel_open(&session)!=0 || !session) return 8;
  if(lefony_channel_info(&channel)!=0 || channel.session!=session || channel.state!=LEFONY_CHANNEL_WAIT_HOST) return 9;
  if(lefony_channel_send(session,1,0,0)!=-LEFONY_CHANNEL_AGAIN) return 10;
  if(lefony_channel_close(session)!=0) return 11;
  if(lefony_channel_info(&channel)!=0 || channel.state!=LEFONY_CHANNEL_ENDED || channel.error!=LEFONY_CHANNEL_CANCELLED) return 12;
  return 0;''')
        (project/'src/main.c').write_text(source)
        write_json(project/'app.json',{'schema':1,'abi':1,'id':'system-c','name':'C System','version':'1.0.0',
            'license':'GPL-3.0-or-later','minimum_api':11 if args.channel else 10,'required_capabilities':6160 if args.channel else 2064,'optional_capabilities':0,'data_schema':0})
        write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c']})
        write_json(project/'tests/system.json',{'schema':1,'name':'system','steps':[{'program_exit':0}]})
        cli=[sys.executable,str(kit/'sdk/tools/cli.py'),'--project',str(project)]
        subprocess.run([*cli,'test','--workspace','system','--qemu',str(qemu),'--firmware',str(args.firmware.resolve())],check=True,timeout=180)
        result=json.loads((project/'build/run.json').read_text());assert result['status']=='passed'
        build=json.loads((project/'build/build.json').read_text())
        commands=json.loads((project/'compile_commands.json').read_text())
        c_commands=[c for c in commands if c['file'].endswith('main.c')]
        assert len(c_commands)==1 and '-std=c11' in c_commands[0]['arguments']
        assert any(str(kit/'sdk/runtime/newlib') in arg for arg in c_commands[0]['arguments'])
        packages=list((project/'build').glob('*.lfapp'));assert len(packages)==1
        (out/packages[0].name).write_bytes(packages[0].read_bytes())
        (out/'main.c').write_text(source)
        for name in ('app-debug.elf','build.json','run.json'):
            (out/name).write_bytes((project/'build'/name).read_bytes())
        write_json(out/'report.json',{'schema':1,'status':'passed','files':len(checksums),'archive_sha256':digest(archive),
            'firmware_sha256':digest(args.firmware),'qemu_sha256':digest(qemu),'runtime':result,'build':build,'channel':args.channel,
            'physical':'not_tested','qualification':'local relocated source kit; installed host tools; not a clean host'})
    print('PASS: reproducible source kit, all file hashes, relocated bundled newlib, pure C system app on ARM')


if __name__=='__main__':main()
