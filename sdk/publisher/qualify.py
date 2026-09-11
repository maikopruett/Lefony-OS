#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the exact isolated validator image before it may consume public jobs."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from source import encode
from lfapp import unpack
from worker import sandbox


def qualify(image):
    base={'format':'lefony-source-0','manifest':{'abi':1,'id':'qualification','name':'Qualification','version':'0.1.0','license':'CC-BY-NC-SA-4.0'}}
    source=lambda code:encode({**base,'files':{'src/main.cpp':'#include <lefony/app.h>\nextern "C" void lefony_event(Lefony::Event,uint32_t,uint32_t){'+code+'}\n'}})
    cases=[('return',source('Lefony::fill({0,0,320,240,Lefony::Green});'),True),
           ('compile-error',source('this is not C++;'),False),
           ('hang',source('while(true) asm volatile("nop");'),False),
           ('privileged-memory',source('(void)*reinterpret_cast<volatile unsigned *>(0x82000000);'),False),
           ('malformed-source',b'{"format":"invalid"}',False)]
    results=[]
    for name,data,expected in cases:
        result=sandbox(image,data)
        if result.get('source_hash')!=hashlib.sha256(data).hexdigest() or result.get('passed') is not expected:
            raise ValueError(f'Validator qualification failed: {name}')
        evidence=json.loads(result['report']) if expected else None
        if expected and (evidence.get('reproducible') is not True or evidence.get('os_responsive') is not True or len(evidence.get('callbacks',[]))!=9):
            raise ValueError('Incomplete successful-run qualification evidence')
        if expected:
            package=base64.b64decode(result['package'],validate=True)
            metadata,_=unpack(package)
            if metadata!=base['manifest'] or evidence.get('package_sha256')!=hashlib.sha256(package).hexdigest() or any(row.get('result')!=1 for row in evidence['callbacks']):
                raise ValueError('Invalid qualification artifact or callback result')
        results.append({'case':name,'expected_pass':expected,'passed':True,'evidence':evidence})
        print(f'PASS: {name}',flush=True)
    return {'schema':1,'image':image,'qualified':True,'cases':results}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    report=qualify(args.image)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
