# SPDX-License-Identifier: GPL-3.0-or-later
"""GDB-only, exact V15751 filesystem experiments in a disposable QEMU instance.

Called by the private-fixture harness after its verified RAM loader. Actual HP
YAFFS, NAND drivers, DMA and BCH execute; no storage callback is intercepted.
The graphics breakpoint supplies an ordinary SYS-mode application context:
calling blocking filesystem APIs from an interrupted idle/SVC context deadlocks.
"""
import gdb
import json
import os

DEV = 0x807bdef8
APIS = {'allocate':0x802b115b, 'open':0x8039c6bd, 'write':0x8039cbd9,
        'read':0x8039c977, 'close':0x8039c6d3, 'unlink':0x8039cea7,
        'sync':0x8039d6c1, 'free':0x8039d8a5, 'format':0x8039d7ef,
        'deinit':0x80471cc9, 'mount_common':0x8039d51b, 'busy':0x8039d6d1,
        'isgood':0x802b19eb, 'block_info':0x8046d4dd, 'reclaim_block':0x8046f343}
CHUNK = 65536
inferior = gdb.selected_inferior()


def memory(address, length):
    return bytes(inferior.read_memory(address, length))


def word(address):
    return int.from_bytes(memory(address,4),'little')


def call(name,*args):
    result = 'long long' if name == 'free' else 'int'
    signature = ','.join('unsigned int' for _ in args) or 'void'
    expression = '((%s (*)(%s))%#x)(%s)' % (result, signature, APIS[name], ','.join(str(x) for x in args))
    return int(gdb.parse_and_eval(expression))


def emit(event, **values):
    values['ecc_programs'] = word(0x01806170)
    if 'P4_LOG' in globals():
        values['nand_log_bytes'] = os.stat(P4_LOG).st_size
    gdb.write('phase4-storage: '+json.dumps({'event':event,**values})+'\n')
    gdb.flush()


def check(condition,message):
    if not condition:
        raise gdb.GdbError(message+'; HP errno='+str(word(0x807bdef0)))


def main():
    mode = int(gdb.parse_and_eval('$p4_mode'))
    limit = int(gdb.parse_and_eval('$p4_mib')) * 1024 * 1024
    fault = int(gdb.parse_and_eval('$p4_fault'))
    # These tests deliberately own a private emulator, never a hardware target.
    check('/tmp/hp-handoff-' in gdb.execute('info connections',to_string=True), 'expected private QEMU socket')
    gdb.execute('thbreak *0x80336620')
    gdb.execute('continue')
    check(int(gdb.parse_and_eval('$cpsr')) & 0x1f == 0x1f, 'application SYS context required')
    check((word(DEV+0x14),word(DEV+0x18),word(DEV+0xf4),word(DEV+0xf8)) == (392,2047,392,2047), 'bounds mismatch')
    buf = call('allocate',CHUNK+1024) & 0xffffffff
    check(buf != 0,'allocation failed')
    path, root, payload = buf, buf+256, buf+1024
    inferior.write_memory(path,b'/usr/phase4-stress.bin\0')
    inferior.write_memory(root,b'/usr\0')
    pattern = bytes((i*13+17)&255 for i in range(CHUNK))
    inferior.write_memory(payload,pattern)
    emit('initial',free=call('free',root),checkpoint=word(DEV+0xec),busy=call('busy',DEV))
    if fault >= 0:
        check(fault==400,'only the declared disposable fault block is supported')
        if mode==0:
            check(call('isgood',DEV,fault)==1,'fault block already retired')
            inferior.write_memory(0x01806128,fault.to_bytes(4,'little'))
            emit('fault-injected',block=fault)
        else:
            check(call('isgood',DEV,fault)==0,'retirement missing after cold boot')
            emit('retirement-retained',block=fault)

    def verify(size):
        fd=call('open',path,0,0)
        check(fd>=0,'read open failed')
        for at in range(0,size,CHUNK):
            amount=min(CHUNK,size-at)
            check(call('read',fd,payload,amount)==amount,'short read')
            check(memory(payload,amount)==pattern[:amount],'content mismatch')
        check(call('read',fd,payload,1)==0,'missing EOF')
        check(call('close',fd)==0,'read close failed')
        emit('verified',bytes=size)

    if mode in (0,2):
        fd=call('open',path,0x242,0o600) # verified Linux-style O_CREAT|O_TRUNC|O_RDWR
        check(fd>=0,'create failed')
        total=0
        while total<limit:
            result=call('write',fd,payload,CHUNK)
            if result<0:
                check(mode==2,'unexpected write failure')
                check(call('free',root)<=131072,'write failure before capacity exhaustion')
                emit('full',bytes=total,errno=word(0x807bdef0)); break
            check(0<result<=CHUNK,'invalid write length')
            total+=result
            if total % (1024*1024)==0: emit('written',bytes=total)
            if result<CHUNK:
                check(mode==2,'short write')
                check(call('write',fd,payload,CHUNK)<0,'short write was not capacity exhaustion')
                check(call('free',root)<=131072,'short write before capacity exhaustion')
                emit('full',bytes=total,errno=word(0x807bdef0)); break
        if mode==2:
            check(total<limit,'did not reach capacity')
            # HP's write wrapper can replace ENOSPC with EINVAL. Establish
            # exhaustion from free space and absence of backend/model faults.
            check(word(0x01806164)==word(0x01806168)==word(0x0180616c)==0,
                  'NAND/model failure is not filesystem capacity exhaustion')
        check(call('close',fd)==0,'write close failed')
        if fault>=0:
            # HP defers retirement until collection. The injected fault is on
            # the first page of a fresh block, so no live chunks need copying.
            # Exercise its real empty-block reclamation, never a NAND shim.
            bi=call('block_info',DEV,fault)&0xffffffff
            flags=word(bi)
            check((flags>>10)&0x3ff==0 and (flags>>24)&1==1,
                  'failed block is not empty and awaiting retirement')
            call('reclaim_block',DEV,fault)
            check(call('isgood',DEV,fault)==0,'failed block was not retired')
            emit('block-retired',block=fault)
        verify(total)
        check(call('sync',root)==0,'sync failed')
        emit('checkpoint-saved',value=word(DEV+0xec),bytes=total)
        check(word(DEV+0xec)==1,'checkpoint not saved')
        if mode==0:
            check(call('busy',DEV)==0,'open handles before remount')
            call('deinit',DEV)
            check(call('mount_common',0,root,0,0)==0,'checkpoint remount failed')
            emit('checkpoint-restored',value=word(DEV+0xec))
            check(word(DEV+0xec)==1,'checkpoint not restored')
            verify(total)
            call('deinit',DEV)
            check(call('mount_common',0,root,0,1)==0,'full scan remount failed')
            emit('full-scan',checkpoint=word(DEV+0xec))
            check(word(DEV+0xec)==0,'full scan unexpectedly used checkpoint')
            verify(total)
            check(call('sync',root)==0,'final sync failed')
    elif mode==1:
        verify(limit)
    else:
        raise gdb.GdbError('unknown experiment mode')
    if mode in (1,2):
        check(call('unlink',path)==0,'unlink failed')
        check(call('open',path,0,0)<0,'deleted file remains')
        emit('deleted',free=call('free',root))
        if mode==2:
            # After capacity exhaustion, writing substantially more than the
            # reserved blocks requires reclamation of previously used blocks.
            fd=call('open',path,0x242,0o600)
            check(fd>=0,'recreate failed')
            inferior.write_memory(payload,pattern)
            for _ in range(16*1024*1024//CHUNK):
                check(call('write',fd,payload,CHUNK)==CHUNK,'reclaimed write failed')
            check(call('close',fd)==0,'reclaimed close failed')
            verify(16*1024*1024)
            emit('reclaimed',bytes=16*1024*1024,free=call('free',root))
        check(call('format',root,1,1,1)==0,'format failed')
        emit('formatted',free=call('free',root))
        check(call('open',path,0,0)<0,'file survived format')
    emit('complete',mode=mode)


main()
