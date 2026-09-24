#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Normal Home during Doom save staging/verification, public export and cold load.

Matching firmware symbols expose read-only phase observations. The test never
calls game/storage functions, sets guest variables or injects direct app events.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from cli import package
from files_device import FileClient
from replay import Controls
from runner import exercise
from signing import sign
from workspace import opened
from sdk_doom_probe import DoomProbe

SAVE='.savegame/doomsav0.dsg'
VOLUME="'PrimeG2::AppManagement::(anonymous namespace)::sVolume'"
SESSION="'PrimeG2::AppManagement::(anonymous namespace)::sFiles'"
FIELDS={'saving':'gameaction == ga_savegame && save_stream != 0',
        'staged':VOLUME+'.m_files.m_position',
        'file_phase':'(int)'+VOLUME+'.m_files.m_phase',
        'document_phase':'(int)'+VOLUME+'.m_documents.m_phase',
        'document_cursor':VOLUME+'.m_documents.m_cursor',
        'writer':SESSION+'.m_handles[4].token',
        'verifying':VOLUME+'.m_files.m_phase == PrimeG2::AppFileStore::Store::Phase::Commit && '+
                    VOLUME+'.m_documents.m_phase == PrimeG2::AppDocumentStore::Store::Phase::CheckReferences'}
PLAYER='players[consoleplayer]'
POSE_FIELDS={'x':PLAYER+'.mo->x','y':PLAYER+'.mo->y','z':PLAYER+'.mo->z',
             'angle':PLAYER+'.mo->angle','momx':PLAYER+'.mo->momx',
             'momy':PLAYER+'.mo->momy','momz':PLAYER+'.mo->momz',
             'health':PLAYER+'.health','ammo':PLAYER+'.ammo[0]',
             'leveltime':'leveltime','episode':'gameepisode','map':'gamemap'}


def load_segments(path):
    data=path.read_bytes()
    assert data[:7]==b'\x7fELF\x01\x01\x01' and struct.unpack_from('<H',data,18)[0]==40,'Expected ARM ELF32'
    start=struct.unpack_from('<I',data,28)[0];size,count=struct.unpack_from('<HH',data,42)
    assert size>=32 and start+size*count<=len(data)
    segments=[]
    for i in range(count):
        kind,offset,virtual,physical,file_bytes,memory_bytes,flags,alignment=struct.unpack_from('<8I',data,start+i*size)
        if kind!=1:continue
        assert offset+file_bytes<=len(data) and file_bytes<=memory_bytes
        segments.append((virtual,physical,memory_bytes,flags,alignment,data[offset:offset+file_bytes]))
    assert segments
    return sorted(segments)


def at_breakpoint(normal,probe,firmware_debug,folder,label,symbol,fields,on_hit=None):
    """Confirm through normal input, read at a temporary hardware breakpoint."""
    session=normal.channel.session_directory
    armed=session/(label+'-armed');hit=session/(label+'-hit')
    # These private session paths contain no spaces; GDB's dump parser does not
    # interpret quoted filenames consistently across the supported builds.
    assert not any(c.isspace() for c in str(session))
    command='printf "WITNESS '+','.join(['%d']*len(fields))+'\\n", '+', '.join('('+v+')' for v in fields.values())
    quoted=str(firmware_debug.resolve()).replace('\\','\\\\').replace('"','\\"')
    argv=[shutil.which('arm-none-eabi-gdb'),'-q','-nx',str(probe.elf.resolve()),
          '-ex','set pagination off','-ex','set confirm off','-ex','add-symbol-file "'+quoted+'"',
          '-ex','set language c++','-ex','target remote '+str(probe.endpoint),
          '-ex','thbreak '+symbol,
          '-ex',f'dump binary memory {armed} &gametic &gametic+1',
          '-ex','continue','-ex',command,
          '-ex',f'dump binary memory {hit} &gametic &gametic+1']
    log=folder/(label+'-breakpoint.log')
    with log.open('w') as stream:
        process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.STDOUT,text=True)
        def wait_marker(path,timeout):
            end=time.monotonic()+timeout
            while not path.exists():
                assert process.poll() is None and time.monotonic()<end,log.read_text()
                time.sleep(.02)
        try:
            wait_marker(armed,30)
            normal.key_edge('ok',True);time.sleep(.25);normal.key_edge('ok',False)
            wait_marker(hit,180)
            # A temporary hardware breakpoint changes neither instructions nor
            # game/storage state. The marker dumps read only four guest bytes.
            if on_hit:on_hit()
            process.communicate('detach\nquit\n',timeout=30)
            assert process.returncode==0,log.read_text()
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:process.communicate('detach\nquit\n',timeout=15)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            normal.key_edge('ok',False)
    text=log.read_text();found=re.search(r'WITNESS ([0-9,\-]+)',text)
    assert found and 'Temporary breakpoint' in text and symbol in text,text
    return dict(zip(fields,map(int,found[1].split(',')),strict=True))


def home_after_prefix(normal,probe,firmware_debug,folder,before_bytes):
    """Observe a written prefix; queue normal Home while paused, then resume."""
    try:
        witness=at_breakpoint(normal,probe,firmware_debug,folder,'prefix',
            'P_ArchiveThinkers',FIELDS,on_hit=lambda:normal.key_edge('home',True))
        time.sleep(.3)
    finally:normal.key_edge('home',False)
    time.sleep(.75);normal.channel.app_client.wait()
    assert witness['saving'] and witness['writer'] and 0<witness['staged']<before_bytes and not witness['verifying'],witness
    return witness


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('seed-project','output','firmware','firmware-debug'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--cases',nargs='+')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True)
    assert load_segments(args.firmware)==load_segments(args.firmware_debug),'Firmware symbols do not match the loaded image'
    project=out/'project';shutil.copytree(args.seed_project,project,
        ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json','compile_commands.json'))
    dest=project/'.lefony/workspaces/game';dest.mkdir(parents=True)
    with opened(args.seed_project.resolve(),'game') as (seed,_):
        for name in ('workspace.json','nand.overlay'):shutil.copyfile(seed/name,dest/name)
    app=package(project)
    assert load_segments(project/'build/app.elf')==load_segments(project/'build/app-debug.elf'), 'App symbols do not match the package image'
    signed=sign(app.read_bytes(),ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem')
    assert hashlib.sha256(signed).hexdigest()==json.loads((dest/'workspace.json').read_text())['package_sha256']
    phases=('home-staging','cold-staging','home-verification','cold-verification','retry','cold-retry')
    if args.cases:
        assert set(args.cases)<=set(phases);phases=tuple(p for p in phases if p in args.cases)
    assert 'cold-retry' not in phases or 'retry' in phases,'cold-retry requires the preceding retry case'
    report={'status':'running','cases':[],'sdk_sha256':identity(ROOT/'sdk'),
        'firmware_sha256':digest(args.firmware),'firmware_debug_sha256':digest(args.firmware_debug),
        'qemu_sha256':digest(ROOT/'build/qemu-prime-g2/qemu-system-arm'),
        'app_elf_sha256':digest(project/'build/app.elf'),
        'app_debug_sha256':digest(project/'build/app-debug.elf'),
        'sources':{name:digest(ROOT/name) for name in ('vm/test-sdk-doom-interruption.py','vm/sdk_doom_probe.py')},
        'physical':'not_tested','timing':'GDB-observed model stages; not physical input or save latency'}
    for name in report['sources']:shutil.copyfile(ROOT/name,out/Path(name).name)
    write_json(out/'report.json',report)
    saved_pose=None
    for phase in phases:
        folder=out/phase;folder.mkdir();records={}
        def prepare(client):
            files=FileClient(client,timeout=180)
            files.export_file('doom-proof',SAVE,folder/'before.dsg')
            files.export_file('doom-proof','default.cfg',folder/'before.cfg')
            records['before']=files.info('doom-proof')
            assert not records['before']['pending_upgrade']
        def controls(channel):
            nonlocal saved_pose
            normal=Controls(channel,folder)
            probe=DoomProbe(normal,project/'build/app-debug.elf',folder,
                symbols=(args.firmware_debug,),fields=FIELDS)
            try:
                ready=probe.until('ready',lambda s:s['state']==0 and s['health']>0 and s['tics']>2)
                if phase.startswith('home-'):
                    probe.save(name=('four','five','six'),confirm=False)
                    start=time.monotonic()
                    if phase=='home-staging':
                        interrupted=home_after_prefix(normal,probe,args.firmware_debug,folder,(folder/'before.dsg').stat().st_size)
                    else:
                        normal.key_edge('ok',True)
                        try:
                            interrupted=probe.until('verifying',lambda s:s['saving'] and s['writer'] and
                                s['verifying'] and s['document_cursor']>=2048)
                        finally:normal.key_edge('ok',False)
                        normal.key('home');channel.app_client.wait()
                    records['interrupted']=interrupted
                    records['observe_home_and_drain_seconds']=time.monotonic()-start
                elif phase=='retry':
                    normal.keys(['up']);time.sleep(1.2);normal.keys([]);time.sleep(.4)
                    moved=probe.read('moved-before-retry')
                    assert (moved['x'],moved['y'])!=(ready['x'],ready['y']),moved
                    probe.save(name=('four','five','six'),confirm=False)
                    # Saving may retain player momentum. Compare the serialized
                    # state before gameplay resumes, not a later sampled tick.
                    saved_pose=at_breakpoint(normal,probe,args.firmware_debug,folder,
                        'serialized','P_WriteSaveGameEOF',POSE_FIELDS)
                    records['saved_pose']=saved_pose
                    saved=probe.until('saved',lambda s:not s['menu'] and not s['save_entry'] and
                        not s['save_request'] and s['action']==0 and not s['writer'])
                    assert not saved['save_error'];probe.capture('retry')
                else:
                    normal.key('symb');probe.until('load-menu',lambda s:s['menu']==1)
                    restored=at_breakpoint(normal,probe,args.firmware_debug,folder,
                        'restored','P_ReadSaveGameEOF',{**POSE_FIELDS,'tics':'gametic'})
                    records['restored_pose']={k:restored[k] for k in POSE_FIELDS}
                    if phase=='cold-retry':assert records['restored_pose']==saved_pose,records
                    loaded=probe.until('loaded',lambda s:not s['menu'] and s['action']==0 and
                        s['tics']>restored['tics'])
                    assert not loaded['save_error'],loaded
                    assert loaded['health']>0;probe.capture('loaded')
                if not phase.startswith('home-'):normal.key('home');channel.app_client.wait()
                files=FileClient(channel.app_client,timeout=180)
                files.export_file('doom-proof',SAVE,folder/'after.dsg')
                files.export_file('doom-proof','default.cfg',folder/'after.cfg')
                records['after']=files.info('doom-proof')
                assert (folder/'before.cfg').read_bytes()==(folder/'after.cfg').read_bytes()
                before=(folder/'before.dsg').read_bytes();after=(folder/'after.dsg').read_bytes()
                if phase=='retry':assert after.startswith(b'456\0') and before!=after
                else:
                    assert before==after
                    assert records['before']['generation']==records['after']['generation']
            finally:
                records['observations']=probe.records;write_json(folder/'observations.json',records);normal.close()
        try:
            with opened(project,'game') as (workspace,_):
                result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',args.firmware,
                    workspace=workspace,prepare_workspace=prepare,controls=controls,measure_resources=True)
            assert result['result']==1 and result['os_responsive'],result
        except BaseException as error:
            report.update(status='failed',failed_phase=phase,
                error={'type':type(error).__name__,'message':str(error)[:4096]})
            write_json(out/'report.json',report)
            raise
        report['cases'].append({'phase':phase,'records':records,'runtime':result})
        write_json(out/'report.json',report);print('PASS:',phase,flush=True)
    report['status']='passed';write_json(out/'report.json',report)


if __name__=='__main__':main()
