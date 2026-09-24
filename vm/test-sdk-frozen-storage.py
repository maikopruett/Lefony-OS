#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual frozen file/data/archive CLI against synthetic ARM storage.

The packet observer forwards bytes unchanged and schedules host interruption
after measured transfer progress. It never emulates a firmware response. The
source harness supplies only model setup, normal input and independent oracles.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'sdk/tools'))
import archive_format
from archive_device import CANCELLED as ARCHIVE_CANCELLED
from build import digest, identity, write_json
from data_device import encode_backup, read_backup
from emulator_usb import PrimeUSBHost
from local_transport import session_directory
from replay import Controls
from runner import exercise
from workspace import opened

APP = 'storage-proof'


class ObservedUSB:
    """Single-client, bounded AF_UNIX relay for an exclusively lent model socket."""
    def __init__(self, target, path, cut=None):
        self.target, self.path, self.cut = target, path, cut
        self.progress = threading.Event();self.errors = [];self.transferred = 0;self.requests = []
        self.signal_delivered = threading.Event()
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(path));self.listener.listen(1);self.listener.settimeout(8)
        self.thread = threading.Thread(target=self.serve, daemon=True)

    def serve(self):
        try:
            with PrimeUSBHost(self.target, timeout=3) as backend:
                connection, _ = self.listener.accept()
                with connection, connection.makefile('rwb', buffering=0) as stream:
                    connection.settimeout(10);request = None;size = 0
                    while True:
                        raw = stream.readline(4096)
                        if not raw:break
                        assert raw.endswith(b'\n') and len(raw)<4096
                        command = raw.decode().strip()
                        if command.startswith('SETUP '):
                            kind, code, value, index, length = struct.unpack('<BBHHH', bytes.fromhex(command[6:]))
                            request = (kind, code);size = 0
                            self.requests.append({'direction':kind,'request':code,'length':length})
                        reply = backend.command(command)
                        if request and request[0]==0xc0 and command.startswith('IN ') and reply.startswith('DATA'):
                            size = len(bytes.fromhex(reply[4:].strip()))
                        elif request and request[0]==0x40 and command.startswith('OUT ') and command!='OUT -' and reply=='OK':
                            size = max(0, len(bytes.fromhex(command[4:]))-(24 if request[1]==0x92 else 8))
                        complete = request and ((request[0]==0xc0 and command=='OUT -' and reply=='OK') or
                                                (request[0]==0x40 and command=='IN 0' and reply.startswith('DATA')))
                        if complete:
                            if self.cut and request==self.cut[:2]:
                                self.transferred += size
                                if self.transferred >= self.cut[2] and not self.progress.is_set():
                                    # Withhold a real control-transfer reply until
                                    # SIGINT arrives. This exercises interruption
                                    # inside I/O, rather than between CLI steps.
                                    self.progress.set()
                                    if not self.signal_delivered.wait(2):raise TimeoutError('SIGINT was not delivered')
                                    time.sleep(.05)
                            request = None;size = 0
                        stream.write((reply+'\n').encode())
        except BaseException as error:
            self.errors.append({'error':str(error),'errno':getattr(error,'errno',None)})

    def __enter__(self):
        self.thread.start();return self

    def __exit__(self, *unused):
        self.listener.close();self.thread.join(12)
        assert not self.thread.is_alive(), 'Model relay failed to stop'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args();bundle=args.bundle.resolve();output=args.output.resolve()
    assert platform.system()=='Darwin', 'The denied-access fixture currently requires macOS'
    output.mkdir(parents=True,exist_ok=False)
    for line in (bundle/'SHA256SUMS').read_text().splitlines():
        expected,name=line.split('  ',1);assert digest(bundle/name)==expected,name
    sdk=identity(bundle/'_internal/sdk');assert sdk==identity(ROOT/'sdk')
    sources=['vm/test-sdk-frozen-storage.py','vm/test-sdk-documents.py','tests/native/sdk_data_recovery.c',
             'tests/native/app_document_fixture.cpp','sdk/tools/cli.py','sdk/tools/data_device.py',
             'sdk/tools/files_device.py','sdk/tools/archive_device.py','sdk/tools/emulator_usb.py','sdk/tools/runner.py']
    sources.append('sdk/tools/usb_files.py')
    hashes={name:digest(ROOT/name) for name in sources}
    report={'schema':1,'status':'running','sdk_identity':sdk,'sources':hashes,
            'candidate':json.loads((bundle/'candidate.json').read_text()),
            'bundle_checksums_sha256':digest(bundle/'SHA256SUMS'),
            'frozen_access':'outbound IP network, Homebrew and checkout denied',
            'physical':'not_tested','commands':[],'cases':[],'sessions':[]}
    write_json(output/'report.json',report)
    profile=('(version 1)(allow default)(deny network-outbound (remote ip "*:*"))'
             '(deny file-read* (subpath "/opt/homebrew"))(deny process-exec (subpath "/opt/homebrew"))'
             f'(deny file-read* (subpath {json.dumps(str(ROOT))}))')
    env={**os.environ,'PATH':'/usr/bin:/bin:/usr/sbin:/sbin'}
    try:
        with tempfile.TemporaryDirectory(prefix='lf-storage-',dir='/tmp') as temporary:
            temp=Path(temporary);relocated=temp/'SDK stockage é';shutil.copytree(bundle,relocated,symlinks=True)
            program=relocated/'lefony-sdk';qemu=relocated/'_internal/runtime/qemu-system-arm'
            firmware=relocated/'_internal/runtime/firmware.elf'
            public=relocated/'_internal/tests/fixtures/prime_g2_emulator_update_public.pem'
            private=relocated/'_internal/tests/fixtures/prime_g2_emulator_update_private.pem'
            shutil.copyfile(public,output/'public.pem');artifacts={}
            def record(name,**detail):
                report['cases'].append({'case':name,'status':'passed',**detail})
                write_json(output/'report.json',report);print('PASS: frozen storage '+name,flush=True)
            def run(arguments,*,expected=0,relay=None):
                number=len(report['commands']);stem=f'{number:03d}';out=output/(stem+'.stdout');err=output/(stem+'.stderr')
                command=['/usr/bin/sandbox-exec','-p',profile,str(program),*map(str,arguments)]
                started=time.monotonic();interrupted=False
                with out.open('w') as stdout,err.open('w') as stderr:
                    process=subprocess.Popen(command,cwd=temp,env=env,stdout=stdout,stderr=stderr)
                    try:
                        while process.poll() is None:
                            assert time.monotonic()-started<240,('CLI deadline',arguments)
                            if relay and relay.progress.is_set() and not interrupted:
                                process.send_signal(signal.SIGINT);interrupted=True
                                relay.signal_delivered.set()
                            time.sleep(.005)
                        process.wait(timeout=5)
                    finally:
                        if process.poll() is None:
                            process.terminate()
                            try:process.wait(timeout=5)
                            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                entry={'argv':list(map(str,arguments)),'exit_code':process.returncode,'expected_exit':expected,
                       'seconds':round(time.monotonic()-started,3),'interrupted':interrupted}
                report['commands'].append(entry);write_json(output/'report.json',report)
                assert process.returncode==expected,(arguments,process.returncode,err.read_text())
                if relay and relay.cut:assert interrupted
                text=out.read_text();return json.loads(text) if text.lstrip().startswith('{') else text
            project=temp/'Data recovery';(project/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'tests/native/sdk_data_recovery.c',project/'src/main.c')
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c']})
            for name,version,schema in [('old','1.0.0',0),('new','2.0.0',1)]:
                write_json(project/'app.json',{'abi':1,'id':APP,'name':'Storage Proof','version':version,
                    'license':'CC-BY-NC-SA-4.0','schema':1,'minimum_api':8,'required_capabilities':536,
                    'optional_capabilities':0,'data_schema':schema})
                run(['--project',project,'package']);unsigned=project/'build'/f'{APP}-{version}.lfapp'
                artifacts[name]=temp/(name+'.lfapp')
                run(['sign',unsigned,'--private-key',private,'--output',artifacts[name]])
                shutil.copyfile(artifacts[name],output/(name+'.lfapp'))
            helper=temp/'Helper';(helper/'src').mkdir(parents=True)
            (helper/'src/main.c').write_text('/* SPDX-License-Identifier: GPL-3.0-or-later */\nint main(void){return 0;}\n')
            write_json(helper/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c']})
            write_json(helper/'app.json',{'abi':1,'id':'storage-helper','name':'Helper','version':'1.0.0','license':'GPL-3.0-or-later',
                                       'schema':1,'minimum_api':3,'required_capabilities':16,'optional_capabilities':0,'data_schema':0})
            run(['--project',helper,'package']);bootstrap=helper/'build/storage-helper-1.0.0.lfapp'
            reader_dir=temp/'reader';reader_dir.mkdir()
            reader=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](reader_dir)
            blob=temp/'blob.bin';blob.write_bytes(bytes((i*37)&255 for i in range(131791)))
            change=temp/'changed.bin';change.write_bytes(b'changed after archive export')
            large=temp/'large.bin';large.write_bytes(bytes(range(256))*4096)
            empty=temp/'empty.bin';empty.write_bytes(b'')
            original=temp/'original.lfdata';maximum=temp/'maximum.lfdata'
            maximum.write_bytes(encode_backup(APP,'1.0.0',0,bytes((i*13)&255 for i in range(65536))))
            current=temp/'current.lfarchive';pending=temp/'pending.lfarchive'
            bad=temp/'invalid.lfdata';bad.write_bytes(b'invalid')
            run(['data','--emulator-usb','/missing-model','restore',APP,bad],expected=1)
            record('frozen-private-backup-preflight-before-model-access')
            for phase in ('initial','cold','pending','cold-rollback','fresh','corrupt-index','corrupt-private','corrupt-code'):
                folder=output/phase;folder.mkdir()
                secondary=phase=='fresh' or phase.startswith('corrupt-')
                with opened(project,phase if secondary else 'primary') as (media,_):
                    if phase.startswith('corrupt-'):
                        shutil.copyfile(output/'initial/nand.overlay',media/'nand.overlay')
                        subprocess.run([reader,phase,media/'nand.overlay',APP],check=True,capture_output=True,timeout=60)
                    def controls(channel):
                        normal=Controls(channel,folder);app=channel.app_client;steps=[]
                        def home():normal.key('home');app.wait();normal.key('back')
                        def device(arguments,*,expected=0,cut=None):
                            with channel.usb_host.lend_connection() as target, session_directory() as sockets:
                                path=Path(sockets)/'relay'
                                with ObservedUSB(target,path,cut) as relay:
                                    if arguments[0]=='install':args=[*arguments,'--emulator-usb',path]
                                    else:args=[arguments[0],'--emulator-usb',path,*arguments[1:]]
                                    value=run(args,expected=expected,relay=relay)
                                details={'requests':relay.requests,'bytes_observed':relay.transferred,'errors':relay.errors}
                                write_json(folder/(f'wire-{len(report["commands"])-1:03d}.json'),details)
                                assert not relay.errors,details
                                if cut:assert relay.transferred>=cut[2] and relay.signal_delivered.is_set()
                                return value
                        def install(name):return device(['install',artifacts[name],'--public-key',public])
                        def launch():
                            entry=next(e for e in app.catalog() if e['id']==APP)
                            assert channel.command(f"APP OPEN {entry['slot']}")=='OK'
                            normal.run({'steps':[{'program_exit':0}]},steps);home()
                        def export_file(path,name,expected):
                            destination=temp/(phase+'-'+name)
                            result=device(['files','export',APP,path,destination])
                            assert destination.read_bytes()==expected
                            assert result['bytes']==len(expected) and result['sha256']==hashlib.sha256(expected).hexdigest()
                            shutil.copyfile(destination,folder/name);return result
                        def private_data(name,expected):
                            destination=temp/(phase+'-'+name+'.lfdata')
                            result=device(['data','export',APP,destination]);assert read_backup(destination)[1]==expected
                            shutil.copyfile(destination,folder/(name+'.lfdata'));return result
                        def restore(archive,**options):
                            args=['archive','restore',archive,'--public-key',public]
                            args += ['--repair-code'] if phase=='corrupt-code' else ['--replace']
                            return device(args,**options)
                        try:
                            normal.run({'steps':[{'program_exit':0}]},steps);home()
                            if phase=='initial':
                                install('old');launch()
                                info=device(['files','info',APP]);assert info['private_bytes']==4 and info['quota_bytes']==33554432
                                assert info['quota_committed_bytes']==info['file_bytes']+info['private_bytes'] and info['shared_available_bytes']>0
                                device(['files','import',APP,'blob.bin',blob]);export_file('blob.bin','blob.bin',blob.read_bytes())
                                device(['files','import',APP,'blob.bin',change],expected=1)
                                for i in range(17):device(['files','import',APP,f'empty-{i:02d}.bin',empty])
                                listing=device(['files','list',APP]);assert len(listing['entries'])==19
                                device(['data','export',APP,original]);assert read_backup(original)[1]==struct.pack('<I',111)
                                device(['data','restore',APP,maximum]);private_data('maximum',read_backup(maximum)[1])
                                device(['data','restore',APP,original]);private_data('original',struct.pack('<I',111))
                                record('listing-pagination-usage-large-file-and-64KiB-private-data-roundtrip')
                                device(['data','restore',APP,maximum],expected=130,cut=(0x40,0x72,32768))
                                assert device(['files','status'])['state']==6
                                private_data('after-private-cancel',struct.pack('<I',111))
                                device(['data','restore',APP,maximum],cut=(0x40,0x74,0))
                                private_data('committed-after-Ctrl-C',read_backup(maximum)[1])
                                kept=temp/'kept-private.lfdata';kept.write_bytes(original.read_bytes())
                                device(['data','export',APP,kept,'--replace'],expected=130,cut=(0xc0,0x72,32768))
                                assert device(['files','status'])['state']==6
                                assert kept.read_bytes()==original.read_bytes() and not list(temp.glob('.kept-private.lfdata.*.partial'))
                                device(['data','restore',APP,original])
                                record('private-data-interruption-preserves-old-bytes-and-reports-accepted-commit')
                                device(['files','import',APP,'blob.bin',large,'--replace'],expected=130,cut=(0x40,0x72,32768))
                                assert device(['files','status'])['state']==6
                                export_file('blob.bin','after-cancel.bin',blob.read_bytes())
                                local=temp/'kept-local.bin';local.write_bytes(b'keep existing local output')
                                device(['files','export',APP,'blob.bin',local,'--replace'],expected=130,cut=(0xc0,0x72,32768))
                                assert device(['files','status'])['state']==6
                                assert local.read_bytes()==b'keep existing local output' and not list(temp.glob('.kept-local.bin.*.partial'))
                                record('Ctrl-C-import-and-export-preserve-both-destinations')
                                committed=device(['files','import',APP,'blob.bin',blob,'--replace'],cut=(0x40,0x74,0))
                                assert committed['committed']
                                export_file('blob.bin','committed-file.bin',blob.read_bytes())
                                device(['archive','export',APP,current,'--public-key',public]);shutil.copyfile(current,folder/'current.lfarchive')
                                archive=archive_format.inspect(current,[public]);assert archive.signatures_checked and len(archive.snapshots)==1
                                kept_archive=temp/'kept.lfarchive';kept_archive.write_bytes(b'keep existing archive')
                                device(['archive','export',APP,kept_archive,'--replace','--public-key',public],expected=130,cut=(0xc0,0x92,32768))
                                assert device(['archive','status'])['state']==ARCHIVE_CANCELLED
                                assert kept_archive.read_bytes()==b'keep existing archive' and not list(temp.glob('.kept.lfarchive.*.partial'))
                                device(['files','import',APP,'blob.bin',change,'--replace'])
                                restore(current,expected=130,cut=(0x40,0x92,32768))
                                cancelled=device(['archive','status'])
                                assert cancelled['state']==ARCHIVE_CANCELLED,cancelled
                                export_file('blob.bin','cancelled-archive.bin',change.read_bytes())
                                assert restore(current,cut=(0x40,0x94,0))['committed'];export_file('blob.bin','restored.bin',blob.read_bytes())
                                private_data('archive-restored',struct.pack('<I',111))
                                again=temp/'again.lfarchive';device(['archive','export',APP,again,'--public-key',public])
                                assert again.read_bytes()==current.read_bytes()
                                record('cancelled-and-complete-whole-app-restore-exact-roundtrip')
                            elif phase=='pending':
                                install('new');launch();state=device(['data','info',APP])
                                assert state['pending_upgrade'] and state['data_schema']==1 and state['high_version']=='2.0.0'
                                device(['data','restore',APP,original],expected=1)
                                device(['archive','export',APP,pending,'--public-key',public])
                                assert len(archive_format.inspect(pending,[public]).snapshots)==2
                                shutil.copyfile(pending,folder/'pending.lfarchive')
                                result=device(['data','rollback',APP],cut=(0x40,0x74,0));assert result['committed'] and result['version']=='1.0.0'
                                assert restore(current)['committed']
                                assert device(['data','info',APP])['high_version']=='2.0.0'
                                private_data('rolled-back',struct.pack('<I',111));export_file('document.txt','document.txt',b'old document')
                                record('schema-upgrade-pair-export-and-rollback-preserve-version-history')
                            elif secondary:
                                if phase!='fresh':
                                    bad_export=temp/(phase+'.lfarchive');bad_export.write_bytes(b'keep existing archive')
                                    device(['archive','export',APP,bad_export,'--replace','--public-key',public],expected=1)
                                    assert bad_export.read_bytes()==b'keep existing archive'
                                result=restore(current);assert result['committed']
                                launch();private_data('repaired',struct.pack('<I',111));export_file('blob.bin','blob.bin',blob.read_bytes())
                                record(phase+'-signed-archive-restores-exact-code-and-data')
                            else:
                                launch();private_data('cold',struct.pack('<I',111));export_file('blob.bin','cold.bin',blob.read_bytes())
                                assert len(device(['files','list',APP])['entries'])==19
                                if phase=='cold-rollback':assert device(['data','info',APP])['high_version']=='2.0.0'
                                record(phase+'-saved-private-and-named-data')
                        finally:normal.close();write_json(folder/'steps.json',steps)
                    try:runtime=exercise(bootstrap,qemu,firmware,workspace=media,controls=controls)
                    finally:shutil.copyfile(media/'nand.overlay',folder/'nand.overlay')
                    assert runtime['os_responsive'] and runtime['result']==1
                    write_json(folder/'runtime.json',runtime);shutil.copyfile(media/'nand.overlay',folder/'nand.overlay')
                    state=json.loads(subprocess.check_output([reader,'inspect-app',media/'nand.overlay',APP],text=True,timeout=60))
                    write_json(folder/'independent-root.json',state)
                    assert state['package_sha256']==digest(artifacts['old']) and not state['pending_upgrade']
                    report['sessions'].append({'phase':phase,'runtime':runtime,'root':state});write_json(output/'report.json',report)
        assert hashes=={name:digest(ROOT/name) for name in sources} and sdk==identity(ROOT/'sdk')
        report['status']='passed';write_json(output/'report.json',report)
    except BaseException as error:
        report.update(status='failed',error=str(error));write_json(output/'report.json',report);raise


if __name__=='__main__':main()
