#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Collect exact Debian sources for inventoried Linux desktop binary inputs.

Run inside the packaging environment that supplied the inventory. APT verifies
repository metadata; exact source versions and SHA-256 lists select downloads.
Only this output directory is written. No packages are installed or unpacked.
Python wheels and their embedded native libraries require separate collection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
from urllib.parse import urlsplit


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_identity(name, version):
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9+.-]+', name):
        raise ValueError('Invalid Debian source package name')
    if not isinstance(version, str) or not re.fullmatch(r'[0-9][A-Za-z0-9.+:~_-]*', version):
        raise ValueError('Invalid exact Debian source version')
    return name, version


def source_records(text):
    """Read deb822 records without interpreting package-controlled file paths."""
    records = []
    record = {}
    key = None
    for line in text.splitlines() + ['']:
        if not line:
            if record:
                records.append(record)
            record = {}; key = None
        elif line[:1].isspace():
            if key is None:
                raise ValueError('Orphan source metadata continuation')
            record[key] += '\n' + line.strip()
        else:
            key, separator, value = line.partition(':')
            if not separator or key in record:
                raise ValueError('Invalid or repeated source metadata field')
            record[key] = value.strip()
    return records


def source_files(text, name, version):
    source_identity(name, version)
    matches = []
    for record in source_records(text):
        if record.get('Package') != name or record.get('Version') != version:
            continue
        files = {}
        for line in record.get('Checksums-Sha256', '').splitlines():
            if not line:
                continue
            fields = line.split()
            if len(fields) != 3:
                raise ValueError('Invalid source checksum record')
            checksum, size, filename = fields
            if (not re.fullmatch(r'[0-9a-f]{64}', checksum) or not size.isdecimal()
                    or not 0 < int(size) <= 1024 ** 3
                    or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+~-]*', filename)
                    or filename in files):
                raise ValueError('Unsafe or duplicated source file')
            files[filename] = {'sha256': checksum, 'bytes': int(size)}
        if not files or sum(n.endswith('.dsc') for n in files) != 1:
            raise ValueError('Source record needs SHA-256 files and one descriptor')
        matches.append(files)
    if not matches or any(item != matches[0] for item in matches[1:]):
        raise ValueError('Exact source version is missing or conflicting: ' + name + '=' + version)
    return matches[0]


def source_urls(text, files):
    urls = {}
    for line in text.splitlines():
        if not line.startswith("'"):
            continue
        values = shlex.split(line)
        if len(values) != 4:
            raise ValueError('Invalid APT source URI record')
        url, name, size, _ = values
        parsed = urlsplit(url)
        if (name not in files or name in urls or parsed.scheme != 'https'
                or not parsed.hostname or parsed.username or parsed.password
                or size != str(files[name]['bytes'])):
            raise ValueError('APT source URI differs from source metadata')
        urls[name] = url
    if set(urls) != set(files):
        raise ValueError('APT did not select every exact source file')
    return urls


def verify_files(directory, files):
    directory = Path(directory)
    if {p.name for p in directory.iterdir()} != set(files):
        raise ValueError('Downloaded source file set differs from metadata')
    for name, expected in files.items():
        path = directory / name
        if (path.is_symlink() or not path.is_file() or path.stat().st_size != expected['bytes']
                or digest(path) != expected['sha256']):
            raise ValueError('Downloaded source differs from metadata: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repositories', type=Path,
                        default=Path(__file__).with_name('sdk-linux') / 'ubuntu-noble.sources')
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        parser.error('Use the Linux x86-64 packaging environment')
    output = args.output.resolve()
    if output.exists():
        parser.error('Output exists; retain that attempt and choose a new directory')
    inventory = json.loads(args.inventory.read_text(encoding='utf-8'))
    selected = {}
    for item in inventory['inputs']:
        source = Path(item['source'])
        if digest(source) != item['source_sha256']:
            parser.error('Installed binary differs from inventory: ' + str(source))
        origin = item['origin']
        if origin['kind'] != 'debian-package':
            continue
        name, version = source_identity(origin['source_package'], origin['source_version'])
        package = origin['package']
        source_identity(package, origin['version'])
        query = subprocess.check_output(['dpkg-query', '-W',
            '-f=${Package}\t${Version}\t${Architecture}\t${source:Package}\t${source:Version}',
            package], text=True, timeout=10).split('\t')
        if query != [package, origin['version'], 'amd64', name, version]:
            parser.error('Installed package differs from inventory: ' + package)
        selected.setdefault((name, version), set()).add(package)
    if not selected:
        parser.error('Inventory has no Debian native inputs')
    output.mkdir(parents=True)
    shutil.copyfile(__file__, output / Path(__file__).name)
    shutil.copyfile(args.inventory, output / 'native-inputs.json')
    apt = output / 'apt'; apt.mkdir()
    shutil.copyfile(args.repositories, apt / 'repositories.sources')
    for name in ('lists/partial', 'cache/archives/partial', 'empty'):
        (apt / name).mkdir(parents=True)
    options = []
    for value in (f'Dir::Etc::sourcelist={apt}/repositories.sources',
                  f'Dir::Etc::sourceparts={apt}/empty', f'Dir::State::lists={apt}/lists',
                  f'Dir::Cache={apt}/cache', 'Acquire::Languages=none',
                  'Acquire::Retries=0', 'Acquire::https::Timeout=30',
                  'APT::Update::Error-Mode=any'):
        options += ['-o', value]
    logs = output / 'logs'; logs.mkdir()
    commands = []
    def run(label, command, cwd=output, timeout=300):
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        for suffix, data in (('stdout', result.stdout), ('stderr', result.stderr)):
            (logs / (label + '.' + suffix)).write_text(data, encoding='utf-8')
        commands.append({'label': label, 'arguments': list(map(str, command)), 'exit_code': result.returncode})
        (output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        if result.returncode:
            raise RuntimeError(label + ' failed; see retained APT logs')
        return result.stdout
    report = {'schema': 1, 'platform': 'linux-x86_64', 'status': 'collecting',
              'inventory_sha256': digest(args.inventory), 'recipe_sha256': digest(__file__),
              'repositories_sha256': digest(args.repositories), 'components': [],
              'complete_desktop_sources': False,
              'scope': 'Exact Debian inputs only; wheel/native-static and built tool sources remain separate'}
    def save():
        (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    save()
    try:
        run('update', ['apt-get', *options, 'update'])
        for (name, version), packages in sorted(selected.items()):
            text = run(name + '-metadata', ['apt-cache', *options, 'showsrc', '--only-source', name], timeout=30)
            files = source_files(text, name, version)
            command = ['apt-get', *options, '--download-only', '--only-source', 'source', name + '=' + version]
            urls = source_urls(run(name + '-uris', [*command[:1], '--print-uris', *command[1:]], timeout=30), files)
            component = output / ('debian-' + name); component.mkdir()
            archives = component / 'archives'; archives.mkdir()
            run(name + '-download', command, cwd=archives)
            verify_files(archives, files)
            notices = component / 'notices'; notices.mkdir()
            for package in sorted(packages):
                source = Path('/usr/share/doc') / package / 'copyright'
                if not source.is_file():
                    raise ValueError('Missing installed copyright file: ' + package)
                shutil.copyfile(source, notices / (package + '.copyright'))
            report['components'].append({'component': 'debian-' + name, 'version': version,
                'binary_packages': sorted(packages),
                'inputs': [{'file': str((archives / f).relative_to(output)), 'url': urls[f], **data}
                           for f, data in sorted(files.items())],
                'installed_notices': [{'file': str(p.relative_to(output)), 'sha256': digest(p)}
                                      for p in sorted(notices.iterdir())]})
            save(); print('Collected ' + name + '=' + version, flush=True)
        common = output / 'common-licenses'
        shutil.copytree('/usr/share/common-licenses', common, symlinks=False)
        report['common_licenses'] = [{'file': str(p.relative_to(output)), 'sha256': digest(p)}
                                    for p in sorted(common.iterdir()) if p.is_file()]
        report['status'] = 'collected'; save()
    except BaseException as error:
        report.update(status='failed', error=str(error)); save(); raise


if __name__ == '__main__':
    main()
