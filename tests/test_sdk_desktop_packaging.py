# SPDX-License-Identifier: GPL-3.0-or-later
"""PE dependency/relocation/archive gates; no native Windows execution claim."""
import hashlib
import json
from pathlib import Path
import struct
import shutil
import subprocess
import sys
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_desktop_windows as windows
import package_native_desktop as desktop
import build_sdk_gdb as gdb_build


@pytest.mark.parametrize('data,home,expected', [
    (b'unspecified/root/aux', '/root', False),
    (b'/rootfs/root/user', '/root', False),
    (b'nobody\0/root\0../src/basic/utf8.c', '/root', False),
    (b'/root\0', '/root', False),
    (b'/root/private.c\0', '/root', True),
    (b'/root\0/root/private.c\0', '/root', True),
    (b'/root/checkout/qemu.c', '/root', True),
    (b'path=/root/build\0', '/root', True),
    (b'file:///root/build', '/root', True),
    (b'"/Users/' + b'developer/private"', '/Users/developer', True),
    (b'/Users/' + b'developer2/project', '/Users/developer', False),
    (b'config\0/Users/developer\0other', '/Users/developer', True),
    (b'path=C:\\Users\\developer\\source', 'C:\\Users\\developer', True),
    (b'C:\\Users\\developer2\\source', 'C:\\Users\\developer', False),
])
def test_home_path_detection_preserves_absolute_boundaries(data, home, expected):
    assert desktop.contains_home_path(data, home) is expected


def pe_file(path, *, normal=(), delayed=(), forwarded=(), machine=0x8664):
    """Minimal PE32+ with real import, delay-import and export directory bytes.

    The ordinary and delayed descriptors point to separate valid thunk/name
    tables. Tests exercise pefile's real parser, not an injected import list.
    """
    content = bytearray(8192)
    content[:2] = b'MZ'
    struct.pack_into('<I', content, 0x3c, 0x80)
    content[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', content, 0x84, machine, 1, 0, 0, 0, 240, 0x2022)
    optional = 0x98
    struct.pack_into('<H', content, optional, 0x20b)
    struct.pack_into('<Q', content, optional + 24, 0x140000000)
    struct.pack_into('<II', content, optional + 32, 0x1000, 0x200)
    struct.pack_into('<II', content, optional + 56, 0x3000, 0x200)
    struct.pack_into('<I', content, optional + 108, 16)
    section = optional + 240
    content[section:section + 8] = b'.rdata\0\0'
    struct.pack_into('<IIII', content, section + 8, 0x1e00, 0x1000, 0x1e00, 0x200)
    struct.pack_into('<I', content, section + 36, 0x40000040)
    cursor = 0x200

    def allocate(data):
        nonlocal cursor
        offset = cursor
        content[offset:offset + len(data)] = data
        cursor = (offset + len(data) + 7) & ~7
        return offset, offset + 0xe00

    def directory(index, rva, size):
        struct.pack_into('<II', content, optional + 112 + index * 8, rva, size)

    for entries, delayed_table in ((normal, False), (delayed, True)):
        if not entries:
            continue
        stride = 32 if delayed_table else 20
        base, rva = allocate(bytes(stride * (len(entries) + 1)))
        directory(13 if delayed_table else 1, rva, stride * (len(entries) + 1))
        for index, name in enumerate(entries):
            _, name_rva = allocate(name.encode('ascii') + b'\0')
            _, symbol_rva = allocate(b'\0\0example\0')
            _, thunk_rva = allocate(struct.pack('<QQ', symbol_rva, 0))
            if delayed_table:
                struct.pack_into('<8I', content, base + index * stride,
                                 1, name_rva, 0, thunk_rva, thunk_rva, 0, 0, 0)
            else:
                struct.pack_into('<5I', content, base + index * stride,
                                 thunk_rva, 0, 0, name_rva, thunk_rva)
    if forwarded:
        base, rva = allocate(bytes(40))
        table, table_rva = allocate(bytes(4 * len(forwarded)))
        _, name_rva = allocate(b'fixture.dll\0')
        for index, target in enumerate(forwarded):
            _, target_rva = allocate(target.encode('ascii') + b'\0')
            struct.pack_into('<I', content, table + index * 4, target_rva)
        struct.pack_into('<IIHHIIIIIII', content, base, 0, 0, 0, 0, name_rva,
                         1, len(forwarded), 0, table_rva, 0, 0)
        directory(0, rva, cursor - base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


@pytest.fixture
def system(tmp_path):
    folder = tmp_path / 'system'; folder.mkdir()
    (folder / 'KERNEL32.DLL').write_bytes(b'OS file; never bundled or parsed')
    return folder


def test_pe_import_delay_and_forwarder_closure(tmp_path, system):
    tool = pe_file(tmp_path/'input/qemu.exe', normal=['KERNEL32.dll', 'Direct.dll'],
                   delayed=['Delay.dll'], forwarded=['Forwarded.entry'])
    dlls = tmp_path/'dependencies'; dlls.mkdir()
    pe_file(dlls/'direct.DLL', normal=['Nested.dll'])
    pe_file(dlls/'Delay.dll', delayed=['Nested.dll'])
    pe_file(dlls/'Forwarded.dll', forwarded=['KERNEL32.entry'])
    pe_file(dlls/'Nested.dll', normal=['api-ms-win-core-file-l1-2-0.dll'])
    closure = windows.collect_dependencies([tool], [dlls], tmp_path/'collected', system)
    assert len(closure) == 5
    assert set(path.name for path in (tmp_path/'collected').iterdir()) == {
        'direct.dll', 'delay.dll', 'forwarded.dll', 'nested.dll'}
    assert windows.imports(tool) == ['delay.dll', 'direct.dll', 'forwarded.dll', 'kernel32.dll']


@pytest.mark.parametrize('kind', ['normal', 'delayed', 'forwarded'])
def test_missing_dependency_is_fatal_even_in_nonstartup_tables(tmp_path, system, kind):
    values = ['absent.entry'] if kind == 'forwarded' else ['Absent.dll']
    tool = pe_file(tmp_path/'tool.exe', **{kind: values})
    with pytest.raises(ValueError, match='Missing Windows DLL absent.dll'):
        windows.dependency_closure([tool], [], system)


def test_ambient_path_never_supplies_a_dependency(tmp_path, system, monkeypatch):
    tool = pe_file(tmp_path/'input/tool.exe', normal=['External.dll'])
    dll = pe_file(tmp_path/'ambient/External.dll')
    monkeypatch.setenv('PATH', str(dll.parent))
    with pytest.raises(ValueError, match='Missing Windows DLL'):
        windows.dependency_closure([tool], [], system)
    assert len(windows.dependency_closure([tool], [dll.parent], system)) == 2


def test_different_same_named_dlls_are_rejected(tmp_path, system):
    a = pe_file(tmp_path/'a/shared.dll')
    b = pe_file(tmp_path/'b/Shared.dll', normal=['kernel32.dll'])
    tool = pe_file(tmp_path/'tool.exe', normal=['shared.dll'])
    with pytest.raises(ValueError, match='Conflicting Windows DLL'):
        windows.dependency_closure([tool], [a.parent, b.parent], system)
    with pytest.raises(ValueError, match='Conflicting Windows DLL'):
        windows.dependency_closure([a, b], [], system)
    b.write_bytes(a.read_bytes())
    assert len(windows.dependency_closure([tool], [a.parent, b.parent], system)) == 2


@pytest.mark.parametrize('dependency', ['msys-2.0.dll', 'cygwin1.dll', '../escape.dll'])
def test_posix_runtime_and_path_imports_are_rejected(tmp_path, system, dependency):
    tool = pe_file(tmp_path/'tool.exe', normal=[dependency])
    with pytest.raises(ValueError, match='MSYS/Cygwin|Invalid PE dependency'):
        windows.dependency_closure([tool], [], system)


def test_system_files_are_not_redistributable_runtime_fallbacks(tmp_path, system):
    tool = pe_file(tmp_path/'tool.exe', normal=['vcruntime140.dll'])
    pe_file(system/'vcruntime140.dll')
    with pytest.raises(ValueError, match='Missing Windows DLL vcruntime140.dll'):
        windows.dependency_closure([tool], [], system)
    pe_file(tmp_path/'kernel32.dll')
    tool = pe_file(tool, normal=['kernel32.dll'])
    with pytest.raises(ValueError, match='system DLL must not be bundled'):
        windows.dependency_closure([tool], [], system)


@pytest.mark.parametrize('machine', [0x14c, 0xaa64, 0x1c4])
def test_non_x64_host_binary_is_rejected(tmp_path, machine):
    with pytest.raises(ValueError, match='x86-64 PE'):
        windows.imports(pe_file(tmp_path/'wrong.exe', machine=machine))


def test_corrupt_dependency_table_is_not_treated_as_empty(tmp_path):
    path = pe_file(tmp_path/'broken.exe', normal=['kernel32.dll'])
    data = bytearray(path.read_bytes())
    struct.pack_into('<I', data, 0x98 + 112 + 8, 0x7ffffff0)
    path.write_bytes(data)
    with pytest.raises(ValueError, match='Unreadable PE dependency table'):
        windows.imports(path)


def test_partially_corrupt_imports_are_not_silently_omitted(tmp_path):
    path = pe_file(tmp_path/'partial.exe', normal=['kernel32.dll', 'hidden.dll'])
    data = bytearray(path.read_bytes())
    struct.pack_into('<I', data, 0x200 + 20 + 12, 0x7ffffff0)
    path.write_bytes(data)
    with pytest.raises(ValueError, match='Unreadable PE dependency table'):
        windows.imports(path)


def test_relocated_bundle_audit_binds_hashes_and_rejects_missing_dll(tmp_path, system):
    bundle = tmp_path/'Moved SDK é'
    (bundle/'_internal/toolchain/bin').mkdir(parents=True)
    pe_file(bundle/'lefony-sdk.exe', normal=['kernel32.dll'])
    tool = pe_file(bundle/'_internal/runtime/qemu-system-arm.exe', delayed=['libtest.dll'])
    dll = pe_file(bundle/'_internal/runtime/libtest.dll', normal=['kernel32.dll'])
    report = windows.audit_bundle(bundle, system)
    assert report['execution_qualified'] is False
    record = report['files'][tool.relative_to(bundle).as_posix()]
    assert record == {'sha256': hashlib.sha256(tool.read_bytes()).hexdigest(),
                      'imports': {'libtest.dll': '_internal/runtime/libtest.dll'}}
    dll.unlink()
    with pytest.raises(ValueError, match='Missing Windows DLL'):
        windows.audit_bundle(bundle, system)


def test_qemu_and_python_keep_distinct_same_named_dlls(tmp_path, system):
    bundle=tmp_path/'SDK with spaces'
    (bundle/'_internal/toolchain/bin').mkdir(parents=True)
    pe_file(bundle/'lefony-sdk.exe',normal=['kernel32.dll'])
    pe_file(bundle/'_internal/_ctypes.pyd',normal=['libffi-8.dll'])
    python=pe_file(bundle/'_internal/libffi-8.dll',normal=['kernel32.dll'])
    qemu=pe_file(bundle/'_internal/runtime/qemu-system-arm.exe',normal=['libffi-8.dll'])
    mingw=pe_file(bundle/'_internal/runtime/libffi-8.dll',normal=['kernel32.dll'],forwarded=['KERNEL32.example'])
    assert windows.digest(python)!=windows.digest(mingw)
    report=windows.audit_bundle(bundle,system)
    assert report['files']['_internal/_ctypes.pyd']['imports']['libffi-8.dll']=='_internal/libffi-8.dll'
    assert report['files'][qemu.relative_to(bundle).as_posix()]['imports']['libffi-8.dll']=='_internal/runtime/libffi-8.dll'
    mingw.unlink()
    with pytest.raises(ValueError,match='Missing Windows DLL libffi-8.dll'):
        windows.audit_bundle(bundle,system)


@pytest.mark.parametrize('system,machine,version,backend,suffix', [
    ('Windows', 'AMD64', (3, 13), 'Windows', '.exe'),
    ('Windows', 'x86_64', (3, 14), 'Windows', '.exe'),
    ('Darwin', 'arm64', (3, 11), 'macOS', ''),
    ('Linux', 'x86_64', (3, 11), 'SecretService', ''),
])
def test_host_tool_and_credential_selection(system, machine, version, backend, suffix):
    settings = desktop.host_settings(system, machine, version)
    assert settings['suffix'] == suffix and settings['keyring'] == 'keyring.backends.' + backend


@pytest.mark.parametrize('system,machine,version', [
    ('Windows', 'ARM64', (3, 14)), ('Windows', 'x86', (3, 14)),
    ('Windows', 'AMD64', (3, 12)), ('CYGWIN_NT-10.0', 'x86_64', (3, 14)),
])
def test_unsupported_host_fails_before_packaging(system, machine, version):
    with pytest.raises(ValueError):
        desktop.host_settings(system, machine, version)


def test_windows_zip_preserves_complete_bundle_and_names(tmp_path):
    bundle = tmp_path/'lefony-sdk'; bundle.mkdir()
    for name in ('lefony-sdk.exe', '_internal/python314.dll', '_internal/sdk/HOSTS.md'):
        path = bundle/name; path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(name.encode())
    archive = desktop.archive_bundle(bundle, tmp_path, 'Windows', 'AMD64')
    assert archive.name == 'lefony-sdk-windows-x86_64.zip'
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
        assert len(output.namelist()) == 3
        for path in bundle.rglob('*'):
            if path.is_file():
                assert output.read('lefony-sdk/' + path.relative_to(bundle).as_posix()) == path.read_bytes()


def test_unix_archive_retains_symlinks(tmp_path):
    bundle = tmp_path/'lefony-sdk'; bundle.mkdir()
    (bundle/'target').write_text('library')
    (bundle/'link').symlink_to('target')
    archive = desktop.archive_bundle(bundle, tmp_path, 'Darwin', 'arm64')
    with tarfile.open(archive) as output:
        assert output.getmember('lefony-sdk/link').issym()
    with pytest.raises(ValueError, match='symbolic links'):
        desktop.archive_bundle(bundle, tmp_path, 'Windows', 'AMD64')


def test_bundle_smoke_rejects_doctor_success_with_missing_usb(tmp_path, monkeypatch):
    doctor = dict.fromkeys(('qemu', 'vm_firmware', 'objcopy', 'gdb', 'pillow', 'libusb'), True)
    outputs = [json.dumps(doctor), 'QEMU', '--target=arm-none-eabi --without-python', 'OpenSSL']
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, outputs[(len(calls)-1) % 4])
    monkeypatch.setattr(desktop.subprocess, 'run', run)
    settings = desktop.host_settings('Darwin', 'arm64', (3, 14))
    assert desktop.smoke_bundle(tmp_path, settings)['clean_host_qualified'] is False
    assert all(call[1]['timeout'] == 60 and call[1]['check'] for call in calls)
    doctor['libusb'] = False; outputs[0] = json.dumps(doctor)
    with pytest.raises(ValueError, match='missing required runtime'):
        desktop.smoke_bundle(tmp_path, settings)


def test_cross_gdb_requires_explicit_matching_compiler(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match='explicit --cross-prefix'):
        gdb_build.host_configuration(True, None)
    prefix = tmp_path/'cross-'
    for name in ('gcc', 'g++', 'ar', 'ranlib', 'strip', 'windres'):
        path = Path(str(prefix) + name); path.write_bytes(b'fixture'); path.chmod(0o700)
    monkeypatch.setattr(gdb_build.subprocess, 'check_output', lambda *a, **kw: 'x86_64-w64-mingw32\n')
    flags, environment, system, machine, suffix = gdb_build.host_configuration(True, prefix)
    assert flags == ['--host=x86_64-w64-mingw32']
    assert (system, machine, suffix) == ('Windows', 'AMD64', '.exe')
    assert set(environment) == {'CC', 'CXX', 'AR', 'RANLIB', 'STRIP', 'WINDRES'}
    monkeypatch.setattr(gdb_build.subprocess, 'check_output', lambda *a, **kw: 'aarch64-linux-gnu\n')
    with pytest.raises(ValueError, match='x86_64-w64-mingw32'):
        gdb_build.host_configuration(True, prefix)


@pytest.mark.parametrize('failed', [False, True])
def test_gdb_build_scratch_retained_only_on_failure(tmp_path, failed):
    unrelated = tmp_path/'existing-evidence'; unrelated.write_text('keep')
    def build():
        with gdb_build.build_directory(tmp_path, tmp_path) as work:
            assert work.parent == tmp_path
            (work/'config.log').write_text('compiler diagnostics')
            if failed:
                raise RuntimeError('compiler failed')
    if failed:
        with pytest.raises(RuntimeError, match='compiler failed'):
            build()
        work = Path(json.loads((tmp_path/'build-directory.json').read_text())['directory'])
        assert (work/'config.log').read_text() == 'compiler diagnostics'
    else:
        build()
        work = Path(json.loads((tmp_path/'build-directory.json').read_text())['directory'])
        assert not work.exists()
    assert unrelated.read_text() == 'keep'


def test_linux_cross_gdb_rejects_wrong_target_tools(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match='explicit --cross-prefix'):
        gdb_build.host_configuration(False, None, True)
    prefix = tmp_path/'linux-'
    for name in ('gcc', 'g++', 'ar', 'ranlib', 'strip'):
        path = Path(str(prefix) + name); path.write_bytes(b'fixture'); path.chmod(0o700)
    monkeypatch.setattr(gdb_build.subprocess, 'check_output', lambda *a, **kw: 'aarch64-linux-gnu\n')
    with pytest.raises(ValueError, match='x86_64-linux-gnu'):
        gdb_build.host_configuration(False, prefix, True)
    monkeypatch.setattr(gdb_build.subprocess, 'check_output', lambda *a, **kw: 'x86_64-linux-gnu\n')
    flags, environment, system, machine, suffix = gdb_build.host_configuration(False, prefix, True)
    assert flags == ['--host=x86_64-linux-gnu'] and 'WINDRES' not in environment
    assert (system, machine, suffix) == ('Linux', 'x86_64', '')
    with pytest.raises(ValueError, match='one GDB host'):
        gdb_build.host_configuration(True, prefix, True)


def test_public_key_validation_uses_explicit_openssl_without_path(monkeypatch):
    from signing import public_der
    program = shutil.which('openssl')
    assert program, 'The host signing tests require OpenSSL'
    key = ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'
    expected = public_der(key)
    monkeypatch.setenv('PATH', '')
    assert public_der(key, program=program) == expected


@pytest.mark.parametrize('selected', [False, True])
@pytest.mark.parametrize('system,machine', [('Linux','x86_64'), ('Darwin','arm64')])
def test_packaging_requires_explicit_project_sources(monkeypatch, tmp_path, capsys, selected, system, machine):
    monkeypatch.setattr(desktop.platform, 'system', lambda: system)
    monkeypatch.setattr(desktop.platform, 'machine', lambda: machine)
    arguments=['package_native_desktop.py']
    for name in ('toolchain','binutils','public-key','output','openssl','source-materials','newlib','gdb-runtime','libusb','emulator-window'):
        arguments += ['--'+name,str(tmp_path/name)]
    if selected:arguments += ['--project-sources',str(tmp_path/'project-sources.json')]
    monkeypatch.setattr(sys, 'argv', arguments)
    with pytest.raises(SystemExit) as caught:desktop.main()
    assert caught.value.code==2
    error=capsys.readouterr().err
    assert ('missing input:' if selected else 'required: --project-sources') in error
    assert not (tmp_path/'output').exists()
