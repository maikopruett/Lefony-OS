#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed Notebook ownership/data recovery through real SDK USB under NAND faults."""
import argparse
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
import cli
from archive_device import Client as Archives
from build import digest,identity,write_json
from data_device import DataClient
from device import DeviceError
from files_device import FileClient
from replay import Controls
from runner import exercise
from sdk_notebook_probe import wait_notebook
from signing import sign
from workspace import opened

APP='root-recovery-note'
PRIVATE=ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem'
PUBLIC=ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    firmware=args.firmware.resolve();qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm'
    sources=['vm/test-sdk-root-recovery.py','vm/test-sdk-archive-media.py','vm/test-sdk-minigzip-media.py',
        'vm/test-sdk-documents.py','tests/native/app_document_fixture.cpp','tests/native/app_documents.cpp',
        'tests/native/app_storage.cpp',*['ports/lefony-prime-g2/ion/src/prime_g2/'+n for n in
        ('app_root_record.cpp','app_root_record.h','app_document_store.cpp','app_storage.cpp','app_archive_source.cpp',
         'app_archive_source.h','app_archive_session.cpp','app_archive_wire.h','app_archive_restore.cpp','app_management.cpp','littlefs/lfs.c')]]
    report={'schema':1,'status':'running','physical':'not_tested','sdk_sha256':identity(ROOT/'sdk'),
        'firmware_sha256':digest(firmware),'qemu_sha256':digest(qemu),'sources':{n:digest(ROOT/n) for n in sources},'cases':[]}
    write_json(output/'report.json',report)
    fault=runpy.run_path(str(ROOT/'vm/test-sdk-minigzip-media.py'))['fault']
    command=runpy.run_path(str(ROOT/'vm/test-sdk-archive-media.py'))['command']
    def record(name,**value):
        report['cases'].append({'case':name,**value});write_json(output/'report.json',report);print('PASS:',name,flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='lefony-root-recovery-') as temp:
            root=Path(temp);helper=root/'helper';helper.mkdir()
            fixture=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](helper)
            project=root/'notebook';shutil.copytree(ROOT/'sdk/examples/notebook',project,ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json'))
            artifacts={};manifest=json.loads((project/'app.json').read_text())
            for version in ('1.0.0','2.0.0','3.0.0','2.5.0'):
                manifest.update(id=APP,version=version);write_json(project/'app.json',manifest)
                target=output/version;target.mkdir()
                artifacts[version]=target/'app.lfapp';artifacts[version].write_bytes(sign(cli.package(project,'debug').read_bytes(),PRIVATE))
                for name in ('app-debug.elf','build.json'):shutil.copyfile(project/'build'/name,target/name)
                for name in ('app.json','project.json','sdk.lock.json'):shutil.copyfile(project/name,target/name)
            shutil.copytree(project/'src',output/'src')
            bootstrap=root/'bootstrap';(bootstrap/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'sdk/examples/counter/src/main.cpp',bootstrap/'src/main.cpp')
            write_json(bootstrap/'app.json',{'abi':1,'id':'root-counter','name':'Root counter','version':'1.0.0','license':'CC-BY-NC-SA-4.0'})
            start=output/'bootstrap.lfapp';shutil.copyfile(cli.package(bootstrap),start)
            document=b'LFNOTE1\n2+3\nx^2\n';input_file=root/'notebook.txt';input_file.write_bytes(document)
            backup=output/'original.lfarchive';baseline={};media=None
            with opened(project,'root-recovery') as (workspace,_):
                for phase in ('seed','fault','cold'):
                    folder=output/phase;folder.mkdir();records=[]
                    if phase=='fault':
                        before=digest(workspace/'nand.overlay')
                        media=json.loads(subprocess.check_output([fixture,'root-media',workspace/'nand.overlay',APP],text=True,timeout=30))
                        assert digest(workspace/'nand.overlay')==before;write_json(output/'root-media.json',media)
                    def controls(channel):
                        normal=Controls(channel,folder);app=channel.app_client;archives=Archives(app);data=DataClient(app)
                        def invoke(name,*arguments):
                            result=command(app.transport,*arguments);write_json(folder/(name+'.json'),result)
                            assert result['exit_status']==0 and not result['stderr'],result
                            return json.loads(result['stdout'])
                        def open_note():
                            normal.key('back');entry=next(e for e in app.catalog() if e['id']==APP)
                            assert channel.command(f"APP OPEN {entry['slot']}")=='OK';wait_notebook(normal,records)
                            normal.run({'steps':[{'capture':'notebook'}]},records)
                            path=folder/'notebook.ppm'
                            if path.exists():
                                with Image.open(path) as frame:frame.save(path.with_suffix('.png'))
                            normal.key('home');app.wait()
                        try:
                            normal.key('home');app.wait();assert app.status()['reserved']&32768
                            if phase=='seed':
                                app.install(artifacts['1.0.0'].read_bytes(),[PUBLIC])
                                FileClient(app).import_file(APP,'notebook.txt',input_file)
                                app.install(artifacts['2.0.0'].read_bytes(),[PUBLIC]);assert data.info(APP)['pending_upgrade']
                                pending=folder/'pending.lfarchive';archives.export(APP,pending,[PUBLIC])
                                open_note();assert not data.info(APP)['pending_upgrade']
                                app.install(artifacts['3.0.0'].read_bytes(),[PUBLIC]);data.rollback(APP)
                                assert data.info(APP)['version']=='2.0.0' and data.info(APP)['high_version']=='3.0.0'
                                archives.restore(pending,[PUBLIC],replace=True)
                                baseline.update(archives.info(APP));assert baseline['root_protection']=='both'
                                assert baseline['pending_upgrade'] and baseline['high_version']==(3,0,0)
                                archives.export(APP,backup,[PUBLIC])
                                record('public-install-rollback-restore-retains-version-history-above-both-packages',info=baseline)
                            else:
                                fault(normal,media,2)
                                if phase=='fault':
                                    overlay=digest(workspace/'nand.overlay')
                                    info=invoke('info','info',APP)
                                    assert info['root_protection']=='metadata-only' and info['high_version']==[3,0,0] and info['pending_upgrade']
                                    recovered=folder/'recovered.lfarchive'
                                    invoke('export','export',APP,recovered,'--public-key',PUBLIC)
                                    assert recovered.read_bytes()==backup.read_bytes() and digest(workspace/'nand.overlay')==overlay
                                    record('CLI-read-only-recovery-export-matches-both-original-signed-pairs',info=info)
                                    try:app.install(artifacts['2.5.0'].read_bytes(),[PUBLIC])
                                    except DeviceError as exc:refusal=str(exc)
                                    else:raise AssertionError('Unreadable root permitted a version below retained history')
                                    assert archives.info(APP)['generation']==baseline['generation']
                                    record('public-installer-rejects-2.5-after-3.0-history',error=refusal)
                                    progress=[0]
                                    try:archives.restore(recovered,[PUBLIC],replace=True,cancelled=lambda:progress[0]>2048,
                                                         progress=lambda done,total:progress.__setitem__(0,done))
                                    except DeviceError as exc:cancelled=str(exc)
                                    else:raise AssertionError('Cancelled restore committed')
                                    assert progress[0]>2048 and archives.info(APP)['generation']==baseline['generation']
                                    record('cancelled-repair-retains-original-root-and-recovery-pair',error=cancelled)
                                    invoke('restore','restore',recovered,'--replace','--public-key',PUBLIC)
                                    info=invoke('after','info',APP)
                                    assert info['root_protection']=='both' and info['high_version']==[3,0,0] and info['pending_upgrade']
                                    exported=folder/'after.lfarchive';archives.export(APP,exported,[PUBLIC]);assert exported.read_bytes()==backup.read_bytes()
                                    record('CLI-explicit-restore-rebuilds-both-copies-with-original-page-unreadable',info=info)
                                else:
                                    info=archives.info(APP);assert info['root_protection']=='both' and info['pending_upgrade'] and info['high_version']==(3,0,0)
                                    archives.export(APP,folder/'cold.lfarchive',[PUBLIC]);assert (folder/'cold.lfarchive').read_bytes()==backup.read_bytes()
                                    open_note();assert not data.info(APP)['pending_upgrade'] and data.info(APP)['high_version']=='3.0.0'
                                    exported=folder/'notebook.txt';FileClient(app).export_file(APP,'notebook.txt',exported);assert exported.read_bytes()==document
                                    record('cold-restored-Notebook-opens-original-document-and-accepts-retained-upgrade')
                        finally:
                            if media:fault(normal,media,0)
                            normal.close()
                    result=exercise(start,qemu,firmware,workspace=workspace,controls=controls)
                    assert result['result']==1 and result['os_responsive'];write_json(folder/'runtime.json',result)
                    shutil.copyfile(workspace/'nand.overlay',folder/'nand.overlay')
            assert report['sdk_sha256']==identity(ROOT/'sdk') and report['firmware_sha256']==digest(firmware)
            assert report['qemu_sha256']==digest(qemu)
            for name,value in report['sources'].items():assert digest(ROOT/name)==value,name
            report['status']='passed';write_json(output/'report.json',report)
    except BaseException as exc:
        report.update(status='failed',error=str(exc));write_json(output/'report.json',report);raise


if __name__=='__main__':main()
