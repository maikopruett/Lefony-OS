#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Production companion command engine on emulator USB, with normal consent."""
import argparse
from pathlib import Path
import shutil
import sys
import tempfile
import time
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from cli import package
from companion import run,ChannelUSB
from files_device import FileClient
from replay import Controls
from runner import exercise
from signing import sign
from sdk_https_probe import service,BODY


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--qemu',type=Path,default=ROOT/'build/qemu-prime-g2/qemu-system-arm')
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    sources=['sdk/tools/companion.py','sdk/tools/channel_device.py','sdk/tools/emulator_usb.py','sdk/tools/https_bridge.py','sdk/tools/https_worker.py','sdk/tools/tls_context.py','sdk/tools/usb_files.py','sdk/tools/cli.py',
             'vm/test-sdk-companion.py','vm/sdk_https_probe.py','tests/native/sdk_https.c']
    hashes={name:digest(ROOT/name) for name in sources}
    with tempfile.TemporaryDirectory(prefix='sdk-companion-') as temp,service() as (origin,cert,requests):
        project=Path(temp);(project/'src').mkdir();shutil.copyfile(ROOT/'tests/native/sdk_https.c',project/'src/main.c')
        write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c'],'arguments':[origin+'/data','get']})
        write_json(project/'app.json',{'abi':1,'id':'https-lab','name':'HTTPS Lab','version':'1.0.0','license':'GPL-3.0-or-later',
            'schema':1,'minimum_api':11,'required_capabilities':4184,'optional_capabilities':0,'data_schema':0})
        artifact=package(project);signed=sign(artifact.read_bytes(),ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem')
        (output/'installed.lfapp').write_bytes(signed)
        for name in ('app-debug.elf','build.json'):shutil.copyfile(project/'build'/name,output/name)
        log=[];commands=set()
        def controls(channel):
            normal=Controls(channel,output)
            class Transport:
                def __enter__(self):return self
                def __exit__(self,*unused):pass
                def read(self,request,**kwargs):
                    assert request in ChannelUSB.READ_REQUESTS;commands.add(('read',request));return channel.app_client.transport.read(request,**kwargs)
                def write(self,request,**kwargs):
                    assert request in ChannelUSB.WRITE_REQUESTS;commands.add(('write',request));return channel.app_client.transport.write(request,**kwargs)
            def emit(text):
                log.append(text)
                if text.startswith('Compare code '):
                    deadline=time.monotonic()+10
                    while True:
                        path=output/'pairing.ppm';normal.execute('screendump',{'filename':str(path)})
                        with Image.open(path) as frame:
                            if sum(max(p)<100 for p in frame.convert('RGB').crop((12,208,305,225)).get_flattened_data())>20:break
                        assert time.monotonic()<deadline;time.sleep(.02)
                    normal.key_edge('ok',True);time.sleep(.3);normal.key_edge('ok',False);time.sleep(.3)
            options=argparse.Namespace(app_id='https-lab',signer=signed[24:56].hex(),package_hash=signed[56:88].hex(),
                allow_origin=[origin],method=['GET'],upload_limit=8*1024*1024,response_limit=8*1024*1024,
                timeout_ms=120000,ca_file=cert,label='Production companion')
            deadline=time.monotonic()+180
            def stopped():
                if time.monotonic()>=deadline:raise TimeoutError('Companion did not observe normal app-channel closure')
                return False
            try:
                code=run(options,transport_factory=Transport,emit=emit,stopped=stopped)
                assert 'The app connection ended. Open a new session to reconnect.' in log,log
                assert code==0;normal.run({'steps':[{'program_exit':0}]},[])
                normal.key('home');channel.wait_for_storage(timeout=20)
                FileClient(channel.app_client).export_file('https-lab','cache.bin',output/'cache.bin')
                assert (output/'cache.bin').read_bytes()==BODY
            finally:normal.close();write_json(output/'command-output.json',log)
        result=exercise(artifact,args.qemu,args.firmware,controls=controls)
        assert result['os_responsive'] and result['result']==1 and requests==[{'method':'GET','path':'/data'}]
        assert hashes=={name:digest(ROOT/name) for name in sources}
        write_json(output/'report.json',{'schema':1,'status':'passed','runtime':result,'sources':hashes,'output':log,'requests':requests,
                   'usb_requests':[{'direction':d,'request':r} for d,r in sorted(commands)],'cache_sha256':digest(output/'cache.bin'),
                   'qemu_sha256':digest(args.qemu),'firmware_sha256':digest(args.firmware),'normal_peer_close':True,'physical':'not_tested'})
    print('PASS: production companion command engine, exact grant/consent, real USB/TLS and cached response')


if __name__=='__main__':main()
