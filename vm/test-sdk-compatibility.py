#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run preserved ABI 1 bytes without recompiling them. No private firmware."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from lfapp import unpack
from runner import exercise
from replay import Controls


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--firmware',type=Path,default=ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-compatibility')
    args=parser.parse_args()
    corpus=json.loads((ROOT/'sdk/contracts/compatibility.json').read_text())
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    results=[]
    for entry in corpus['packages']:
        path=args.corpus/entry['file']
        assert digest(path)==entry['sha256'],'corpus package changed'
        metadata,_=unpack(path.read_bytes())
        assert metadata['abi']==entry['abi'] and metadata['id']==entry['id']
        def controls(channel):
            device=Controls(channel,output)
            try:
                device.run({'steps':[
                    {'capture':entry['id']+'-before'},
                    {'key':'ok' if entry['id']=='counter' else 'right'},
                    {'capture':entry['id']+'-after'},
                    {'different':[entry['id']+'-before',entry['id']+'-after']},
                    {'key':'back'}]},[])
            finally:device.close()
        result=exercise(path.resolve(),ROOT/'build/qemu-prime-g2/qemu-system-arm',
                        args.firmware.resolve(),controls=controls)
        assert result['result']==1 and result['os_responsive']
        assert digest(path)==entry['sha256']
        results.append(result)
        print('PASS: unchanged ABI 1 package',entry['id'],entry['sha256'],flush=True)
    write_json(output/'report.json',{'schema':1,'validation':'developer-local','cases':results,'status':'passed'})


if __name__=='__main__':main()
