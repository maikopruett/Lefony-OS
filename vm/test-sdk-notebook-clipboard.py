#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Notebook exchanges real gesture-controlled clipboard text with OS/apps."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from cli import package
from files_device import FileClient
from replay import Controls
from runner import exercise
from signing import sign
from sdk_notebook_probe import wait_notebook

SEED=r'''/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#include <lefony/input.h>
#include <lefony/system.h>
#include <lefony/foreground.h>
static const char payload[]={PAYLOAD};
int main() {
  uint32_t sequence=0;
  for(;;) {
    Lefony::InputSnapshot input;
    if(Lefony::readInput(input)==0 && input.sequence!=sequence) {
      sequence=input.sequence;
      if(input.event==1 && input.key==Lefony::InputKey::Copy)
        return lefony_clipboard_write(input.sequence,payload,sizeof(payload))<0?2:0;
    }
    lefony_program_yield();
  }
}
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-notebook-system/clipboard')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm';sdk_identity=identity(ROOT/'sdk');cases=[]
    public=ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem';private=ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem'
    def shortcut(key):return [{'key':'shift'},{'key':key}]
    def tap(x,y):return [{'touch':[[1,x,y]]},{'touch':[]}]
    with tempfile.TemporaryDirectory(prefix='Notebook clipboard é ') as temp:
        root=Path(temp);project=root/'Notebook'
        shutil.copytree(ROOT/'sdk/examples/notebook',project,ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json'))
        for profile in ('debug','release'):
            artifact=package(project,profile);retained=output/profile;retained.mkdir(exist_ok=True)
            for item in ('app-debug.elf','build.json',artifact.name):shutil.copyfile(project/'build'/item,retained/item)
            for mode,payload,expected in [('calculator',None,b'2*3-1'),('unicode','π×2÷3−4',b'pi*2/3-4'),
                                         ('newline','two\nlines',b'2+3*4'),('oversized','1'*200,b'2+3*4')]:
                folder=retained/mode;folder.mkdir(exist_ok=True);records=[];seed={}
                if payload is not None:
                    helper=root/(profile+'-'+mode);(helper/'src').mkdir(parents=True)
                    (helper/'src/main.cpp').write_text(SEED.replace('PAYLOAD',','.join(str(b) for b in payload.encode('utf-8'))))
                    write_json(helper/'app.json',{'schema':1,'abi':1,'id':'notebook-clipboard-source','name':'Clipboard Source',
                        'version':'1.0.0','license':'CC-BY-NC-SA-4.0','minimum_api':10,
                        'required_capabilities':2066,'optional_capabilities':0,'data_schema':0})
                    write_json(helper/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.cpp']})
                    seed['package']=sign(package(helper,profile).read_bytes(),private)
                def controls(channel):
                    normal=Controls(channel,folder)
                    def run(steps):normal.run({'steps':steps},records)
                    def launch(slot):
                        assert channel.command(f'APP OPEN {slot}')=='OK'
                        run([{'wait_ms':500}])
                    try:
                        run([{'key':'home'}]);channel.wait_for_storage()
                        if payload is None:
                            assert channel.command('STATE').startswith('STATE app=1 '),'Home did not open Calculation'
                            run([{'key':key} for key in ('two','multiply','three','minus','one')])
                            run(shortcut('left')*5+shortcut('view')+[{'capture':'calculator-selection'}])
                        else:
                            # Slots are catalog positions, not durable identity.
                            # Install only after the runner's initial launch and
                            # resolve Notebook again after changing the catalog.
                            seed['slot']=channel.app_client.install(seed['package'],[public])['slot']
                            channel.installed_slot=next(entry['slot'] for entry in channel.app_client.catalog() if entry['id']=='notebook')
                            launch(seed['slot']);run(shortcut('view')+[{'program_exit':0},{'key':'home'}]);channel.wait_for_storage()
                        launch(channel.installed_slot)
                        wait_notebook(normal,records)
                        run([{'key':'ok'}]+tap(260,20)+[{'capture':'before-paste'}]+shortcut('menu')+[{'capture':'after-paste'}])
                        if mode in ('newline','oversized'):
                            with Image.open(folder/'before-paste.ppm') as before,Image.open(folder/'after-paste.ppm') as after:
                                assert before.crop((12,65,308,97)).tobytes()==after.crop((12,65,308,97)).tobytes(),'rejected paste changed selection/text'
                        run([{'key':'ok'}]);wait_notebook(normal,records)
                        run(tap(260,205));wait_notebook(normal,records)
                        if payload is None:
                            # Copy the edited expression back to the built-in
                            # calculator and evaluate it through normal input.
                            run(tap(60,80)+[{'key':'plus'},{'key':'two'}]+shortcut('view')+[{'key':'home'}])
                            # Calculation discards its selection on focus loss;
                            # select the existing five glyphs again to replace.
                            run(shortcut('left')*5+shortcut('menu')+[{'capture':'calculator-return'},{'key':'ok'}])
                            answer=channel.command('RESULT EXACT');assert answer=='TEXT 7',answer
                            records.append({'action':'calculator-result','status':'passed','value':'7'})
                        else:run([{'key':'home'}])
                        channel.wait_for_storage();files=FileClient(channel.app_client)
                        for path in ('notebook.txt','export.txt'):files.export_file('notebook',path,folder/path,replace=True)
                    finally:
                        write_json(folder/'steps.json',records)
                        normal.close()
                result=exercise(artifact,qemu,args.firmware,controls=controls)
                assert result['result']==1 and result['os_responsive'],result
                assert (folder/'notebook.txt').read_bytes()==b'LFNOTE3\nL\n0 0 07\n'+expected+b'\n',(mode,(folder/'notebook.txt').read_bytes())
                assert (folder/'export.txt').read_bytes().startswith(b'# Notebook DEG AUTO 7 / x=1\n'+expected+b' = ')
                cases.append({'name':mode,'profile':profile,'runtime':result,'steps':records,
                    'document_sha256':digest(folder/'notebook.txt'),'export_sha256':digest(folder/'export.txt')})
                print('PASS:',profile,mode,flush=True)
    frames=[]
    for path in (output/'debug').rglob('*.ppm'):
        other=output/'release'/path.relative_to(output/'debug')
        with Image.open(path) as a,Image.open(other) as b:
            assert a.size==b.size and a.tobytes()==b.tobytes(),f'debug/release mismatch: {path}'
            png=path.with_suffix('.png');a.save(png);frames.append(str(png.relative_to(output)))
    assert sdk_identity==identity(ROOT/'sdk'),'SDK changed during qualification'
    write_json(output/'report.json',{'schema':1,'status':'passed','sdk_sha256':sdk_identity,'cases':cases,
        'firmware_sha256':digest(args.firmware),'qemu_sha256':digest(qemu),'physical':'not_tested','matching_frames':frames})


if __name__=='__main__':main()
