# SPDX-License-Identifier: GPL-3.0-or-later
"""Collect Linux helper libraries and verify relocatable native SDK tools.

The input executables are trusted build artifacts; ldd inspects their actual
loader resolution. Host glibc and its loader remain system requirements. Other
linked libraries must resolve inside the assembled bundle, including libraries
excluded by PyInstaller's default graphics-library policy.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

SYSTEM = frozenset(('libc.so.6', 'libm.so.6', 'libdl.so.2', 'libpthread.so.0',
    'librt.so.1', 'libresolv.so.2', 'libutil.so.1', 'ld-linux-x86-64.so.2'))


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def native(path):
    with path.open('rb') as stream:
        header = stream.read(64)
    return (len(header) == 64 and header[:6] == b'\x7fELF\x02\x01'
            and int.from_bytes(header[16:18], 'little') in (2, 3)
            and int.from_bytes(header[18:20], 'little') == 62)


def native_files(directory):
    return [path for path in sorted(directory.rglob('*'))
            if path.is_file() and not path.is_symlink() and native(path)]


def parse_ldd(text):
    files = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line in ('statically linked', 'not a dynamic executable'):
            continue
        if re.fullmatch(r'linux-vdso\.so\.1 \(0x[0-9a-fA-F]+\)', line):
            continue
        if '=> not found' in line:
            raise ValueError('Missing Linux dependency: ' + line.split(' =>', 1)[0])
        mapped = re.fullmatch(r'([A-Za-z0-9_.+-]+) => (/.+) \(0x[0-9a-fA-F]+\)', line)
        loader = re.fullmatch(r'(/.+/ld-linux-x86-64\.so\.2) \(0x[0-9a-fA-F]+\)', line)
        if mapped:
            name, path = mapped.groups()
        elif loader:
            path = loader.group(1); name = 'ld-linux-x86-64.so.2'
        else:
            raise ValueError('Unrecognized Linux loader output: ' + line)
        if name in files and files[name] != Path(path):
            raise ValueError('Conflicting Linux loader resolution: ' + name)
        files[name] = Path(path)
    return files


def loader_environment(library_path=None):
    environment = dict(os.environ)
    for name in ('LD_LIBRARY_PATH', 'LD_LIBRARY_PATH_ORIG', 'LD_PRELOAD', 'LD_AUDIT'):
        environment.pop(name, None)
    environment['LC_ALL'] = 'C'
    if library_path is not None:
        environment['LD_LIBRARY_PATH'] = str(library_path)
    return environment


def dependencies(binary, library_path=None):
    binary = binary.resolve()
    if any(character in str(binary) for character in ('\n', '\r', '\0')) or not native(binary):
        raise ValueError('Linux dependency input is not an x86-64 ELF program: ' + binary.name)
    result = subprocess.run(['ldd', str(binary)], capture_output=True, text=True,
        encoding='utf-8', errors='strict', env=loader_environment(library_path), timeout=30)
    # Preserve the missing SONAME even when the loader returns a nonzero code.
    if '=> not found' in result.stdout:
        parse_ldd(result.stdout)
    if result.returncode and result.stdout.strip() not in ('statically linked', 'not a dynamic executable'):
        raise ValueError('Linux loader inspection failed: ' + binary.name + ': ' +
                         (result.stderr or result.stdout).strip())
    return parse_ldd(result.stdout)


def collect_dependencies(roots, output):
    if output.exists():
        raise ValueError('Linux dependency output already exists')
    providers = {}; system = set(); inputs = []
    for root in roots:
        inputs.append({'file': root.name, 'sha256': digest(root)})
        for name, path in dependencies(root).items():
            if name in SYSTEM:
                system.add(name); continue
            path = path.resolve()
            if not path.is_file() or not native(path):
                raise ValueError('Linux library is missing or has the wrong architecture: ' + name)
            checksum = digest(path)
            if name in providers and providers[name][1] != checksum:
                raise ValueError('Conflicting Linux library bytes: ' + name)
            providers[name] = (path, checksum)
    output.mkdir(parents=True)
    files = {}
    for name, (source, checksum) in sorted(providers.items()):
        shutil.copy2(source, output / name)
        if digest(output / name) != checksum:
            raise ValueError('Copied Linux library changed: ' + name)
        files[name] = {'source_basename': source.name, 'sha256': checksum,
                       'bytes': source.stat().st_size}
    return {'schema': 1, 'platform': 'linux-x86_64', 'roots': inputs,
            'files': files, 'system_dependencies': sorted(system)}


def checked_links(bundle):
    bundle = bundle.resolve()
    for path in bundle.rglob('*'):
        if path.is_symlink() and (not path.exists() or not path.resolve().is_relative_to(bundle)
                                  or Path(os.readlink(path)).is_absolute()):
            raise ValueError('Linux bundle has a broken, absolute or escaping symlink: ' + str(path.relative_to(bundle)))


def relative_search_path(binary, bundle, previous):
    bundle = bundle.resolve(); binary = binary.resolve(); paths = ['$ORIGIN']
    for value in previous.split(':'):
        value = value.replace('${ORIGIN}', '$ORIGIN')
        if value == '$ORIGIN' or value.startswith('$ORIGIN/'):
            suffix = value[len('$ORIGIN'):].lstrip('/')
            if '$' in suffix or any(character in suffix for character in ('\n', '\r', '\0')):
                raise ValueError('Unsupported Linux relative library path')
            if (binary.parent / suffix).resolve().is_relative_to(bundle):
                paths.append(value)
    relative = os.path.relpath(bundle / '_internal', binary.parent)
    paths.append('$ORIGIN' if relative == '.' else '$ORIGIN/' + relative)
    return ':'.join(dict.fromkeys(paths))


def relocate_launcher(bundle, tool):
    """Give the ELF loader a bundle path before the frozen Python runtime starts.

    PyInstaller stores its archive in an ELF pydata section. Remove that section
    before patchelf rewrites the ELF, then reattach the exact archive using the
    same objcopy mechanism as PyInstaller. Verify every entry before replacement.
    """
    from PyInstaller.archive.readers import CArchiveReader
    binary = bundle / 'lefony-sdk'
    before = digest(binary)
    raw = binary.read_bytes()
    archive = CArchiveReader(str(binary))
    if not native(binary) or not 64 <= archive._start_offset < archive._end_offset <= len(raw):
        raise ValueError('Unsupported Linux launcher archive layout')
    objcopy = shutil.which('objcopy')
    if objcopy is None:
        raise ValueError('Linux launcher relocation requires objcopy')
    payload = raw[archive._start_offset:archive._end_offset]
    entries = {name: hashlib.sha256(archive.extract(name)).hexdigest() for name in archive.toc}
    with tempfile.TemporaryDirectory(prefix='.launcher-', dir=bundle) as temporary:
        patched = Path(temporary) / 'lefony-sdk'
        data = Path(temporary) / 'pydata'
        shutil.copy2(binary, patched)
        subprocess.run([objcopy, '--dump-section', 'pydata=' + str(data), str(patched)],
            capture_output=True, check=True, timeout=30)
        if data.read_bytes() != payload:
            raise ValueError('Linux launcher pydata section differs from its archive')
        subprocess.run([objcopy, '--remove-section', 'pydata', str(patched)],
            capture_output=True, check=True, timeout=30)
        result = subprocess.run([tool, '--print-rpath', str(patched)], capture_output=True,
            text=True, encoding='utf-8', check=True, timeout=30)
        previous = result.stdout.rstrip('\n')
        wanted = '$ORIGIN/_internal'
        if previous != wanted:
            subprocess.run([tool, '--set-rpath', wanted, str(patched)], capture_output=True,
                check=True, timeout=30)
        subprocess.run([objcopy, '--add-section', 'pydata=' + str(data), str(patched)],
            capture_output=True, check=True, timeout=30)
        recovered = CArchiveReader(str(patched))
        if (not 64 <= recovered._start_offset < recovered._end_offset <= patched.stat().st_size
                or patched.read_bytes()[recovered._start_offset:recovered._end_offset] != payload
                or recovered.toc != archive.toc or recovered.options != archive.options
                or {name: hashlib.sha256(recovered.extract(name)).hexdigest() for name in recovered.toc} != entries):
            raise ValueError('Linux launcher relocation changed its embedded archive')
        # Replacing also avoids altering an earlier candidate through hardlinks.
        patched.replace(binary)
    return {'input_sha256': before, 'sha256': digest(binary), 'runpath': wanted,
            'archive_sha256': hashlib.sha256(payload).hexdigest(), 'archive_entries': len(entries),
            'objcopy_sha256': digest(Path(objcopy).resolve())}


def relocate_bundle(bundle):
    bundle = bundle.resolve(); checked_links(bundle)
    tool = shutil.which('patchelf')
    if tool is None:
        raise ValueError('Linux packaging requires patchelf')
    records = {'lefony-sdk': relocate_launcher(bundle, tool)}
    # Patch ordinary ELF helpers/libraries, including directly invoked GCC.
    for binary in native_files(bundle / '_internal'):
        before = digest(binary)
        result = subprocess.run([tool, '--print-rpath', str(binary)], capture_output=True,
            text=True, encoding='utf-8', check=True, timeout=30)
        previous = result.stdout.rstrip('\n')
        wanted = relative_search_path(binary, bundle, previous)
        if previous != wanted:
            subprocess.run([tool, '--set-rpath', wanted, str(binary)], capture_output=True,
                check=True, timeout=30)
        records[binary.relative_to(bundle).as_posix()] = {
            'input_sha256': before, 'sha256': digest(binary), 'runpath': wanted}
    return {'schema': 1, 'platform': 'linux-x86_64', 'patchelf_sha256': digest(Path(tool).resolve()),
            'files': records}


def audit_bundle(bundle):
    bundle = bundle.resolve(); checked_links(bundle); records = {}; system = set()
    for binary in native_files(bundle):
        linked = {}
        # The initial ELF loader runs before PyInstaller can change its process
        # environment. Every executable, including the launcher, must resolve
        # its dependencies without injected LD_LIBRARY_PATH.
        for name, provider in dependencies(binary).items():
            if name in SYSTEM:
                system.add(name); linked[name] = {'system': True}; continue
            provider = provider.resolve()
            if not provider.is_relative_to(bundle):
                raise ValueError('Linux bundle relies on an external library: ' + name + ' for ' + str(binary.relative_to(bundle)))
            linked[name] = {'file': provider.relative_to(bundle).as_posix(), 'sha256': digest(provider)}
        records[binary.relative_to(bundle).as_posix()] = {'sha256': digest(binary), 'dependencies': linked}
    return {'schema': 1, 'platform': 'linux-x86_64', 'files': records,
            'system_dependencies': sorted(system), 'dynamic_plugins_qualified': False}
