#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual ARM widget clipping, long fields, menus and dialog/input journeys."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from cli import package
from preview import inspect_layout
from replay import Controls
from runner import exercise
from workspace import opened
CLIPS=[(0,0,320,240),(83,82,133,41),(0,0,100,240),(130,0,190,240),(0,108,320,132),(91,111,94,3),(0,0,0,0)]


def settled(normal,path,marker=None):
    deadline=time.monotonic()+15;previous=None;since=None
    while time.monotonic()<deadline:
        assert normal.channel.command('APP DIAG 15')=='VALUE 0','App exited: '+normal.channel.command('APP DIAG 21')
        normal.execute('screendump',{'filename':str(path.resolve())})
        with Image.open(path) as source:frame=source.convert('RGB')
        ready=frame.size==(320,240) and (marker is None or frame.getpixel((0,239))==marker)
        now=time.monotonic();pixels=frame.tobytes()
        if ready and pixels==previous:
            if since is not None and now-since>=.15:return frame
        else:since=now if ready else None
        previous=pixels;time.sleep(.05)
    raise AssertionError('The app did not render a stable expected frame')


def retain(project,artifact,target):
    target.mkdir(parents=True)
    for name in ('app-debug.elf','build.json',artifact.name):shutil.copyfile(project/'build'/name,target/name)


def paint(args,out,report):
    with tempfile.TemporaryDirectory(prefix='sdk-widget-paint-') as temp:
        project=Path(temp);(project/'src').mkdir();shutil.copyfile(ROOT/'tests/native/sdk_widget_paint.cpp',project/'src/main.cpp')
        write_json(project/'app.json',{'abi':1,'id':'widget-paint','name':'Widget Paint','version':'1.0.0','license':'GPL-3.0-or-later',
            'schema':1,'minimum_api':9,'required_capabilities':1042,'optional_capabilities':0,'data_schema':0})
        for profile in ('debug','release'):
            for kind in args.paint_kinds:
                write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.cpp'],'arguments':[str(kind)]})
                artifact=package(project,profile);folder=out/'paint'/profile/str(kind);retain(project,artifact,folder)
                case={'profile':profile,'kind':kind,'frames':[]};report['paint'].append(case)
                def controls(channel):
                    normal=Controls(channel,folder);reference=None
                    try:
                        for page,clip in enumerate(CLIPS):
                            if page:normal.key('ok')
                            frame=settled(normal,folder/f'{page}.ppm',(0,255,0) if page%2 else (255,0,0))
                            frame.save(folder/f'{page}.png')
                            if kind in (17,18,19,22):
                                untouched=Image.new('RGB',(320,240),frame.getpixel((319,0)))
                                untouched.paste(frame.crop((0,238,2,240)),(0,238))
                                assert ImageChops.difference(frame,untouched).getbbox() is None,'Rejected paragraph changed pixels'
                            if reference is None:reference=frame.copy()
                            expected=Image.new('RGB',(320,240),reference.getpixel((319,0)))
                            x,y,w,h=clip
                            if w and h:expected.paste(reference.crop((x,y,x+w,y+h)),(x,y))
                            expected.paste(frame.crop((0,238,2,240)),(0,238))
                            difference=ImageChops.difference(frame,expected)
                            if difference.getbbox():difference.save(folder/f'{page}-difference.png')
                            assert difference.getbbox() is None,(kind,page,difference.getbbox())
                            if profile=='debug':
                                details=folder/f'layout-{page}';details.mkdir()
                                layout=inspect_layout(normal,folder/'app-debug.elf',details)
                                assert not layout['overflow'];assert next(n for n in layout['nodes'] if n['id']==900)['name']==str(page)
                            case['frames'].append({'page':page,'clip':clip,'sha256':digest(folder/f'{page}.png')})
                        assert channel.command('PING')=='PONG'
                    finally:normal.close()
                with opened(project,f'paint-{kind}-{profile}') as (workspace,_):
                    result=exercise(artifact,args.qemu,args.firmware,workspace=workspace,controls=controls)
                assert result['result']==1 and result['os_responsive'] and not result['program']['exited'],result
                case.update(status='passed',runtime=result);write_json(out/'report.json',report);print('PASS: paint',profile,kind,flush=True)
        if 6 in args.paint_kinds and 10 in args.paint_kinds:
            for profile in ('debug','release'):
                for page in range(len(CLIPS)):
                    with Image.open(out/'paint'/profile/'6'/f'{page}.png') as a,Image.open(out/'paint'/profile/'10'/f'{page}.png') as b:
                        assert a.tobytes()==b.tobytes(),'Long field differs from its visible short suffix'


def gallery(args,out,report):
    with tempfile.TemporaryDirectory(prefix='sdk-ui-gallery-') as temp:
        project=Path(temp)/'External Gallery é';shutil.copytree(ROOT/'sdk/examples/ui-gallery',project)
        for profile in ('debug','release'):
            artifact=package(project,profile);folder=out/'gallery'/profile;retain(project,artifact,folder)
            symbols=subprocess.check_output(['arm-none-eabi-nm',str(folder/'app-debug.elf')],text=True)
            assert ('lefony_ui_debug' in symbols)==(profile=='debug')
            case={'profile':profile,'frames':[]};report['gallery'].append(case)
            def controls(channel):
                normal=Controls(channel,folder);records=[]
                def touch(*contacts):normal.run({'steps':[{'touch':[list(c) for c in contacts]}]},records)
                def tap(x,y):touch((1,x,y));touch()
                def key(name,count=1):
                    for _ in range(count):normal.key(name)
                def snapshot(name,*,title=None,field=None,focused=None,disabled=(),pressed=None,message=None):
                    frame=settled(normal,folder/(name+'.ppm'));frame.save(folder/(name+'.png'))
                    if profile=='debug':
                        details=folder/name;details.mkdir();layout=inspect_layout(normal,folder/'app-debug.elf',details)
                        assert not layout['overflow'];nodes={n['id']:n for n in layout['nodes']}
                        if title is not None:assert nodes[50]['name']==title,(name,nodes[50])
                        if field is not None:assert nodes[10]['name']==field,(name,nodes[10])
                        if focused is not None:assert [n['id'] for n in layout['nodes'] if n['state']&2]==[focused],(name,layout)
                        for id in disabled:assert not nodes[id]['state']&1,(name,nodes[id])
                        if pressed is not None:assert nodes[pressed]['state']&4,(name,nodes[pressed])
                        if message is not None:assert message in nodes[52]['name'],(name,nodes[52])
                        assert all(n['file']=='src/main.cpp' and n['line']>0 for n in layout['nodes'])
                    case['frames'].append({'name':name,'sha256':digest(folder/(name+'.png'))});print('FRAME:',profile,name,flush=True)
                def actions():tap(260,20)
                try:
                    snapshot('initial',title='UI gallery',field='Cafe\u0301 \u03c0',focused=10)
                    touch((1,50,118));snapshot('choice-pressed',pressed=11)
                    touch((1,180,118));touch();snapshot('choice-cancelled',title='UI gallery',field='Cafe\u0301 \u03c0')
                    tap(50,118);snapshot('disabled',disabled=(10,12,13),focused=11)
                    tap(230,118);snapshot('disabled-tap',title='UI gallery',disabled=(10,12,13))
                    tap(50,118);key('up');key('ok');key('seven');snapshot('edited',field='7',focused=10)
                    tap(230,118);snapshot('dialog',title='Confirmation',focused=21)
                    touch((1,50,150));touch((1,300,180));touch();snapshot('dialog-cancelled-drag',title='Confirmation')
                    tap(200,150);snapshot('cancel-return',title='UI gallery',field='7',focused=12)
                    tap(230,118);key('left');key('ok');snapshot('confirmed',field='Ready',focused=12)
                    touch((1,80,160));touch((1,180,160));snapshot('slider-pressed',pressed=13)
                    touch((1,319,160));touch();snapshot('slider-cancelled',message='Value: 50')
                    touch((1,70,160));touch((1,220,160));touch();snapshot('slider-committed',message='Value: 72')
                    actions();snapshot('menu',title='Actions',focused=100,disabled=(101,))
                    tap(40,95);snapshot('menu-disabled',title='Actions',focused=100)
                    touch((1,40,125));touch((2,40,125));touch();snapshot('menu-contact-cancelled',title='Actions')
                    tap(40,125);snapshot('long-field',title='UI gallery',field='a'*31,focused=10)
                    actions();key('down',3);key('ok');snapshot('fonts',title='OS fonts')
                    key('back');actions();key('down',7);key('ok');snapshot('paragraphs',title='Wrapped text')
                    key('back');actions();key('ok');snapshot('dark',title='UI gallery')
                    actions();key('down',4);key('ok');snapshot('empty-menu',title='Menu states')
                    key('ok');key('down');snapshot('empty-no-action',title='Menu states')
                    tap(260,20);actions();key('down',5);key('ok');snapshot('loading',title='Menu states')
                    normal.run({'steps':[{'wait_ms':3200}]},records);snapshot('ready',title='Menu states',focused=300)
                    key('ok');snapshot('loaded-action',title='UI gallery')
                    actions();touch((1,60,180));touch((1,60,100));key('home');touch()
                    normal.run({'steps':[{'relaunch':True}]},records);snapshot('relaunch',title='UI gallery',field='Cafe\u0301 \u03c0',focused=10)
                    assert channel.command('PING')=='PONG'
                finally:normal.close()
            with opened(project,'gallery-'+profile) as (workspace,_):
                result=exercise(artifact,args.qemu,args.firmware,workspace=workspace,controls=controls)
            assert result['result']==1 and result['os_responsive'] and not result['program']['exited'],result
            case.update(status='passed',runtime=result);write_json(out/'report.json',report)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--qemu',type=Path,default=ROOT/'build/qemu-prime-g2/qemu-system-arm')
    parser.add_argument('--only',choices=('all','paint','gallery'),default='all')
    parser.add_argument('--paint-kinds',type=int,nargs='+',choices=range(25),default=list(range(25)))
    args=parser.parse_args();args.firmware=args.firmware.resolve();args.qemu=args.qemu.resolve()
    out=args.output.resolve();out.mkdir(parents=True)
    report={'schema':1,'status':'running','physical':'not_tested','sdk_sha256':identity(ROOT/'sdk'),
        'firmware_sha256':digest(args.firmware),'qemu_sha256':digest(args.qemu),'paint':[],'gallery':[]}
    write_json(out/'report.json',report)
    try:
        if args.only!='gallery':paint(args,out,report)
        if args.only!='paint':gallery(args,out,report)
        matches=[]
        for family in ('paint','gallery'):
            for path in sorted((out/family/'debug').rglob('*.png')):
                other=out/family/'release'/path.relative_to(out/family/'debug')
                with Image.open(path) as a,Image.open(other) as b:assert a.tobytes()==b.tobytes(),str(path)
                matches.append(str(path.relative_to(out)))
        assert report['sdk_sha256']==identity(ROOT/'sdk'),'SDK changed during qualification'
        report.update(status='passed',matching_frames=matches,sources={str(p.relative_to(ROOT)):digest(p) for p in
            [Path(__file__),ROOT/'tests/native/sdk_widget_paint.cpp',ROOT/'sdk/include/lefony/ui_widgets.h',
             ROOT/'sdk/include/lefony/ui_patterns.h',ROOT/'sdk/include/lefony/ui_paragraph.h',ROOT/'sdk/examples/ui-gallery/src/main.cpp']})
        write_json(out/'report.json',report)
    except Exception as exc:
        report.update(status='failed',error=str(exc));write_json(out/'report.json',report);raise


if __name__=='__main__':main()
