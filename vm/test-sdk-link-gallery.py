#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Gallery UI, streamed TLS image, reconnect/cancel and cold cache through public APIs."""
import argparse
import hashlib
from pathlib import Path
import shutil
import runpy
import struct
import subprocess
import sys
import tempfile
import time
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from channel_device import Client,ChannelError
from cli import package
from files_device import FileClient
from https_bridge import Bridge
from https_worker import Policy
from replay import Controls
from runner import exercise
from signing import sign
from workspace import opened
import sdk_https_probe as fixture


def picture(variant):
    payload=bytearray();rgb=bytearray()
    for y in range(128):
        for x in range(288):
            r=(x//10+variant*5)%32;g=(y//2+variant*11)%64;b=((x+y)//13+variant*7)%32
            if 25<y<103 and abs(x-144)<(y-15):r,g,b=(29,57,23) if variant%2 else (5,28,29)
            value=(r<<11)|(g<<5)|b;payload.extend(struct.pack('<H',value));rgb.extend(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)))
    checksum=2166136261
    for value in payload:checksum=((checksum^value)*16777619)&0xffffffff
    return b'LFGAL1\r\n'+struct.pack('<6I',288,128,len(payload),checksum,0,0)+payload,Image.frombytes('RGB',(288,128),bytes(rgb))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--profiles',nargs='+',default=['debug','release'])
    parser.add_argument('--full-quota',action='store_true',help='Also replace, reject and cancel cached images at the full 32 MiB app quota')
    parser.add_argument('--measure-resources',action='store_true')
    parser.add_argument('--profile-heap',action='store_true',help='Build the temporary project with newlib heap diagnostics; requires --measure-resources')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    if args.profile_heap and not args.measure_resources:parser.error('--profile-heap requires --measure-resources')
    report={'schema':1,'status':'running','firmware_sha256':digest(args.firmware),'sdk_sha256':identity(ROOT/'sdk'),'cases':[],'physical':'not_tested'}
    source_paths=['sdk/examples/link-gallery/src/main.cpp','sdk/examples/link-gallery/src/cache.h','sdk/include/lefony/https.h',
        'sdk/include/lefony/file_writer.h','sdk/tools/https_bridge.py','sdk/tools/https_worker.py','vm/test-sdk-link-gallery.py','vm/sdk_https_probe.py']
    report['sources']={name:digest(ROOT/name) for name in source_paths};write_json(output/'report.json',report)
    first,first_image=picture(1);second,second_image=picture(2);third,_=picture(3)
    with tempfile.TemporaryDirectory(prefix='sdk-gallery-') as temp,fixture.service() as (origin,cert,requests):
        if args.full_quota:
            helper=Path(temp)/'helper';helper.mkdir()
            storage_fixture=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](helper)
            filler=Path(temp)/'filler';filler.write_bytes(bytes(32*1024*1024-len(second)))
        for profile in args.profiles:
            project=Path(temp)/profile;shutil.copytree(ROOT/'sdk/examples/link-gallery',project,ignore=shutil.ignore_patterns('build','sdk.lock.json','compile_commands.json','.lefony'))
            config={'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.cpp'],'arguments':[origin+'/image']}
            if args.profile_heap:config['defines']={'LEFONY_PROFILE_HEAP':1}
            write_json(project/'project.json',config)
            artifact=package(project,profile);retained=output/profile;retained.mkdir(exist_ok=True)
            shutil.copyfile(project/'project.json',retained/'project.json')
            signed=sign(artifact.read_bytes(),ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem');(retained/'installed.lfapp').write_bytes(signed)
            for name in ('app-debug.elf','build.json'):shutil.copyfile(project/'build'/name,retained/name)
            with opened(project,'gallery') as (workspace,_):
                for phase in (('connected','cold','quota','quota-cold') if args.full_quota else ('connected','cold')):
                    cold=phase in ('cold','quota-cold');quota=phase.startswith('quota')
                    expected,expected_image=(first,first_image) if quota else (second,second_image)
                    if phase=='quota':
                        subprocess.run([storage_fixture,'put-file',workspace/'nand.overlay','link-gallery','filler',filler],
                            check=True,stdout=subprocess.DEVNULL,timeout=90)
                    folder=retained/phase;folder.mkdir(exist_ok=True);records=[];progress=[]
                    def controls(channel):
                        normal=Controls(channel,folder);client=None;bridge=None;active_fill=None
                        def wait(predicate,label,timeout=30):
                            deadline=time.monotonic()+timeout
                            while not predicate():
                                if time.monotonic()>=deadline:raise AssertionError((profile,label,channel.command('STATE'),channel.command('APP DIAG 9'),channel.command('APP DIAG 21')))
                                time.sleep(.01)
                        def frame(name):
                            path=folder/(name+'.ppm');normal.execute('screendump',{'filename':str(path)})
                            with Image.open(path) as image:return image.convert('RGB')
                        def same(name,image):return frame(name).crop((16,48,304,176)).tobytes()==image.tobytes()
                        def capture(name):normal.run({'steps':[{'capture':name}]},records)
                        def ready():return frame('ui-ready').getpixel((60,202))==active_fill
                        def download():
                            if bridge is not None and not bridge.closed:pump(ready,'download control enabled')
                            else:wait(ready,'download control enabled')
                            normal.run({'steps':[{'touch':[[7,80,210]]},{'touch':[]}]},records)
                        def pair():
                            nonlocal client,bridge
                            client=Client(channel.app_client.transport,'link-gallery',signed[24:56],package_hash=signed[56:88])
                            wait(lambda:client.status()['state']==1,'app connection open');code=client.attach('Gallery validation')
                            def pairing_visible():
                                pixels=frame('pairing');return sum(max(p)<100 for p in pixels.crop((175,18,235,36)).get_flattened_data())>20
                            wait(pairing_visible,'OS pairing screen');records.append({'action':'pairing','code':f'{code:06d}'})
                            normal.key_edge('ok',True);time.sleep(.3);normal.key_edge('ok',False);time.sleep(.3);wait(client.paired,'consent')
                            bridge=Bridge(client,Policy((origin,),ca_file=str(cert)),progress=progress.append)
                        def pump(predicate,label,timeout=150):
                            deadline=time.monotonic()+timeout
                            while not predicate():
                                bridge.step()
                                assert channel.command('APP DIAG 9')=='VALUE 0',(profile,'fault',channel.command('APP DIAG 10'))
                                if time.monotonic()>=deadline:raise AssertionError((profile,label,progress[-4:],channel.command('APP DIAG 21')))
                                time.sleep(.001)
                        try:
                            wait(lambda:channel.command('APP DIAG 13')!='VALUE 0','app ready')
                            if cold:
                                count=len(requests);wait(lambda:same('cold-ready',expected_image),'saved image on cold start');capture('cold-cache')
                                assert len(requests)==count and channel.command('APP DIAG 15')=='VALUE 0'
                            elif quota:
                                wait(lambda:same('quota-ready',second_image),'existing image at full quota')
                                active_fill=frame('quota-start').getpixel((60,202));capture('quota-start')
                                fixture.BODY=first;download();pair()
                                pump(lambda:len([p for p in progress if p['phase']=='complete'])==1,'full-quota download')
                                pump(lambda:same('quota-replacement-ready',first_image),'full-quota replacement saved');capture('quota-replaced')
                                malformed=bytearray(third);malformed[-1]^=1;fixture.BODY=bytes(malformed);download()
                                pump(lambda:len([p for p in progress if p['phase']=='complete'])==2,'full-quota invalid content')
                                pump(ready,'invalid replacement discarded');assert same('quota-invalid-ready',first_image);capture('quota-invalid')
                                fixture.BODY=third;download();pump(lambda:bridge.downloaded>4096,'full-quota cancel begins')
                                normal.key('back');pump(lambda:bridge.id is None,'full-quota cancel completes');pump(ready,'full-quota cancel cleanup')
                                assert same('quota-cancelled-ready',first_image);capture('quota-cancelled')
                            else:
                                fixture.BODY=first;capture('empty');active_fill=frame('empty').getpixel((60,202));download();pair()
                                pump(lambda:len([p for p in progress if p['phase']=='complete'])==1,'first download')
                                pump(lambda:same('first-ready',first_image),'first image saved');capture('first-saved')
                                # USB reset during the next response cannot replace
                                # the previous image or automatically resend HTTP.
                                fixture.BODY=second;download();pump(lambda:bridge.downloaded>4096,'second stream begins')
                                capture('downloading');before=len(requests);channel.app_client.transport.reset()
                                try:bridge.step()
                                except ChannelError:pass
                                else:raise AssertionError('Bridge did not notice reset')
                                bridge.close();time.sleep(.5);assert len(requests)==before
                                wait(lambda:same('disconnected-ready',first_image),'image retained after disconnect');capture('disconnected')
                                download();pair();pump(lambda:len([p for p in progress if p['phase']=='complete'])==2,'explicit reconnect download')
                                pump(lambda:same('second-ready',second_image),'replacement saved');capture('reconnected')
                                fixture.BODY=third;download();pump(lambda:bridge.downloaded>4096,'cancel stream begins')
                                normal.key('back');pump(lambda:bridge.id is None,'cancel completes');pump(ready,'cancel cleanup completes')
                                assert same('cancelled-ready',second_image);capture('cancelled')
                                # Correct length and magic, but failed content checksum.
                                malformed=bytearray(third);malformed[-1]^=1;fixture.BODY=bytes(malformed)
                                count=len([p for p in progress if p['phase']=='complete']);download()
                                pump(lambda:len([p for p in progress if p['phase']=='complete'])==count+1,'malformed image transfer')
                                pump(lambda:bridge.id is None,'malformed image terminal');pump(ready,'malformed image rejected')
                                assert same('invalid-ready',second_image);capture('invalid-image')
                            if bridge is not None:bridge.close()
                            normal.key('home');channel.wait_for_storage(timeout=20)
                            files=FileClient(channel.app_client);files.export_file('link-gallery','image.cache',folder/'image.cache')
                            assert (folder/'image.cache').read_bytes()==expected
                            assert all(e['path']!='download.part' for e in files.list('link-gallery')['entries'])
                            records.append({'action':'verified-cache','bytes':len(expected),'sha256':digest(folder/'image.cache')})
                            if quota:
                                info=files.info('link-gallery');assert info['quota_committed_bytes']==info['quota_bytes']==32*1024*1024
                                records.append({'action':'verified-full-quota','info':info})
                        except Exception:
                            try:capture('failure')
                            except Exception:pass
                            raise
                        finally:
                            if bridge is not None:bridge.close()
                            write_json(folder/'records.json',records);write_json(folder/'progress.json',progress);normal.close()
                    result=exercise(artifact,ROOT/'build/qemu-prime-g2/qemu-system-arm',args.firmware,controls=controls,workspace=workspace,measure_resources=args.measure_resources)
                    assert result['result']==1 and result['os_responsive'],result
                    if args.profile_heap:assert result['resources']['heap']['status'] in ('observed','not_observed'),result
                    report['cases'].append({'profile':profile,'cold':cold,'phase':phase,'runtime':result,'records':records,'progress':progress})
                    write_json(output/'report.json',report);print('PASS:',profile,phase,flush=True)
    assert report['sources']=={name:digest(ROOT/name) for name in source_paths},'Source changed during qualification'
    assert report['sdk_sha256']==identity(ROOT/'sdk'),'SDK changed during qualification'
    if set(args.profiles)=={'debug','release'}:
        frames=[('connected',('empty','first-saved','downloading','disconnected','reconnected','cancelled','invalid-image')),('cold',('cold-cache',))]
        if args.full_quota:frames.extend([('quota',('quota-start','quota-replaced','quota-invalid','quota-cancelled')),('quota-cold',('cold-cache',))])
        for phase,names in frames:
            for name in names:
                with Image.open(output/'debug'/phase/(name+'.ppm')) as left,Image.open(output/'release'/phase/(name+'.ppm')) as right:
                    # Progress during transfer is timing-dependent; image/control
                    # comparisons omit only the 4-pixel progress bar in that frame.
                    a,b=left.convert('RGB'),right.convert('RGB')
                    if name=='downloading':a.paste((0,0,0),(12,184,308,188));b.paste((0,0,0),(12,184,308,188))
                    assert a.tobytes()==b.tobytes(),(phase,name)
        report['matching_frames']=sum(len(names) for _,names in frames)
    report['status']='passed';write_json(output/'report.json',report)


if __name__=='__main__':main()
