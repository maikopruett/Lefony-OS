#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed C app to real USB channel to local TLS, with durable cache checks."""
import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import time
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from channel_device import Client,ChannelError
from cli import package
from files_device import FileClient
from https_bridge import Bridge
from https_worker import Policy
from replay import Controls
from runner import exercise
from signing import sign
from sdk_https_probe import BODY,service


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--modes',nargs='+',default=['get','chunked','post','chunked-post','policy','tls','timeout','cancel','truncated','disconnect'])
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    source_paths=['tests/native/sdk_https.c','vm/test-sdk-https.py','vm/sdk_https_probe.py','sdk/tools/https_worker.py',
                  'sdk/tools/https_bridge.py','sdk/tools/channel_device.py','sdk/include/lefony/https.h']
    report={'schema':1,'status':'running','firmware_sha256':digest(args.firmware),'sources':{p:digest(ROOT/p) for p in source_paths},'cases':[],'physical':'not_tested'}
    write_json(output/'report.json',report)
    with tempfile.TemporaryDirectory(prefix='sdk-https-') as temp,service() as (origin,cert,requests):
        for mode in args.modes:
            project=Path(temp)/mode;(project/'src').mkdir(parents=True);shutil.copyfile(ROOT/'tests/native/sdk_https.c',project/'src/main.c')
            url='https://not-granted.invalid/private' if mode=='policy' else origin+('/slow' if mode in ('timeout','disconnect') else '/truncated' if mode=='truncated' else '/chunked' if mode=='chunked' else '/echo' if mode in ('post','chunked-post') else '/data')
            write_json(project/'app.json',{'abi':1,'id':'https-lab','name':'HTTPS Lab','version':'1.0.0','license':'GPL-3.0-or-later',
                'schema':1,'minimum_api':11,'required_capabilities':4184,'optional_capabilities':0,'data_schema':0})
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c'],'arguments':[url,mode]})
            artifact=package(project);folder=output/mode;folder.mkdir(exist_ok=True)
            signed=sign(artifact.read_bytes(),ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem');(folder/'installed.lfapp').write_bytes(signed)
            for name in ('app-debug.elf','build.json'):shutil.copyfile(project/'build'/name,folder/name)
            original=b'previous verified offline cache';seed=folder/'previous.bin';seed.write_bytes(original)
            records=[];progress=[];request_start=len(requests)
            def prepare(client):FileClient(client).import_file('https-lab','cache.bin',seed)
            def controls(channel):
                normal=Controls(channel,folder);client=Client(channel.app_client.transport,'https-lab',signed[24:56],package_hash=signed[56:88]);bridge=None
                def wait(predicate,description,timeout=20):
                    deadline=time.monotonic()+timeout
                    while not predicate():
                        if time.monotonic()>=deadline:raise AssertionError((mode,description,channel.command('APP DIAG 21')))
                        time.sleep(.01)
                def visible():
                    path=folder/'pairing.ppm';normal.execute('screendump',{'filename':str(path)})
                    with Image.open(path) as frame:
                        pixels=frame.convert('RGB');return sum(max(p)<100 for p in pixels.crop((12,208,305,225)).get_flattened_data())>20
                try:
                    wait(lambda:client.status()['state']==1,'app open');code=client.attach('HTTPS validation');wait(visible,'visible OS pairing')
                    records.append({'action':'pairing','code':f'{code:06d}','frame_sha256':digest(folder/'pairing.ppm')})
                    normal.key_edge('ok',True);time.sleep(.3);normal.key_edge('ok',False);time.sleep(.3)
                    wait(client.paired,'consent')
                    bridge=Bridge(client,Policy((origin,),methods=('GET','POST'),ca_file=None if mode=='tls' else str(cert)),progress=progress.append)
                    start=time.monotonic();disconnected=False
                    while channel.command('APP DIAG 15')=='VALUE 0':
                        if mode=='disconnect' and bridge.exchange is not None and bridge.exchange.started and not disconnected:
                            bridge.close();client.close();disconnected=True
                        if not disconnected:
                            # The app exits only after receiving the terminal
                            # frame; avoid another USB operation after its exit.
                            state=client.status()['state']
                            if state==3:
                                try:bridge.step()
                                except ChannelError:
                                    wait(lambda:channel.command('APP DIAG 15')!='VALUE 0','app exit after channel close');break
                            elif state in (0,4):wait(lambda:channel.command('APP DIAG 15')!='VALUE 0','app exit');break
                        assert time.monotonic()-start<180,(mode,'exchange timeout',progress[-3:])
                        time.sleep(.001)
                    normal.run({'steps':[{'program_exit':0}]},records)
                    if bridge is not None:bridge.close()
                    normal.key('home');channel.wait_for_storage(timeout=20)
                    files=FileClient(channel.app_client);files.export_file('https-lab','cache.bin',folder/'cache.bin')
                    expected=BODY[:70017] if mode in ('post','chunked-post') else BODY if mode in ('get','chunked') else original
                    assert (folder/'cache.bin').read_bytes()==expected,(mode,'cache changed or truncated')
                    entries=files.list('https-lab')['entries'];assert all(e['path']!='download.part' for e in entries),entries
                    records.append({'action':'verified-cache','bytes':len(expected),'sha256':digest(folder/'cache.bin'),'seconds':time.monotonic()-start})
                finally:
                    if bridge is not None:bridge.close()
                    write_json(folder/'records.json',records);write_json(folder/'progress.json',progress);normal.close()
            result=exercise(artifact,ROOT/'build/qemu-prime-g2/qemu-system-arm',args.firmware,controls=controls,prepare_workspace=prepare)
            assert result['os_responsive'] and result['result']==1,result
            observed=requests[request_start:]
            if mode in ('policy','tls'):assert not observed,observed
            elif mode in ('post','chunked-post'):
                assert observed==[{'method':'POST','path':'/echo','bytes':70017,'sha256':hashlib.sha256(BODY[:70017]).hexdigest()}],observed
            report['cases'].append({'mode':mode,'runtime':result,'records':records,'progress':progress,'requests':observed})
            write_json(output/'report.json',report);print('PASS:',mode,flush=True)
    assert report['sources']=={p:digest(ROOT/p) for p in source_paths},'Source changed during qualification'
    report['status']='passed';write_json(output/'report.json',report)


if __name__=='__main__':main()
