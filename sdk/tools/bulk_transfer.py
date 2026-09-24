# SPDX-License-Identifier: GPL-3.0-or-later
"""LFB1 RAM staging. No commit, no replay after an ambiguous write.

Negotiation is read-only and uses standard USB descriptors so old devices are
never probed with an unsupported vendor request. Target authorization belongs
in the transport: app-only transports cannot upload firmware.
"""
import struct
import time

MAGIC = 0x3142464c
CAPACITY = 32 * 1024 * 1024


def available(descriptor):
    return (len(descriptor) == 32 and descriptor[:4] == bytes((9,2,32,0)) and
            descriptor[9:18] == bytes((9,4,0,0,2,255,77,71,0)) and
            descriptor[18:25] == bytes((7,5,1,2,0,2,0)) and
            descriptor[25:32] == bytes((7,5,129,2,0,2,0)))


def status(read):
    raw = read(0x58, length=64)
    if len(raw) != 64:
        raise RuntimeError('Short bulk status; no write was retried')
    v = struct.unpack('<16I', raw)
    if (v[:2] != (MAGIC,1) or v[2] > 5 or v[4] > 5 or v[5] > CAPACITY or
            v[6] > v[5] or v[7] > v[5] or v[9:13] != (CAPACITY,262144,1,1) or
            v[13] != 1 or any(v[14:])):
        raise RuntimeError('Unsupported bulk transfer status')
    return v


def upload(read, write, send, target, data, *, sequence=0,
           progress=lambda done,total:None, cancelled=lambda:False):
    before = status(read)
    if before[2] in (1,2,3) or not 0 < len(data) <= CAPACITY:
        raise RuntimeError('RAM staging is busy or payload exceeds its limit')
    if cancelled():
        raise RuntimeError('Transfer cancelled before RAM staging')
    token = before[3] + 1
    # From here failure is fatal: never silently retry over EP0.
    try:
        write(0x59, struct.pack('<6I', MAGIC,1,target,len(data),sequence,0))
        for offset in range(0,len(data),262144):
            if cancelled():
                raise RuntimeError('RAM transfer cancelled before installation')
            block = data[offset:offset+262144]
            send(block)
            progress(offset+len(block),len(data))
        # Physical NAND/file installation can exceed ten minutes for a 29 MB
        # WAD. Allow continuing progress, with both a stall and absolute bound.
        now = time.monotonic()
        deadline = now+(1800 if target == 3 else 600)
        progress_deadline = now+120
        last_applied = 0
        applied = False
        while time.monotonic()<deadline:
            if cancelled():
                raise RuntimeError('Transfer cancelled before commit')
            state = status(read)
            if state[3:6] != (token,target,len(data)) or state[2] in (0,5):
                raise RuntimeError(f'Bulk transfer failed ({state[8]}); no write was retried')
            if target == 3:
                if state[7] > last_applied:
                    last_applied = state[7]
                    progress_deadline = time.monotonic()+120
                elif time.monotonic() >= progress_deadline:
                    raise RuntimeError('Bulk installation stalled; inspect device status')
            if state[2]==2 and not applied:
                write(0x5a, value=token&65535, index=token>>16)
                applied=True
            elif state[2]==4:
                if state[6:8] != (len(data),len(data)):
                    raise RuntimeError('Incomplete RAM transfer/application')
                return True
            time.sleep(.01)
        raise RuntimeError('Bulk transfer timed out; inspect device status')
    except BaseException:
        try:
            write(0x5b, value=token&65535, index=token>>16)
        except Exception:
            pass
        raise


def try_upload(transport,target,data,**kwargs):
    method=getattr(transport,'bulk_upload',None)
    return bool(method and method(target,data,**kwargs))


def download(read,write,receive,target,length,*,sequence=0,
             progress=lambda done,total:None,cancelled=lambda:False):
    before=status(read)
    if before[2] in (1,2,3) or not 0<length<=CAPACITY:
        raise RuntimeError('RAM staging is busy or response exceeds limit')
    token=before[3]+1
    try:
        write(0x59,struct.pack('<6I',MAGIC,1,target,length,sequence,0))
        deadline=time.monotonic()+600
        while True:
            s=status(read)
            if s[3:6]!=(token,target,length) or s[2] not in (1,3):
                raise RuntimeError('Bulk export session changed or failed')
            if s[2]==1:break
            if cancelled() or time.monotonic()>=deadline:raise RuntimeError('Bulk export cancelled/timed out')
            time.sleep(.01)
        result=bytearray()
        while len(result)<length:
            if cancelled():raise RuntimeError('Bulk read cancelled')
            size=min(262144,length-len(result));block=receive(size)
            if len(block)!=size:raise RuntimeError('Short bulk read; no retry')
            result.extend(block);progress(len(result),length)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            s=status(read)
            if s[3:6]!=(token,target,length) or s[2] not in (1,4):raise RuntimeError('Bulk read failed')
            if s[2]==4 and s[6:8]==(length,length):return bytes(result)
            time.sleep(.01)
        raise RuntimeError('Bulk read completion timed out')
    except BaseException:
        try:write(0x5b,value=token&65535,index=token>>16)
        except Exception:pass
        raise


def try_download(transport,target,length,**kwargs):
    method=getattr(transport,'bulk_download',None)
    return method(target,length,**kwargs) if method else None
