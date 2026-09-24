# SPDX-License-Identifier: GPL-3.0-or-later
"""LFAPP1 authenticated envelope. The inner executable retains its own ABI.

Keys belong to the developer or publication host, never the untrusted build container.
No key is generated implicitly. Only RSA-2048/e=65537 SPKI public keys qualify.
"""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from lfapp import HEADER as INNER_HEADER, MAX_IMAGE, MAX_MANIFEST, require, unpack
from sdk_environment import openssl_environment

MAGIC = b'LFAPP1\0\0'
HEADER = struct.Struct('<8sIIII32s32s8s')
SIGNATURE_BYTES = 256
PREFIX_BYTES = HEADER.size + SIGNATURE_BYTES
MAX_PACKAGE = PREFIX_BYTES + INNER_HEADER.size + MAX_IMAGE + MAX_MANIFEST
SPKI_PREFIX = bytes.fromhex('30820122300d06092a864886f70d01010105000382010f003082010a0282010100')
SPKI_SUFFIX = bytes.fromhex('0203010001')


def openssl(*args, data=None, program='openssl', runtime=None):
    if program == 'openssl' and getattr(sys, 'frozen', False) and sys.platform == 'win32':
        program = Path(sys._MEIPASS) / 'toolchain/bin/openssl.exe'
    return subprocess.run([str(program), *map(str, args)], input=data, capture_output=True,
                          check=True, timeout=30, env=openssl_environment(runtime)).stdout


def public_der(key, private=False, *, program='openssl', runtime=None):
    args = ['pkey', '-in', key]
    if not private:
        args += ['-pubin']
    der = openssl(*args, '-pubout', '-outform', 'DER', program=program, runtime=runtime)
    require(len(der) == len(SPKI_PREFIX) + 256 + len(SPKI_SUFFIX) and
            der.startswith(SPKI_PREFIX) and der.endswith(SPKI_SUFFIX),
            'app signing requires RSA-2048 with exponent 65537')
    modulus = der[len(SPKI_PREFIX):-len(SPKI_SUFFIX)]
    require(modulus[0] & 128 and modulus[-1] & 1, 'invalid RSA modulus')
    return der


def envelope(package):
    """Parse/check integrity only. Call verify() before trusting its contents."""
    require(PREFIX_BYTES + 116 <= len(package) <= MAX_PACKAGE, 'invalid signed package size')
    magic, version, size, abi, flags, key_id, digest, reserved = HEADER.unpack_from(package)
    require(magic == MAGIC and version == 1 and flags == 0 and reserved == bytes(8),
            'unsupported signed package header')
    payload = package[PREFIX_BYTES:]
    require(len(payload) == size and hashlib.sha256(payload).digest() == digest,
            'signed payload length or digest mismatch')
    metadata, image = unpack(payload)
    require(metadata['abi'] == abi, 'signed ABI does not match payload')
    return key_id.hex(), payload, metadata, image


def sign(payload, private_key):
    metadata, _ = unpack(payload)
    der = public_der(private_key, private=True)
    header = HEADER.pack(MAGIC, 1, len(payload), metadata['abi'], 0,
                         hashlib.sha256(der).digest(), hashlib.sha256(payload).digest(), bytes(8))
    signature = openssl('dgst', '-sha256', '-sign', private_key, data=header)
    require(len(signature) == SIGNATURE_BYTES, 'unexpected app signature length')
    result = header + signature + payload
    with tempfile.TemporaryDirectory(prefix='lf-sign-') as directory:
        public = Path(directory) / 'public.pem'
        public.write_bytes(openssl('pkey', '-in', private_key, '-pubout'))
        verify(result, [public])
    return result


def verify(package, public_keys):
    key_id, _, metadata, image = envelope(package)
    matching = [Path(key) for key in public_keys if hashlib.sha256(public_der(key)).hexdigest() == key_id]
    require(len(matching) == 1, 'unknown, duplicated or retired app signing key')
    with tempfile.TemporaryDirectory(prefix='lf-verify-') as directory:
        signature = Path(directory) / 'signature'
        signature.write_bytes(package[HEADER.size:PREFIX_BYTES])
        try:
            openssl('dgst', '-sha256', '-verify', matching[0], '-signature', signature,
                    data=package[:HEADER.size])
        except subprocess.CalledProcessError as exc:
            raise ValueError('app signature rejected') from exc
    return metadata, image


def keygen(private, public):
    """Explicit new app identity; never replace an existing file or symlink."""
    private, public = Path(private), Path(public)
    require(private.resolve() != public.resolve(), 'key paths must differ')
    require(not os.path.lexists(private) and not os.path.lexists(public),
            'refusing to replace an existing identity')
    # Reserve both destinations before generating key material. An interrupted
    # operation may leave reserved files; it never retries or replaces them.
    descriptor = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as output, public.open('xb') as public_output:
        output.write(openssl('genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048'))
        output.flush()
        os.fsync(output.fileno())
        public_output.write(openssl('pkey', '-in', private, '-pubout'))
        public_output.flush()
        os.fsync(public_output.fileno())
    return {'private_key': str(private), 'public_key': str(public),
            'fingerprint': hashlib.sha256(public_der(public)).hexdigest()}


def sign_file(package, private_key, output):
    """Sign a bounded unsigned package into a new, distinct output file."""
    package, private_key, output = map(Path, (package, private_key, output))
    require(output.resolve() not in (package.resolve(), private_key.resolve()),
            'use a separate signed output path')
    require(package.is_file(), 'select a regular unsigned package file')
    require(not os.path.lexists(output), 'refusing to replace an existing signed output')
    with package.open('rb') as source:
        payload = source.read(MAX_PACKAGE + 1)
    require(len(payload) <= MAX_PACKAGE, 'unsigned package exceeds maximum size')
    result = sign(payload, private_key)
    # Signature and inner package verification finish before creating output.
    with output.open('xb') as destination:
        destination.write(result)
        destination.flush()
        os.fsync(destination.fileno())
    signer, _, metadata, _ = envelope(result)
    return {'package': str(output), 'id': metadata['id'], 'version': metadata['version'],
            'signer': signer, 'sha256': hashlib.sha256(result).hexdigest()}


def firmware_header(keys, destination):
    require(1 <= len(keys) <= 4, 'provide one to four active app public keys')
    entries, identities = [], set()
    for key in keys:
        der = public_der(key)
        identity = hashlib.sha256(der).digest()
        require(identity not in identities, 'duplicate app public key')
        identities.add(identity)
        byte_list = lambda value: '{' + ','.join(f'0x{b:02x}' for b in value) + '}'
        entries.append('  {' + byte_list(identity) + ',' + byte_list(der[len(SPKI_PREFIX):-len(SPKI_SUFFIX)]) + '}')
    Path(destination).write_text('// Generated from explicitly configured PUBLIC app keys. No firmware keys.\n'
        '#ifndef LEFONY_APP_TRUST_ROOTS_H\n#define LEFONY_APP_TRUST_ROOTS_H\n#include <stdint.h>\n'
        'struct LefonyAppTrustRoot { uint8_t id[32], modulus[256]; };\n'
        f'constexpr unsigned LefonyAppTrustRootCount={len(entries)};\n'
        'constexpr LefonyAppTrustRoot LefonyAppTrustRoots[]={\n' + ',\n'.join(entries) + '\n};\n#endif\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    key = sub.add_parser('keygen', help='Explicitly create a NEW, independent app signing identity')
    key.add_argument('private', type=Path); key.add_argument('public', type=Path)
    for action in ('sign', 'verify'):
        command = sub.add_parser(action)
        command.add_argument('package', type=Path)
        if action == 'sign':
            command.add_argument('--private-key', required=True, type=Path)
            command.add_argument('--output', required=True, type=Path)
        else:
            command.add_argument('--public-key', action='append', required=True, type=Path)
    header = sub.add_parser('header')
    header.add_argument('--public-key', action='append', required=True, type=Path)
    header.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'keygen':
        print('Created independent app signing identity:', keygen(args.private, args.public)['fingerprint'])
    elif args.command == 'header':
        firmware_header(args.public_key, args.output)
    elif args.command == 'sign':
        require(args.output.resolve() != args.package.resolve(), 'use a separate signed output path')
        args.output.write_bytes(sign(args.package.read_bytes(), args.private_key))
    else:
        print(verify(args.package.read_bytes(), args.public_key)[0])


if __name__ == '__main__':
    main()
