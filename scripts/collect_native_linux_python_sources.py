#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Collect exact Python sdists and installed metadata for a Linux SDK freeze.

Run in the packaging image, using its pip installation report and actual native
input inventory. Embedded native/static source closure remains separate.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import shutil
from urllib.parse import urlsplit

from collect_native_desktop_sources import collect_python


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name):
        raise ValueError('Invalid Python distribution name')
    return re.sub(r'[-_.]+', '-', name).lower()


def wheel_identity(download):
    url = download['url']
    parsed = urlsplit(url)
    checksum = download['archive_info']['hashes']['sha256']
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or not parsed.path.endswith('.whl') or not re.fullmatch(r'[0-9a-f]{64}', checksum)):
        raise ValueError('Expected an exact HTTPS wheel and SHA-256')
    return url, checksum


def metadata_root(entry):
    path = Path(str(entry))
    for index, part in enumerate(path.parts):
        if part.endswith('.dist-info'):
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe installed metadata path')
            return Path(*path.parts[:index + 1])
    return None


def validate_inputs(report, inventory):
    if inventory.get('status') != 'passed' or not inventory.get('inputs'):
        raise ValueError('A passing native input inventory is required')
    selected = {}
    for item in report['install']:
        name = canonical(item['metadata']['name'])
        if name in selected:
            raise ValueError('Repeated distribution in pip report: ' + name)
        version = item['metadata']['version']
        if not isinstance(version, str) or importlib.metadata.version(name) != version:
            raise ValueError('Installed Python version differs from pip report: ' + name)
        wheel_identity(item['download_info'])
        selected[name] = item
    if not selected:
        raise ValueError('Pip report has no installed wheels')
    for item in inventory['inputs']:
        if digest(item['source']) != item['source_sha256']:
            raise ValueError('Installed native input differs from inventory: ' + item['target'])
        origin = item['origin']
        if origin['kind'] == 'python-wheel':
            name = canonical(origin['name'])
            expected = selected.get(name)
            if (expected is None or expected['metadata']['version'] != origin['version']
                    or wheel_identity(expected['download_info']) != wheel_identity(origin['download'])):
                raise ValueError('Native input wheel differs from pip report: ' + name)
        elif origin['kind'] != 'debian-package':
            raise ValueError('Unmapped native input origin')
    return selected


def collect(install_report, inventory_path, output):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('Use the Linux x86-64 packaging environment')
    if output.exists():
        raise ValueError('Output exists; retain that attempt and choose a new directory')
    selected = validate_inputs(json.loads(install_report.read_text()), json.loads(inventory_path.read_text()))
    output.mkdir(parents=True)
    shutil.copyfile(install_report, output / 'install-report.json')
    shutil.copyfile(inventory_path, output / 'native-inputs.json')
    recipes = []
    for name in (Path(__file__).name, 'collect_native_desktop_sources.py', 'pillow_native_sources.py'):
        source = Path(__file__).with_name(name)
        shutil.copyfile(source, output / name)
        recipes.append({'file': name, 'sha256': digest(source)})
    manifest = {'schema': 1, 'platform': 'linux-x86_64', 'status': 'collecting',
                'install_report_sha256': digest(install_report), 'inventory_sha256': digest(inventory_path),
                'recipes': recipes, 'components': [], 'complete_desktop_sources': False,
                'scope': 'Python sdists and installed wheel metadata only; embedded native/static and tool sources remain separate'}
    def save():
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    save()
    try:
        for name, wheel in sorted(selected.items()):
            component, = collect_python(output, names={name})
            component['installed_wheel'] = wheel['download_info']
            metadata = output / name / 'installed-metadata'; metadata.mkdir()
            entries = []
            distribution = importlib.metadata.distribution(name)
            for entry in distribution.files or []:
                relative_root = metadata_root(entry)
                if relative_root is None:
                    continue
                source = Path(distribution.locate_file(entry))
                root = Path(distribution.locate_file(relative_root)).resolve()
                if (not source.resolve().is_relative_to(root)
                        or not source.is_file() or source.stat().st_size > 8 * 1024 * 1024):
                    raise ValueError('Missing or oversized installed metadata: ' + str(entry))
                target = metadata / (hashlib.sha256(str(entry).encode()).hexdigest()[:16] + '-' + source.name)
                shutil.copyfile(source, target)
                entries.append({'file': str(target.relative_to(output)), 'installed_path': str(entry), 'sha256': digest(target)})
                if source.name.upper().startswith(('LICENSE', 'COPYING', 'COPYRIGHT', 'NOTICE', 'AUTHORS')):
                    notices = component.setdefault('installed_notices', [])
                    if not any(item['sha256'] == digest(target) for item in notices):
                        notice = output / name / 'notices' / ('metadata-' + target.name)
                        shutil.copyfile(target, notice)
                        notices.append({'file': str(notice.relative_to(output)), 'sha256': digest(notice)})
            component['installed_metadata'] = entries
            manifest['components'].append(component); save()
            print('Collected ' + name + '=' + component['version'], flush=True)
        manifest['status'] = 'collected'; save()
    except BaseException as error:
        manifest.update(status='failed', error=str(error)); save(); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-report', required=True, type=Path)
    parser.add_argument('--inventory', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    collect(args.install_report, args.inventory, args.output.resolve())
