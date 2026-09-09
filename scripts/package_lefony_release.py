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


def package(root, output, version, commit, private_key):
    parts = parse_version(version)
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Release needs a full source commit')
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
    # The ZIP contains firmware, signed capsule, emulator ELF and attribution.
    # Full corresponding source is a separate release asset to avoid duplication.
    with zipfile.ZipFile(output / FILES['package'], 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ('firmware', 'emulator', 'capsule', 'publicKey'):
            archive.write(output / FILES[name], FILES[name])
        for path in [root / 'LICENSE.md', root / 'THIRD_PARTY_NOTICES.md', *sorted((root / 'LICENSES').glob('*.txt'))]:
            archive.write(path, str(path.relative_to(root)))
        archive.writestr('README.txt', '\n'.join(notes) + f'\nSource: https://github.com/maikopruett/Lefony-OS/tree/{commit}\nDownload lefony-os-source.tar.gz from this same release for the full prepared source.\n')
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
    args = parser.parse_args()
    package(ROOT, args.output, args.version, args.commit, args.private_key)
