# SPDX-License-Identifier: GPL-3.0-or-later
"""Local private signing and model install preserve identity/USB boundaries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from test_native_app_package import META, image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
import cli
import emulator_usb
import keys_device
import signing
from lfapp import pack


def command(*arguments):
    return subprocess.run([sys.executable, str(ROOT/'sdk/tools/cli.py'), *map(str, arguments)],
                          capture_output=True, text=True, timeout=30)


def test_local_cli_generates_signs_and_preserves_existing_outputs(tmp_path):
    private, public = tmp_path/'private.pem', tmp_path/'public.pem'
    old_umask = os.umask(0)
    try:
        generated = command('keys', 'generate', '--private-key', private, '--public-key', public)
    finally:
        os.umask(old_umask)
    assert generated.returncode == 0, generated.stderr
    identity = json.loads(generated.stdout)
    assert identity['fingerprint'] == hashlib.sha256(signing.public_der(public)).hexdigest()
    if os.name != 'nt':
        assert private.stat().st_mode & 0o777 == 0o600
    before = private.read_bytes(), public.read_bytes()
    assert command('keys', 'generate', '--private-key', private, '--public-key', public).returncode == 1
    assert (private.read_bytes(), public.read_bytes()) == before
    unsigned, signed = tmp_path/'unsigned.lfapp', tmp_path/'signed.lfapp'
    payload = pack(META, image());unsigned.write_bytes(payload)
    result = command('sign', unsigned, '--private-key', private, '--output', signed)
    assert result.returncode == 0, result.stderr
    assert signing.verify(signed.read_bytes(), [public]) == (META, image())
    assert json.loads(result.stdout)['sha256'] == hashlib.sha256(signed.read_bytes()).hexdigest()
    original = signed.read_bytes()
    for output in (unsigned, private, public, signed):
        assert command('sign', unsigned, '--private-key', private, '--output', output).returncode == 1
    assert signed.read_bytes() == original and unsigned.read_bytes() == payload
    assert (private.read_bytes(), public.read_bytes()) == before


@pytest.mark.parametrize('kind', ['existing', 'dangling', 'same'])
def test_key_generation_rejects_destinations_before_generating(kind, tmp_path, monkeypatch):
    private, public = tmp_path/'private', tmp_path/'public'
    if kind == 'existing':public.write_bytes(b'existing identity')
    elif kind == 'dangling':public.symlink_to(tmp_path/'missing')
    else:public = private
    monkeypatch.setattr(signing, 'openssl', lambda *a, **k: pytest.fail('Generated despite conflicting paths'))
    with pytest.raises(ValueError):signing.keygen(private, public)
    assert not private.exists()


def test_sign_rejects_invalid_and_oversized_package_before_key_access(tmp_path, monkeypatch):
    unsigned, output = tmp_path/'app', tmp_path/'signed'
    monkeypatch.setattr(signing, 'openssl', lambda *a, **k: pytest.fail('Invalid payload reached private key'))
    for payload in (b'invalid', b'X' * (signing.MAX_PACKAGE + 1)):
        unsigned.write_bytes(payload)
        with pytest.raises(ValueError):signing.sign_file(unsigned, tmp_path/'private', output)
        assert not output.exists()


@pytest.mark.parametrize('recover', [False, True])
def test_install_verifies_before_opening_any_usb(recover, tmp_path, monkeypatch):
    package = tmp_path/'bad.lfapp';package.write_bytes(b'X' * 512)
    monkeypatch.setattr(cli, 'management_transport', lambda *a: pytest.fail('Unverified package opened USB'))
    monkeypatch.setattr(sys, 'argv', ['lefony-sdk', 'install', str(package), '--public-key', 'missing',
                                   *(['--recover-signer'] if recover else [])])
    assert cli.main() == 1


@pytest.mark.parametrize('policy', [keys_device.KeyUSB, keys_device.InstallUSB, keys_device.RecoveryUSB])
def test_model_matches_each_command_family_and_refuses_extra_authority(policy, monkeypatch):
    calls = []
    class Host:
        def __init__(self, path, timeout):calls.append(('open', path))
        def control_in(self, *args):calls.append(('read', args));return b'reply'
        def control_out(self, *args):calls.append(('write', args))
        def close(self):calls.append(('close',))
    monkeypatch.setattr(emulator_usb, 'PrimeUSBHost', Host)
    with emulator_usb.ManagementUSB('model', policy) as transport:
        for request in range(256):
            if request in policy.READ_REQUESTS:assert transport.read(request) == b'reply'
            else:
                with pytest.raises(emulator_usb.USBError):transport.read(request)
            if request in policy.WRITE_REQUESTS:transport.write(request)
            else:
                with pytest.raises(emulator_usb.USBError):transport.write(request)
        for length in (-1, 513, True):
            with pytest.raises(emulator_usb.USBError):transport.read(0x60, length=length)
        for data in ('text', b'X'*513):
            with pytest.raises(emulator_usb.USBError):transport.write(policy.WRITE_REQUESTS[0], data)
    assert len(calls) == 2 + len(policy.READ_REQUESTS) + len(policy.WRITE_REQUESTS)
    assert calls[-1] == ('close',)


def test_explicit_model_failure_never_discovers_physical_usb(monkeypatch):
    monkeypatch.setattr(keys_device.KeyUSB, '__init__', lambda self: pytest.fail('Physical device opened'))
    def fail(*a, **k):raise RuntimeError('Model socket unavailable')
    monkeypatch.setattr(emulator_usb, 'PrimeUSBHost', fail)
    monkeypatch.setattr(sys, 'argv', ['lefony-sdk', 'keys', '--emulator-usb', '/missing', 'list'])
    assert cli.main() == 1
