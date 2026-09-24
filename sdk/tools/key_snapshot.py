# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded partial developer-registry backups; never import their key trust."""
import hashlib
import struct

CHUNK = 512
MAX_SOURCE = 65536
MAX_BYTES = 32 + MAX_SOURCE//CHUNK*16 + MAX_SOURCE


def inspect(raw):
    if not isinstance(raw, (bytes, bytearray)) or not 32 <= len(raw) <= MAX_BYTES or raw[:8] != b'LFKREAD1':
        raise ValueError('Invalid partial registry backup')
    schema, source, chunk, count, reserved, reserved2 = struct.unpack_from('<6I', raw, 8)
    if schema != 1 or not 0 < source <= MAX_SOURCE or chunk != CHUNK or count != (source+CHUNK-1)//CHUNK or reserved or reserved2:
        raise ValueError('Unsupported partial registry backup header')
    cursor, readable, missing = 32, 0, 0
    for index in range(count):
        if cursor+16 > len(raw):
            raise ValueError('Truncated partial registry record')
        offset, size, state, reserved = struct.unpack_from('<4I', raw, cursor); cursor += 16
        if offset != index*CHUNK or size != min(CHUNK, source-offset) or state not in (0,1) or reserved:
            raise ValueError('Invalid partial registry record')
        if state:
            missing += 1
        else:
            if cursor+size > len(raw):
                raise ValueError('Truncated readable registry region')
            cursor += size; readable += size
    if cursor != len(raw) or not missing:
        raise ValueError('Partial registry backup must mark unreadable regions and have no trailing bytes')
    return {'original_bytes': source, 'bytes': len(raw), 'readable_bytes': readable,
            'unreadable_chunks': missing, 'sha256': hashlib.sha256(raw).hexdigest()}
