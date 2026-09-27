#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a disposable Phase 5 NAND-boot-menu fixture, not a migration image.

Uses the Phase 4 recreated filesystem; this does not claim logical HP restore
or a ROM control transition. Input images and all generated NAND remain private.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import zlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prime_dual_boot_contract import load_layout,capacity,sign_descriptor,verify_descriptor,record,sha
from analyze_hp_prime_compatibility import private_output, require
from prime_gpmi_bch import Layout
from prime_bch_native import NativeBCH


def build(a):
    out=private_output(a.output);out.mkdir(parents=True,exist_ok=False)
    metadata=json.loads((a.fixture/'fixture.json').read_text())
    source=a.fixture/'confined-physical.raw'
    with source.open('rb') as f: require(hashlib.file_digest(f,'sha256').hexdigest()==metadata['fixture_sha256'],'fixture changed')
    doc,regions=load_layout()
    images={'hp_image':a.hp.read_bytes(),'lefony_image':a.lefony.read_bytes(),
            'lefony_dtb':a.dtb.read_bytes(),'rescue':a.lefony.read_bytes()}
    descriptor=sign_descriptor(images,1,a.private_key)
    verify_descriptor(descriptor,a.public_key,images)
    (out/'descriptor.bin').write_bytes(descriptor)
    target=out/'nand.raw';shutil.copyfile(source,target)
    ecc=Layout(0x030a0880,0x08400880)
    bad=set(metadata['preserved_bad_markers'])
    with target.open('r+b') as f, NativeBCH() as native:
        def program(page,payload):
            payload=payload.ljust(2048,b'\xff')
            data,aux=ecc.swap_marker(payload,b'\xff'*10)
            f.seek(page*2112);f.write(ecc.encode(data,aux,native))
        def clear(name):
            r=regions[name]
            for block in range(r.first,r.end):
                if block not in bad:
                    f.seek(block*64*2112);f.write(b'\xff'*(64*2112))
        for name in (*images,'lefony_apps','layout_primary','layout_secondary',
                     'preference_primary','preference_secondary'):
            clear(name)
        for name,payload in images.items():
            positions=capacity(name,len(payload),bad)
            offset=0
            for block in positions:
                for page in range(64):
                    if offset>=len(payload):break
                    program(block*64+page,payload[offset:offset+2048]);offset+=2048
        tx=sha(b'Phase 5 disposable boot fixture'+descriptor)
        for name in ('layout_primary','layout_secondary'):
            program(regions[name].first*64,record(1,'committed',tx,descriptor))
        preference=bytearray(64)
        struct.pack_into('<4s4I',preference,0,b'LFBP',1,5,1,a.priority)
        struct.pack_into('<I',preference,60,zlib.crc32(preference[:60]))
        for name in ('preference_primary','preference_secondary'):
            program(regions[name].first*64,bytes(preference))
    with target.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    (out/'fixture.json').write_text(json.dumps({'schema':1,'device_flash_input':False,
        'scope':'emulator NAND image-location test; ROM transition and logical migration not asserted',
        'sha256':digest,'source_sha256':metadata['fixture_sha256'],
        'descriptor_sha256':sha(descriptor).hex(),'priority':a.priority},indent=2)+'\n')
    print('Prepared private emulator fixture',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','hp','lefony','dtb','private-key','public-key','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--priority',type=int,choices=(0,1),default=0)
    build(p.parse_args())
