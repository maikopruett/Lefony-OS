#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage both dual boot streams and redirected FCBs in a disposable fixture.

The per-block transition plan is emitted for fault tests. This is NOT an
installation tool: logical data migration and device qualification are separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from analyze_hp_prime_compatibility import private_output,require
from prime_dual_boot_contract import capacity,sha
from prime_nand_image import decode_fcb,encode_fcb,checksum,fcb_layout
from prime_gpmi_bch import Layout
from prime_bch_native import NativeBCH


def build(a):
    out=private_output(a.output);out.mkdir(parents=True,exist_ok=False)
    target=out/'nand.raw';shutil.copyfile(a.source,target)
    stream=bytes(1024)+a.uboot.read_bytes()
    require(stream[0x400:0x404]==bytes.fromhex('d1002040'),'expected paired NAND IVT')
    pages=(len(stream)+2047)//2048
    stream=stream.ljust(pages*2048,b'\xff')
    plan=[]
    # HP's FCB preserves the displaced payload byte in metadata[34]. The
    # physical ROM consumes that field even though ordinary Lefony uses [0].
    with a.source.open('rb') as source:
        fcb,_=decode_fcb(source.read(2112))
    geometry=fcb_layout(fcb)
    expected=Layout(0x03241080,0x08401080,marker_metadata_index=34)
    require(geometry.chunks==expected.chunks and geometry.page_bytes==expected.page_bytes and
            geometry.marker_metadata_index==34,'unsupported stock ROM marker layout')
    with target.open('r+b') as f,NativeBCH() as native:
        for name in ('boot_primary','boot_secondary'):
            blocks=capacity(name,len(stream),set())
            offset=0
            for block in blocks:
                f.seek(block*64*2112);before=f.read(64*2112)
                require(before==b'\xff'*(64*2112),'recovery staging area is not verified erased')
                raw=bytearray(b'\xff'*(64*2112))
                for page in range(64):
                    if offset>=len(stream):break
                    data,aux=geometry.swap_marker(stream[offset:offset+2048],b'\xff'*36)
                    raw[page*2112:(page+1)*2112]=geometry.encode(data,aux,native)
                    offset+=2048
                f.seek(block*64*2112);f.write(raw)
                (out/f'{block}.raw').write_bytes(raw)
                plan.append({'block':block,'phase':'stage-recovery','before':sha(before).hex(),'after':sha(raw).hex()})
        # Lowest-priority copies first. Before every copy has been redirected,
        # no HP filesystem or upper-region migration is permitted.
        for block in (3,2,1,0):
            f.seek(block*64*2112);before=f.read(64*2112)
            fcb,_=decode_fcb(before[:2112]);fcb=bytearray(fcb)
            struct.pack_into('<4I',fcb,0x68,240*64,248*64,pages,pages)
            struct.pack_into('<I',fcb,0,checksum(fcb))
            raw=encode_fcb(fcb,covered_metadata=before[:32])+b'\xff'*(63*2112)
            f.seek(block*64*2112);f.write(raw)
            (out/f'{block}.raw').write_bytes(raw)
            plan.append({'block':block,'phase':'redirect-rom','before':sha(before).hex(),'after':sha(raw).hex()})
    with target.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    (out/'transition.json').write_text(json.dumps({'device_flash_input':False,'pages':pages,
        'bootstream_sha256':sha(stream).hex(),'fixture_sha256':digest,'changes':plan},indent=2)+'\n')
    print('Prepared ROM fixture with both streams and four FCB copies',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','uboot','output'):p.add_argument('--'+name,type=Path,required=True)
    build(p.parse_args())
