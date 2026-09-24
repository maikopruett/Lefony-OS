#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Browser TypeScript file exchange against synthetic ARM/QEMU USB only."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from runner import exercise
from workspace import opened
from replay import Controls, control_session
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--project',type=Path,required=True)
parser.add_argument('--website',type=Path,required=True)
args=parser.parse_args()
project=args.project.resolve();website=args.website.resolve()
package=project/'build/doom-proof-0.2.2.lfapp'
results=[]
def prepare(client):
    child=subprocess.Popen([str(website/'node_modules/.bin/tsx'),str(website/'scripts/test-bundled-data-emulator.ts')],
                           stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        for line in child.stdout:
            request=json.loads(line)
            if request.get('done'):results.append(request);break
            try:
                if 'read' in request:
                    assert request['read'] in (0x70,0x72) and 0<=request['length']<=512
                    response={'data':client.read(request['read'],request['length'],request['argument']).hex()}
                else:
                    assert request['write'] in (0x71,0x72,0x73,0x74,0x75)
                    payload=bytes.fromhex(request['data']);assert len(payload)<=512
                    client.write(request['write'],payload,request['argument']);response={}
            except Exception as e:response={'error':str(e)}
            child.stdin.write(json.dumps(response)+'\n');child.stdin.flush()
        assert child.wait(timeout=15)==0 and results,'Browser exchange failed'
    finally:
        if child.poll() is None:child.kill();child.wait()
def controls(channel):
    with control_session(Controls(channel,project/'build/browser-test')) as normal:
        normal.key('home')
with opened(project,'browser-bundle-files') as (media,_):
    result=exercise(package,ROOT/'build/qemu-prime-g2/qemu-system-arm',ROOT/'dist/lefony-os-prime-g2-vm-native.elf',
                    workspace=media,prepare_workspace=prepare,controls=controls)
assert result['os_responsive']
output={'status':'passed','validation':'synthetic ARM USB','cases':['create','exact readback','idempotence','mismatch preserves existing','pre-commit cancellation and retry','lost commit acknowledgement reconciliation'],'result':results}
(project/'build/browser-bundle-report.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
