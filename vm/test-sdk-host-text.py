#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real ARM document preview under a non-UTF-8 host text locale; no hardware."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'sdk/tools'))
from archive_format import inspect
from build import identity
from preview_data import Checkpoints, PUBLIC


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu',type=Path,required=True)
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    env={**os.environ,'LC_ALL':'C','LANG':'C','PYTHONUTF8':'0',
         'PYTHONCOERCECLOCALE':'0','PYTHONIOENCODING':'ascii:strict',
         'PYTHONWARNDEFAULTENCODING':'1','PYTHONWARNINGS':'error::EncodingWarning'}
    probe=subprocess.check_output([sys.executable,'-c',
        'import json,locale,sys;print(json.dumps({"locale":locale.getencoding(),"filesystem":sys.getfilesystemencoding(),"utf8_mode":sys.flags.utf8_mode}))'],env=env,timeout=10)
    host=json.loads(probe)
    assert host['utf8_mode']==0 and host['locale'].lower().replace('-','')!='utf8',host
    project=output/('Document Café 数学' if host['filesystem'].lower().replace('-','')=='utf8' else 'document')
    commands=[]

    def command(*arguments,expected=0):
        result=subprocess.run([sys.executable,str(ROOT/'sdk/tools/cli.py'),*map(str,arguments)],
                              env=env,capture_output=True,timeout=240)
        number=len(commands)
        (output/f'{number:02d}.stdout').write_bytes(result.stdout)
        (output/f'{number:02d}.stderr').write_bytes(result.stderr)
        commands.append({'arguments':list(map(str,arguments)),'returncode':result.returncode})
        assert result.returncode==expected,result.stdout.decode('utf-8','replace')+result.stderr.decode('utf-8','replace')
        assert b'EncodingWarning' not in result.stderr,result.stderr
        result.stdout.decode('utf-8');result.stderr.decode('utf-8')

    command('new',project,'--template','notebook')
    # A cold preview captures the list without creating or modifying a document.
    (project/'tests/reopen.json').write_text(json.dumps({'schema':1,'name':'reopen',
        'steps':[{'capture':'reopened'}]}),encoding='utf-8',newline='\n')
    records=[]
    previous_document=None

    def preview(name,scenario,expected=0):
        nonlocal previous_document
        command('--project',project,'preview','--once','--scenario',scenario,
                '--qemu',args.qemu.resolve(),'--firmware',args.firmware.resolve(),expected=expected)
        state=json.loads((project/'build/preview/status.json').read_bytes())
        assert state['status']==('ready' if not expected else 'failed'),state
        kept=output/name;shutil.copytree(project/'build/preview',kept)
        checkpoints=Checkpoints(project);receipt=checkpoints.read();archive=checkpoints.path(receipt)
        wire=inspect(archive,[PUBLIC])
        entry=next(entry for entry in wire.snapshots[0].entries if entry.path=='notebook.txt')
        with archive.open('rb') as stream:
            stream.seek(entry.content.offset);document=stream.read(entry.content.size)
        assert document.startswith(b'LFNOTE3\nD\n') and b'2+3*4\n' in document,document
        if previous_document is not None:assert document==previous_document
        previous_document=document
        if not expected:assert state['layout']['nodes'] and state['runtime']['os_responsive']
        records.append({'case':name,'status':state['status'],'package_sha256':state['package_sha256'],
                        'frame_sha256':digest(kept/'frame.png'),'document_sha256':entry.content.sha256,
                        'archive_sha256':wire.sha256,'receipt':receipt})
        print('PASS: non-UTF-8 host '+name,flush=True)

    preview('edit','tests/edit.json')
    source=project/'src/main.cpp';original=source.read_bytes()
    revised=original+'\n// Café 数学 → π: source-save preview\n'.encode('utf-8')
    source.write_bytes(revised)
    preview('cold-source-edit','tests/reopen.json')
    before=records[-1]
    source.write_bytes(revised+'\n#error Café 数学\n'.encode('utf-8'))
    preview('failed-build','tests/reopen.json',expected=1)
    failure=json.loads((project/'build/preview/status.json').read_bytes())
    assert 'Café 数学' in failure['error'],failure
    for key in ('frame_sha256','archive_sha256','receipt'):
        assert records[-1][key]==before[key],key
    source.write_bytes(revised)
    preview('repaired-build','tests/reopen.json')
    assert records[-1]['frame_sha256']==before['frame_sha256']
    report={'schema':1,'status':'passed','host':host,'sdk_sha256':identity(ROOT/'sdk'),
            'qemu_sha256':digest(args.qemu),'firmware_sha256':digest(args.firmware),
            'commands':commands,'cases':records,'native_windows_qualified':False}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':
    main()
