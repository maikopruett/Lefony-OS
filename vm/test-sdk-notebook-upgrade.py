#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Notebook accepts readable upgrades and retains an intact pair for failed ones."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
import archive_format as wire
from archive_device import Client as ArchiveClient
from cli import package
from data_device import DataClient
from device import DeviceError
from files_device import FileClient
from preview import inspect_layout
from replay import Controls
from runner import exercise
from workspace import opened
from sdk_notebook_probe import wait_notebook
from signing import sign,verify
PUBLIC=ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'
PRIVATE=ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem'
SCRATCH=b'Legacy notebook temporary bytes for explicit recovery\n'


def recovery_fixture(path,artifacts,bad,good):
    """A portable pending backup: readable old data and unsupported new data.

    Normal host file import deliberately refuses pending upgrades. Restore this
    explicit synthetic backup through the public archive API instead. Package
    signatures remain real; no guest memory or raw NAND is edited.
    """
    pairs=[];high=(0,0,0)
    for name,data in [('new',bad),('old',good)]:
        package=sign(artifacts[name].read_bytes(),PRIVATE);metadata,_=verify(package,[PUBLIC])
        version=tuple(map(int,metadata['version'].split('.')))
        high=max(high,version)
        pairs.append(wire.PAIR.pack(128,1,len(package),0,0,2,*version,*([0]*7),
            hashlib.sha256(package).digest(),hashlib.sha256(b'').digest())+package+
            wire.ENTRY.pack(b'notebook.txt',1,len(data),0,0)+data+hashlib.sha256(data).digest()+
            wire.ENTRY.pack(b'notebook.tmp',1,len(SCRATCH),0,0)+SCRATCH+hashlib.sha256(SCRATCH).digest())
    path.write_bytes(wire.HEADER.pack(b'LFARCH1\0',1,128,128+sum(map(len,pairs)),2,1,0,*high,*([0]*5),b'notebook')+b''.join(pairs))
    with path.open('rb') as source:checked=wire.validate(source,[PUBLIC])
    assert len(checked.snapshots)==2


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--previous-notebook',type=Path,required=True,help='exact preceding Notebook source project')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    firmware=output/'firmware.elf';shutil.copyfile(args.firmware,firmware);qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm'
    good=b'LFNOTE1\n2+3\nx^2\n';bad=b'LFNOTE99\nunsupported document\n'
    report={'schema':1,'status':'running','physical':'not_tested','firmware_sha256':digest(firmware),'qemu_sha256':digest(qemu),'cases':[]}
    write_json(output/'report.json',report)
    try:
        with tempfile.TemporaryDirectory(prefix='notebook-upgrade-') as temp:
            projects={};artifacts={};versions={}
            for name,source in [('old',args.previous_notebook),('new',ROOT/'sdk/examples/notebook')]:
                dest=Path(temp)/name;shutil.copytree(source,dest,ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json'))
                metadata=json.loads((dest/'app.json').read_text());versions[name]=metadata['version']
                if name=='new':assert tuple(map(int,versions['old'].split('.')))<tuple(map(int,versions['new'].split('.')))
                artifact=package(dest,'debug');target=output/name;target.mkdir()
                shutil.copytree(dest/'src',target/'src');shutil.copyfile(dest/'app.json',target/'app.json')
                for filename in ('app-debug.elf','build.json',artifact.name):shutil.copyfile(dest/'build'/filename,target/filename)
                projects[name]=dest;artifacts[name]=target/artifact.name
            report['versions']=versions
            for kind in ('readable','malformed'):
                for phase in (('initial','upgrade','cold') if kind=='readable' else ('initial','upgrade','cold-pending','cold')):
                    name='old' if phase=='initial' or kind=='malformed' and phase=='cold' else 'new'
                    target=output/f'{kind}-{phase}';target.mkdir();records=[];observed={}
                    def prepare(client):
                        if phase=='initial':
                            path=target/'fixture.txt';path.write_bytes(good)
                            FileClient(client).import_file('notebook','notebook.txt',path)
                            path=target/'scratch.txt';path.write_bytes(SCRATCH)
                            FileClient(client).import_file('notebook','notebook.tmp',path)
                        elif phase=='upgrade' and kind=='malformed':
                            path=target/'fixture.txt';path.write_bytes(bad)
                            try:FileClient(client).import_file('notebook','notebook.txt',path,replace=True)
                            except DeviceError as exc:
                                assert 'upgrade is not ready for import' in str(exc);observed['pending_import_rejected']=str(exc)
                            else:raise AssertionError('Pending upgrade allowed external data replacement')
                            path=target/'recovery.lfarchive';recovery_fixture(path,artifacts,bad,good)
                            ArchiveClient(client).restore(path,[PUBLIC],replace=True)
                        observed['before']=DataClient(client).info('notebook')
                    def controls(channel):
                        normal=Controls(channel,target);data=DataClient(channel.app_client)
                        try:
                            wait_notebook(normal,records);normal.run({'steps':[{'capture':'document'}]},records)
                            layout=inspect_layout(normal,artifacts[name].parent/'app-debug.elf',target)
                            retained=phase in ('upgrade','cold-pending') and kind=='malformed'
                            if retained:assert not next(n for n in layout['nodes'] if n['id']==1)['state']&1
                            normal.key('home');channel.app_client.wait();observed['info']=data.info('notebook')
                            assert observed['info']['pending_upgrade']==retained
                            destination=target/'notebook.txt';FileClient(channel.app_client).export_file('notebook','notebook.txt',destination)
                            assert destination.read_bytes()==(bad if retained else good)
                            files=FileClient(channel.app_client);entries=files.list('notebook')['entries']
                            scratch='notebook.tmp' in {entry['path'] for entry in entries}
                            assert scratch==(retained or name=='old'),'Temporary-file cleanup crossed the readable-upgrade boundary'
                            if scratch:
                                files.export_file('notebook','notebook.tmp',target/'exported-scratch.txt')
                                assert (target/'exported-scratch.txt').read_bytes()==SCRATCH
                            observed['legacy_scratch_preserved']=scratch
                            if retained:
                                assert observed['info']['rollback_available']
                                assert observed['info']['generation']==observed['before']['generation'],'Read-only startup changed the retained data pair'
                            if phase=='cold-pending':
                                observed['rollback']=data.rollback('notebook')
                                destination=target/'recovered.txt';FileClient(channel.app_client).export_file('notebook','notebook.txt',destination)
                                assert destination.read_bytes()==good
                            if phase=='cold':assert observed['info']['high_version']==versions['new']
                        finally:normal.close()
                    with opened(projects['new'],kind) as (media,_):
                        result=exercise(artifacts[name],qemu,firmware,workspace=media,prepare_workspace=prepare,controls=controls)
                        assert result['result']==1 and result['os_responsive']
                        shutil.copyfile(media/'nand.overlay',target/'nand.overlay')
                    report['cases'].append({'case':f'{kind}-{phase}','runtime':result,**observed})
                    write_json(output/'report.json',report);print('PASS:',kind,phase,flush=True)
        report.update(status='passed',sources={p:digest(ROOT/p) for p in ('sdk/examples/notebook/app.json','sdk/examples/notebook/src/main.cpp',
            'sdk/examples/notebook/src/document.h','sdk/examples/notebook/src/package_data.h','vm/test-sdk-notebook-upgrade.py')})
        write_json(output/'report.json',report)
    except Exception as exc:
        report.update(status='failed',error=str(exc));write_json(output/'report.json',report);raise


if __name__=='__main__':main()
