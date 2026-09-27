#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Verified RAM-only U-Boot handoff using bootm's normal ARM cleanup path.

Caller owns the reviewed recovery assets and physical authorization. This
module never opens a device, writes NAND, retries, or claims the new boot ran.
"""
import hashlib
import struct
import zlib
from prime_dual_boot_contract import require
from prime_hp_raw_restore import RAW_BLOCK,SCRIPT,legacy_script


def kernel_image(binary):
    require(0x100<=len(binary)<=0xff000 and struct.unpack_from('<I',binary)[0]&0xff000000==0xea000000,
            'bounded Prime ARM recovery image required')
    header=struct.pack('>7I4B32s',0x27051956,0,0,len(binary),0x87800000,0x87800000,
                       zlib.crc32(binary),5,2,2,0,b'RAM recovery diagnostic')
    return header[:4]+struct.pack('>I',zlib.crc32(header))+header[8:]+binary


def handoff(device,binary,dtb):
    require(len(dtb)>=40 and len(dtb)<=65536 and struct.unpack_from('>2I',dtb)==(0xd00dfeed,len(dtb)),
            'complete bounded device tree required')
    image=kernel_image(binary)
    for address,data in ((0x84000000,image),(0x83000000,dtb)):
        device._command(0x0404,address,data)
        readback=hashlib.sha256()
        for at in range(0,len(data),RAW_BLOCK):
            readback.update(device.read(address+at,min(RAW_BLOCK,len(data)-at)))
        require(readback.digest()==hashlib.sha256(data).digest(),'RAM handoff readback differs')
    device._command(0x0404,SCRIPT,legacy_script('bootm 84000000 - 83000000'))
    device._command(0x0b0b,SCRIPT)
