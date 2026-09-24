# SPDX-License-Identifier: GPL-3.0-or-later
"""Retain and verify the Windows OpenSSL candidate's relocatable runtime data."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def checked_file(root, name, expected):
    relative = PurePosixPath(name)
    if (not name or relative.is_absolute() or '..' in relative.parts or
            relative.as_posix() != name or ':' in name or '\\' in name):
        raise ValueError('Invalid OpenSSL candidate path: ' + name)
    path = root / name
    chain = [root.joinpath(*relative.parts[:index]) for index in range(len(relative.parts) + 1)]
    if (any(part.is_symlink() for part in chain)
            or not path.is_file() or not path.resolve().is_relative_to(root.resolve())
            or digest(path) != expected):
        raise ValueError('OpenSSL candidate file differs: ' + name)
    return path


def verify_candidate(candidate, executable, sources=None):
    candidate = candidate.resolve()
    report = json.loads((candidate/'candidate.json').read_text(encoding='utf-8'))
    if (report.get('schema') != 1 or report.get('status') != 'passed' or
            report.get('platform') != 'Windows' or report.get('architecture') != 'AMD64'):
        raise ValueError('Require a passed Windows x86-64 OpenSSL candidate')
    files = report.get('files', {})
    required = {'bin/openssl.exe', 'bin/libcrypto-3-x64.dll', 'bin/libssl-3-x64.dll',
                'ssl/openssl.cnf', 'lib/ossl-modules/legacy.dll', 'lib/engines-3/capi.dll'}
    if not required <= files.keys():
        raise ValueError('OpenSSL candidate lacks required runtime files')
    install = candidate/'install'
    actual = {p.relative_to(install).as_posix() for p in install.rglob('*') if p.is_file()}
    if actual != files.keys() or any(p.is_symlink() for p in install.rglob('*')):
        raise ValueError('OpenSSL installed file set differs from candidate')
    for name, expected in files.items():
        checked_file(install, name, expected)
    if executable.resolve() != (install/'bin/openssl.exe').resolve():
        raise ValueError('--openssl must select the verified candidate executable')
    for key, directory in (('source_files', candidate/'sources'), ('recipes', candidate)):
        entries = report.get(key, {})
        if not entries:
            raise ValueError('OpenSSL candidate lacks ' + key)
        for name, expected in entries.items():
            checked_file(directory, name, expected)
    if sources is not None:
        components = [c for c in sources['components'] if c['component'] == 'windows-openssl']
        expected = {*report['source_files'].values(), *report['recipes'].values()}
        if (len(components) != 1 or components[0].get('version') != report['version'] or
                not expected <= {item['sha256'] for item in components[0]['inputs']}):
            raise ValueError('Windows OpenSSL corresponding sources differ from candidate')
    return report


def stage_runtime(candidate, report, destination):
    """Copy runtime data and dynamically loaded DLLs; rehash after copying."""
    destination.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, expected in report['files'].items():
        if not name.startswith(('ssl/', 'lib/ossl-modules/', 'lib/engines-3/')):
            continue
        source = checked_file(candidate/'install', name, expected)
        target = destination/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        checked_file(destination, name, expected)
        files[name] = expected
    return {'schema': 1, 'candidate_sha256': digest(candidate/'candidate.json'),
            'version': report['version'], 'files': files, 'native_execution_qualified': False}


def verify_runtime(destination, record):
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    if actual != record['files'].keys() or any(p.is_symlink() for p in destination.rglob('*')):
        raise ValueError('Bundled OpenSSL runtime file set differs')
    for name, expected in record['files'].items():
        checked_file(destination, name, expected)
