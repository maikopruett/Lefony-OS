#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Enter the pinned RAM recovery loader from native Lefony or real 6ULL ROM.

Caller must verify asset hashes before entry. Never edits NAND, forces ROM
straps, retries a handoff or substitutes software SDP for immutable ROM.
"""
from pathlib import Path
import hashlib
import struct
import time
from prime_dual_boot_contract import require
from prime_hp_raw_restore import PrimeSDP,RAW_BLOCK
from prime_phase6_transport import Phase6SDP
from prime_g2_uboot_recovery import ram_capsule
import prime_g2_usb_diag as usb


def enter(binary,imx,workspace,*,event=lambda value:None):
    import hid
    binary,imx=Path(binary),Path(imx)
    found=hid.enumerate(0xcafe,0x5053)
    if found:
        d=Phase6SDP()
        try:d.verify_protocol()
        finally:d.close()
        return
    image=imx.read_bytes();code=binary.read_bytes()
    ivt=struct.unpack_from('<8I',image)
    require((ivt[0],ivt[1],ivt[5])==(0x402000d1,0x87800000,0x877ff400),'unsupported recovery IVT')
    require(image[ivt[1]-ivt[5]:ivt[1]-ivt[5]+len(code)]==code,'recovery binary/IMX mismatch')
    rom=[d for d in hid.enumerate(0x15a2,0x0080) if d['usage_page']==0xff00 and d['usage']==1]
    if rom:
        require(len(rom)==1,'connect exactly one 6ULL ROM device')
        d=PrimeSDP.__new__(PrimeSDP);d.device=hid.device();d.device.open_path(rom[0]['path'])
        offset=ivt[3]-ivt[5];size=int.from_bytes(image[offset+1:offset+3],'big')
        dcd=image[offset:offset+size]
        require(len(dcd)==488 and dcd[0]==0xd2,'unsupported recovery DCD')
        try:
            event({'state':'ram-dcd-pending'})
            d._command(0x0a0a,0x00910000,dcd);require(d._ack(4,64)==0x128a8a12,'ROM DCD rejected')
            d._command(0x0c0c,0);require(d._ack(4,64)==0x900dd009,'ROM skip-DCD rejected')
            d._command(0x0404,ivt[5],image)
            readback=hashlib.sha256()
            for at in range(0,len(image),RAW_BLOCK):
                readback.update(d.read(ivt[5]+at,min(RAW_BLOCK,len(image)-at)))
            require(readback.digest()==hashlib.sha256(image).digest(),'ROM RAM readback mismatch')
            # The pinned Phase 6 RAM image enters recovery unconditionally.
            # No retained SNVS write is needed or inferred from a ROM ACK.
            event({'state':'ram-handoff-pending'})
            d._command(0x0b0b,ivt[5])
        finally:d.close()
    else:
        with usb.LibUSB() as d:
            d.bulk_upload=None
            require(usb.development_capabilities(d)['flags']&8,'native RAM recovery is unavailable; enter ROM recovery')
            wrapper=Path(workspace)/'recovery.zImage';wrapper.write_bytes(ram_capsule(code))
            staged=usb.stage_capsule(d,wrapper);crc=staged['crc32']
            event({'state':'ram-handoff-pending'})
            d.write(0x5d,value=crc&65535,index=crc>>16)
    end=time.monotonic()+45
    while time.monotonic()<end:
        if hid.enumerate(0xcafe,0x5053):
            d=Phase6SDP()
            try:d.verify_protocol()
            finally:d.close()
            event({'state':'ram-recovery-ready'});return
        time.sleep(.25)
    raise TimeoutError('RAM recovery did not reconnect; handoff was not retried')
