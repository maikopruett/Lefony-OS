# SPDX-License-Identifier: GPL-3.0-or-later
"""Public packaging boundaries, using only the documented emulator test key."""
import base64
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prime_dual_boot_contract as contract
from package_prime_dual_release import package
from prime_g2_update_capsule import verify_signature


def fixture(tmp_path, monkeypatch):
    images = {name: (name.encode() + b'\0') * 32 for name in contract.COMPONENTS}
    image = bytearray(images['lefony_image'])
    image[0x30:0x40] = struct.pack('<4s3I', b'LFL5', 5, 1, 0)
    images['lefony_image'] = images['rescue'] = bytes(image)
    monkeypatch.setitem(contract.INPUTS, 'HPPrime.img', (len(images['hp_image']), contract.sha(images['hp_image']).hex()))
    key = ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem'
    pub = ROOT / 'tests/fixtures/prime_g2_emulator_update_public.pem'
    paths = {}
    for name, data in [('lefony', images['lefony_image']), ('dtb', images['lefony_dtb']), ('descriptor', contract.sign_descriptor(images, 3, key))]:
        paths[name] = tmp_path / name; paths[name].write_bytes(data)
    for name in ('uboot', 'recovery'):
        binary = struct.pack('<I', 0xea000010) + bytes(508)
        imx = bytearray(4096)
        struct.pack_into('<8I', imx, 0, 0x402000d1, 0x87800000, 0, 0, 0, 0x877ff400, 0, 0)
        imx[3072:3072 + len(binary)] = binary
        paths[name] = tmp_path / (name + '.imx')
        paths[name].write_bytes(imx); paths[name].with_suffix('.bin').write_bytes(binary)
    return SimpleNamespace(**paths, private_key=key, public_key=pub, output=tmp_path/'public', source_tag='dual-boot-test')


def test_package_contains_only_public_allowlist(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch)
    (tmp_path/'HPPrime.img').write_bytes(b'private fixture not distributed')
    package(args)
    envelope = json.loads((args.output/'release.json').read_text())
    payload = base64.b64decode(envelope['payload'])
    verify_signature(payload, base64.b64decode(envelope['signature']), args.public_key)
    manifest = json.loads(payload)
    assert manifest['release'] == 3
    assert set(manifest['assets']) == {'boot.imx','boot.bin','recovery.imx','recovery.bin','recovery.zImage','lefony.zImage','lefony.dtb','descriptor.bin'}
    assert set(p.name for p in args.output.iterdir()) == set(manifest['assets']) | {'release.json','SHA256SUMS'}


@pytest.mark.parametrize('changed', ['uboot', 'lefony'])
def test_mismatched_inputs_fail_before_public_directory(tmp_path, monkeypatch, changed):
    args = fixture(tmp_path, monkeypatch)
    path = args.uboot.with_suffix('.bin') if changed == 'uboot' else args.lefony
    path.write_bytes(path.read_bytes() + b'changed')
    with pytest.raises(ValueError):
        package(args)
    assert not args.output.exists()
