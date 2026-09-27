# SPDX-License-Identifier: GPL-3.0-or-later
"""Desktop approval boundaries and read-only protocol; no device or HP data."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json
import struct
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prime_dual_installer as i


def identity(layout=5, flags=3, release=1):
    c = i.contract()
    return struct.pack('<8I', c['native_info']['magic'], 1, c['model'], layout,
                       flags, release, 4096, 131072) + (bytes.fromhex(c['layout_sha256']) if layout else bytes(32))


def test_layout_identity_is_read_only_and_fail_closed():
    device = Mock()
    device.read.side_effect = [struct.pack('<4I', 0x3156444c, 1, 24, 8388608), identity()]
    with pytest.raises(ValueError, match='shared layout'):
        i.require_legacy_native(device)
    device.write.assert_not_called()
    assert device.read.call_args_list[-1].kwargs == {'value': 4, 'length': 64}
    assert i.decode_native_info(identity(0, 0, 0))['legacy_writes_allowed']
    assert i.decode_native_info(identity(flags=1, release=0))['state'] == 'recovery-required'


@pytest.mark.parametrize('offset', [0, 4, 8, 12, 16, 24, 28, 32, 63])
def test_unknown_or_contradictory_identity_is_not_legacy(offset):
    raw = bytearray(identity()); raw[offset] ^= 0x80
    with pytest.raises(ValueError): i.decode_native_info(raw)


def test_absence_and_corruption_are_distinct():
    device = Mock()
    device.read.return_value = struct.pack('<4I', 0x3156444c, 1, 14, 8388608)
    assert i.inspect_native(device)['state'] == 'legacy-unreported'
    device.read.side_effect = [struct.pack('<4I', 0x3156444c, 1, 24, 8388608), b'']
    with pytest.raises(ValueError): i.inspect_native(device)
    device.write.assert_not_called()


@pytest.fixture
def session(tmp_path, monkeypatch):
    backend = SimpleNamespace(private_output=lambda p: p, execute=Mock(return_value={'verified': True}))
    tx = SimpleNamespace(id=bytes(range(32)), changes=[1, 2])
    paths = {name: tmp_path / name for name in ('backup', 'candidate', 'uboot', 'archive', 'recreated', 'public_key')}
    plan = Mock(return_value=(tx, {42}, paths, bytes(32)))
    monkeypatch.setattr(i, 'migration', lambda: backend)
    monkeypatch.setattr(i, 'checked_plan', plan)
    monkeypatch.setattr(i.shutil, 'disk_usage', lambda _: SimpleNamespace(free=10**10))
    directory = tmp_path / 'session'
    review = i.prepare({}, directory, mode='keep-hp', priority='hp', now=100)
    return directory, review, backend, plan


def test_review_retains_backup_and_priority_without_starting(session):
    directory, review, backend, plan = session
    retained = json.loads((directory / 'review.json').read_text())
    assert retained['priority'] == 'hp' and retained['backup']['bytes'] == 553648128
    assert 'approval' not in retained and retained['phase'] == 'review'
    assert (directory / 'review.json').stat().st_mode & 0o777 == 0o600
    backend.execute.assert_not_called()
    plan.assert_called_once_with({}, 'hp')


@pytest.mark.parametrize('kwargs', [dict(approval='wrong', now=101, emulator=True),
    dict(approval=None, now=101, emulator=True), dict(resume=True, emulator=True),
    dict(approval='valid', now=400, emulator=True), dict(approval='valid', now=101)])
def test_bad_expired_or_missing_approval_never_executes(session, kwargs):
    directory, review, backend, _ = session
    if kwargs.get('approval') == 'valid': kwargs['approval'] = review['approval']
    with pytest.raises(ValueError): i.run(directory, **kwargs)
    backend.execute.assert_not_called()
    assert not json.loads((directory / 'review.json').read_text())['approval_used']


def test_changed_inputs_require_new_review(session):
    directory, review, backend, plan = session
    plan.return_value[0].id = bytes(32)
    with pytest.raises(ValueError, match='changed'): i.run(directory, approval=review['approval'], emulator=True, now=101)
    backend.execute.assert_not_called()


def test_approval_is_used_once_and_verification_is_not_boot_confirmation(session):
    directory, review, backend, _ = session
    done = i.run(directory, approval=review['approval'], emulator=True, now=101)
    assert done['phase'] == 'verified' and done['boot_confirmed'] is False
    assert backend.execute.call_args.kwargs['priority'] == 1
    with pytest.raises(ValueError): i.run(directory, approval=review['approval'], emulator=True, now=102)
    assert backend.execute.call_count == 1


def test_ambiguous_execution_is_retained_and_resumes_same_transaction(session):
    directory, review, backend, _ = session
    backend.execute.side_effect = OSError('connection lost')
    (directory / 'migration').mkdir()
    with pytest.raises(OSError): i.run(directory, approval=review['approval'], emulator=True, now=101)
    retained = json.loads((directory / 'review.json').read_text())
    assert retained['phase'] == 'reconnect' and retained['approval_used']
    backend.execute.side_effect = None
    i.run(directory, resume=True, emulator=True, now=999)
    assert backend.execute.call_args.kwargs['resume'] is True
    assert backend.execute.call_args.kwargs['priority'] == 1


def test_insufficient_disk_never_creates_a_session(session, monkeypatch):
    directory, _, backend, _ = session
    monkeypatch.setattr(i.shutil, 'disk_usage', lambda _: SimpleNamespace(free=1))
    other = directory.parent / 'too-small'
    with pytest.raises(ValueError, match='disk space'): i.prepare({}, other, mode='keep-hp', priority='lefony')
    assert not other.exists()
    backend.execute.assert_not_called()


def test_parallel_execution_is_refused(session):
    directory, review, backend, _ = session
    with i.locked(directory), pytest.raises(ValueError, match='already running'):
        i.run(directory, approval=review['approval'], emulator=True, now=101)
    backend.execute.assert_not_called()


def test_desktop_development_path_refuses_shared_before_writer(monkeypatch):
    import lefony_installer as desktop
    from unittest.mock import MagicMock
    device = MagicMock(); device.__enter__.return_value = device
    device.read.return_value = identity()
    monkeypatch.setattr(desktop.usb_update, 'LibUSB', lambda: device)
    monkeypatch.setattr(desktop.usb_update, 'development_capabilities', lambda _: {'flags': 18})
    app = desktop.LefonyOSPrimeInstaller.__new__(desktop.LefonyOSPrimeInstaller)
    app.validation_errors = lambda _: []
    app._native_development_update = Mock()
    with pytest.raises(RuntimeError, match='Shared layout'): app._development_update()
    app._native_development_update.assert_not_called()
    device.write.assert_not_called()


@pytest.mark.parametrize('dual', [False, True])
def test_firmware_response_matches_host_contract(tmp_path, dual):
    import shutil
    import subprocess
    import zlib
    compiler = shutil.which('c++')
    if not compiler: pytest.skip('C++ compiler unavailable')
    port = ROOT / 'ports/lefony-prime-g2/ion/src/prime_g2'
    for name in ('dual_boot_guard.h', 'installer_info.h'):
        shutil.copyfile(port / name, tmp_path / name)
    digest = bytes.fromhex(i.contract()['layout_sha256'])
    (tmp_path / 'dual_boot_build.h').write_text(
        '#define LEFONY_DUAL_BOOT_CANDIDATE ' + str(int(dual)) + '\n' +
        'static constexpr unsigned char LefonyDualLayoutSHA[32] = {' + ','.join(map(str, digest)) + '};\n')
    source = tmp_path / 'main.cpp'
    source.write_text('''#include "installer_info.h"
#include <stdio.h>
int main() {
  uint8_t handoff[64]; uint32_t out[16];
  if (fread(handoff,1,64,stdin)!=64) return 1;
  PrimeG2::DualBoot::installerInfo(out,handoff);
  return fwrite(out,1,64,stdout)!=64;
}
''')
    executable = tmp_path / 'info'
    subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(executable)], check=True)
    handoff = bytearray(struct.pack('<I', 0x3548464c) + digest + struct.pack('<I', 12) + bytes(24))
    struct.pack_into('<I', handoff, 60, zlib.crc32(handoff[:60]))
    for valid in (True, False):
        if not valid: handoff[60] ^= 1
        raw = subprocess.run([str(executable)], input=handoff, check=True, capture_output=True).stdout
        decoded = i.decode_native_info(raw)
        expected = ('dual-boot' if valid else 'recovery-required') if dual else 'lefony-legacy'
        assert decoded['state'] == expected
        assert decoded['release'] == (12 if valid and dual else 0)


def test_expiry_during_input_revalidation_does_not_execute(session, monkeypatch):
    directory, review, backend, _ = session
    times = iter([101, 401])
    monkeypatch.setattr(i.time, 'time', lambda: next(times))
    with pytest.raises(ValueError, match='during input verification'):
        i.run(directory, approval=review['approval'], emulator=True)
    backend.execute.assert_not_called()
    assert not json.loads((directory / 'review.json').read_text())['approval_used']


@pytest.mark.parametrize('field,value', [('hp_profile', 'unknown'), ('hp_images', []), ('raw_backup_bytes', 1), ('hp_filesystem_bytes', 1), ('lefony_app_bytes', 1), ('physical_migration_allowed', True)])
def test_public_contract_cannot_drift_from_qualified_inputs(tmp_path, monkeypatch, field, value):
    data = i.contract(); data[field] = value
    path = tmp_path / 'contract.json'; path.write_text(json.dumps(data))
    monkeypatch.setattr(i, 'CONTRACT_PATH', path)
    with pytest.raises(ValueError): i.contract()


def test_readback_or_media_contract_failure_requires_recovery(session):
    directory, review, backend, _ = session
    backend.execute.side_effect = i.ContractError('final migration readback mismatch')
    with pytest.raises(i.ContractError): i.run(directory, approval=review['approval'], emulator=True, now=101)
    assert json.loads((directory / 'review.json').read_text())['phase'] == 'recovery-required'
    with pytest.raises(ValueError, match='No approved migration'): i.run(directory, resume=True, emulator=True)
    assert backend.execute.call_count == 1
