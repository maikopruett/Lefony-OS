#!/usr/bin/env python3
"""Audit a recovery candidate or assemble a release from exact tested artifacts.

SPDX-License-Identifier: GPL-3.0-or-later

This tool never opens USB, signs firmware, downloads files, or publishes releases.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile

from lefony_uboot_history import inspect_bytes, validation_errors
from prime_g2_update_capsule import inspect, parse_version

RECOVERY_ASSETS = ('recoveryUboot', 'recoveryKernel', 'recoveryDtb',
                   'recoveryInitramfs', 'baselineUboot', 'baselineHistory')
INSTALL_ASSETS = ('capsule', 'publicKey', *RECOVERY_ASSETS)
PACKAGE_ASSETS = ('firmware', 'emulator', 'source', 'capsule', 'publicKey', 'package')
SOURCE_ASSETS = ('recoverySource', 'recoveryNotices')
CHECKS = ('romBootstrap', 'deviceIdentity', 'baselineComparison', 'nandWrite',
          'nandReadback', 'normalBoot', 'tabLossContinuation', 'browserRecoveryExit')
CONTRACT = {'protocol': 1, 'target': 'single-slot-mtd1'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    if path.stat().st_size > 65536:
        raise ValueError('Metadata exceeds 64 KiB')
    result = json.loads(path.read_text())
    if not isinstance(result, dict):
        raise ValueError('Expected a JSON object')
    return result


def read_assets(manifest, directory, required, *, flat=False):
    assets = manifest.get('assets', {})
    data, names = {}, set()
    for key in required:
        asset = assets.get(key, {})
        name = asset.get('path', '')
        if not isinstance(name, str) or not re.fullmatch(r'artifacts/[A-Za-z0-9][A-Za-z0-9._-]*', name):
            raise ValueError(f'Missing or invalid artifact: {key}')
        filename = name.removeprefix('artifacts/')
        if filename in names:
            raise ValueError('Artifact filenames must be unique')
        names.add(filename)
        path = directory / (filename if flat else name)
        if path.resolve().parent != (directory if flat else directory / 'artifacts').resolve() or path.is_symlink():
            raise ValueError(f'Artifact escapes its directory: {key}')
        size = asset.get('bytes')
        limit = {'capsule': 8 * 1024 * 1024 + 512, 'publicKey': 8192,
                 'baselineHistory': 65536, 'baselineUboot': 1572864}.get(key, 128 * 1024 * 1024)
        if type(size) is not int or not 0 < size <= limit or path.stat().st_size != size:
            raise ValueError(f'Artifact size mismatch: {key}')
        data[key] = path.read_bytes()
        if digest(data[key]) != asset.get('sha256'):
            raise ValueError(f'Artifact hash mismatch: {key}')
    return data


def bootstrap_ranges(files):
    """Mirror the website's fixed i.MX6ULL RAM layout and header checks."""
    boot = files['recoveryUboot']
    u32 = lambda data, at: int.from_bytes(data[at:at + 4], 'little')
    offset = next((n for n in range(0, min(len(boot) - 31, 4096), 4)
                   if u32(boot, n) in (0x402000d1, 0x412000d1)), -1)
    if offset < 0:
        raise ValueError('Recovery U-Boot lacks a supported IVT')
    entry, dcd, boot_pointer, address = (u32(boot, offset + n) for n in (4, 12, 16, 20))

    def local(pointer, size):
        at = offset + pointer - address
        if at < offset or at + size > len(boot):
            raise ValueError('Recovery U-Boot pointer is outside the image')
        return at

    at = local(boot_pointer, 12)
    start, size, plugin = (u32(boot, at + n) for n in (0, 4, 8))
    length = min(size - (address - start), len(boot) - offset)
    if plugin or u32(boot, offset + 24) or address % 4 or start > address or length < 32 or not address <= entry < address + length:
        raise ValueError('Unsupported recovery U-Boot boot data')
    if dcd:
        at = local(dcd, 4)
        count = int.from_bytes(boot[at + 1:at + 3], 'big')
        if boot[at] != 0xd2 or boot[at + 3] != 0x40 or not 4 <= count <= 65536:
            raise ValueError('Unsupported recovery DCD')
        local(dcd, count)
    kernel, dtb, initrd = (files[n] for n in ('recoveryKernel', 'recoveryDtb', 'recoveryInitramfs'))
    if len(kernel) < 48 or u32(kernel, 36) != 0x016f2818 or u32(kernel, 44) - u32(kernel, 40) != len(kernel):
        raise ValueError('Invalid recovery kernel header/size')
    if len(dtb) < 40 or dtb[:4] != bytes.fromhex('d00dfeed') or int.from_bytes(dtb[4:8], 'big') != len(dtb):
        raise ValueError('Invalid recovery DTB header/size')
    if len(initrd) < 64 or initrd[:4] != bytes.fromhex('27051956') or int.from_bytes(initrd[12:16], 'big') + 64 != len(initrd):
        raise ValueError('Invalid recovery initramfs header/size')
    ranges = [(address, length), (0x80800000, len(kernel)),
              (0x83000000, len(dtb)), (0x86800000, len(initrd))]
    ends = [(a, a + (n + 1023) // 1024 * 1024) for a, n in ranges]
    if any(a < 0x80000000 or b > 0x90000000 for a, b in ends):
        raise ValueError('Recovery image is outside DDR')
    if any(a < d and c < b for i, (a, b) in enumerate(ends) for c, d in ends[i + 1:]):
        raise ValueError('Recovery images overlap')
    marker = b'bootcmd_mfg='
    at = boot.find(marker)
    end = boot.find(b'\0', at)
    if boot.count(marker) != 1 or end - at < len(b'bootcmd_mfg=mw.l 20d8040 0 2; reset;'):
        raise ValueError('Recovery U-Boot cannot hold the browser exit command')
    return [{'address': a, 'bytes': n} for a, n in ranges]


def audit(bundle_path, trusted_public_key):
    bundle = read_json(bundle_path)
    if bundle.get('schema') != 1 or bundle.get('status') != 'recovery-candidate':
        raise ValueError('Expected a schema 1 recovery-candidate manifest')
    files = read_assets(bundle, bundle_path.parent, INSTALL_ASSETS)
    if files['publicKey'] != trusted_public_key.read_bytes():
        raise ValueError('Candidate public key differs from the trusted release key')
    capsule_path = bundle_path.parent / bundle['assets']['capsule']['path']
    signed = inspect(capsule_path, trusted_public_key)
    if signed.version != parse_version(bundle['version']) or not 1048576 <= len(signed.payload) <= 8388608:
        raise ValueError('Candidate version or physical payload size mismatch')
    ranges = bootstrap_ranges(files)
    history = json.loads(files['baselineHistory'])
    if history.get('schema_version') != 1 or len(history.get('builds', [])) != 1:
        raise ValueError('Expected exactly one baseline history entry')
    entry = history['builds'][0]
    info = inspect_bytes(files['baselineUboot'])
    if (entry.get('artifact') != 'baseline.imx' or
        entry.get('status') not in ('cold-boot-known-good', 'lefony-nand-boot-verified') or
        validation_errors(info, require_nand_handoff=False) or
        any(entry.get(k) != v for k, v in asdict(info).items())):
        raise ValueError('Baseline history does not match the qualified U-Boot bytes')
    return bundle, files, {'schema': 1, 'status': 'recovery-candidate',
        'version': bundle['version'], 'payloadSha256': digest(signed.payload),
        'assets': {k: digest(v) for k, v in files.items()}, 'ramImages': ranges,
        'physicalQualification': 'not-established-by-this-audit'}


def verify_acceptance(path, report):
    record = read_json(path)
    if (record.get('schema') != 1 or record.get('model') != 'HPG2' or
        record.get('qualification') != 'physical-verified' or
        record.get('browserRecovery') != CONTRACT or
        any(record.get(k) != report[k] for k in ('version', 'payloadSha256', 'assets')) or
        not isinstance(record.get('evidence'), str) or not record['evidence'].strip() or
        any(record.get('checks', {}).get(k) is not True for k in CHECKS)):
        raise ValueError('Physical acceptance is incomplete or belongs to different artifacts')
    return record


def assemble(package_path, bundle_path, output, trusted_public_key, acceptance_path=None):
    bundle, files, report = audit(bundle_path, trusted_public_key)
    development = read_json(package_path)
    if (development.get('schema') != 1 or development.get('status') != 'package' or
        development.get('qualification') != 'build-tested' or development.get('model') != 'HPG2' or
        development.get('version') != bundle['version'] or
        not re.fullmatch('[a-f0-9]{40}', development.get('commit', ''))):
        raise ValueError('Expected the matching development release manifest')
    package_files = read_assets(development, package_path.parent, PACKAGE_ASSETS, flat=True)
    if any(files[k] != package_files[k] for k in ('capsule', 'publicKey')):
        raise ValueError('Development release and recovery candidate differ')
    # Explicit corresponding source and notices are required before creating any
    # distribution directory. Private recovery archives alone are not a release.
    source_files = read_assets(bundle, bundle_path.parent, SOURCE_ASSETS)
    record = verify_acceptance(acceptance_path, report) if acceptance_path else None
    files = {**package_files, **files, **source_files}
    descriptors = {**development['assets'], **bundle['assets']}
    descriptors = {k: descriptors[k] for k in files}
    filenames = [a['path'].removeprefix('artifacts/') for a in descriptors.values()]
    if (len(set(filenames)) != len(filenames) or
        set(filenames) & {'lefony-release.json', 'release-notes.md', 'SHA256SUMS'}):
        raise ValueError('Release artifact filenames collide')
    notes = [
        'Lefony for HP Prime G2 with a complete browser recovery environment.',
        'Recovery preserves the existing bootloader and writes only the existing OS slot.',
        'Only calculators matching the included bootloader baseline are supported.',
        ('Browser recovery acceptance covers these exact artifacts.' if record else
         'Recovery candidate only. Physical browser acceptance is still required.'),
    ]
    manifest = {**development, 'publishedAt': datetime.now(timezone.utc).isoformat(),
                'notes': notes, 'assets': descriptors}
    if record:
        manifest.update(status='ready', qualification='physical-verified', browserRecovery=CONTRACT)
        manifest.pop('message', None)
    else:
        manifest['message'] = 'Recovery files are prepared. Browser recovery qualification is pending.'
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.recovery-release-', dir=output.parent) as temporary:
        staging = Path(temporary) / 'release'
        staging.mkdir()
        for key, data in files.items():
            (staging / descriptors[key]['path'].removeprefix('artifacts/')).write_bytes(data)
        (staging / 'lefony-release.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (staging / 'release-notes.md').write_text('\n\n'.join(notes) +
            '\n\n<!-- lefony-release-v1\n' + json.dumps(manifest, separators=(',', ':')) + '\n-->\n')
        (staging / 'SHA256SUMS').write_text(''.join(
            f'{digest(p.read_bytes())}  {p.name}\n' for p in sorted(staging.iterdir())))
        staging.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--public-key', type=Path, default=Path(__file__).resolve().parents[1] / 'ports/lefony-prime-g2/release-signing.pub')
    parser.add_argument('--package', type=Path, help='Existing signed development release manifest')
    parser.add_argument('--output', type=Path, help='New private staging directory; never overwritten')
    parser.add_argument('--acceptance', type=Path, help='Recorded physical acceptance of these exact artifacts')
    args = parser.parse_args()
    if bool(args.package) != bool(args.output) or (args.acceptance and not args.output):
        parser.error('--package and --output are required together; --acceptance needs both')
    result = (assemble(args.package, args.bundle, args.output, args.public_key, args.acceptance)
              if args.output else audit(args.bundle, args.public_key)[2])
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
