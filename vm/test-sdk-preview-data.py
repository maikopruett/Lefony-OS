#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real preview private/files persistence, source edits, failure, reset and migration."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from preview import once
from preview_data import Checkpoints,PUBLIC
import archive_format


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--firmware',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm';firmware=output/'firmware.elf';shutil.copyfile(args.firmware,firmware)
    names=['sdk/tools/preview.py','sdk/tools/preview_data.py','sdk/tools/runner.py','sdk/tools/archive_device.py','sdk/tools/cli.py',
        'vm/test-sdk-preview-data.py','tests/native/sdk_preview_data.c']
    report={'schema':1,'status':'running','physical':'not_tested','firmware_sha256':digest(firmware),'qemu_sha256':digest(qemu),
        'sources':{p:digest(ROOT/p) for p in names},'cases':[]}
    write_json(output/'report.json',report)
    try:
        with tempfile.TemporaryDirectory(prefix='preview-data-') as temp:
            project=Path(temp)/'External preview é';(project/'src').mkdir(parents=True);(project/'tests').mkdir()
            source=project/'src/main.c';original=(ROOT/'tests/native/sdk_preview_data.c').read_text();source.write_text(original)
            metadata={'abi':1,'id':'preview-data','name':'Preview Data','version':'1.0.0','license':'CC-BY-NC-SA-4.0',
                'schema':1,'minimum_api':8,'required_capabilities':536,'optional_capabilities':0,'data_schema':0}
            write_json(project/'app.json',metadata);write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c']})
            scenario=Path('tests/preview.json');write_json(project/scenario,{'schema':1,'name':'saved-data','steps':[{'program_exit':0}]})
            inputs=Path(temp)/'fixtures';(inputs/'nested/empty').mkdir(parents=True);(inputs/'nested/input.txt').write_text('initial')
            store=Checkpoints(project)
            def capture(name,expected='ready',**options):
                value=once(project,qemu,firmware,scenario=scenario,fixture_dir=inputs,inspect=False,**options)
                target=output/name;shutil.copytree(project/'build/preview',target,ignore=shutil.ignore_patterns('.lock'))
                assert value['status']==expected,(name,value.get('error'))
                report['cases'].append({'case':name,'status':expected,'timings':value.get('timings'),'error':value.get('error'),'checkpoint':value.get('checkpoint')})
                write_json(output/'report.json',report);print('PASS:',name,flush=True);return value
            def check(count,values,schema=0):
                receipt=store.read();path=store.path(receipt);archive=archive_format.inspect(path,[PUBLIC])
                assert archive.sha256==receipt['archive'] and len(archive.snapshots)==1
                pair=archive.snapshots[0];assert pair.data_schema==schema and pair.private.size==4
                with path.open('rb') as stream:
                    stream.seek(pair.private.offset);assert struct.unpack('<I',stream.read(4))[0]==count
                    entries={e.path:e for e in pair.entries};assert entries['nested/empty'].directory
                    data=entries['nested/output.bin'].content;stream.seek(data.offset)
                    assert stream.read(data.size)==b''.join(struct.pack('<I',n) for n in values)
                shutil.copyfile(path,output/(f'checkpoint-{count}-schema-{schema}.lfarchive'))
                return receipt
            capture('first');first=check(1,[1])
            source.write_text(original.replace('#define EDIT_MARK 1','#define EDIT_MARK 2'))
            capture('source-edit');second=check(2,[1,2]);assert first['archive']!=second['archive']
            prior=store.receipt.read_bytes();frame=digest(project/'build/preview/frame.png')
            source.write_text(original+'\nThis is invalid C;\n')
            capture('compile-error','failed');assert store.receipt.read_bytes()==prior and digest(project/'build/preview/frame.png')==frame
            source.write_text(original);(inputs/'nested/input.txt').write_text('reseeded')
            value=capture('changed-fixture','failed');assert '--reset-data' in value['error'] and store.receipt.read_bytes()==prior
            capture('reset',reset_data=True);reset=check(1,[1]);assert reset['fixture_sha256']!=second['fixture_sha256']
            prior=store.receipt.read_bytes();capture('disposable',fresh_data=True);assert store.receipt.read_bytes()==prior
            metadata.update(version='2.0.0',data_schema=1);write_json(project/'app.json',metadata)
            capture('schema-migration');check(2,[1,2],schema=1)
            source.write_text(original.replace('#define EDIT_MARK 1','#define EDIT_MARK 3'))
            capture('reopen-migrated');check(3,[1,2,3],schema=1)
            prior=store.receipt.read_bytes();frame=digest(project/'build/preview/frame.png')
            source.write_text(original.replace('#define EXIT_CODE 0','#define EXIT_CODE 9'))
            write_json(project/scenario,{'schema':1,'name':'failed-app','steps':[{'program_exit':9}]})
            capture('app-error','failed');assert store.receipt.read_bytes()==prior and digest(project/'build/preview/frame.png')==frame
            # A failed reset must not discard the saved data either.
            source.write_text(original+'\nInvalid reset build;\n')
            capture('failed-reset','failed',reset_data=True);assert store.receipt.read_bytes()==prior
            shutil.copytree(project/'.lefony/preview',output/'saved-preview',ignore=shutil.ignore_patterns('.lock'))
        report['status']='passed';write_json(output/'report.json',report)
    except Exception as exc:
        report.update(status='failed',error=str(exc));write_json(output/'report.json',report);raise


if __name__=='__main__':main()
