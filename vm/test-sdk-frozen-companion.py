#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Frozen companion on real ARM/model USB, including streamed data and failures.

The harness controls synthetic emulator storage/input and a local TLS fixture.
The relocated SDK builds every guest package and runs its actual companion CLI
and spawned HTTPS worker with Homebrew/checkout access denied. No physical USB.
"""
import argparse
from contextlib import ExitStack,contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import runpy
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from files_device import FileClient
from channel_device import decode_info
from replay import Controls
from runner import exercise
from signing import sign
from sdk_https_probe import BODY,service
from sdk_frozen_access import command_prefix,interpreted_qemu,linux_processes
from workspace import opened


@contextmanager
def failure_report(report, output):
    try:
        yield
    except BaseException as error:
        report.update(status='failed',error=str(error))
        write_json(output/'report.json',report)
        raise


def descendants(pid):
    pairs=list(linux_processes().items()) if platform.system()=='Linux' else [tuple(map(int,line.split())) for line in subprocess.check_output(
        ['/bin/ps','-axo','pid=,ppid='],text=True).splitlines()]
    found={pid}
    while True:
        updated=found|{child for child,parent in pairs if parent in found}
        if updated==found:return found-{pid}
        found=updated


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--access-launcher',type=Path,help='Linux-native vm/linux-sdk-access.c executable')
    parser.add_argument('--interpreter',type=Path,help='Explicit recursive host interpreter, when required')
    parser.add_argument('--bundle-in-place',action='store_true',help='Use an already relocated bundle without copying; verify it again afterward')
    parser.add_argument('--trace-usb',action='store_true',help='Observe unchanged USB packets and retain request boundaries for diagnosis')
    parser.add_argument('--modes',nargs='+',choices=['get','chunked','post','chunked-post','policy','tls','timeout','cancel','truncated','disconnect','terminal'],
                        default=['get','chunked','post','chunked-post','policy','tls','timeout','cancel','truncated','disconnect','terminal'])
    args=parser.parse_args();bundle=args.bundle.resolve();output=args.output.resolve()
    assert platform.system() in ('Darwin','Linux'),'Unsupported frozen qualification host'
    output.mkdir(parents=True,exist_ok=False)
    for line in (bundle/'SHA256SUMS').read_text().splitlines():
        expected,name=line.split('  ',1);assert digest(bundle/name)==expected,name
    sdk_identity=identity(bundle/'_internal/sdk')
    assert identity(ROOT/'sdk')==sdk_identity,'Harness and frozen SDK sources must match'
    sources=['vm/test-sdk-frozen-companion.py','vm/sdk_frozen_access.py','vm/linux-sdk-access.c','vm/sdk_https_probe.py','tests/native/sdk_https.c','tests/native/sdk_https_terminal.c',
             'sdk/tools/runner.py','sdk/tools/companion.py','sdk/tools/emulator_usb.py']
    if args.trace_usb:sources.append('vm/test-sdk-frozen-storage.py')
    source_hashes={name:digest(ROOT/name) for name in sources}
    report={'schema':1,'status':'running','sdk_identity':sdk_identity,
            'candidate':json.loads((bundle/'candidate.json').read_text()),
            'bundle_checksums_sha256':digest(bundle/'SHA256SUMS'),'sources':source_hashes,
            'homebrew_and_checkout_access':'denied for frozen package/companion commands',
            'usb':'QEMU model via narrow explicit emulator adapter','physical':'not_tested','cases':[]}
    write_json(output/'report.json',report)
    env={key:value for key,value in os.environ.items() if key not in ('PYTHONPATH','PYTHONHOME')}
    env['PATH']='/usr/bin:/bin:/usr/sbin:/sbin'
    with failure_report(report,output),tempfile.TemporaryDirectory(prefix='lf-companion-',dir='/tmp') as temp,service() as (origin,cert,requests):
        temp=Path(temp);relocated=bundle if args.bundle_in_place else temp/'SDK companion é'
        if not args.bundle_in_place:shutil.copytree(bundle,relocated,symlinks=True)
        prefix,access=command_prefix(ROOT,relocated,temp,launcher=args.access_launcher,interpreter=args.interpreter)
        report['access']=access
        if args.access_launcher:report['access_launcher_sha256']=digest(args.access_launcher)
        if args.interpreter:report['interpreter_sha256']=digest(args.interpreter)
        report['bundle_in_place']=args.bundle_in_place;write_json(output/'report.json',report)
        program=relocated/'lefony-sdk';qemu=relocated/'_internal/runtime/qemu-system-arm';firmware=relocated/'_internal/runtime/firmware.elf'
        report['qemu_execution']={'target_sha256':digest(qemu),
                                 'interpreter_sha256':digest(args.interpreter) if args.interpreter else None}
        for mode in args.modes:
            folder=output/mode;folder.mkdir();project=temp/('App '+mode);(project/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'tests/native'/('sdk_https_terminal.c' if mode=='terminal' else 'sdk_https.c'),project/'src/main.c')
            url='https://not-granted.invalid/private' if mode=='policy' else origin+(
                '/slow' if mode in ('timeout','disconnect') else '/truncated' if mode=='truncated'
                else '/chunked' if mode=='chunked' else '/echo' if mode in ('post','chunked-post') else '/data')
            write_json(project/'app.json',{'abi':1,'id':'https-lab','name':'HTTPS Lab','version':'1.0.0','license':'GPL-3.0-or-later',
                'schema':1,'minimum_api':11,'required_capabilities':4184,'optional_capabilities':0,'data_schema':0})
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c'],'arguments':[url,mode]})
            with (folder/'package.log').open('w') as log:
                subprocess.run([*prefix,str(program),'--project',str(project),'package'],
                               cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
            artifact=project/'build/https-lab-1.0.0.lfapp'
            signed=sign(artifact.read_bytes(),ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem')
            (folder/'installed.lfapp').write_bytes(signed)
            for name in ('app-debug.elf','build.json'):shutil.copyfile(project/'build'/name,folder/name)
            original=b'previous verified offline cache';seed=folder/'previous.bin';seed.write_bytes(original)
            request_start=len(requests);records=[];lines=[];progress=[];observed_children=set()
            def prepare(client):FileClient(client).import_file('https-lab','cache.bin',seed)
            def controls(channel):
                normal=Controls(channel,folder);observer=None
                try:
                    with channel.usb_host.lend_connection() as socket,ExitStack() as observed:
                        if args.trace_usb:
                            relay=runpy.run_path(str(ROOT/'vm/test-sdk-frozen-storage.py'))['ObservedUSB']
                            observer=observed.enter_context(relay(socket,temp/(mode+'-usb')))
                            socket=observer.path
                        command=[*prefix,str(program),'companion',
                            '--emulator-usb',str(socket),'--app-id','https-lab','--signer',signed[24:56].hex(),
                            '--package-hash',signed[56:88].hex(),'--allow-origin',origin,'--method','GET','--method','POST',
                            '--label','Frozen SDK companion']
                        if mode!='tls':command+=['--ca-file',str(cert)]
                        with (folder/'companion.stderr').open('w') as errors:
                            process=subprocess.Popen(command,cwd=temp,env=env,stdout=subprocess.PIPE,stderr=errors,
                                                     text=True,start_new_session=True)
                            messages=queue.Queue()
                            def collect():
                                for line in process.stdout:messages.put(line.rstrip('\n'))
                            reader=threading.Thread(target=collect,daemon=True);reader.start()
                            started=time.monotonic();approved=False;interrupted=False;cancel_at=None;observed_request_count=-1
                            try:
                                while process.poll() is None or not messages.empty():
                                    assert time.monotonic()-started<180,(mode,'frozen companion deadline',lines[-5:])
                                    try:line=messages.get(timeout=.02)
                                    except queue.Empty:line=None
                                    if line is not None:
                                        lines.append(line)
                                        if line.startswith('Compare code '):
                                            assert not approved;deadline=time.monotonic()+10
                                            while True:
                                                path=folder/'pairing.ppm';normal.execute('screendump',{'filename':str(path)})
                                                with Image.open(path) as frame:
                                                    if sum(max(p)<100 for p in frame.convert('RGB').crop((12,208,305,225)).get_flattened_data())>20:break
                                                assert time.monotonic()<deadline;time.sleep(.02)
                                            normal.key_edge('ok',True);time.sleep(.3);normal.key_edge('ok',False);time.sleep(.3)
                                            approved=True;records.append({'action':'normal-pairing-consent','frame_sha256':digest(path)})
                                        elif line.startswith('{'):progress.append(json.loads(line))
                                    if ((len(requests)>request_start or any(p['phase']=='connecting' for p in progress))
                                            and (not observed_children or len(requests)>observed_request_count)):
                                        observed_children.update(descendants(process.pid))
                                        observed_request_count=len(requests)
                                    if mode=='disconnect' and len(requests)>request_start and not interrupted:
                                        assert observed_children,'No frozen network worker observed'
                                        cancel_at=time.monotonic();process.send_signal(signal.SIGINT);interrupted=True
                                process.wait(timeout=5);reader.join(2)
                                if process.returncode:
                                    # Collect independent guest state before cleanup, without
                                    # retrying or replacing any failed companion operation.
                                    diagnostics={}
                                    for index in (9,10,15,21):
                                        try:diagnostics[str(index)]=channel.command('APP DIAG '+str(index))
                                        except (RuntimeError,OSError) as error:diagnostics[str(index)]=str(error)
                                    write_json(folder/'failure-guest.json',diagnostics)
                                    normal.execute('screendump',{'filename':str(folder/'failure.ppm')})
                                assert not reader.is_alive() and approved and process.returncode==0,(mode,process.returncode,lines[-5:])
                                if mode=='disconnect':assert interrupted and time.monotonic()-cancel_at<5
                                if observed_children:
                                    deadline=time.monotonic()+3
                                    while True:
                                        alive=(set(linux_processes()) if platform.system()=='Linux' else set(map(int,subprocess.check_output(['/bin/ps','-axo','pid='],text=True).split())))&observed_children
                                        if not alive:break
                                        assert time.monotonic()<deadline,('Frozen worker survived companion exit',alive)
                                        time.sleep(.02)
                                records.append({'action':'companion-exit','code':process.returncode,
                                                'seconds':round(time.monotonic()-started,3),'observed_children_stopped':len(observed_children)})
                            finally:
                                if process.poll() is None:
                                    process.send_signal(signal.SIGINT)
                                    try:process.wait(timeout=5)
                                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                                reader.join(2);process.stdout.close()
                    if mode=='disconnect':
                        state=decode_info(channel.app_client.transport.read(0x78,length=320))
                        records.append({'action':'channel-after-host-interrupt','state':state['state'],'error':state['error']})
                    normal.run({'steps':[{'program_exit':0}]},records)
                    normal.key('home');channel.wait_for_storage(timeout=20)
                    files=FileClient(channel.app_client);files.export_file('https-lab','cache.bin',folder/'cache.bin')
                    expected=BODY[:70017] if mode in ('post','chunked-post') else BODY if mode in ('get','chunked','terminal') else original
                    assert (folder/'cache.bin').read_bytes()==expected,(mode,'cache changed or truncated')
                    entries=files.list('https-lab')['entries'];assert all(e['path']!='download.part' for e in entries),entries
                    records.append({'action':'verified-cache','bytes':len(expected),'sha256':digest(folder/'cache.bin')})
                finally:
                    if observer is not None:
                        write_json(folder/'usb-observer.json',{'requests':observer.requests,'errors':observer.errors})
                    normal.close();write_json(folder/'records.json',records);write_json(folder/'progress.json',progress)
                    (folder/'companion.stdout').write_text('\n'.join(lines)+'\n')
            with opened(project,'companion') as (media,_):
                try:
                    with interpreted_qemu(qemu,args.interpreter):
                        runtime=exercise(artifact,qemu,firmware,workspace=media,controls=controls,
                                         prepare_workspace=prepare,diagnostics_dir=folder/'emulator')
                finally:
                    # exercise has stopped QEMU before this copy, including on failure.
                    shutil.copyfile(media/'nand.overlay',folder/'nand.overlay')
            assert runtime['os_responsive'] and runtime['result']==1,runtime
            observed=requests[request_start:]
            if mode in ('policy','tls'):assert not observed,observed
            elif mode=='terminal':
                assert observed==[{'method':'GET','path':'/data'}]*2,observed
                assert [(p['id'],p.get('code')) for p in progress if p['phase']=='error']==[(1,'policy')],progress
                assert [p['id'] for p in progress if p['phase']=='complete']==[2,3],progress
                assert sum(r['action']=='normal-pairing-consent' for r in records)==1,records
            elif mode in ('post','chunked-post'):
                assert observed==[{'method':'POST','path':'/echo','bytes':70017,'sha256':hashlib.sha256(BODY[:70017]).hexdigest()}],observed
            errors={'policy':'policy','tls':'tls','timeout':'timeout','cancel':'cancelled','truncated':'protocol'}
            if mode in errors:assert any(p.get('code')==errors[mode] for p in progress),progress
            report['cases'].append({'mode':mode,'runtime':runtime,'records':records,'progress':progress,'requests':observed})
            write_json(output/'report.json',report);print('PASS: frozen companion '+mode,flush=True)
        assert source_hashes=={name:digest(ROOT/name) for name in sources}
        assert sdk_identity==identity(ROOT/'sdk')
        for line in (bundle/'SHA256SUMS').read_text().splitlines():
            expected,name=line.split('  ',1);assert digest(bundle/name)==expected,name
        report['status']='passed';write_json(output/'report.json',report)


if __name__=='__main__':main()
