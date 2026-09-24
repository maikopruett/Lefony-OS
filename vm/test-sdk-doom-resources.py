#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Doom startup failures, real allocation exhaustion and recursive cleanup."""
import argparse
from pathlib import Path
import runpy
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from cli import package
from files_device import FileClient
from replay import Controls
from runner import exercise
from workspace import opened
from sdk_doom_probe import DoomProbe


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--firmware',type=Path,required=True)
    modes=('missing-wad','zone-exhausted','screen-exhausted','recursive-cleanup','recursive-output')
    parser.add_argument('--cases',nargs='+',choices=modes)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True)
    prepare=runpy.run_path(str(ROOT/'scripts/prepare_sdk_doom.py'))['prepare']
    report={'status':'running','cases':[],'sdk_sha256':identity(ROOT/'sdk'),
            'firmware_sha256':digest(args.firmware),'physical':'not_tested',
            'sources':{name:digest(ROOT/name) for name in
                ('scripts/prepare_sdk_doom.py','vm/test-sdk-doom-resources.py','vm/sdk_doom_probe.py')}}
    write_json(out/'report.json',report)
    for mode in args.cases or modes:
        folder=out/mode;folder.mkdir();project=folder/'project'
        arguments=['-iwad','freedoom1.wad','-warp','1','1','-skill','2','-nosound','-nogui']
        if mode=='zone-exhausted':arguments+=['-mb','9']
        config=prepare(project,ROOT/'build/sdk-1.0-upstream/doomgeneric',arguments)
        if mode=='screen-exhausted':
            # This is an additional ordinary constructor using the real newlib
            # allocator, not a replacement allocator or privileged test service.
            (project/'src/exhaustion.c').write_text('''/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <stdlib.h>
#include <unistd.h>
static volatile unsigned char *reserved;
__attribute__((constructor)) static void occupy_heap(void) {
    reserved=malloc(8250000);
    if(!reserved) _exit(80);
    reserved[0]=1;
}
''')
            config['sources'].append('src/exhaustion.c');write_json(project/'project.json',config)
        if mode in ('recursive-cleanup','recursive-output'):
            # A normal engine exit callback fails while handling missing WAD
            # data. This fixture does not replace I_Error or mutate OS state.
            (project/'src/recursive_cleanup.c').write_text('''/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "i_system.h"
static void fail_cleanup(void) { I_Error("Cleanup failed"); }
__attribute__((constructor)) static void register_cleanup(void) {
    I_AtExit(fail_cleanup, true);
}
''')
            config['sources'].append('src/recursive_cleanup.c');write_json(project/'project.json',config)
            if mode=='recursive-output':
                (project/'src/recursive_cleanup.c').write_text('''/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "i_system.h"
#include "output.h"
#include <unistd.h>
static void fail_cleanup(void) {
    char data[4096] = {1};
    FILE *stream = DG_OpenOutput("cleanup.tmp");
    if (!stream || fwrite(data, 1, sizeof(data), stream) != sizeof(data) || fflush(stream))
        _exit(81);
    I_Error("Cleanup failed with staged output");
}
__attribute__((constructor)) static void register_cleanup(void) {
    I_AtExit(fail_cleanup, true);
}
''')
        app=package(project)
        def controls(channel):
            normal=Controls(channel,folder);probe=DoomProbe(normal,project/'build/app-debug.elf',folder)
            try:
                exited=probe.until('failure',lambda s:s['exited'])
                assert exited['exit_status']==-1,exited
                probe.capture('failure')
                normal.key('home');assert channel.command('PING')=='PONG'
                channel.app_client.wait()
                files=FileClient(channel.app_client,timeout=180)
                listing=files.list('doom-proof')
                assert not listing['entries'],listing
                write_json(folder/'files-after.json',listing)
            finally:write_json(folder/'observations.json',probe.records);normal.close()
        try:
            with opened(project,'game') as (workspace,_):
                result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',args.firmware,
                    workspace=workspace,controls=controls,measure_resources=True)
            assert result['result']==1 and result['os_responsive'] and result['resources']['faults']==0,result
        except BaseException as error:
            report.update(status='failed',failed_mode=mode,
                error={'type':type(error).__name__,'message':str(error)[:4096]})
            write_json(out/'report.json',report)
            raise
        report['cases'].append({'mode':mode,'package_sha256':digest(app),'runtime':result})
        write_json(out/'report.json',report);print('PASS:',mode,flush=True)
    report['status']='passed';write_json(out/'report.json',report)


if __name__=='__main__':main()
