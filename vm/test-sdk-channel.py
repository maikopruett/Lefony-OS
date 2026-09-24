#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ordinary signed C app, real USB packets and OS-owned KPP pairing consent."""
import argparse
import hashlib
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import time
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from channel_device import Client,ChannelError
from cli import package
from replay import Controls
from runner import exercise
from signing import sign


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--old-firmware',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--modes',nargs='+',default=['denied','unsupported','stream','userdeny','hostclose','lease','reset','home','fault','reopen','pair-timeout','pair-shift-home','pair-shift-apps'])
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    source_paths=['tests/native/sdk_channel.c','vm/test-sdk-channel.py','sdk/tools/channel_device.py',
        'sdk/include/lefony/channel.h','sdk/include/lefony/channel_wire.h',
        'ports/lefony-prime-g2/ion/src/prime_g2/app_channel.h','ports/lefony-prime-g2/ion/src/prime_g2/app_channel.cpp',
        'ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp','ports/lefony-prime-g2/ion/src/prime_g2/usb_diagnostics.cpp',
        'ports/lefony-prime-g2/apps/native_apps/app.cpp']
    report={'schema':1,'status':'running','firmware_sha256':digest(args.firmware),'old_firmware_sha256':digest(args.old_firmware),
            'sources':{p:digest(ROOT/p) for p in source_paths},'cases':[],'physical':'not_tested'}
    write_json(output/'report.json',report)
    with tempfile.TemporaryDirectory(prefix='sdk-channel-') as temp:
        for mode in args.modes:
            project=Path(temp)/mode;(project/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'tests/native/sdk_channel.c',project/'src/main.c')
            enabled=mode not in ('denied','unsupported')
            write_json(project/'app.json',{'abi':1,'id':'channel-lab','name':'Channel Lab','version':'1.0.0','license':'GPL-3.0-or-later',
                'schema':1,'minimum_api':11 if enabled else 4,'required_capabilities':4144 if enabled else 48,'optional_capabilities':0,'data_schema':0})
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c'],'arguments':[mode]})
            artifact=package(project);folder=output/mode;folder.mkdir(exist_ok=True)
            for name in ('app-debug.elf','build.json',artifact.name):shutil.copyfile(project/'build'/name,folder/name)
            signed=sign(artifact.read_bytes(),ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem')
            (folder/'installed.lfapp').write_bytes(signed)
            records=[]
            def controls(channel):
                normal=Controls(channel,folder);client=Client(channel.app_client.transport,'channel-lab',signed[24:56],package_hash=signed[56:88])
                def wait(predicate,description,timeout=20):
                    deadline=time.monotonic()+timeout
                    while True:
                        value=predicate()
                        if value:return value
                        if time.monotonic()>=deadline:
                            raise AssertionError((mode,description,channel.command('STATE'),channel.command('APP DIAG 9'),channel.command('APP DIAG 21'),client.status()))
                        time.sleep(.01)
                def os_key(name):
                    # Pairing consumes the key in Escher, so no app key counter
                    # change is expected. Injection still traverses normal KPP.
                    normal.key_edge(name,True);time.sleep(.3);normal.key_edge(name,False);time.sleep(.3)
                def capture(name):normal.run({'steps':[{'capture':name}]},records)
                def pairing_visible():
                    path=folder/'pairing-ready.ppm';normal.execute('screendump',{'filename':str(path)})
                    with Image.open(path) as frame:
                        # The app fixture has no pixels below its title. Require
                        # both the OS pairing code and consent footer to render.
                        pixels=frame.convert('RGB')
                        return all(sum(max(pixel)-min(pixel)<20 and max(pixel)<100
                            for pixel in pixels.crop(rect).getdata())>20
                            for rect in ((12,158,180,183),(12,208,305,225)))
                def receive():
                    def attempt():
                        client.keepalive();return client.receive()
                    return wait(attempt,'app message')
                def send(kind,data=b''):
                    wait(lambda:client.send(kind,data),'host queue')
                def exit_ok():normal.run({'steps':[{'program_exit':0}]},records)
                try:
                    if not enabled:exit_ok();return
                    wait(lambda:client.status()['state']==1,'app open')
                    code=client.attach('SDK channel validation');records.append({'action':'pairing-code','code':f'{code:06d}'})
                    wait(lambda:client.status()['state']==2,'OS consent')
                    wait(pairing_visible,'visible OS consent screen',8);capture('pairing')
                    # Neither a digit nor Goodix touch grants consent.
                    os_key('one');normal.run({'steps':[{'touch':[[1,120,210]]},{'touch':[]}]},records)
                    assert not client.paired()
                    if mode=='pair-timeout':
                        wait(lambda:client.status()['state']==4,'pairing timeout',35);exit_ok();capture('pairing-expired');return
                    if mode in ('pair-shift-home','pair-shift-apps'):
                        normal.key('shift');normal.key(mode.removeprefix('pair-shift-'))
                        assert client.status()['state'] in (0,4)
                        assert channel.command('STATE').split(' home_row=')[0]!=channel.native_state
                        assert channel.command('MOD STATE')=='VALUE 0'
                        capture('pairing-dismissed');return
                    os_key('back' if mode=='userdeny' else 'ok')
                    if mode=='userdeny':exit_ok();capture('denied');return
                    wait(client.paired,'approved');wait(lambda:client.status()['send_queued']==4,'copied app queue')
                    # Reads never consume. Host queue ACKs each owned message.
                    for i in range(4):
                        message=receive();assert message['kind']==1 and message['data']==bytes([i]),message
                        assert client.receive()==message;client.acknowledge()
                    capture('connected')
                    if mode=='home':
                        normal.key('home');assert client.status()['state'] in (0,4);return
                    if mode=='reset':
                        channel.app_client.transport.reset();exit_ok();return
                    if mode=='lease':
                        wait(lambda:client.status()['state']==4,'host lease',8);exit_ok();return
                    if mode=='hostclose':client.close();exit_ok();return
                    if mode=='fault':
                        send(4);wait(lambda:channel.command('APP DIAG 9')!='VALUE 0','expected app fault')
                        assert client.status()['state']==0;return
                    if mode=='reopen':
                        old=client.binding;send(5);wait(lambda:client.status()['state']==1,'fresh app session')
                        for operation in (client.keepalive,lambda:client.send(2,b'old')):
                            try:operation()
                            except ChannelError:pass
                            else:raise AssertionError('Stale host client accepted')
                        client=Client(channel.app_client.transport,'channel-lab',signed[24:56],package_hash=signed[56:88])
                        client.attach('SDK channel validation');wait(pairing_visible,'visible new consent screen',8)
                        os_key('ok');wait(client.paired,'new consent')
                        assert client.binding['session']>old['session'] and client.binding['nonce']!=old['nonce']
                        message=receive();assert message['kind']==5 and message['data']==b'fresh';client.acknowledge()
                        send(4);exit_ok();return
                    assert mode=='stream'
                    normal.key('one')
                    payload=bytes((i*37+11)&255 for i in range(70017));received=bytearray()
                    # Include zero-length and maximum-size public frames. Keep
                    # at most four in flight and ACK after application receipt.
                    sent=0;pending=[];start=time.monotonic()
                    send(2);pending.append(b'')
                    while sent<len(payload) or pending:
                        client.keepalive()
                        while sent<len(payload) and len(pending)<4:
                            block=payload[sent:sent+448]
                            if not client.send(2,block):break
                            sent+=len(block);pending.append(block)
                        message=client.receive()
                        if message:
                            assert pending and message['kind']==2
                            expected=bytes(b^0xa5 for b in pending.pop(0));assert message['data']==expected
                            received.extend(message['data']);client.acknowledge()
                        if time.monotonic()-start>300:raise AssertionError('Stream timed out')
                    assert bytes(received)==bytes(b^0xa5 for b in payload)
                    send(3);message=receive();assert message['kind']==3 and struct.unpack('<3I',message['data'])==(70017,sum(payload),1)
                    client.acknowledge();records.append({'action':'bidirectional-stream','bytes_each_direction':len(payload),
                        'host_sha256':hashlib.sha256(payload).hexdigest(),'app_sha256':hashlib.sha256(received).hexdigest(),'seconds':time.monotonic()-start})
                    send(4);exit_ok();assert client.status()['state']==4
                except Exception as exc:
                    records.append({'status':'failed','error':str(exc)})
                    try:capture('failure')
                    except Exception:pass
                    raise
                finally:
                    write_json(folder/'records.json',records);normal.close()
            result=exercise(artifact,ROOT/'build/qemu-prime-g2/qemu-system-arm',args.old_firmware if mode=='unsupported' else args.firmware,controls=controls)
            assert result['os_responsive'] and result['result']==(-14 if mode=='fault' else 1),result
            report['cases'].append({'mode':mode,'runtime':result,'records':records});write_json(output/'report.json',report)
            print('PASS:',mode,flush=True)
    assert report['sources']=={p:digest(ROOT/p) for p in source_paths},'Source changed during qualification'
    report['status']='passed';write_json(output/'report.json',report)


if __name__=='__main__':main()
