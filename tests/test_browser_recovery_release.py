"""Offline release tests. Every image and acceptance record here is synthetic."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from package_lefony_release import package
from lefony_uboot_history import inspect_bytes
from prepare_browser_recovery_release import (
    INSTALL_ASSETS, CHECKS, CONTRACT, assemble, audit,
)


@pytest.fixture
def recovery(tmp_path):
    (tmp_path / 'dist').mkdir()
    (tmp_path / 'ports/lefony-prime-g2').mkdir(parents=True)
    (tmp_path / 'LICENSES').mkdir()
    for name in ('LICENSE.md', 'THIRD_PARTY_NOTICES.md'):
        (tmp_path / name).write_text('Synthetic license notice')
    key = tmp_path / 'ports/lefony-prime-g2/release-signing.pub'
    shutil.copyfile(ROOT / 'tests/fixtures/prime_g2_emulator_update_public.pem', key)
    kernel = bytearray(1048576)
    kernel[36:40] = (0x016f2818).to_bytes(4, 'little')
    kernel[44:48] = len(kernel).to_bytes(4, 'little')
    (tmp_path / 'dist/lefony-os-prime-g2.zImage').write_bytes(kernel)
    for name in ('lefony-os-prime-g2-native.bin', 'lefony-os-prime-g2-vm-native.elf', 'lefony-os-source.tar.gz'):
        (tmp_path / 'dist' / name).write_bytes(b'synthetic build artifact')
    packaged = tmp_path / 'dist/development'
    development = package(tmp_path, packaged, '1.0.0+123', 'a' * 40,
                          ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem')
    directory = tmp_path / 'candidate'
    (directory / 'artifacts').mkdir(parents=True)
    boot = bytearray(8192)
    address = 0x87800400
    for at, value in ((1024, 0x402000d1), (1028, address + 100),
                      (1040, address + 32), (1044, address),
                      (1056, address), (1060, len(boot) - 1024)):
        boot[at:at + 4] = value.to_bytes(4, 'little')
    environment = (b'U-Boot 2018.03 (synthetic)\0bootcmd=nand read ${loadaddr} 0x400000 0x800000\0'
                   b'bootcmd_mfg=run mfgtool_args;bootz ${loadaddr} ${initrd_addr} ${fdt_addr};\0\0')
    boot[2048:2048 + len(environment)] = environment
    dtb = bytearray(40)
    dtb[:4] = bytes.fromhex('d00dfeed')
    dtb[4:8] = len(dtb).to_bytes(4, 'big')
    initrd = bytearray(128)
    initrd[:4] = bytes.fromhex('27051956')
    initrd[12:16] = (len(initrd) - 64).to_bytes(4, 'big')
    history = {'schema_version': 1, 'builds': [{**asdict(inspect_bytes(boot)),
        'artifact': 'baseline.imx', 'status': 'lefony-nand-boot-verified',
        'notes': 'Synthetic test evidence only.'}]}
    files = {
        'capsule': (packaged / 'lefony-os-prime-g2.lfu').read_bytes(),
        'publicKey': key.read_bytes(), 'recoveryUboot': boot, 'recoveryKernel': kernel,
        'recoveryDtb': dtb, 'recoveryInitramfs': initrd, 'baselineUboot': boot,
        'baselineHistory': json.dumps(history).encode(),
        'recoverySource': b'synthetic corresponding source archive',
        'recoveryNotices': b'synthetic recovery notices',
    }
    manifest = {'schema': 1, 'status': 'recovery-candidate', 'version': development['version'], 'assets': {}}
    for name, data in files.items():
        filename = {'baselineUboot': 'baseline.imx', 'capsule': 'lefony-os-prime-g2.lfu',
                    'publicKey': 'release-signing.pub'}.get(name, name + '.test')
        path = 'artifacts/' + filename
        (directory / path).write_bytes(data)
        manifest['assets'][name] = {'path': path, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    candidate = directory / 'candidate.json'
    candidate.write_text(json.dumps(manifest))
    report = audit(candidate, key)[2]
    acceptance = directory / 'acceptance.json'
    acceptance.write_text(json.dumps({**{k: report[k] for k in ('version', 'payloadSha256', 'assets')},
        'schema': 1, 'model': 'HPG2', 'qualification': 'physical-verified',
        'browserRecovery': CONTRACT, 'checks': {k: True for k in CHECKS},
        'evidence': 'Synthetic test record, never hardware evidence.'}))
    return candidate, packaged / 'lefony-release.json', key, acceptance


def test_audit_does_not_qualify_or_write(recovery):
    candidate, _, key, _ = recovery
    _, _, report = audit(candidate, key)
    assert report['status'] == 'recovery-candidate'
    assert report['physicalQualification'] == 'not-established-by-this-audit'
    assert set(report['assets']) == set(INSTALL_ASSETS)


@pytest.mark.parametrize('qualified', [False, True])
def test_complete_release_and_checksums(recovery, tmp_path, qualified):
    candidate, development, key, acceptance = recovery
    (development.parent / 'private-backup.mtd').write_bytes(b'never copied')
    output = tmp_path / 'output'
    manifest = assemble(development, candidate, output, key, acceptance if qualified else None)
    assert manifest['status'] == ('ready' if qualified else 'package')
    assert manifest.get('browserRecovery') == (CONTRACT if qualified else None)
    assert json.loads((output / 'lefony-release.json').read_text()) == manifest
    embedded = (output / 'release-notes.md').read_text().split('<!-- lefony-release-v1\n')[1].split('\n-->')[0]
    assert json.loads(embedded) == manifest
    assert not (output / 'private-backup.mtd').exists()
    for asset in manifest['assets'].values():
        data = (output / asset['path'].split('/')[-1]).read_bytes()
        assert len(data) == asset['bytes']
        assert hashlib.sha256(data).hexdigest() == asset['sha256']
    for line in (output / 'SHA256SUMS').read_text().splitlines():
        expected, filename = line.split('  ')
        assert hashlib.sha256((output / filename).read_bytes()).hexdigest() == expected
    with pytest.raises(FileExistsError):
        assemble(development, candidate, output, key)


@pytest.mark.parametrize('changed', ['version', 'payloadSha256', 'assets', 'checks', 'evidence'])
def test_stale_or_incomplete_acceptance_refused(recovery, tmp_path, changed):
    candidate, development, key, acceptance = recovery
    record = json.loads(acceptance.read_text())
    record[changed] = {} if changed in ('assets', 'checks') else 'mismatched' if changed != 'evidence' else ''
    acceptance.write_text(json.dumps(record))
    output = tmp_path / 'output'
    with pytest.raises(ValueError, match='acceptance'):
        assemble(development, candidate, output, key, acceptance)
    assert not output.exists()


def test_missing_source_refused_before_distribution(recovery, tmp_path):
    candidate, development, key, acceptance = recovery
    manifest = json.loads(candidate.read_text())
    del manifest['assets']['recoverySource']
    candidate.write_text(json.dumps(manifest))
    output = tmp_path / 'output'
    with pytest.raises(ValueError, match='recoverySource'):
        assemble(development, candidate, output, key, acceptance)
    assert not output.exists()


@pytest.mark.parametrize('kind', ['hash', 'size', 'header', 'baseline', 'traversal', 'key'])
def test_corrupt_candidates_refused(recovery, kind):
    candidate, _, key, _ = recovery
    manifest = json.loads(candidate.read_text())
    asset = manifest['assets']['recoveryKernel']
    if kind == 'hash':
        asset['sha256'] = '0' * 64
    elif kind == 'size':
        asset['bytes'] -= 1
    elif kind == 'traversal':
        asset['path'] = 'artifacts/../outside'
    elif kind == 'key':
        key.write_bytes(key.read_bytes() + b'\n')
    else:
        if kind == 'baseline':
            asset = manifest['assets']['baselineHistory']
            history = json.loads((candidate.parent / asset['path']).read_bytes())
            history['builds'][0]['bootcmd'] = 'invented'
            data = json.dumps(history).encode()
        else:
            data = bytearray((candidate.parent / asset['path']).read_bytes())
            data[36] ^= 1
        (candidate.parent / asset['path']).write_bytes(data)
        asset.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    candidate.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        audit(candidate, key)
