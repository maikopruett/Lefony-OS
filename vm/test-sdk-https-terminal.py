#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Late HTTPS fragments through the real Gallery, paired USB and localhost TLS."""
import argparse
from contextlib import contextmanager,nullcontext
import hashlib
import importlib.util
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import time
from unittest.mock import patch
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from channel_device import Client as ChannelClient
from device import Client as DeviceClient
from cli import package
from files_device import FileClient
from https_bridge import Bridge,URL,CANCEL,DONE,ERROR
from https_worker import Policy
from preview import inspect_layout
from replay import Controls
from runner import exercise
from signing import sign,verify
from workspace import opened
import sdk_https_probe as fixture
spec=importlib.util.spec_from_file_location('gallery',ROOT/'vm/test-sdk-link-gallery.py')
gallery=importlib.util.module_from_spec(spec);spec.loader.exec_module(gallery)


class DelayedFragment:
    """Delay one host receive/ACK until its terminal is accepted by real USB.

    No frame is invented or changed. This deterministically schedules ordinary
    full-duplex transport latency at a boundary the app cannot observe atomically.
    """
    def __init__(self,client,kind,terminal,records):
        self.client=client;self.kind=kind;self.terminal=terminal;self.records=records
        self.held=self.released=self.drained=False
    def __getattr__(self,name):return getattr(self.client,name)
    def receive(self):
        message=self.client.receive()
        if message and message['kind']==self.kind and struct.unpack_from('<I',message['data'])[0]==1:
            if not self.held:
                self.held=True;self.records.append({'event':'fragment-held','kind':self.kind,'id':1})
            if not self.released:return None
            self.drained=True
        return message
    def acknowledge(self):
        self.client.acknowledge()
        if self.drained:self.records.append({'event':'fragment-acknowledged','kind':self.kind,'id':1});self.drained=False
    def send(self,kind,data):
        boundary=kind==self.terminal and not self.released
        if boundary and not self.held:return False
        sent=self.client.send(kind,data)
        if sent and boundary:
            self.released=True;self.records.append({'event':'terminal-enqueued','kind':kind,'id':struct.unpack_from('<I',data)[0]})
        return sent


@contextmanager
def existing_package(case):
    def inspect(client,content,keys):
        metadata,_=verify(content,keys);client.require_compatible(metadata)
        entries=[e for e in client.catalog() if e['id']==metadata['id']];assert len(entries)==1
        entry=entries[0];assert entry['version']==metadata['version'] and entry['bytes']==len(content)
        assert client.read_package(entry['slot'],entry['bytes'])==content
        case['bootstrap']={'action':'signed-public-readback','catalog':entry,'sha256':hashlib.sha256(content).hexdigest()}
        return entry
    with patch.object(DeviceClient,'install',inspect):yield


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--profiles',choices=('debug','release'),nargs='+',default=['debug','release'])
    parser.add_argument('--phases',choices=('policy','cancel','user-cancel','cold'),nargs='+',default=['policy','cancel','user-cancel','cold'])
    args=parser.parse_args();args.firmware=args.firmware.resolve();output=args.output.resolve();output.mkdir(parents=True)
    if not args.phases or args.phases[0]=='cold':parser.error('A connected phase must seed the workspace before cold inspection')
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm'
    report={'schema':1,'status':'running','sdk_sha256':identity(ROOT/'sdk'),'firmware_sha256':digest(args.firmware),
        'qemu_sha256':digest(qemu),'physical':'not_tested','cases':[]}
    write_json(output/'report.json',report)
    response={'status':200,'body':b''}
    try:
        with tempfile.TemporaryDirectory(prefix='gallery-terminal-') as temp,fixture.service(response=lambda _: (response['status'],response['body'])) as (origin,cert,requests):
            for profile in args.profiles:
                project=Path(temp)/profile;shutil.copytree(ROOT/'sdk/examples/link-gallery',project,
                    ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json','compile_commands.json'))
                config={'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.cpp'],'arguments':[origin+'/image']}
                write_json(project/'project.json',config);artifact=package(project,profile)
                retained=output/profile;retained.mkdir();write_json(retained/'project.json',config)
                signed=sign(artifact.read_bytes(),ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem')
                (retained/'installed.lfapp').write_bytes(signed)
                for name in ('app.elf','app-debug.elf','build.json',artifact.name):shutil.copyfile(project/'build'/name,retained/name)
                expected,expected_image=gallery.picture(1)
                for index,phase in enumerate(args.phases):
                    folder=retained/phase;folder.mkdir();records=[];progress=[];boundaries=[]
                    case={'profile':profile,'phase':phase,'status':'running','records':records,'progress':progress,'boundaries':boundaries}
                    report['cases'].append(case)
                    next_bytes,next_image=gallery.picture(index+2)
                    def prepare(client):
                        seed=folder/'seed.cache';seed.write_bytes(expected);FileClient(client).import_file('link-gallery','image.cache',seed)
                    def controls(channel):
                        normal=Controls(channel,folder);client=None;bridge=None;active=None;gate=None
                        def frame(name):
                            path=folder/(name+'.ppm');normal.execute('screendump',{'filename':str(path)})
                            with Image.open(path) as source:return source.convert('RGB')
                        def same(image):return frame('observed').crop((16,48,304,176)).tobytes()==image.tobytes()
                        def ready():return frame('ready').getpixel((60,202))==active
                        def wait(predicate,label,*,pump=False,timeout=45):
                            deadline=time.monotonic()+timeout
                            while not predicate():
                                if pump:bridge.step()
                                assert channel.command('APP DIAG 9')=='VALUE 0'
                                if time.monotonic()>=deadline:raise AssertionError((label,progress[-3:],boundaries,channel.command('STATE')))
                                time.sleep(.005)
                        def capture(name,*,message=None):
                            image=frame(name);image.save(folder/(name+'.png'))
                            if profile=='debug':
                                directory=folder/name;directory.mkdir();layout=inspect_layout(normal,retained/'app-debug.elf',directory)
                                if message is not None:assert next(n['name'] for n in layout['nodes'] if n['id']==15).startswith(message)
                            records.append({'action':'frame','name':name,'sha256':digest(folder/(name+'.png'))})
                            print('FRAME:',profile,phase,name,flush=True)
                        def tap(x,y):normal.run({'steps':[{'touch':[[1,x,y]]},{'touch':[]}]},records)
                        def pair(policy,kind=None,terminal=None):
                            nonlocal client,bridge,gate
                            client=ChannelClient(channel.app_client.transport,'link-gallery',signed[24:56],package_hash=signed[56:88])
                            wait(lambda:client.status()['state']==1,'channel open');code=client.attach('Terminal boundary test')
                            wait(lambda:sum(max(p)<100 for p in frame('pairing').crop((175,18,235,36)).get_flattened_data())>20,'pairing screen')
                            normal.key_edge('ok',True);time.sleep(.3);normal.key_edge('ok',False);time.sleep(.3)
                            wait(client.paired,'calculator consent');records.append({'action':'pairing','code':code})
                            gate=DelayedFragment(client,kind,terminal,boundaries) if kind is not None else None
                            bridge=Bridge(gate or client,policy,progress=progress.append)
                        try:
                            wait(lambda:same(expected_image),'cached image on start');active=frame('initial').getpixel((60,202));capture('initial')
                            count=len(requests)
                            if phase=='cold':
                                assert len(requests)==count;capture('cold-cache',message='Saved image available offline')
                            else:
                                response.update(status=404 if phase=='cancel' else 200,body=b'' if phase=='cancel' else next_bytes)
                                tap(80,210)
                                policy=Policy((origin,),response_limit=1 if phase=='policy' else len(next_bytes),ca_file=str(cert))
                                pair(policy,URL if phase=='policy' else CANCEL,ERROR if phase=='policy' else DONE)
                                if phase=='user-cancel':
                                    wait(lambda:bridge.downloaded>=4096,'response streaming before Back',pump=True)
                                    assert bridge.downloaded<len(next_bytes)
                                    case['downloaded_at_back']=bridge.downloaded
                                    normal.key('back');capture('user-cancelling')
                                wait(lambda:any(e['event']=='fragment-acknowledged' for e in boundaries),'late fragment drained',pump=True)
                                wait(ready,'controls after terminal',pump=True)
                                assert bridge.id is None and not bridge.closed and same(expected_image)
                                assert [b['event'] for b in boundaries]==['fragment-held','terminal-enqueued','fragment-acknowledged']
                                assert len(requests)==count+(phase!='policy')
                                capture('retained-after-terminal',message='Host did not grant' if phase=='policy' else
                                        'Cancelled; saved image kept' if phase=='user-cancel' else 'Server returned HTTP 404')
                                # An unchanged grant remains usable for another explicit refusal.
                                if phase=='policy':
                                    tap(80,210)
                                    wait(lambda:sum(e['phase']=='error' for e in progress)==2,'second explicit refusal',pump=True)
                                    wait(ready,'second refusal cleanup',pump=True)
                                    # Drain already queued metadata even after the app returns idle.
                                    until=time.monotonic()+.4
                                    while time.monotonic()<until:bridge.step();time.sleep(.005)
                                    assert len(requests)==count and not bridge.closed and same(expected_image)
                                    capture('second-refusal')
                                    tap(230,210);bridge.close();bridge=None
                                    response.update(status=200,body=next_bytes);tap(80,210)
                                    pair(Policy((origin,),ca_file=str(cert)))
                                elif phase=='cancel':
                                    # DONE already won the race. Refresh uses the same consent/session.
                                    session=client.binding['session'];response.update(status=200,body=next_bytes);tap(80,210)
                                    case['same_session_retry']=session
                                if phase!='user-cancel':
                                    target=sum(e['phase']=='complete' for e in progress)+1
                                    wait(lambda:sum(e['phase']=='complete' for e in progress)==target,'explicit corrected refresh',pump=True,timeout=150)
                                    wait(lambda:same(next_image) and ready(),'new cache saved',pump=True)
                                    if phase=='cancel':assert client.binding['session']==case['same_session_retry']
                                    assert len(requests)==count+1+(phase=='cancel')
                                    capture('refreshed',message='Saved for offline viewing')
                            if bridge is not None:bridge.close()
                            normal.key('home');channel.wait_for_storage()
                            files=FileClient(channel.app_client);files.export_file('link-gallery','image.cache',folder/'image.cache')
                            assert (folder/'image.cache').read_bytes()==(expected if phase in ('cold','user-cancel') else next_bytes)
                            case['cache_sha256']=digest(folder/'image.cache');case['requests']=requests[count:]
                            assert channel.command('PING')=='PONG'
                        except BaseException:
                            try:capture('failure')
                            except Exception:pass
                            raise
                        finally:
                            if bridge is not None:bridge.close()
                            write_json(folder/'records.json',records);write_json(folder/'progress.json',progress);write_json(folder/'boundaries.json',boundaries)
                            normal.close()
                    with opened(project,'gallery') as (workspace,_),existing_package(case) if index else nullcontext():
                        result=exercise(artifact,qemu,args.firmware,workspace=workspace,controls=controls,prepare_workspace=prepare if not index else None)
                    assert result['result']==1 and result['os_responsive'],result
                    case.update(status='passed',runtime=result);write_json(output/'report.json',report);print('PASS:',profile,phase,flush=True)
                    if phase not in ('cold','user-cancel'):expected,expected_image=next_bytes,next_image
        if set(args.profiles)=={'debug','release'}:
            matches=[]
            for p in (output/'debug').glob('*/*.png'):
                if p.stem not in ('initial','retained-after-terminal','second-refusal','refreshed','cold-cache'):continue
                other=output/'release'/p.relative_to(output/'debug')
                with Image.open(p) as a,Image.open(other) as b:
                    a,b=a.convert('RGB'),b.convert('RGB')
                    if p.parent.name=='user-cancel' and p.stem=='retained-after-terminal':
                        # Amount already received at Back depends on scheduling.
                        a.paste((0,0,0),(12,184,308,188));b.paste((0,0,0),(12,184,308,188))
                    assert a.tobytes()==b.tobytes(),str(p)
                matches.append(str(p.relative_to(output)))
            report['matching_frames']=matches
        assert identity(ROOT/'sdk')==report['sdk_sha256'],'SDK changed during qualification'
        report.update(status='passed',sources={str(p.relative_to(ROOT)):digest(p) for p in
            [Path(__file__),ROOT/'vm/sdk_https_probe.py',ROOT/'sdk/tools/https_bridge.py',ROOT/'sdk/examples/link-gallery/src/main.cpp']})
        write_json(output/'report.json',report)
    except BaseException as exc:
        report.update(status='failed',error=str(exc));write_json(output/'report.json',report);raise


if __name__=='__main__':main()
