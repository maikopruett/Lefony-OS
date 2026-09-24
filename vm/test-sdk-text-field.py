#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Normal Goodix/keypad field editing, cancelled selection and durable Notebook saves."""
import argparse
from contextlib import contextmanager,nullcontext
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from cli import package
from device import Client
from files_device import FileClient,REQUEST,INFO,EXPORT,LIST
from preview import inspect_layout
from replay import Controls
from runner import exercise
from workspace import opened
from signing import verify
from sdk_notebook_probe import wait_notebook
spec=importlib.util.spec_from_file_location('components',ROOT/'vm/test-sdk-ui-components.py')
components=importlib.util.module_from_spec(spec);spec.loader.exec_module(components)
INITIAL=b'LFNOTE3\nL\n0 0 07\n2+3*4\n'
SAVED=b'LFNOTE3\nL\n0 0 07\n2+9*24\n'


@contextmanager
def read_existing(records):
    """Cold bootstrap authenticates/readbacks the package, with no installation."""
    original_write=Client.write
    def existing(client,content,keys):
        metadata,_=verify(content,keys);client.require_compatible(metadata)
        matches=[entry for entry in client.catalog() if entry['id']==metadata['id']]
        assert len(matches)==1,matches
        entry=matches[0]
        assert entry['version']==metadata['version'] and entry['bytes']==len(content),entry
        actual=client.read_package(entry['slot'],entry['bytes'])
        assert actual==content,'Cold package changed; no repair attempted'
        records['bootstrap']={'action':'public-readback-only','catalog':entry,'sha256':hashlib.sha256(actual).hexdigest()}
        return entry
    def read_only_write(client,request,data=b'',argument=0):
        assert request in (0x6a,0x71,0x73,0x75),('unexpected host mutation',request)
        if request==0x71:assert REQUEST.unpack(data)[2] in (INFO,EXPORT,LIST),'unexpected file mutation'
        key=hex(request);counts=records.setdefault('host_requests',{});counts[key]=counts.get(key,0)+1
        return original_write(client,request,data,argument)
    with patch.object(Client,'install',existing),patch.object(Client,'write',read_only_write):yield


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--qemu',type=Path,default=ROOT/'build/qemu-prime-g2/qemu-system-arm')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--only',choices=('all','notebook','gallery'),default='all')
    args=parser.parse_args();args.firmware=args.firmware.resolve();args.qemu=args.qemu.resolve()
    output=args.output.resolve();output.mkdir(parents=True)
    report={'schema':1,'status':'running','sdk_sha256':identity(ROOT/'sdk'),
        'firmware_sha256':digest(args.firmware),'qemu_sha256':digest(args.qemu),'physical':'not_tested','cases':[]}
    write_json(output/'report.json',report)
    try:
        with tempfile.TemporaryDirectory(prefix='sdk-field-é-') as temp:
            for app in ('notebook','ui-gallery'):
                if args.only!='all' and (args.only=='notebook')!=(app=='notebook'):continue
                project=Path(temp)/app
                shutil.copytree(ROOT/'sdk/examples'/app,project,ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json'))
                for profile in ('debug','release'):
                    artifact=package(project,profile);retained=output/app/profile;retained.mkdir(parents=True)
                    for name in (artifact.name,'app.elf','app-debug.elf','build.json'):
                        shutil.copyfile(project/'build'/name,retained/name)
                    symbols=subprocess.check_output(['arm-none-eabi-nm',str(retained/'app-debug.elf')],text=True)
                    assert ('lefony_ui_debug' in symbols)==(profile=='debug')
                    for phase in (('edit','cold') if app=='notebook' else ('edit',)):
                        folder=retained/phase;folder.mkdir();records=[];frames=[]
                        case={'app':app,'profile':profile,'phase':phase,'status':'running','steps':records,'frames':frames}
                        report['cases'].append(case)
                        def prepare(client):
                            source=folder/'input.txt';source.write_bytes(INITIAL)
                            FileClient(client).import_file('notebook','notebook.txt',source)
                        def controls(channel):
                            normal=Controls(channel,folder)
                            def run(step):normal.run({'steps':[step]},records)
                            def key(name):run({'key':name})
                            def touch(*contacts):run({'touch':[list(c) for c in contacts]})
                            def tap(x,y):touch((1,x,y));touch()
                            def snapshot(name,*,title=None,text=None):
                                if app=='notebook':wait_notebook(normal,records)
                                frame=components.settled(normal,folder/(name+'.ppm'));frame.save(folder/(name+'.png'))
                                if profile=='debug':
                                    details=folder/name;details.mkdir();layout=inspect_layout(normal,retained/'app-debug.elf',details)
                                    assert not layout['overflow'];nodes={n['id']:n for n in layout['nodes']}
                                    if title is not None:assert nodes[50]['name']==title,(name,nodes[50])
                                    if text is not None:assert nodes[10]['name']==text,(name,nodes.get(10))
                                frames.append({'name':name,'sha256':digest(folder/(name+'.png'))})
                                print('FRAME:',app,profile,phase,name,flush=True)
                                return frame
                            def same_field(before,after):
                                box=(12,65,308,97) if app=='notebook' else (12,62,308,94)
                                assert before.crop(box).tobytes()==after.crop(box).tobytes(),'cancelled gesture changed field painting'
                            try:
                                snapshot('initial',title='Notebook' if app=='notebook' else 'UI gallery')
                                if app=='notebook':
                                    key('ok');snapshot('opened',title='Edit expression',text='2+3*4' if phase=='edit' else '2+9*24')
                                    if phase=='edit':
                                        tap(32,80);snapshot('tap-caret',title='Edit expression',text='2+3*4')
                                        key('seven');snapshot('insert-middle',text='2+73*4')
                                        touch((1,32,80));touch((1,46,80));snapshot('drag-selection',text='2+73*4');touch()
                                        key('nine');baseline=snapshot('replace-selection',text='2+9*4')
                                        for name,contacts in (
                                            ('outside',[(1,60,205)]),('second-contact',[(1,32,80),(2,50,80)]),
                                            ('changed-contact',[(2,32,80)])):
                                            touch((1,18,80));touch(*contacts);touch()
                                            after=snapshot('cancel-'+name,title='Edit expression',text='2+9*4');same_field(baseline,after)
                                        touch((1,18,80));key('right');touch();key('two')
                                        snapshot('key-during-touch',text='2+9*24')
                                        tap(60,205);snapshot('saved',title='Notebook')
                                        tap(260,205);snapshot('exported',title='Notebook')
                                        tap(60,80);snapshot('reopened',title='Edit expression',text='2+9*24')
                                        touch((1,18,80));key('home');touch()
                                        run({'relaunch':True});snapshot('home-relaunch',title='Notebook')
                                    key('home');channel.wait_for_storage()
                                    files=FileClient(channel.app_client)
                                    for name in ('notebook.txt','export.txt'):files.export_file('notebook',name,folder/name,replace=True)
                                    assert (folder/'notebook.txt').read_bytes()==SAVED
                                    assert (folder/'export.txt').read_bytes()==b'# Notebook DEG AUTO 7 / x=1\n2+9*24 = 218\n'
                                else:
                                    touch((1,39,78));touch((1,46,78));snapshot('accent-selection',text='Cafe\u0301 \u03c0');touch()
                                    key('five');snapshot('accent-replaced',text='Caf5 \u03c0')
                                    tap(53,78);key('one');snapshot('before-pi',text='Caf5 1\u03c0')
                                    tap(50,118);baseline=snapshot('disabled',text='Caf5 1\u03c0')
                                    tap(39,78);same_field(baseline,snapshot('disabled-touch',text='Caf5 1\u03c0'))
                                    tap(50,118);tap(18,78);key('ok');key('backspace');snapshot('empty',text='')
                                    tap(290,78);key('eight');snapshot('empty-insert',text='8')
                                    tap(260,20);tap(50,125);snapshot('maximum',text='a'*31)
                                    touch((1,277,78));touch((1,298,78));snapshot('maximum-suffix-selection');touch()
                                    key('nine');snapshot('maximum-suffix-replaced',text='a'*31)
                                    key('ok');key('nine');snapshot('maximum-replaced',text='9')
                                    touch((1,18,78));key('home');touch();run({'relaunch':True})
                                    snapshot('home-relaunch',title='UI gallery',text='Cafe\u0301 \u03c0')
                                    key('home');channel.wait_for_storage()
                                assert channel.command('PING')=='PONG'
                            finally:write_json(folder/'steps.json',records);normal.close()
                        with opened(project,profile) as (workspace,_),read_existing(case) if phase=='cold' else nullcontext():
                            result=exercise(artifact,args.qemu,args.firmware,workspace=workspace,controls=controls,
                                prepare_workspace=prepare if app=='notebook' and phase=='edit' else None)
                        assert result['result']==1 and result['os_responsive'],result
                        case.update(status='passed',runtime=result);write_json(output/'report.json',report)
                        print('PASS:',app,profile,phase,flush=True)
        matches=[]
        for path in output.glob('*/debug/**/*.png'):
            parts=path.relative_to(output).parts;other=output/parts[0]/'release'/Path(*parts[2:])
            with Image.open(path) as a,Image.open(other) as b:assert a.size==b.size and a.tobytes()==b.tobytes(),str(path)
            matches.append(str(path.relative_to(output)))
        assert report['sdk_sha256']==identity(ROOT/'sdk'),'SDK changed during qualification'
        sources=[Path(__file__),ROOT/'sdk/include/lefony/ui_model.h',ROOT/'sdk/include/lefony/ui_text_field.h',
            ROOT/'sdk/include/lefony/ui_widgets.h',ROOT/'tests/native/sdk_text_field.cpp',
            ROOT/'sdk/examples/notebook/src/main.cpp',ROOT/'sdk/examples/ui-gallery/src/main.cpp']
        report.update(status='passed',matching_frames=sorted(matches),sources={str(p.relative_to(ROOT)):digest(p) for p in sources})
        write_json(output/'report.json',report)
    except BaseException as exc:
        report.update(status='failed',error=str(exc));write_json(output/'report.json',report);raise


if __name__=='__main__':main()
