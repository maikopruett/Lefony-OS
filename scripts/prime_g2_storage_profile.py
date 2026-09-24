#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read cumulative NAND timings. Never writes, resets, or benchmarks raw blocks."""
import argparse
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from usb_files import LibUSB

NAMES=('read','program','erase','usable','raw_read','program_wait','erase_wait','other_ready','command_dma')
SIZE=392

def decode(data):
    if len(data)!=SIZE:raise ValueError('Incomplete storage profile')
    h=struct.unpack_from('<8I',data)
    if h[:5]!=(0x3150464c,1,SIZE,3000000,len(NAMES)) or h[6] not in (0,1) or h[7]:
        raise ValueError('Unsupported storage profile')
    counters={}
    for i,name in enumerate(NAMES):
        calls,bytes_,ticks,minimum,maximum,failures,reserved=struct.unpack_from('<3Q4I',data,32+40*i)
        if reserved or failures>calls or minimum>maximum:raise ValueError('Invalid storage counter')
        counters[name]={'calls':calls,'bytes':bytes_,'ticks':ticks,'minimum_ticks':minimum,'maximum_ticks':maximum,'failures':failures}
    return {'schema':1,'tick_hz':h[3],'now_ticks':h[5],'physical':bool(h[6]),'counters':counters}

def difference(before,after):
    if before['physical']!=after['physical'] or before['tick_hz']!=after['tick_hz']:
        raise ValueError('Different profile targets')
    result={}
    for name in NAMES:
        delta={k:after['counters'][name][k]-before['counters'][name][k] for k in ('calls','bytes','ticks','failures')}
        if any(n<0 for n in delta.values()):raise ValueError('Counters reset; repeat measurement with one boot')
        seconds=delta['ticks']/after['tick_hz']
        result[name]={**delta,'seconds':seconds,'MB_per_second':delta['bytes']/seconds/1e6 if seconds and not delta['failures'] else None}
    return {'physical':after['physical'],'nested_categories':True,'counters':result}

class ProfileUSB(LibUSB):
    READ_REQUESTS=(0x56,)
    WRITE_REQUESTS=()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path)
    p.add_argument('--before',type=Path,help='subtract an earlier snapshot from the same boot')
    a=p.parse_args()
    with ProfileUSB() as usb:result=decode(usb.read(0x56,length=SIZE))
    if a.before:result={'snapshot':result,'difference':difference(json.loads(a.before.read_text()),result)}
    text=json.dumps(result,indent=2)+'\n'
    if a.output:a.output.write_text(text)
    else:print(text,end='')

if __name__=='__main__':main()
