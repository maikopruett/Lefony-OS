# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic app-local resources. No hooks, downloads, or firmware services."""
import hashlib
import json
import io
from pathlib import Path
import re
import struct
import zlib
from lfapp import require
from source import RESERVED

MAGIC = b'LFRSRC1\0'
HEADER = struct.Struct('<8s6I')
ENTRY = struct.Struct('<24s10I')
MAX_BUNDLE = 524288
PILLOW = '12.3.0'


def prepare(project):
    project = Path(project)
    config = project / 'assets.json'
    if not config.exists():
        require(not config.is_symlink(), 'asset configuration symlink forbidden')
        return None, {'schema': 1, 'bytes': 0, 'inputs': {}, 'entries': []}
    require(not config.is_symlink() and config.is_file() and config.stat().st_size <= 65536, 'invalid assets.json')
    spec = json.loads(config.read_text(encoding='utf-8'))
    require(isinstance(spec, dict) and set(spec) == {'schema', 'resources'} and type(spec['schema']) is int and spec['schema'] == 1,
            'assets.json requires schema 1 and resources')
    records = spec['resources']
    require(isinstance(records, list) and 1 <= len(records) <= 32, 'expected 1–32 resources')
    identities = set()
    inputs = {'assets.json': hashlib.sha256(config.read_bytes()).hexdigest()}
    seen_paths = {}
    entries = []
    total_inputs = config.stat().st_size
    for record in records:
        require(isinstance(record, dict) and set(record) in ({'id', 'path', 'type'}, {'id', 'path', 'type', 'transparent'}), 'invalid asset record')
        ident, name, kind = record['id'], record['path'], record['type']
        require(isinstance(ident, str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,22}', ident) and ident not in identities, 'invalid/duplicate resource id')
        identities.add(ident)
        require(isinstance(name, str) and len(name) <= 120 and re.fullmatch(r'assets/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:png|rgb565|bin|txt|json)', name), 'invalid resource path')
        require(kind in ('blob', 'rgb565'), 'unsupported resource conversion')
        path = project
        for part in name.split('/'):
            require(not RESERVED.match(part), 'platform-reserved resource path')
            path = path / part
            require(not path.is_symlink(), 'asset symlinks forbidden')
            prefix = path.relative_to(project).as_posix()
            require(seen_paths.get(prefix.lower(), prefix) == prefix, 'case-colliding resource paths')
            seen_paths[prefix.lower()] = prefix
        require(path.is_file() and 0 < path.stat().st_size <= 65536, 'asset input must contain 1–65536 bytes')
        raw = path.read_bytes()
        if name not in inputs: total_inputs += len(raw)
        require(total_inputs <= 524288, 'asset inputs exceed source budget')
        inputs[name] = hashlib.sha256(raw).hexdigest()
        width = height = stride = flags = key = 0
        if kind == 'blob':
            require('transparent' not in record, 'blob resources cannot declare transparency')
            data = raw;typ = 1
        else:
            require(path.suffix == '.png', 'rgb565 conversion requires original PNG input')
            import PIL
            from PIL import Image
            require(PIL.__version__ == PILLOW, f'RGB565 converter pins Pillow {PILLOW}')
            key = record.get('transparent', 0)
            require(type(key) is int and 0 <= key <= 65535, 'invalid RGB565 transparent color')
            flags = int('transparent' in record)
            with Image.open(io.BytesIO(raw)) as image:
                require(image.format == 'PNG' and 1 <= image.width <= 320 and 1 <= image.height <= 240 and getattr(image, 'n_frames', 1) == 1,
                        'resource PNG must be a single 1–320 by 1–240 image')
                width, height = image.size;stride = width * 2
                data = bytearray()
                for r, g, b, alpha in image.convert('RGBA').get_flattened_data():
                    require(alpha in (0, 255) and (alpha == 255 or flags), 'PNG needs opaque pixels or binary transparency with an explicit color key')
                    pixel = (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3)
                    require(not (alpha and flags and pixel == key), 'opaque PNG pixel collides with transparent color key')
                    data.extend(struct.pack('<H', pixel if alpha else key))
            data = bytes(data);typ = 2
        entries.append((ident, typ, data, width, height, stride, flags, key))
    entries.sort()
    start = HEADER.size + len(entries) * ENTRY.size
    offset = start;table = bytearray();payload = bytearray();report = []
    for ident, typ, data, width, height, stride, flags, key in entries:
        require(offset + len(data) <= MAX_BUNDLE, 'converted resources exceed 512 KiB')
        table.extend(ENTRY.pack(ident.encode(), typ, offset, len(data), width, height, stride, flags, key, 0, 0))
        payload.extend(data)
        report.append({'id': ident, 'kind': typ, 'offset': offset, 'bytes': len(data), 'width': width, 'height': height,
                       'sha256': hashlib.sha256(data).hexdigest()})
        offset += len(data)
    body = table + payload
    bundle = HEADER.pack(MAGIC, 1, len(entries), offset, HEADER.size, start, zlib.crc32(body)) + body
    return bytes(bundle), {'schema': 1, 'converter': 'lefony-rgb565-1', 'pillow': PILLOW, 'bytes': len(bundle),
                          'sha256': hashlib.sha256(bundle).hexdigest(), 'inputs': inputs, 'entries': report}


def write_generated(output, bundle):
    directory = output / 'generated';directory.mkdir(exist_ok=True)
    target = directory / 'lefony-resources.cpp'
    if bundle is None:
        target.unlink(missing_ok=True)
        (directory / 'resources.bin').unlink(missing_ok=True)
        return None
    # Explicit external linkage, read-only ELF segment, no global initializer.
    rows = [','.join(str(b) for b in bundle[i:i+32]) for i in range(0, len(bundle), 32)]
    text = '// Generated from assets.json; do not edit.\n#include <stdint.h>\nnamespace Lefony { namespace Resources {\n' + \
           'alignas(4) extern const uint8_t embedded[]={\n' + ',\n'.join(rows) + '\n};\n' + \
           f'extern const uint32_t embeddedBytes={len(bundle)};\n' + '}}\n'
    if not target.exists() or target.read_text(encoding='utf-8') != text: target.write_text(text, encoding='utf-8', newline='\n')
    (directory / 'resources.bin').write_bytes(bundle)
    return target
