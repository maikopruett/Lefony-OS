# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, deterministic install-time data, separate from executable resources."""
import gzip
import hashlib
import io
import json
import re
from pathlib import Path
from lfapp import require

MAX_RAW = 32 * 1024 * 1024
MAX_PACKED = 12 * 1024 * 1024
PART = 8 * 1024 * 1024
CONFIG = 'notices/bundled-data.txt'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def descriptor(value):
    require(isinstance(value, dict) and set(value) == {'schema', 'encoding', 'bytes', 'sha256', 'files'} and
            value['schema'] == 1 and value['encoding'] == 'gzip', 'Invalid bundled data descriptor')
    require(type(value['bytes']) is int and 1 <= value['bytes'] <= MAX_RAW and
            isinstance(value['sha256'], str) and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'Invalid bundled data size/hash')
    require(isinstance(value['files'], list) and 1 <= len(value['files']) <= 16, 'Bundle requires 1–16 files')
    offset = 0
    names = set()
    for item in value['files']:
        require(isinstance(item, dict) and set(item) == {'path', 'offset', 'bytes', 'sha256'}, 'Invalid bundled file')
        name = item['path']
        # Immutable first-install inputs only. Keep saves/configuration out of this namespace.
        require(isinstance(name, str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,39}\\.(?:wad|bin|txt)', name) and
                name.lower() not in names, 'Invalid or duplicate bundled filename')
        names.add(name.lower())
        require(type(item['offset']) is int and item['offset'] == offset and type(item['bytes']) is int and
                1 <= item['bytes'] <= MAX_RAW - offset and isinstance(item['sha256'], str) and
                re.fullmatch('[0-9a-f]{64}', item['sha256']), 'Invalid bundled file range/hash')
        offset += item['bytes']
    require(offset == value['bytes'], 'Bundled files do not cover the declared data')
    return value


def prepare(project):
    from store_snapshot import read_file
    if not (project / CONFIG).exists():
        return None, []
    spec = descriptor(json.loads(read_file(project, CONFIG, 65536)))
    raw = bytearray()
    for item in spec['files']:
        data = read_file(project, 'data/' + item['path'], item['bytes'])
        require(len(data) == item['bytes'] and sha(data) == item['sha256'], 'Bundled input differs: ' + item['path'])
        raw.extend(data)
    require(sha(raw) == spec['sha256'], 'Bundled input digest mismatch')
    packed = gzip.compress(raw, mtime=0)
    require(len(packed) <= MAX_PACKED, 'Compressed bundled data exceeds 12 MiB')
    return spec, [(f'data/{i // PART:02d}.gzpart', packed[i:i + PART]) for i in range(0, len(packed), PART)]


def unpack(spec, parts):
    descriptor(spec)
    packed = b''.join(parts)
    require(0 < len(packed) <= MAX_PACKED, 'Invalid compressed data length')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(spec['bytes'] + 1)
    require(len(raw) == spec['bytes'] and sha(raw) == spec['sha256'], 'Bundled data size/hash mismatch')
    result = []
    for item in spec['files']:
        data = raw[item['offset']:item['offset'] + item['bytes']]
        require(sha(data) == item['sha256'], 'Bundled file digest mismatch')
        result.append((item, data))
    return result


def install(client, app_id, spec, parts, *, progress=lambda done, total: None):
    """Only create absent inputs; never overwrite saves or existing user files."""
    from files_device import FileClient
    files = FileClient(client)
    contents = unpack(spec, parts)
    existing = {item['path']: item for item in files.list(app_id)['entries']}
    for item, data in contents:
        prior = existing.get(item['path'])
        if prior:
            require(prior['kind'] == 'file' and prior['bytes'] == len(data), 'Existing bundled file differs; preserved: ' + item['path'])
            identity = files.info(app_id)
            output = io.BytesIO()
            files._download(files._begin(app_id, 2, item['path'], identity=identity), output)
            require(sha(output.getvalue()) == item['sha256'], 'Existing bundled file differs; preserved: ' + item['path'])
    missing = [(item, data) for item, data in contents if item['path'] not in existing]
    info = files.info(app_id)
    if missing:
        require(not info['pending_upgrade'] and info['data_schema'] == info['app_schema'],
                'Finish the pending app upgrade before installing bundled files')
        require(sum(len(data) for _, data in missing) <= info['quota_remaining_bytes'], 'Bundled data exceeds app quota')
    for item, data in sorted(missing, key=lambda pair: len(pair[1])):
        identity = files.info(app_id)
        files._upload(app_id, item['path'], io.BytesIO(data), len(data), bytes.fromhex(item['sha256']), identity, progress=progress)
    return [item['path'] for item, _ in missing]


def verify_metadata(signed, public_keys, package_hash):
    import subprocess
    import tempfile
    from signing import HEADER, MAGIC, PREFIX_BYTES, public_der, openssl
    require(468 <= len(signed) <= 65888, 'Invalid signed bundle metadata size')
    magic, version, size, abi, flags, key_id, digest, reserved = HEADER.unpack_from(signed)
    payload = signed[PREFIX_BYTES:]
    require((magic, version, size, abi, flags, reserved) == (MAGIC, 1, len(payload), 1, 0, bytes(8)) and
            hashlib.sha256(payload).digest() == digest, 'Invalid signed bundle metadata header')
    matching = [Path(key) for key in public_keys if hashlib.sha256(public_der(key)).digest() == key_id]
    require(len(matching) == 1, 'Unknown or retired bundle signing key')
    with tempfile.TemporaryDirectory(prefix='lf-data-verify-') as directory:
        signature = Path(directory) / 'signature'
        signature.write_bytes(signed[HEADER.size:PREFIX_BYTES])
        try:
            openssl('dgst', '-sha256', '-verify', matching[0], '-signature', signature, data=signed[:HEADER.size])
        except subprocess.CalledProcessError as exc:
            raise ValueError('Bundled data signature rejected') from exc
    metadata = json.loads(payload)
    require(isinstance(metadata, dict) and set(metadata) == {'schema', 'kind', 'package_sha256', 'data', 'parts'} and
            metadata['schema'] == 1 and metadata['kind'] == 'lefony-install-data-1' and metadata['package_sha256'] == package_hash,
            'Signed data does not match the app package')
    descriptor(metadata['data'])
    require(isinstance(metadata['parts'], list) and 1 <= len(metadata['parts']) <= 2, 'Invalid bundle parts')
    for i, part in enumerate(metadata['parts']):
        require(isinstance(part, dict) and set(part) == {'path', 'bytes', 'sha256'} and part['path'] == f'data/{i:02d}.gzpart' and
                type(part['bytes']) is int and 1 <= part['bytes'] <= PART and isinstance(part['sha256'], str) and
                re.fullmatch('[0-9a-f]{64}', part['sha256']), 'Invalid bundle part')
    return metadata


def load_bundle(path, public_keys):
    import struct
    from signing import verify
    with Path(path).open('rb') as stream:
        content = stream.read(16777217)
    require(12 < len(content) <= 16777216 and content[:8] == b'LFBNDL1\0', 'Invalid app bundle size/header')
    size = struct.unpack_from('<I', content, 8)[0]
    require(1 <= size <= 65536 and 12 + size < len(content), 'Invalid bundle index size')
    index = json.loads(content[12:12 + size])
    require(isinstance(index, dict) and set(index) == {'schema', 'files'} and index['schema'] == 1 and
            isinstance(index['files'], list) and 3 <= len(index['files']) <= 4, 'Invalid bundle index')
    offset = 12 + size
    files = {}
    names = ['package.lfapp', 'data.signed'] + [f'data/{i:02d}.gzpart' for i in range(len(index['files']) - 2)]
    for item, name in zip(index['files'], names):
        require(isinstance(item, dict) and set(item) == {'path', 'bytes', 'sha256'} and item['path'] == name and
                type(item['bytes']) is int and 1 <= item['bytes'] <= len(content) - offset, 'Invalid bundle member')
        data = content[offset:offset + item['bytes']];offset += len(data)
        require(sha(data) == item['sha256'], 'Bundle member checksum mismatch')
        files[name] = data
    require(offset == len(content), 'Unexpected trailing bundle bytes')
    app, _ = verify(files['package.lfapp'], public_keys)
    metadata = verify_metadata(files['data.signed'], public_keys, sha(files['package.lfapp']))
    require(metadata['parts'] == index['files'][2:], 'Bundle parts differ from signed metadata')
    parts = [files[p['path']] for p in metadata['parts']]
    unpack(metadata['data'], parts)
    return files['package.lfapp'], app, metadata['data'], parts
