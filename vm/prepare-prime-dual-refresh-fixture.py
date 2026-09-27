#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a disposable signed update fixture from an intact dual-layout snapshot.

Preserves HP, apps and preferences. This file-copy builder is NOT a physical
update transaction: its write order and erased journals must never be flashed.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prime_dual_migration as m
from prime_dual_boot_contract import (load_layout, select_record, sign_descriptor,
    verify_descriptor, record, sha, require)
from prime_nand_image import encode_fcb, checksum


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'old-uboot', 'uboot', 'lefony', 'private-key', 'public-key', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args(); out = m.private_output(a.output)
    require(not out.exists(), 'output must be new')
    before_hash = m.file_hash(a.source)
    bad = m.factory_inventory(a.source)
    _, regions = load_layout()
    with m.NativeBCH() as native:
        m.verify_routes(a.source, a.old_uboot, bad, native)
        selected = select_record([m.payload(m.read_block(a.source, b)[:2112], native)
                                  for b in (256,257)])
        require(selected['state'] == 'committed', 'committed source required')
        old = verify_descriptor(selected['descriptor'], a.public_key)
        images = {name: m.read_image(a.source, name, size, bad, native)
                  for name, (size, _) in old['images'].items()}
        verify_descriptor(selected['descriptor'], a.public_key, images)
        images['lefony_image'] = images['rescue'] = a.lefony.read_bytes()
        # The old signed release is at byte 16 of the exact validated descriptor.
        release = struct.unpack_from('<I', selected['descriptor'], 16)[0] + 1
        require(release < 2**32, 'release overflow')
        descriptor = sign_descriptor(images, release, a.private_key)
        verify_descriptor(descriptor, a.public_key, images)
        stream = bytes(1024) + a.uboot.read_bytes()
        require(stream[1024:1028] == bytes.fromhex('d1002040'), 'expected NAND IMX')
        pages = (len(stream)+2047)//2048
        stream = stream.ljust(pages*2048, b'\xff')
        out.mkdir(parents=True)
        target = out/'nand.raw'; shutil.copyfile(a.source, target)
        tx = sha(before_hash + descriptor + sha(stream))
        with target.open('r+b') as f:
            def replace_region(name, data, codec):
                region = regions[name]
                if name in ('layout_primary','layout_secondary'):
                    require(region.first not in bad and len(data)==2048,'invalid layout slot')
                    positions = [region.first]
                else:
                    positions = m.capacity(name, len(data), bad)
                for block in range(region.first, region.end):
                    if block not in bad:
                        f.seek(block*m.RAW_BLOCK); f.write(m.ERASED)
                at = 0
                for block in positions:
                    for page in range(64):
                        if at >= len(data): break
                        payload, aux = codec.swap_marker(data[at:at+2048].ljust(2048,b'\xff'),
                                                        b'\xff'*(36 if codec is m.BOOT_ECC else 10))
                        f.seek((block*64+page)*2112); f.write(codec.encode(payload,aux,native))
                        at += 2048
            for name in ('boot_secondary','boot_primary'):
                replace_region(name, stream, m.BOOT_ECC)
            for block in (3,2,1,0):
                source = m.read_block(a.source,block)
                fcb, errors = m.decode_fcb(source[:2112]); require(not any(errors),'damaged FCB')
                fcb = bytearray(fcb)
                struct.pack_into('<4I',fcb,0x68,240*64,248*64,pages,pages)
                struct.pack_into('<I',fcb,0,checksum(fcb))
                f.seek(block*m.RAW_BLOCK)
                f.write(encode_fcb(fcb,covered_metadata=source[:32])+m.ERASED[2112:])
            for name in ('lefony_image','rescue'):
                replace_region(name,images[name],m.ECC)
            # Independent fixture identity, not a resumable on-device transaction.
            generation = selected['generation'] + 1
            for name in ('layout_primary','layout_secondary'):
                replace_region(name,record(generation,'committed',tx,descriptor),m.ECC)
            for block in (258,259):
                f.seek(block*m.RAW_BLOCK); f.write(m.ERASED)
        m.verify_routes(target,a.uboot,bad,native)
        for name,(size,_) in verify_descriptor(descriptor,a.public_key)['images'].items():
            require(m.read_image(target,name,size,bad,native)==images[name],'fixture image readback failed')
    require(m.file_hash(a.source)==before_hash,'source snapshot changed')
    allowed=set(range(4))|set(range(240,260))|set(range(2128,2208))|set(range(2216,2296))
    changes=[b for b in range(4096) if m.read_block(a.source,b)!=m.read_block(target,b)]
    require(set(changes)<=allowed,'fixture changed HP, apps or preferences')
    (out/'qualification.json').write_text(json.dumps({
        'device_flash_input':False,'purpose':'disposable signed dual refresh fixture',
        'source_sha256':before_hash.hex(),'sha256':m.file_hash(target).hex(),
        'release':release,'changed_blocks':changes,
        'uboot_sha256':m.file_hash(a.uboot).hex(),'lefony_sha256':m.file_hash(a.lefony).hex(),
        'scope':'all images/routes read back; HP/app/preference bytes preserved; no physical transaction'},
        indent=2)+'\n')
    print('Prepared private refresh fixture; never use as a physical flash input',flush=True)


if __name__ == '__main__': main()
