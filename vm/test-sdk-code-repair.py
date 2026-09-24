#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unreadable signed app recovery over ARM USB, with independently checked cold data."""
import argparse
from contextlib import nullcontext,redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
import archive_device as archive
import archive_format
import cli
from build import digest,write_json
from device import DeviceError
from replay import Controls
from runner import exercise
from signing import sign
from workspace import opened
APP='document-arm'
KEY=ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem'
PUBLIC=ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'


def command(transport,*args):
    previous,argv=archive.ArchiveUSB,sys.argv
    try:
        archive.ArchiveUSB=lambda:nullcontext(transport)
        sys.argv=['lefony-sdk','archive',*map(str,args)];out=io.StringIO()
        with redirect_stdout(out):assert cli.main()==0,out.getvalue()
        return json.loads(out.getvalue())
    finally:archive.ArchiveUSB=previous;sys.argv=argv


def rejected(action):
    try:action()
    except DeviceError as exc:return str(exc)
    raise AssertionError('Expected archive rejection')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    firmware=output/'firmware.elf';shutil.copyfile(args.firmware,firmware)
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm';cases=[]
    sources=['vm/test-sdk-code-repair.py','vm/test-sdk-documents.py','tests/native/app_document_fixture.cpp',
        'sdk/tools/archive_device.py','sdk/tools/archive_format.py','sdk/tools/cli.py',
        *['ports/lefony-prime-g2/ion/src/prime_g2/'+p for p in ('app_archive_source.cpp','app_archive_source.h',
            'app_archive_restore.cpp','app_archive_restore.h','app_archive_session.cpp','app_archive_session.h',
            'app_archive_wire.h','app_management.cpp','app_storage.cpp','app_document_store.cpp','usb_diagnostics.cpp')]]
    report={'schema':1,'status':'running','physical':'not_tested','firmware_sha256':digest(firmware),
        'qemu_sha256':digest(qemu),'sources':{p:digest(ROOT/p) for p in sources},'cases':cases}
    write_json(output/'report.json',report)
    try:
        with tempfile.TemporaryDirectory(prefix='lefony-code-repair-') as temp:
            project=Path(temp)/'project';(project/'src').mkdir(parents=True)
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c']})
            artifacts={}
            for name,app_id in [('app',APP),('helper','repair-helper')]:
                source='#include <lefony/app_c.h>\n#include <stdint.h>\nint main(void) {\n'
                if name=='app':source+='uint32_t value=0;if(lefony_read_data(0,&value,4)!=4 || value!=14) return 17;\nlefony_fill((lefony_rect_t){0,0,320,240,LEFONY_GREEN});\n'
                source+='return 0;}\n';(project/'src/main.c').write_text(source)
                write_json(project/'app.json',{'abi':1,'id':app_id,'name':'Code Repair Validation','version':'1.0.0',
                    'license':'CC-BY-NC-SA-4.0','schema':1,'minimum_api':3,'required_capabilities':24,'optional_capabilities':0,'data_schema':0})
                pkg=cli.package(project);folder=output/name;folder.mkdir(exist_ok=True)
                for filename in ('app-debug.elf','app.elf','build.json'):shutil.copyfile(project/'build'/filename,folder/filename)
                shutil.copyfile(project/'src/main.c',folder/'main.c')
                artifacts[name]=folder/'app.lfapp';artifacts[name].write_bytes(sign(pkg.read_bytes(),KEY))
            helper=Path(temp)/'reader';helper.mkdir();reader=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](helper)
            phases=[('source-legacy',None),('source-doc',None),('legacy-payload','corrupt-code'),
                    ('legacy-envelope','corrupt-envelope'),('legacy-truncated','truncate-legacy'),
                    ('legacy-prefix','truncate-code'),('doc-missing','missing-code'),('doc-truncated','truncate-code'),
                    ('doc-payload','corrupt-code'),('root-refused','corrupt-root')]
            for phase,damage in phases:
                target=output/phase;target.mkdir(exist_ok=True);legacy='legacy' in phase
                source_phase='source-legacy' if legacy else 'source-doc';backup=output/source_phase/'backup.lfarchive'
                with opened(project,phase) as (workspace,_):
                    if damage:
                        shutil.copyfile(output/source_phase/'nand.overlay',workspace/'nand.overlay')
                        subprocess.run([reader,damage,workspace/'nand.overlay',APP],check=True,capture_output=True,timeout=60)
                    else:subprocess.run([reader,'seed-legacy' if legacy else 'seed-files',artifacts['app'],workspace/'nand.overlay'],check=True,capture_output=True,timeout=60)
                    observed={}
                    def controls(channel):
                        normal=Controls(channel,target);client=channel.app_client;c=archive.Client(client,timeout=180)
                        try:
                            normal.run({'steps':[{'program_exit':0}]},[]);normal.key('home');client.wait()
                            if not damage:
                                observed['before']=c.info(APP)
                                observed['export']=command(client.transport,'export',APP,backup,'--public-key',PUBLIC)
                                parsed=archive_format.inspect(backup,[PUBLIC]);assert parsed.signatures_checked
                                assert parsed.snapshots[0].private.size==4 and parsed.snapshots[0].package.sha256==digest(artifacts['app'])
                            else:
                                observed['ordinary_refusal']=rejected(lambda:c.info(APP));client.wait()
                                if phase=='root-refused':
                                    observed['repair_refusal']=rejected(lambda:c.info(APP,include_unreadable=True));client.wait()
                                    assert any(e['id']=='repair-helper' for e in client.catalog());return
                                info=command(client.transport,'info',APP,'--include-unreadable');observed['before']=info
                                assert info['exists'] and info['code_unavailable'] and info['version'] is None and info['signer'] is None
                                assert info['legacy']==legacy
                                observed['restore']=command(client.transport,'restore',backup,'--public-key',PUBLIC,'--repair-code')
                                assert observed['restore']['code_repaired']
                                out=target/'roundtrip.lfarchive'
                                command(client.transport,'export',APP,out,'--public-key',PUBLIC)
                                assert out.read_bytes()==backup.read_bytes()
                                observed['after']=c.info(APP);assert not observed['after']['code_unavailable']
                                assert any(e['id']=='repair-helper' for e in client.catalog())
                            assert channel.command('PING')=='PONG'
                        finally:normal.close()
                    try:
                        result=exercise(artifacts['helper'] if damage else artifacts['app'],qemu,firmware,workspace=workspace,controls=controls,public_keys=[PUBLIC])
                        assert result['result']==1 and result['os_responsive'],result
                    except BaseException:
                        shutil.copyfile(workspace/'nand.overlay',target/'failed-nand.overlay');raise
                    if phase!='root-refused':
                        state=json.loads(subprocess.check_output([reader,'inspect-app',workspace/'nand.overlay',APP],text=True,timeout=60))
                        assert state['private_data_sha256']==hashlib.sha256((14).to_bytes(4,'little')).hexdigest()
                        assert state['package_sha256']==digest(artifacts['app']);observed['cold_storage']=state
                        if not legacy:
                            out=target/'asset.bin';subprocess.run([reader,'export-file',workspace/'nand.overlay',APP,'assets/data.bin',out],check=True,capture_output=True,timeout=60)
                            assert out.read_bytes()==bytes((i*131)&255 for i in range(128*1024-128+17))
                        if damage:
                            def cold(channel):
                                normal=Controls(channel,target)
                                try:
                                    normal.run({'steps':[{'program_exit':0},{'capture':'cold-repaired'}]},[])
                                    normal.key('home');channel.app_client.wait()
                                    assert archive.Client(channel.app_client).info(APP)['package_sha256']==digest(artifacts['app'])
                                finally:normal.close()
                            reopened=exercise(artifacts['app'],qemu,firmware,workspace=workspace,controls=cold,public_keys=[PUBLIC])
                            assert reopened['result']==1 and reopened['os_responsive'];observed['cold_runtime']=reopened
                    shutil.copyfile(workspace/'nand.overlay',target/'nand.overlay')
                    cases.append({'case':phase,'runtime':result,**observed});write_json(output/'report.json',report);print('PASS:',phase,flush=True)
        assert all(digest(ROOT/p)==value for p,value in report['sources'].items())
        report['status']='passed';write_json(output/'report.json',report)
    except BaseException as exc:
        report.update(status='failed',error=str(exc));write_json(output/'report.json',report);raise


if __name__=='__main__':main()
