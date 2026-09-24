# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Windows bundle dependencies, inspected without executing PE inputs.

Only explicit input directories and the native Windows system directory are
searched. Imports, delayed imports and forwarded exports participate in the
closure; DLLs loaded by name at runtime must be supplied as explicit roots.
This build-time audit does not qualify execution, USB drivers or OS versions.
"""
import ctypes
import hashlib
import os
from pathlib import Path
import re
import shutil
import struct


# Windows components, not third-party redistributables (notably VC runtimes).
# Require the actual system file as well; unknown names need explicit inputs.
SYSTEM_DLLS = frozenset(('advapi32 avrt bcrypt bcryptprimitives cabinet cfgmgr32 '
    'comctl32 comdlg32 crypt32 cryptbase cryptnet cryptsp d3d11 d3d12 dbghelp '
    'dnsapi dwmapi dxgi gdi32 hid imm32 iphlpapi kernel32 kernelbase mpr '
    'msimg32 msvcrt ncrypt netapi32 normaliz ntdll ole32 oleaut32 opengl32 '
    'powrprof propsys psapi rpcrt4 secur32 setupapi shell32 shlwapi sspicli '
    'ucrtbase user32 userenv usp10 uxtheme version winhttp wininet winmm '
    'winspool.drv wintrust winusb ws2_32 wtsapi32').split())
SYSTEM_DLLS = frozenset(name if '.' in name else name + '.dll' for name in SYSTEM_DLLS)
API_SET = re.compile(r'(?:api|ext)-ms-win-[a-z0-9-]+-l[0-9]+-[0-9]+-[0-9]+\.dll')


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def system_directory():
    if os.name != 'nt':
        raise ValueError('Windows packaging must run on native Windows')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetSystemDirectoryW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
    kernel.GetSystemDirectoryW.restype = ctypes.c_uint
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel.GetSystemDirectoryW(buffer, len(buffer))
    if not 0 < length < len(buffer):
        raise OSError('Cannot locate the native Windows system directory')
    return Path(buffer.value).resolve()


def dll_name(value):
    try:
        name = value.decode('ascii').lower()
    except UnicodeDecodeError:
        raise ValueError('PE dependency has a non-ASCII name') from None
    if not re.fullmatch(r'[a-z0-9_+.-]+\.(?:dll|drv)', name):
        raise ValueError('Invalid PE dependency name: ' + repr(name))
    if name.startswith(('msys-', 'cyg')):
        raise ValueError('Native Windows tools must not require MSYS/Cygwin: ' + name)
    return name


def imports(path):
    import pefile
    try:
        with pefile.PE(str(path), fast_load=True) as pe:
            if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20b:
                raise ValueError('Windows SDK requires x86-64 PE binaries: ' + path.name)
            warning_count = len(pe.get_warnings())
            pe.parse_data_directories(directories=[
                pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT'],
                pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT'],
                pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT'],
            ])
            if len(pe.get_warnings()) != warning_count:
                raise ValueError('Unreadable PE dependency table: ' + path.name)
            # Do not let a malformed import table silently become no imports.
            for index, attribute in ((1, 'DIRECTORY_ENTRY_IMPORT'),
                                     (13, 'DIRECTORY_ENTRY_DELAY_IMPORT'),
                                     (0, 'DIRECTORY_ENTRY_EXPORT')):
                directory = pe.OPTIONAL_HEADER.DATA_DIRECTORY[index]
                if directory.VirtualAddress and not hasattr(pe, attribute):
                    raise ValueError('Unreadable PE dependency table: ' + path.name)
            for index, attribute, stride, name_offset in (
                    (1, 'DIRECTORY_ENTRY_IMPORT', 20, 12),
                    (13, 'DIRECTORY_ENTRY_DELAY_IMPORT', 32, 4)):
                directory = pe.OPTIONAL_HEADER.DATA_DIRECTORY[index]
                if not directory.VirtualAddress:
                    continue
                declared = []
                for offset in range(0, min(directory.Size, 10000 * stride), stride):
                    data = pe.get_data(directory.VirtualAddress + offset, stride)
                    if len(data) != stride:
                        raise ValueError('Unreadable PE dependency table: ' + path.name)
                    if not any(data):
                        break
                    # PE32+ delay descriptors must use RVAs, not 32-bit VAs.
                    if index == 13 and struct.unpack_from('<I', data)[0] != 1:
                        raise ValueError('Unsupported PE delay-import addresses: ' + path.name)
                    name_rva = struct.unpack_from('<I', data, name_offset)[0]
                    name = pe.get_string_at_rva(name_rva, 256)
                    if not name:
                        raise ValueError('Unreadable PE dependency table: ' + path.name)
                    declared.append(dll_name(name))
                else:
                    raise ValueError('Unterminated PE dependency table: ' + path.name)
                parsed = [dll_name(entry.dll) for entry in getattr(pe, attribute, [])]
                if declared != parsed:
                    raise ValueError('Unreadable PE dependency table: ' + path.name)
            names = {dll_name(entry.dll) for attribute in
                     ('DIRECTORY_ENTRY_IMPORT', 'DIRECTORY_ENTRY_DELAY_IMPORT')
                     for entry in getattr(pe, attribute, [])}
            exports = getattr(pe, 'DIRECTORY_ENTRY_EXPORT', None)
            if exports:
                for symbol in exports.symbols:
                    if symbol.forwarder:
                        module, separator, target = symbol.forwarder.rpartition(b'.')
                        if not separator or not target:
                            raise ValueError('Invalid PE forwarded export: ' + path.name)
                        names.add(dll_name(module if module.lower().endswith(b'.dll') else module + b'.dll'))
            return sorted(names)
    except pefile.PEFormatError as exc:
        raise ValueError('Invalid Windows PE input: ' + path.name) from exc


def native_files(folder):
    return sorted(path for path in folder.rglob('*')
                  if path.is_file() and path.suffix.lower() in ('.exe', '.dll', '.drv', '.pyd'))


def directory_index(directory):
    files = {}
    if not directory.is_dir():
        raise ValueError('Missing DLL directory: ' + str(directory))
    for path in directory.iterdir():
        if path.is_file():
            name = path.name.lower()
            if name in files:
                raise ValueError('Case-colliding Windows input: ' + name)
            files[name] = path.resolve()
    return files


def dependency_closure(roots, search_directories, system):
    """Return every non-system dependency, rejecting ambiguous flattened DLLs."""
    directories = {}
    def index(directory):
        directory = directory.resolve()
        if directory not in directories:
            directories[directory] = directory_index(directory)
        return directories[directory]
    system_files = index(system)
    explicit = [index(path) for path in dict.fromkeys(search_directories)]
    pending = list(roots)
    seen = {}
    dlls = {}
    while pending:
        path = pending.pop().resolve()
        if path in seen:
            continue
        if not path.is_file():
            raise ValueError('Missing Windows binary: ' + str(path))
        file_hash = digest(path)
        if path.suffix.lower() in ('.dll', '.drv'):
            name = dll_name(path.name.encode('ascii'))
            previous = dlls.get(name)
            if previous and previous[1] != file_hash:
                raise ValueError('Conflicting Windows DLL inputs: ' + name)
            dlls[name] = (path, file_hash)
        dependencies = {}
        for name in imports(path):
            if API_SET.fullmatch(name):
                dependencies[name] = None
                continue
            candidates = list(dict.fromkeys(table[name] for table in
                              [index(path.parent), *explicit] if name in table))
            if name in SYSTEM_DLLS and name in system_files:
                if candidates:
                    raise ValueError('Windows system DLL must not be bundled: ' + name)
                dependencies[name] = None
                continue
            if not candidates:
                raise ValueError('Missing Windows DLL ' + name + ' required by ' + path.name)
            if len({digest(candidate) for candidate in candidates}) != 1:
                raise ValueError('Conflicting Windows DLL inputs: ' + name)
            dependencies[name] = candidates[0]
            pending.append(candidates[0])
        seen[path] = {'sha256': file_hash, 'imports': dependencies}
    return seen


def collect_dependencies(roots, search_directories, destination, system):
    closure = dependency_closure(roots, search_directories, system)
    destination.mkdir(parents=True, exist_ok=False)
    for path in closure:
        if path.suffix.lower() in ('.dll', '.drv'):
            shutil.copyfile(path, destination / path.name.lower())
    return closure


def audit_bundle(bundle, system):
    internal = bundle / '_internal'
    qemu = internal / 'runtime'
    all_files = native_files(bundle)
    # QEMU is a separate process with its own application-directory DLLs.
    # CPython and GLib can require different libraries with identical names.
    qemu_files = [p for p in all_files if p.is_relative_to(qemu)]
    parent_files = [p for p in all_files if not p.is_relative_to(qemu)]
    closure = dependency_closure(parent_files, [internal, internal / 'toolchain/bin'], system)
    qemu_closure = dependency_closure(qemu_files, [qemu], system) if qemu_files else {}
    for path in qemu_closure:
        if not path.is_relative_to(qemu.resolve()):
            raise ValueError('QEMU dependency escaped its isolated runtime: ' + path.name)
    closure.update(qemu_closure)
    report = {}
    for path, record in sorted(closure.items()):
        if not path.is_relative_to(bundle.resolve()):
            raise ValueError('Windows dependency escaped the bundle: ' + path.name)
        report[path.relative_to(bundle.resolve()).as_posix()] = {
            'sha256': record['sha256'],
            'imports': {name: dependency.relative_to(bundle.resolve()).as_posix()
                        if dependency else 'windows-system'
                        for name, dependency in record['imports'].items()},
        }
    return {'schema': 1, 'architecture': 'x86_64', 'files': report,
            'execution_qualified': False, 'dynamic_loads': 'explicit inputs only',
            'process_scopes': {'sdk': '_internal', 'qemu': '_internal/runtime'}}
