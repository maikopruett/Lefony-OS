#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Relocated source kit, bundled newlib and offline Notebook or gallery preview."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-ui/kit')
    parser.add_argument('--template',choices=('notebook','ui-gallery'),default='notebook')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    archive=output/'sdk-with-newlib.tar.gz'
    command=[sys.executable,str(ROOT/'scripts/package_native_sdk.py'),'--newlib',str(ROOT/'build/sdk-newlib')]
    subprocess.run([*command,'--output',str(archive)],check=True,timeout=60)
    environment={k:v for k,v in os.environ.items() if k not in ('LEFONY_SDK_NEWLIB','PYTHONPATH')}
    with tempfile.TemporaryDirectory(prefix='SDK UI archive é ') as temp:
        directory=Path(temp);repeat=directory/'repeat.tar.gz'
        subprocess.run([*command,'--output',str(repeat)],check=True,timeout=60)
        assert digest(archive)==digest(repeat)
        with tarfile.open(archive) as source:
            for member in source.getmembers():
                assert member.isfile() and member.size<=16*1024*1024 and member.name.startswith('lefony-native-sdk/') and '..' not in Path(member.name).parts
                path=directory/member.name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(source.extractfile(member).read());path.chmod(member.mode)
        kit=directory/'lefony-native-sdk';checksums={}
        for line in (kit/'SHA256SUMS').read_text().splitlines():
            checksum,name=line.split('  ',1);assert digest(kit/name)==checksum;checksums[name]=checksum
        for name in ('sdk/UI.md','sdk/include/lefony/text_wire.h','sdk/include/lefony/ui_widgets.h',
                     'sdk/include/lefony/number_format.h','sdk/include/lefony/ui_system.h','sdk/include/lefony/system.h',
                     'sdk/include/lefony/ui_patterns.h','sdk/include/lefony/file_writer.h',
                     'sdk/tools/preview.py','sdk/examples/notebook/src/main.cpp',
                     'sdk/examples/ui-gallery/src/main.cpp','sdk/runtime/newlib/COPYING.NEWLIB'):
            assert name in checksums
        assert set(checksums)=={p.relative_to(kit).as_posix() for p in kit.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
        prefix=['/usr/bin/sandbox-exec','-p','(version 1)(allow default)(deny network-outbound (remote ip "*:*"))'] if sys.platform=='darwin' else []
        cli=[*prefix,sys.executable,str(kit/'sdk/tools/cli.py')];project=directory/f'External {args.template} é'
        log=(output/'commands.log').open('w')
        def run(arguments):
            subprocess.run(arguments,check=True,env=environment,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        try:
            run([*cli,'new',str(project),'--template',args.template])
            scenario='tests/edit.json' if args.template=='notebook' else 'tests/startup.json'
            run([*cli,'--project',str(project),'preview','--once','--scenario',scenario,
                '--firmware',str(args.firmware.resolve()),'--qemu',str(ROOT/'build/qemu-prime-g2/qemu-system-arm')])
            state=json.loads((project/'build/preview/status.json').read_text());assert state['status']=='ready'
            if args.template=='ui-gallery':
                nodes={node['id']:node for node in state['layout']['nodes']}
                assert nodes[50]['name']=='UI gallery' and nodes[10]['name']=='7'
                assert nodes[10]['state']&3==3 and nodes[10]['bounds']==[12,62,296,32]
                assert all(node['file']=='src/main.cpp' and node['line']>0 for node in nodes.values())
            build=json.loads((project/'build/build.json').read_text())
            assert any(str(kit/'sdk/runtime/newlib') in arg for arg in build['link'])
            run([*cli,'--project',str(project),'source','--format','2'])
            shutil.copytree(project/'build/preview',output/'preview',dirs_exist_ok=True)
            write_json(output/'report.json',{'schema':1,'status':'passed','template':args.template,'archive_sha256':digest(archive),'files':len(checksums),
                'network_outbound':'denied' if prefix else 'not_enforced','host':sys.platform,'physical':'not_tested',
                'preview':state,'source_sha256':digest(project/'build/app.lfsrc')})
        finally:log.close()
    print('PASS: reproducible relocated kit, bundled newlib, source-2 export and actual ARM preview',flush=True)


if __name__=='__main__':main()
