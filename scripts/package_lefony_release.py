#!/usr/bin/env python3
"""Package only explicitly selected CI outputs; never recurse through build/.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

from prime_g2_update_capsule import build, inspect, parse_version
from browser_recovery_assets import verified_assets

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    'firmware': 'lefony-os-prime-g2-native.bin',
    'emulator': 'lefony-os-prime-g2-vm-native.elf',
    'source': 'lefony-os-source.tar.gz',
    'capsule': 'lefony-os-prime-g2.lfu',
    'publicKey': 'release-signing.pub',
    'package': 'lefony-os-prime-g2.zip',
}


def describe(path):
    data = path.read_bytes()
    if not data:
        raise ValueError(f'Empty release artifact: {path.name}')
    return {'path': 'artifacts/' + path.name, 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def package(root, output, version, commit, private_key, recovery_directory=None,
            working_tree=False, full_install=False):
    parts = parse_version(version)
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Release needs a full source commit')
    recovery = verified_assets(recovery_directory) if recovery_directory is not None else None
    if full_install and recovery is None:
        raise ValueError('Full installation requires the pinned complete recovery bundle')
    if recovery and set(Path(a['path']).name for a in recovery[0].values()) & set(FILES.values()):
        raise ValueError('Recovery artifact collides with firmware package')
    output.mkdir(parents=True, exist_ok=False)
    public_key = root / 'ports/lefony-prime-g2/release-signing.pub'
    payload = root / 'dist/lefony-os-prime-g2.zImage'
    build(payload, output / FILES['capsule'], parts, private_key)
    signed = inspect(output / FILES['capsule'], public_key)
    if signed.version != parts or len(signed.payload) < 1024 * 1024:
        raise ValueError('Release requires a physical-size signed capsule')
    for name in ('firmware', 'emulator', 'source'):
        shutil.copyfile(root / 'dist' / FILES[name], output / FILES[name])
    shutil.copyfile(public_key, output / FILES['publicKey'])
    notes = [
        'Automatic development build for HP Prime G2.',
        'Host tests and physical/emulator compilation passed; this build has not been physically qualified.',
        'Recovery assets and a qualified bootloader baseline are not included. Website installation remains unavailable.',
    ]
    manifest = {
        'schema': 1, 'status': 'package', 'version': version, 'model': 'HPG2',
        'qualification': 'build-tested', 'commit': commit,
        'publishedAt': datetime.now(timezone.utc).isoformat(), 'notes': notes,
        'message': 'The latest development package is available. Guided installation will open when a qualified recovery bundle is published.',
        'assets': {name: describe(output / filename) for name, filename in FILES.items() if name != 'package'},
    }
    if recovery:
        descriptors, files = recovery
        for name, data in files.items():
            (output / Path(descriptors[name]['path']).name).write_bytes(data)
        manifest['assets'].update(descriptors)
        manifest['browserRecovery'] = {'protocol': 1, 'target': 'single-slot-mtd1', 'development': True}
        notes[2:] = [
            'Includes the pinned public recovery environment for browser installation testing.',
            'Recovery replaces the existing OS slot without a backup and preserves the bootloader.',
            'The installed bootloader must match the included baseline. This does not provision or repartition a stock calculator.',
            'Recovery components and their upstream references/notices are separate downloads in this release.',
        ]
        manifest['message'] = 'Development browser recovery installation is available for testing.'
        if full_install:
            manifest['browserRecovery'] = {'protocol': 2, 'target': 'boot-os-dtb', 'development': True}
            notes[3:5] = [
                'Explicit full recovery installation writes and verifies the bootloader, OS and device tree, including on blank NAND.',
                'This development path uses fixed MTD0/MTD1/MTD2 targets; no A/B repartitioning is performed. Physical power-loss qualification remains open.',
            ]
    if working_tree:
        notes[0] = 'Working-tree development build for HP Prime G2.'
        notes.append('The commit identifies the base revision. The corresponding-source archive contains the exact public working tree and prepared firmware sources used for this build.')
        manifest['sourceState'] = {
            'kind': 'working-tree', 'baseCommit': commit,
            'archiveSha256': manifest['assets']['source']['sha256'],
        }
    # The ZIP contains firmware, signed capsule, emulator ELF and attribution.
    # Full corresponding source is a separate release asset to avoid duplication.
    with zipfile.ZipFile(output / FILES['package'], 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ('firmware', 'emulator', 'capsule', 'publicKey'):
            archive.write(output / FILES[name], FILES[name])
        for path in [root / 'LICENSE.md', root / 'THIRD_PARTY_NOTICES.md', *sorted((root / 'LICENSES').glob('*.txt'))]:
            archive.write(path, str(path.relative_to(root)))
        source_label = 'Base commit' if working_tree else 'Source'
        archive.writestr('README.txt', '\n'.join(notes) + f'\n{source_label}: https://github.com/maikopruett/Lefony-OS/tree/{commit}\nDownload lefony-os-source.tar.gz from this same release for the full prepared source.\n')
        archive.writestr('build.json', json.dumps(manifest, indent=2) + '\n')
    manifest['assets']['package'] = describe(output / FILES['package'])
    (output / 'lefony-release.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'SHA256SUMS').write_text(''.join(f'{describe(path)["sha256"]}  {path.name}\n' for path in sorted(output.iterdir())))
    # Public REST metadata has browser CORS support; release asset downloads don't.
    # Embed the same validated manifest in the release body for discovery.
    (root / 'dist/release-notes.md').write_text('\n'.join(notes) +
        '\n\n<!-- lefony-release-v1\n' + json.dumps(manifest, separators=(',', ':')) + '\n-->\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--private-key', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/release')
    parser.add_argument('--recovery-dir', type=Path, help='Directory containing the exact pinned public recovery files')
    parser.add_argument('--working-tree', action='store_true', help='Identify --commit as the base of the exact working-tree source archive, not a clean source revision')
    parser.add_argument('--full-install', action='store_true', help='Explicitly enable development browser protocol 2 bootloader/OS/device-tree provisioning; requires --recovery-dir')
    args = parser.parse_args()
    package(ROOT, args.output, args.version, args.commit, args.private_key, args.recovery_dir,
            args.working_tree, args.full_install)
