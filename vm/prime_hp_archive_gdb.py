# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify logical file bytes using original V15751 APIs in private QEMU only.

Set ARCHIVE and EXPECTED_END in the GDB Python context before exec(). The
independent reader is HP's ARM filesystem, not the host YAFFS decoder.
"""
import gdb
import hashlib
import json
from pathlib import Path


def verify_archive():
    connection = gdb.execute('info connections', to_string=True)
    if '/tmp/hp-handoff-' not in connection:
        raise gdb.GdbError('private emulator socket required')
    inferior = gdb.selected_inferior()
    def word(address):
        return int.from_bytes(inferior.read_memory(address, 4), 'little')
    def check(value, message):
        if not value:
            raise gdb.GdbError(message + '; errno=' + str(word(0x807bdef0)))
    apis = {'allocate': 0x802b115b, 'open': 0x8039c6bd, 'read': 0x8039c977, 'close': 0x8039c6d3}
    def call(name, *args):
        signature = ','.join('unsigned int' for _ in args)
        return int(gdb.parse_and_eval('((int (*)(%s))%#x)(%s)' %
                   (signature, apis[name], ','.join(str(x) for x in args))))
    gdb.execute('thbreak *0x80336620')
    # A modeled Down press wakes the ordinary UI without editing files.
    inferior.write_memory(0x020b8008, (0x8405).to_bytes(2, 'little'))
    gdb.execute('continue')
    inferior.write_memory(0x020b8008, (0x0405).to_bytes(2, 'little'))
    check(int(gdb.parse_and_eval('$cpsr')) & 0x1f == 0x1f, 'SYS application context required')
    check(tuple(word(0x807bdef8 + o) for o in (0x14, 0x18, 0xf4, 0xf8)) ==
          (392, EXPECTED_END, 392, EXPECTED_END), 'filesystem bounds mismatch')
    report = json.loads((Path(ARCHIVE) / 'archive.json').read_text())
    objects = {o['id']: o for o in report['objects']}
    def path(obj):
        if obj == 1: return b'/usr'
        if obj == 2: return b'/usr/lost+found'
        item = objects[obj]
        return path(item['parent']) + b'/' + bytes.fromhex(item['name_hex'])
    buffer = call('allocate', 65536 + 4096) & 0xffffffff
    check(buffer != 0, 'allocation failed')
    verified = []
    for item in objects.values():
        if item['kind'] != 1: continue
        name = path(item['id'])
        check(len(name) < 4096, 'path too long')
        inferior.write_memory(buffer, name + b'\0')
        fd = call('open', buffer, 0, 0)
        check(fd >= 0, 'open failed: ' + repr(name))
        digest = hashlib.sha256()
        for at in range(0, item['size'], 65536):
            amount = min(65536, item['size'] - at)
            check(call('read', fd, buffer + 4096, amount) == amount, 'short read: ' + repr(name))
            digest.update(bytes(inferior.read_memory(buffer + 4096, amount)))
        check(call('read', fd, buffer + 4096, 1) == 0, 'missing EOF: ' + repr(name))
        check(call('close', fd) == 0, 'close failed')
        check(digest.hexdigest() == item['sha256'], 'file hash mismatch: ' + repr(name))
        verified.append(item['id'])
    gdb.write('phase5-logical: ' + json.dumps({'result': 'PASS', 'files': len(verified),
              'archive_sha256': report['archive_sha256'], 'bytes': report['total_file_bytes'],
              'filesystem_end': EXPECTED_END}) + '\n')
    gdb.flush()


verify_archive()
