#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real external source edit, layout defect, failed-build stale frame, fix and watch."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json,project_lock
from preview import once,source_state


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-ui/preview')
    args=parser.parse_args();qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm'
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True);cases=[]
    with tempfile.TemporaryDirectory(prefix='sdk-preview-') as temp:
        project=Path(temp)/'External source project é'
        shutil.copytree(ROOT/'sdk/examples/notebook',project,ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json'))
        source=project/'src/main.cpp';original=source.read_text()
        scenario=project/'tests/preview.json';write_json(scenario,{'schema':1,'name':'editor','steps':[{'key':'ok'}]})
        def capture(name):
            value=once(project,qemu,args.firmware,scenario=Path('tests/preview.json'))
            target=output/name
            shutil.copytree(project/'build/preview',target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.lock'))
            cases.append({'name':name,'status':value['status'],'timings':value.get('timings'),'package':value.get('package_sha256')})
            return value
        value=capture('first');assert value['status']=='ready',value.get('error')
        source.write_text(original.replace('Third{216,190,92,32}','Third{295,190,92,32}'))
        value=capture('clipped');assert value['status']=='ready',value.get('error')
        node=next(node for node in value['layout']['nodes'] if node['id']==13)
        assert node['clipped'] and node['file']=='src/main.cpp' and node['line']>0
        assert 'ui.button(13' in source.read_text().splitlines()[node['line']-1]
        first_hash=digest(project/'build/preview/frame.png');source.write_text(original+'\nthis is a deliberate syntax error;\n')
        value=capture('failed');assert value['status']=='failed' and 'error:' in value['error']
        assert digest(project/'build/preview/frame.png')==first_hash
        assert 'STALE' in (project/'build/preview/index.html').read_text()
        source.write_text(original);value=capture('fixed');assert value['status']=='ready'
        assert not next(node for node in value['layout']['nodes'] if node['id']==13)['clipped']
        assert digest(output/'first/frame.png')==digest(output/'fixed/frame.png')
        # Watch is the public CLI, not a mocked filesystem notifier. A save
        # changes source code; the next published frame/package must follow it.
        log=(output/'watch.log').open('w')
        process=subprocess.Popen([sys.executable,str(ROOT/'sdk/tools/cli.py'),'--project',str(project),
            'preview','--firmware',str(args.firmware.resolve()),'--qemu',str(qemu),
            '--scenario','tests/preview.json'],stdout=log,stderr=subprocess.STDOUT)
        def wait_source(wanted):
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                assert process.poll() is None,'preview watcher exited'
                try:state=json.loads((project/'build/preview/status.json').read_text())
                except (ValueError,OSError):state={}
                if state.get('status')=='ready' and state.get('source_sha256')==wanted:return state
                time.sleep(.1)
            raise AssertionError('watcher did not publish the saved source within 120 seconds')
        try:
            wait_source(source_state(project));source.write_text(original.replace('"Edit expression"','"Expression editor"'))
            value=wait_source(source_state(project));assert value['package_sha256']!=cases[-1]['package']
            shutil.copytree(project/'build/preview',output/'watched',dirs_exist_ok=True,ignore=shutil.ignore_patterns('.lock'))
        finally:
            process.terminate();process.wait(timeout=30);log.close()
        # Source-owned action handlers are byte-identical throughout the layout edit.
        assert source.read_text().split('  void activate(unsigned id) {')[1].split('public:')[0]==original.split('  void activate(unsigned id) {')[1].split('public:')[0]
        cases.append({'name':'watch-save','status':'ready','timings':value['timings']})
    write_json(output/'report.json',{'schema':1,'status':'passed','cases':cases,'physical':'not_tested',
        'firmware_sha256':digest(args.firmware),'qemu_sha256':digest(qemu),
        'sources':{p:digest(ROOT/p) for p in ('sdk/tools/preview.py','sdk/tools/runner.py','sdk/tools/build.py','sdk/tools/cli.py','vm/test-sdk-preview.py')}})


if __name__=='__main__':main()
