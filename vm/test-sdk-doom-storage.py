#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Doom saves at real quota, public configuration inputs, and cold recovery."""
import argparse
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json,identity
from cli import package
from files_device import FileClient
from replay import Controls
from runner import exercise
from signing import sign
from workspace import opened
from sdk_doom_probe import DoomProbe

LIMIT=32*1024*1024
SAVE='.savegame/doomsav0.dsg'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('project','seed-project','output','firmware'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--baseline',action='store_true')
    parser.add_argument('--cases',nargs='+')
    parser.add_argument('--accepted-seed',action='store_true',help='Require a seed with this exact package already installed; firmware still checks import readiness')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True)
    project=out/'project';shutil.copytree(args.project,project,ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json','compile_commands.json'))
    dest=project/'.lefony/workspaces/game';dest.mkdir(parents=True)
    with opened(args.seed_project.resolve(),'game') as (seed,_):
        for name in ('workspace.json','nand.overlay'):shutil.copyfile(seed/name,dest/name)
    app=package(project);report={'status':'running','cases':[],'sdk_sha256':identity(ROOT/'sdk'),
        'firmware_sha256':digest(args.firmware),'physical':'not_tested','baseline':args.baseline}
    phases=('full','cold') if args.baseline else ('full','cold','settings','settings-cold','config-quota','config-quota-cold','config-retry','config-retry-cold')
    if args.cases:
        assert set(args.cases)<=set(phases),'Unknown case'
        phases=tuple(p for p in phases if p in args.cases)
    if args.accepted_seed:
        import hashlib
        state=json.loads((dest/'workspace.json').read_text())
        signed=sign(app.read_bytes(),ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem')
        assert hashlib.sha256(signed).hexdigest()==state['package_sha256'],'Seed package differs'
    if not args.baseline and not args.accepted_seed:
        # Finish the real package upgrade before host imports can modify data.
        # Import rejection while an old compatible pair is pending is required.
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
    for phase in phases:
        folder=out/phase;folder.mkdir();records={}
        def prepare(client):
            files=FileClient(client,timeout=180)
            records['before_files']=files.list('doom-proof')
            files.export_file('doom-proof',SAVE,folder/'before.dsg')
            if phase in ('settings','config-retry'):
                empty=folder/'empty';empty.write_bytes(b'')
                files.import_file('doom-proof','quota-filler',empty,replace=True)
            if phase=='full':
                config=folder/'config-input';config.write_bytes(b'mouse_sensitivity 7\nscreenblocks 10\n')
                files.import_file('doom-proof','default.cfg',config,replace=True)
                usage=files.info('doom-proof');records['before_space']=usage
                filler=folder/'filler';filler.write_bytes(bytes(LIMIT-usage['quota_committed_bytes']))
                files.import_file('doom-proof','quota-filler',filler)
            elif phase=='config-quota':
                usage=files.info('doom-proof')
                filler=folder/'filler';filler.write_bytes(bytes(LIMIT-usage['quota_committed_bytes']))
                files.import_file('doom-proof','quota-filler',filler,replace=True)
            if phase.startswith('config') or phase=='settings-cold':
                files.export_file('doom-proof','default.cfg',folder/'before.cfg')
            records['full_space']=files.info('doom-proof')
            if phase in ('full','cold','config-quota','config-quota-cold'):
                assert records['full_space']['quota_committed_bytes']==LIMIT,records
        def controls(channel):
            normal=Controls(channel,folder);probe=DoomProbe(normal,project/'build/app-debug.elf',folder)
            try:
                ready=probe.until('ready',lambda s:s['state']==0 and s['health']>0 and s['tics']>2)
                expected_mouse=5 if args.baseline else 7 if phase in ('full','cold','settings') else 8
                expected_screen=10 if phase in ('full','cold','settings','config-retry-cold') else 9
                records['loaded_settings']=ready['mouse'];assert ready['mouse']==expected_mouse and ready['screen']==expected_screen,ready
                if phase=='full':
                    probe.save()
                    if args.baseline:normal.run({'steps':[{'program_exit':-1}]},[])
                    else:probe.until('saved',lambda s:s['menu']==0 and not s['save_entry'] and not s['save_request'] and s['action']==0 and not s['save_error'])
                    probe.capture('save-result')
                elif phase=='cold':
                    normal.key('symb');probe.until('load-menu',lambda s:s['menu']==1)
                    normal.key('ok');probe.until('loaded',lambda s:s['menu']==0 and s['action']==0)
                    probe.capture('loaded')
                elif phase=='settings':
                    probe.settings();probe.quit()
                elif phase in ('config-quota','config-retry'):
                    normal.key('plus');probe.until('larger-screen',lambda s:s['screen']==10)
                    probe.quit(-1 if phase=='config-quota' else 0)
                else:probe.capture('cold-settings')
                normal.key('home');channel.app_client.wait()
                files=FileClient(channel.app_client,timeout=180)
                files.export_file('doom-proof',SAVE,folder/'after.dsg')
                records['after_files']=files.list('doom-proof');records['after_space']=files.info('doom-proof')
                if phase not in ('full','cold'):
                    files.export_file('doom-proof','default.cfg',folder/'after.cfg')
                    if phase in ('config-quota','config-quota-cold','settings-cold','config-retry-cold'):
                        assert (folder/'after.cfg').read_bytes()==(folder/'before.cfg').read_bytes()
                    if phase=='settings':
                        import re
                        config=(folder/'after.cfg').read_text()
                        assert re.search(r'^mouse_sensitivity\s+8$',config,re.M) and re.search(r'^screenblocks\s+9$',config,re.M),config
                assert records['after_space']['quota_committed_bytes']<=LIMIT
            finally:
                records['observations']=probe.records;write_json(folder/'observations.json',records);normal.close()
        with opened(project,'game') as (workspace,_):
            result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',args.firmware,
                workspace=workspace,prepare_workspace=prepare,controls=controls,measure_resources=True)
        assert result['result']==1 and result['os_responsive'],result
        before=(folder/'before.dsg').read_bytes();after=(folder/'after.dsg').read_bytes()
        if args.baseline or phase!='full':assert before==after
        else:assert after.startswith(b'123\0') and before!=after
        report['cases'].append({'phase':phase,'runtime':result,'records':records,'before_sha256':digest(folder/'before.dsg'),'after_sha256':digest(folder/'after.dsg')})
        write_json(out/'report.json',report);print('PASS:',phase,'baseline' if args.baseline else 'current',flush=True)
    report['status']='baseline-gaps-reproduced' if args.baseline else 'passed';write_json(out/'report.json',report)

if __name__=='__main__':main()
