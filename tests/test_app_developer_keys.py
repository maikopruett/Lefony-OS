# SPDX-License-Identifier: GPL-3.0-or-later
"""Developer trust metadata on real littlefs and synthetic NAND, never a device."""
import hashlib
import json
import struct
import subprocess
import sys

from test_app_files import ROOT, compile_fixture
from test_native_app_package import META, image

sys.path.insert(0, str(ROOT / 'sdk/tools'))
import signing
from lfapp import pack


def test_developer_key_registry_and_interrupted_storage(tmp_path):
    binary = compile_fixture(tmp_path, source=ROOT / 'tests/native/app_developer_keys.cpp',
                             extra_sources=('app_developer_keys.cpp',))
    der = signing.public_der(ROOT / 'tests/fixtures/prime_g2_emulator_update_public.pem')
    modulus = der[len(signing.SPKI_PREFIX):-len(signing.SPKI_SUFFIX)]
    key = tmp_path / 'modulus.bin'
    key.write_bytes(modulus)
    encoded = tmp_path / 'registry.bin'
    package = tmp_path / 'signed.lfapp'
    package.write_bytes(signing.sign(pack(META, image()),
                                    ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem'))
    result = subprocess.run([binary, key, encoded, package], text=True, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    wire = encoded.read_bytes()
    assert len(wire) == 2752 and wire[:8] == b'LFDKEY1\0'
    assert struct.unpack_from('<6I', wire, 8) == (2, 2752, 2, 1, 0, 0)
    assert hashlib.sha256(wire[:32] + wire[64:]).digest() == wire[32:64]
    assert struct.unpack_from('<4I', wire, 64) == (2, 0, 0, 0)
    assert wire[80:112] == hashlib.sha256(der).digest()
    assert wire[112:368] == modulus
    assert wire[368:400] == b'Development' + bytes(21)
    assert wire[400:] == bytes(2352)
    report = json.loads(result.stdout)
    assert report['interruption_cases'] > 30
    assert report['repair_interruption_cases'] > 10
    assert report['cancellation_cases'] > 10 and report['read_fault_cases'] > 10
    assert report['store_bytes'] < 10 * 1024
    destination = ROOT / 'build/sdk-developer-keys'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'storage-report.json').write_text(json.dumps(report, indent=2) + '\n')
