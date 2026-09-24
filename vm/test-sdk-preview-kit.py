#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source-kit or frozen CLI preview retains data and excludes it from uploads."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from PIL import Image


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('sdk','qemu','firmware','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--cli',type=Path,help='Execute this frozen CLI instead of the source-kit Python entry point')
    args=parser.parse_args();sdk=args.sdk.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    cli=args.cli.resolve() if args.cli else None
    if cli and not cli.is_file():parser.error('Frozen CLI is missing')
    sys.path.insert(0,str(sdk/'tools'))
    import archive_format
    from build import identity,write_json
    from source import decode
    assert (sdk/'runtime/newlib/candidate.json').is_file(),'Qualify a kit containing the verified newlib runtime'
    report={'schema':1,'status':'running','sdk_sha256':identity(sdk),'firmware_sha256':digest(args.firmware),
        'qemu_sha256':digest(args.qemu),'physical':'not_tested','cases':[]}
    if cli:report['frozen_cli_sha256']=digest(cli)
    write_json(output/'report.json',report)
    try:
        with tempfile.TemporaryDirectory(prefix='preview-kit-') as temp:
            project=Path(temp)/'External notebook é';fixtures=Path(temp)/'fixtures'
            (fixtures/'nested/empty').mkdir(parents=True)
            document=b'LFNOTE1\n'+b''.join(f'{i}+100\n'.encode() for i in range(12));attachment=bytes(range(256))*513
            (fixtures/'notebook.txt').write_bytes(document);(fixtures/'nested/data.bin').write_bytes(attachment)
            def command(name,*arguments,expected=0):
                with (output/(name+'.log')).open('w') as log:
                    result=subprocess.run([*([str(cli)] if cli else [sys.executable,str(sdk/'tools/cli.py')]),*map(str,arguments)],
                        stdout=log,stderr=subprocess.STDOUT,timeout=180)
                assert result.returncode==expected,(name,result.returncode,expected)
            command('new','new',project,'--template','notebook')
            version=json.loads((project/'app.json').read_text())['version']
            scenario=project/'tests/scroll.json'
            # Preview must finish its initial layout before replaying input;
            # a guessed startup delay would conceal the original race.
            scenario.write_text(json.dumps({'schema':1,'name':'scroll','steps':[
                {'touch':[[1,80,75]]},{'touch':[[1,80,58]]},{'touch':[]}]}))
            def preview(name,*options,expected=0):
                target=output/name
                try:
                    command(name,'--project',project,'preview','--once','--firmware',args.firmware.resolve(),
                        '--qemu',args.qemu.resolve(),'--scenario','tests/scroll.json',*options,expected=expected)
                finally:
                    if (project/'build/preview').is_dir():
                        shutil.copytree(project/'build/preview',target,ignore=shutil.ignore_patterns('.lock'))
                state=json.loads((project/'build/preview/status.json').read_text())
                assert state['status']==('failed' if expected else 'ready'),state.get('error')
                nodes={node['id']:node for node in state['layout']['nodes']}
                assert nodes[63]['kind']=='scrollbar' and not nodes[63]['state']&4
                assert nodes[100]['bounds']==[12,43,296,36] and nodes[100]['clip']==[12,60,296,19], nodes[100]
                assert nodes[103]['bounds']==[12,163,296,36] and nodes[103]['clip']==[12,163,296,13], nodes[103]
                assert nodes[103]['file'].endswith('src/main.cpp') and nodes[103]['line']>0
                receipt=json.loads((project/'.lefony/preview/state.json').read_text())
                path=project/'.lefony/preview'/(receipt['archive']+'.lfarchive')
                with path.open('rb') as source:
                    archive=archive_format.validate(source,[sdk.parent/'tests/fixtures/prime_g2_emulator_update_public.pem'])
                    assert archive.sha256==receipt['archive'] and len(archive.snapshots)==1
                    files={entry.path:entry for entry in archive.snapshots[0].entries}
                    assert set(files)=={'notebook.txt','nested','nested/data.bin','nested/empty'}
                    assert files['nested/empty'].directory
                    for filename,expected in [('notebook.txt',document),('nested/data.bin',attachment)]:
                        span=files[filename].content;source.seek(span.offset);assert source.read(span.size)==expected
                shutil.copyfile(path,target/'data.lfarchive')
                report['cases'].append({'case':name,'preview_status':state['status'],'package_sha256':state['package_sha256'],
                    'checkpoint':receipt,'timings':state['timings']})
                write_json(output/'report.json',report);return state
            before=preview('seeded','--fixture-dir',fixtures)
            # A source edit reuses saved data even when the original fixture
            # is no longer supplied. It cannot silently import changed inputs.
            (fixtures/'notebook.txt').write_bytes(b'not a document')
            source=project/'src/main.cpp';original=source.read_text();assert original.count('?"Notebook":')==1
            source.write_text(original.replace('?"Notebook":','?"My notebook":'))
            assert original.split('  void input(',1)[1]==source.read_text().split('  void input(',1)[1]
            after=preview('source-edit')
            assert next(node for node in before['layout']['nodes'] if node['id']==50)['name']=='Notebook'
            assert next(node for node in after['layout']['nodes'] if node['id']==50)['name']=='My notebook'
            with Image.open(output/'seeded/frame.png') as a,Image.open(output/'source-edit/frame.png') as b:
                assert a.crop((0,40,320,240)).tobytes()==b.crop((0,40,320,240)).tobytes()
                assert a.crop((12,8,210,36)).tobytes()!=b.crop((12,8,210,36)).tobytes()
            assert before['package_sha256']!=after['package_sha256']
            assert before['checkpoint']['archive']==after['checkpoint']['previous']
            assert before['checkpoint']['fixture_sha256']==after['checkpoint']['fixture_sha256']
            cold=preview('cold-reopen')
            assert cold['package_sha256']==after['package_sha256']
            assert cold['checkpoint']['previous']==after['checkpoint']['archive']
            assert cold['checkpoint']['fixture_sha256']==after['checkpoint']['fixture_sha256']
            with Image.open(output/'source-edit/frame.png') as a,Image.open(output/'cold-reopen/frame.png') as b:
                assert a.tobytes()==b.tobytes()
            changed=source.read_text();assert changed.count('inspectionEnd();')==changed.count('inspectionEnd(false);')==1
            source.write_text(changed.replace('inspectionEnd();','/* Deliberately unfinished layout. */')
                .replace('inspectionEnd(false);','/* Deliberately unfinished loading layout. */'))
            failed=preview('incomplete-layout',expected=1)
            assert 'completed frame within 30 seconds' in failed['error'],failed['error']
            assert failed['checkpoint']==cold['checkpoint']
            assert digest(output/'incomplete-layout/frame.png')==digest(output/'cold-reopen/frame.png')
            assert 'STALE' in (output/'incomplete-layout/index.html').read_text()
            assert 'Hardware watchpoint' in (output/'incomplete-layout/initial-layout-gdb.log').read_text()
            source.write_text(changed)
            recovered=preview('recovered-layout')
            assert recovered['package_sha256']==cold['package_sha256']
            assert recovered['checkpoint']['previous']==cold['checkpoint']['archive']
            assert digest(output/'recovered-layout/frame.png')==digest(output/'cold-reopen/frame.png')
            command('source','--project',project,'source','--format','2')
            bundle=project/'build/app.lfsrc';value=decode(bundle.read_bytes())
            assert value['manifest']['version']==version
            assert all(not name.startswith(('.lefony/','build/','fixtures/')) for name in value['files'])
            assert all(not name.endswith('.lfarchive') for name in value['files'])
            shutil.copyfile(bundle,output/'app.lfsrc')
            report['source_sha256']=digest(bundle)
        assert report['sdk_sha256']==identity(sdk),'Kit changed during qualification'
        if cli:assert report['frozen_cli_sha256']==digest(cli),'Frozen CLI changed during qualification'
        report.update(status='passed',test_sha256=digest(Path(__file__)))
        write_json(output/'report.json',report)
    except Exception as exc:
        report.update(status='failed',error=str(exc));write_json(output/'report.json',report);raise


if __name__=='__main__':main()
