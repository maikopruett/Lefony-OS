#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""External C++ document app: input, live saves, export, old/malformed data and release parity."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json,identity
from cli import package
from files_device import FileClient
from preview import inspect_layout
from replay import Controls,load
from runner import exercise
from workspace import opened
from sdk_notebook_probe import wait_notebook


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-notebook-system/notebook')
    parser.add_argument('--measure-resources',action='store_true')
    parser.add_argument('--profile-heap',action='store_true',help='Build the temporary project with newlib heap diagnostics; requires --measure-resources')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    if args.profile_heap and not args.measure_resources:parser.error('--profile-heap requires --measure-resources')
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm';cases=[]
    sdk_identity=identity(ROOT/'sdk')
    def tap(x,y):return [{'touch':[[1,x,y]]},{'touch':[]}]
    def shortcut(key):return [{'key':'shift'},{'key':key}]
    with tempfile.TemporaryDirectory(prefix='sdk-notebook-') as temp:
        project=Path(temp)/'External C++ notebook é'
        shutil.copytree(ROOT/'sdk/examples/notebook',project,ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json'))
        if args.profile_heap:
            config=json.loads((project/'project.json').read_text())
            config.setdefault('defines',{})['LEFONY_PROFILE_HEAP']=1
            write_json(project/'project.json',config)
        shutil.copyfile(project/'project.json',output/'project.json')
        for profile in ('debug','release'):
            artifact=package(project,profile)
            symbols=subprocess.check_output(['arm-none-eabi-nm',str(project/'build/app-debug.elf')],text=True)
            assert ('lefony_ui_debug' in symbols)==(profile=='debug')
            retained=output/profile;retained.mkdir(exist_ok=True)
            for name in ('app-debug.elf','build.json',artifact.name):shutil.copyfile(project/'build'/name,retained/name)
            def execute(name,steps,fixture=None,exports=()):
                folder=retained/name;folder.mkdir(exist_ok=True);record=[]
                def prepare(client):
                    if fixture is not None:
                        source=folder/'input.txt';source.write_bytes(fixture)
                        FileClient(client).import_file('notebook','notebook.txt',source)
                def controls(channel):
                    normal=Controls(channel,folder)
                    try:
                        wait_notebook(normal,record)
                        for step in steps:
                            normal.run({'steps':[step]},record)
                            if step.get('key')=='ok' or step.get('touch')==[]:
                                wait_notebook(normal,record)
                        if profile=='debug':inspect_layout(normal,retained/'app-debug.elf',folder)
                        normal.key('home');channel.wait_for_storage();files=FileClient(channel.app_client)
                        for path in exports:files.export_file('notebook',path,folder/path,replace=True)
                    finally:normal.close()
                with opened(project,name+'-'+profile) as (workspace,_):
                    result=exercise(artifact,qemu,args.firmware,controls=controls,workspace=workspace,
                        prepare_workspace=prepare if fixture is not None else None,measure_resources=args.measure_resources)
                assert result['result']==1 and result['os_responsive'],result
                if args.profile_heap:assert result['resources']['heap']['status'] in ('observed','not_observed'),result
                cases.append({'profile':profile,'name':name,'runtime':result,'steps':record});print('PASS:',profile,name,flush=True)
                return folder
            steps=load(project/'tests/edit.json')['steps']
            folder=execute('edit',steps,exports=('notebook.txt','export.txt'))
            assert (folder/'notebook.txt').read_bytes()==b'LFNOTE3\nD\n0 0 07\n2+3*4\n'
            assert (folder/'export.txt').read_bytes()==b'# Notebook DEG AUTO 7 / x=1\n2+3*4 = 14\n'
            # The same exact package and synthetic media cold-start again.
            cold=execute('edit',[{'capture':'cold'},{'key':'ok'},{'capture':'cold-editor'}],exports=('notebook.txt',))
            assert (cold/'notebook.txt').read_bytes()==b'LFNOTE3\nD\n0 0 07\n2+3*4\n'
            old=b'LFNOTE1\n'+b'1+2+3+4+5+6+7+8+9+10+11+12+13+14+15+16+17+18+19+20\n'+b'x^2\n2+2\n3+3\n4+4\n'
            steps=[{'capture':'old'},{'key':'down'},{'key':'down'},{'key':'down'},{'capture':'scrolled'},
                {'different':['old','scrolled']},{'key':'ok'},{'capture':'old-editor'},{'key':'ok'},{'capture':'upgraded'}]
            folder=execute('old',steps,old,('notebook.txt',))
            assert (folder/'notebook.txt').read_bytes()==b'LFNOTE3\nL\n1 0 09\n'+old[8:]
            bad=b'LFNOTE4\nfuture document bytes\n'
            folder=execute('bad',[{'capture':'error'},{'touch':[[1,30,205]]},{'touch':[]},{'capture':'disabled'},
                                 {'same':['error','disabled']}],bad,('notebook.txt',))
            assert (folder/'notebook.txt').read_bytes()==bad
            steps=[{'key':'ok'},{'key':'plus'},{'capture':'invalid'},{'key':'ok'},{'capture':'invalid-save'},
                {'key':'back'},{'capture':'discard'},{'key':'back'},{'capture':'cancelled'},
                {'key':'backspace'},{'capture':'fixed'},{'key':'ok'},{'capture':'saved'}]
            folder=execute('validation',steps,exports=('notebook.txt',))
            assert (folder/'notebook.txt').read_bytes()==b'LFNOTE3\nL\n0 0 07\n2+3*4\n'
            # Document settings are explicit, saved atomically and independent
            # of later OS defaults. Old documents retain radians/auto/9 digits.
            old2=b'LFNOTE2\nL\nsin(30)\nasin(1)\n123456\nsqrt(-1)\n'
            steps=tap(260,20)+[{'capture':'options'}]+tap(55,70)+tap(260,120)+tap(86,165)
            steps += [{'capture':'degree-engineering-four'}]+tap(55,205)+tap(260,205)+[{'capture':'formatted'}]
            folder=execute('options',steps,old2,('notebook.txt','export.txt'))
            settings=b'LFNOTE3\nL\n0 2 04\n'+old2[10:]
            assert (folder/'notebook.txt').read_bytes()==settings
            assert (folder/'export.txt').read_bytes()==(b'# Notebook DEG ENG 4 / x=1\nsin(30) = 500.0e-3\n'
                b'asin(1) = 90.00e+0\n123456 = 123.5e+3\nsqrt(-1) = Undefined result at 1\n')
            cold=execute('options',[{'capture':'cold-options'},{'key':'ok'},{'capture':'cold-sine'}],exports=('notebook.txt',))
            assert (cold/'notebook.txt').read_bytes()==settings
            # A drag leaving its bounds or acquiring another contact reverts;
            # dismissing the options page also discards unsaved choices.
            steps=tap(260,20)+[{'touch':[[1,298,165]]},{'touch':[[1,310,165]]},{'touch':[]},
                {'touch':[[1,298,165]]},{'touch':[[1,298,165],[2,240,160]]},{'touch':[]},
                {'capture':'cancelled-drags'}]+tap(55,205)
            steps+=tap(260,20)+tap(160,205)+[{'capture':'os-defaults'}]+tap(260,205)+[{'capture':'cancelled-options'}]
            folder=execute('cancel-options',steps,settings,('notebook.txt',))
            assert (folder/'notebook.txt').read_bytes()==settings
            steps=tap(260,20)+tap(260,70)+tap(160,120)+tap(107,165)
            steps += [{'key':'right'},{'key':'left'},{'capture':'gradian-scientific-five'}]+tap(55,205)+tap(260,205)
            grad=b'LFNOTE3\nL\n1 0 09\nsin(100)\nasin(1)\n'
            folder=execute('gradians',steps,grad,('notebook.txt','export.txt'))
            assert (folder/'notebook.txt').read_bytes()==b'LFNOTE3\nL\n2 1 05\n'+grad[17:]
            assert (folder/'export.txt').read_bytes()==b'# Notebook GRAD SCI 5 / x=1\nsin(100) = 1.0000e+00\nasin(1) = 1.0000e+02\n'
            # Normal Copy/Cut/Paste gestures; first the whole expression, then
            # Shift+Left selects one character to append through the clipboard.
            steps=[{'key':'ok'}]+shortcut('view')+tap(260,20)+shortcut('ok')+[{'capture':'cut'}]
            steps+=shortcut('menu')+[{'capture':'pasted'}]+shortcut('left')+shortcut('view')
            steps += [{'key':'right'},{'key':'plus'}]+shortcut('menu')+[{'capture':'selection-paste'},{'key':'ok'}]+tap(260,205)
            folder=execute('clipboard',steps,exports=('notebook.txt','export.txt'))
            assert (folder/'notebook.txt').read_bytes()==b'LFNOTE3\nL\n0 0 07\n2+3*4+4\n'
            assert (folder/'export.txt').read_bytes()==b'# Notebook DEG AUTO 7 / x=1\n2+3*4+4 = 18\n'
            maximum=b'LFNOTE3\nL\n0 0 07\n'+b'1'*95+b'\n'
            steps=[{'key':'ok'},{'capture':'full-before'}]+shortcut('view')+shortcut('menu')+[{'capture':'full-rejected'},{'key':'ok'}]
            folder=execute('clipboard-full',steps,maximum,('notebook.txt',))
            assert (folder/'notebook.txt').read_bytes()==maximum
            with Image.open(folder/'full-before.ppm') as before,Image.open(folder/'full-rejected.ppm') as after:
                assert before.crop((12,65,308,97)).tobytes()==after.crop((12,65,308,97)).tobytes(),'rejected paste edited the field'
            folder=execute('legacy-radians',tap(260,205),b'LFNOTE2\nD\nsin(30)\n',('export.txt',))
            assert (folder/'export.txt').read_bytes()==b'# Notebook RAD AUTO 9 / x=1\nsin(30) = -0.988031624\n'
        frames=[]
        for path in (output/'debug').rglob('*.ppm'):
            other=output/'release'/path.relative_to(output/'debug')
            with Image.open(path) as a,Image.open(other) as b:
                assert a.size==b.size and a.tobytes()==b.tobytes(),f'debug/release image mismatch: {path}'
                png=path.with_suffix('.png');a.save(png);frames.append(str(png.relative_to(output)))
    assert sdk_identity==identity(ROOT/'sdk'),'SDK changed during qualification'
    write_json(output/'report.json',{'schema':1,'status':'passed','firmware_sha256':digest(args.firmware),'sdk_sha256':sdk_identity,
        'qemu_sha256':digest(qemu),'physical':'not_tested','cases':cases,'matching_frames':frames,
        'sources':{str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/'sdk/examples/notebook/src').glob('*'))}})


if __name__=='__main__':main()
