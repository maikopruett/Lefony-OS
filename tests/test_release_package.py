"""Release boundary tests use only the deliberately public emulator key."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from package_lefony_release import package


@pytest.mark.parametrize('working_tree', [False, True])
@pytest.mark.parametrize('recovery_mode', ['none', 'slot', 'full'])
def test_package_allowlist_and_integrity(tmp_path, working_tree, recovery_mode, monkeypatch):
    if recovery_mode != 'none':
        data = b'synthetic public recovery asset'
        descriptor = {'path': 'artifacts/recovery.bin', 'bytes': len(data),
                      'sha256': hashlib.sha256(data).hexdigest()}
        monkeypatch.setattr('package_lefony_release.verified_assets',
                            lambda _: ({'recoveryUboot': descriptor}, {'recoveryUboot': data}))
    (tmp_path / 'dist').mkdir()
    (tmp_path / 'ports/lefony-prime-g2').mkdir(parents=True)
    (tmp_path / 'LICENSES').mkdir()
    for filename in ('LICENSE.md', 'THIRD_PARTY_NOTICES.md'):
        (tmp_path / filename).write_text('Test license notice')
    shutil.copyfile(ROOT / 'tests/fixtures/prime_g2_emulator_update_public.pem',
                    tmp_path / 'ports/lefony-prime-g2/release-signing.pub')
    payload = bytearray(1024 * 1024)
    payload[0x24:0x28] = (0x016f2818).to_bytes(4, 'little')
    payload[0x2c:0x30] = len(payload).to_bytes(4, 'little')
    (tmp_path / 'dist/lefony-os-prime-g2.zImage').write_bytes(payload)
    for name in ('lefony-os-prime-g2-native.bin', 'lefony-os-prime-g2-vm-native.elf', 'lefony-os-source.tar.gz'):
        (tmp_path / 'dist' / name).write_bytes(b'synthetic test artifact')
    (tmp_path / 'dist/private-backup.mtd').write_bytes(b'must not be included')
    output = tmp_path / 'dist/release'
    manifest = package(tmp_path, output, '1.0.0+123', 'a' * 40,
                       ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem',
                       working_tree=working_tree,
                       recovery_directory=tmp_path if recovery_mode != 'none' else None,
                       full_install=recovery_mode == 'full')
    assert manifest['status'] == 'package'
    assert manifest['qualification'] == 'build-tested'
    if recovery_mode == 'none':
        assert 'browserRecovery' not in manifest
    else:
        assert manifest['browserRecovery'] == {
            'protocol': 2 if recovery_mode == 'full' else 1,
            'target': 'boot-os-dtb' if recovery_mode == 'full' else 'single-slot-mtd1',
            'development': True,
        }
    if working_tree:
        assert manifest['sourceState'] == {
            'kind': 'working-tree', 'baseCommit': 'a' * 40,
            'archiveSha256': manifest['assets']['source']['sha256'],
        }
    else:
        assert 'sourceState' not in manifest
    assert json.loads((output / 'lefony-release.json').read_text()) == manifest
    for asset in manifest['assets'].values():
        data = (output / Path(asset['path']).name).read_bytes()
        assert len(data) == asset['bytes']
        assert hashlib.sha256(data).hexdigest() == asset['sha256']
    with zipfile.ZipFile(output / 'lefony-os-prime-g2.zip') as archive:
        assert json.loads(archive.read('build.json'))['assets']['source'] == manifest['assets']['source']
        assert ('Base commit:' in archive.read('README.txt').decode()) == working_tree
        assert set(archive.namelist()) == {
            'lefony-os-prime-g2-native.bin', 'lefony-os-prime-g2-vm-native.elf',
            'lefony-os-prime-g2.lfu', 'release-signing.pub', 'LICENSE.md',
            'THIRD_PARTY_NOTICES.md', 'README.txt', 'build.json'}
    with pytest.raises(FileExistsError):
        package(tmp_path, output, '1.0.0+123', 'a' * 40,
                ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem')


def test_full_install_requires_recovery_before_creating_output(tmp_path):
    output = tmp_path / 'release'
    with pytest.raises(ValueError, match='complete recovery bundle'):
        package(tmp_path, output, '1.0.0+123', 'a' * 40,
                ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem',
                full_install=True)
    assert not output.exists()
