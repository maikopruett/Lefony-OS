#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real Doom partial-save failure, retry, cold load and bounded config input.

Clone an accepted same-package workspace. All data changes use public file
exchange and all game actions use normal keys. GDB only observes engine state.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

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

LIMIT=32*1024*1024
SAVE='.savegame/doomsav0.dsg'
SECOND='.savegame/doomsav1.dsg'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('seed-project','output','firmware'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--project',type=Path,help='Updated source project; complete its ordinary package upgrade before changing data')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True)
    project=out/'project'
    shutil.copytree(args.project or args.seed_project,project,ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json','compile_commands.json'))
    dest=project/'.lefony/workspaces/game';dest.mkdir(parents=True)
    with opened(args.seed_project.resolve(),'game') as (seed,_):
        for name in ('workspace.json','nand.overlay'):shutil.copyfile(seed/name,dest/name)
    app=package(project)
    signed=sign(app.read_bytes(),ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem')
    same_package=hashlib.sha256(signed).hexdigest()==json.loads((dest/'workspace.json').read_text())['package_sha256']
    assert args.project or same_package,'Seed package differs'
    report={'status':'running','cases':[],'sdk_sha256':identity(ROOT/'sdk'),
            'firmware_sha256':digest(args.firmware),'package_sha256':digest(app),'physical':'not_tested'}
    if not same_package:
        folder=out/'upgrade';folder.mkdir()
        def upgrade(channel):
            normal=Controls(channel,folder);probe=DoomProbe(normal,project/'build/app-debug.elf',folder)
            try:
                probe.until('ready',lambda s:s['state']==0 and s['health']>0 and s['tics']>2)
                probe.quit()
            finally:write_json(folder/'observations.json',probe.records);normal.close()
        with opened(project,'game') as (workspace,_):
            upgraded=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',args.firmware,
                workspace=workspace,controls=upgrade,measure_resources=True)
        assert upgraded['result']==1 and upgraded['program']['exit_status']==0,upgraded
        report['upgrade']=upgraded
    saved=None
    for phase in ('save-short','save-short-cold','save-retry','save-cold','config-large','config-repair'):
        folder=out/phase;folder.mkdir();records={}
        def prepare(client):
            files=FileClient(client,timeout=180)
            if phase in ('save-short','save-retry'):
                empty=folder/'empty';empty.write_bytes(b'')
                files.import_file('doom-proof','quota-filler',empty,replace=True)
            if phase=='save-short':
                info=files.info('doom-proof');filler=folder/'filler'
                filler.write_bytes(bytes(LIMIT-info['quota_committed_bytes']-4096))
                files.import_file('doom-proof','quota-filler',filler,replace=True)
            elif phase=='config-large':
                files.export_file('doom-proof','default.cfg',out/'good.cfg')
                large=folder/'oversized.cfg';large.write_bytes(b'mouse_sensitivity 8\n'+b' '*(65537-20))
                assert large.stat().st_size==65537
                files.import_file('doom-proof','default.cfg',large,replace=True)
            elif phase=='config-repair':
                files.import_file('doom-proof','default.cfg',out/'good.cfg',replace=True)
            files.export_file('doom-proof',SAVE,folder/'before.dsg')
            files.export_file('doom-proof','default.cfg',folder/'before.cfg')
            records['before_space']=files.info('doom-proof')
            records['before_saves']=files.list('doom-proof','.savegame')
            if phase in ('save-short','save-short-cold'):
                assert records['before_space']['quota_remaining_bytes']==4096
                assert not any(e['path']==SECOND for e in records['before_saves']['entries'])
        def controls(channel):
            nonlocal saved
            normal=Controls(channel,folder);probe=DoomProbe(normal,project/'build/app-debug.elf',folder)
            try:
                if phase=='config-large':
                    exited=probe.until('config-error',lambda s:s['exited'])
                    assert exited['exit_status']==-1,exited
                    probe.capture('config-error')
                else:
                    probe.until('ready',lambda s:s['state']==0 and s['health']>0 and s['tics']>2)
                    if phase in ('save-short','save-retry'):
                        probe.save(slot=1)
                        state=probe.until('save-result',lambda s:s['menu']==0 and not s['save_entry'] and not s['save_request'] and s['action']==0)
                        assert bool(state['save_error'])==(phase=='save-short'),state
                        assert not state['exited'];probe.capture('save-result')
                        if phase=='save-retry':saved=(state['x'],state['y'])
                        normal.key('back');probe.until('responsive-menu',lambda s:s['menu']==1);normal.key('back')
                    elif phase in ('save-short-cold','save-cold'):
                        normal.key('symb');probe.until('load-menu',lambda s:s['menu']==1)
                        if phase=='save-cold':normal.key('down')
                        normal.key('ok');state=probe.until('loaded',lambda s:s['menu']==0 and s['action']==0)
                        if phase=='save-cold':assert (state['x'],state['y'])==saved,state
                        probe.capture('loaded')
                    else:probe.capture('repaired-config')
                normal.key('home');channel.app_client.wait()
                files=FileClient(channel.app_client,timeout=180)
                records['after_saves']=files.list('doom-proof','.savegame')
                records['after_space']=files.info('doom-proof')
                files.export_file('doom-proof',SAVE,folder/'after.dsg')
                files.export_file('doom-proof','default.cfg',folder/'after.cfg')
                if phase in ('save-short','save-short-cold'):
                    assert records['before_saves']['entries']==records['after_saves']['entries']
                    assert records['after_space']['quota_committed_bytes']==records['before_space']['quota_committed_bytes']
                else:
                    files.export_file('doom-proof',SECOND,folder/'second.dsg')
                    if phase!='save-retry':assert (folder/'second.dsg').read_bytes()==(out/'save-retry/second.dsg').read_bytes()
                    else:assert (folder/'second.dsg').read_bytes().startswith(b'123\0') and (folder/'second.dsg').stat().st_size>4096
                assert (folder/'before.dsg').read_bytes()==(folder/'after.dsg').read_bytes()
                assert (folder/'before.cfg').read_bytes()==(folder/'after.cfg').read_bytes()
            finally:
                records['observations']=probe.records;write_json(folder/'observations.json',records);normal.close()
        with opened(project,'game') as (workspace,_):
            result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',args.firmware,
                workspace=workspace,prepare_workspace=prepare,controls=controls,measure_resources=True)
        assert result['result']==1 and result['os_responsive'],result
        report['cases'].append({'phase':phase,'runtime':result,'records':records})
        write_json(out/'report.json',report);print('PASS:',phase,flush=True)
    report['status']='passed';write_json(out/'report.json',report)


if __name__=='__main__':main()
