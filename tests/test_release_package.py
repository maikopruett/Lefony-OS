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


def test_package_allowlist_and_integrity(tmp_path):
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
                       ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem')
    assert manifest['status'] == 'package'
    assert manifest['qualification'] == 'build-tested'
    assert json.loads((output / 'lefony-release.json').read_text()) == manifest
    for asset in manifest['assets'].values():
        data = (output / Path(asset['path']).name).read_bytes()
        assert len(data) == asset['bytes']
        assert hashlib.sha256(data).hexdigest() == asset['sha256']
    with zipfile.ZipFile(output / 'lefony-os-prime-g2.zip') as archive:
        assert set(archive.namelist()) == {
            'lefony-os-prime-g2-native.bin', 'lefony-os-prime-g2-vm-native.elf',
            'lefony-os-prime-g2.lfu', 'release-signing.pub', 'LICENSE.md',
            'THIRD_PARTY_NOTICES.md', 'README.txt', 'build.json'}
    with pytest.raises(FileExistsError):
        package(tmp_path, output, '1.0.0+123', 'a' * 40,
                ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem')
