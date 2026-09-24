# SPDX-License-Identifier: GPL-3.0-or-later
"""Linux dependency gates; native loader execution has separate bundle evidence."""
import hashlib
from pathlib import Path
import struct
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_desktop_linux as linux


def elf(path, *, machine=62, elf_type=3, marker=b''):
    header = bytearray(64)
    header[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HH', header, 16, elf_type, machine)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + marker)
    return path


def test_ldd_reads_transitive_dependencies_and_spaces():
    result = linux.parse_ldd('''
    linux-vdso.so.1 (0x7ffe1)
    libdrm.so.2 => /Moved SDK é/_internal/libdrm.so.2 (0xabCD)
    libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x123)
    /lib64/ld-linux-x86-64.so.2 (0x456)
    ''')
    assert result == {
        'libdrm.so.2': Path('/Moved SDK é/_internal/libdrm.so.2'),
        'libc.so.6': Path('/lib/x86_64-linux-gnu/libc.so.6'),
        'ld-linux-x86-64.so.2': Path('/lib64/ld-linux-x86-64.so.2')}
    assert linux.parse_ldd('statically linked') == {}


@pytest.mark.parametrize('output,match', [
    ('libdrm.so.2 => not found', 'Missing Linux dependency: libdrm'),
    ('libfoo.so => relative/path (0x123)', 'Unrecognized'),
    ('../libfoo.so => /lib/foo (0x123)', 'Unrecognized'),
    ('libfoo.so => /one (0x123)\nlibfoo.so => /two (0x456)', 'Conflicting'),
    ('garbled output', 'Unrecognized'),
])
def test_ldd_rejects_missing_conflicting_or_unrecognized_output(output, match):
    with pytest.raises(ValueError, match=match):
        linux.parse_ldd(output)


def test_native_scan_excludes_arm_objects_and_symlink_duplicates(tmp_path):
    helper = elf(tmp_path/'tool')
    elf(tmp_path/'firmware.elf', machine=40)
    elf(tmp_path/'link-object.o', elf_type=1)
    (tmp_path/'readme').write_text('text')
    (tmp_path/'alias').symlink_to('tool')
    assert linux.native_files(tmp_path) == [helper]


def test_collects_graphics_and_transitive_libraries_under_needed_names(tmp_path, monkeypatch):
    tool = elf(tmp_path/'qemu')
    drm = elf(tmp_path/'providers/libdrm.so.2.4.0', marker=b'drm')
    pci = elf(tmp_path/'providers/libpciaccess.so.0.11.1', marker=b'pci')
    monkeypatch.setattr(linux, 'dependencies', lambda _: {
        'libdrm.so.2': drm, 'libpciaccess.so.0': pci,
        'libc.so.6': Path('/system/libc.so.6')})
    output = tmp_path/'libraries'
    report = linux.collect_dependencies([tool], output)
    assert sorted(p.name for p in output.iterdir()) == ['libdrm.so.2', 'libpciaccess.so.0']
    assert (output/'libdrm.so.2').read_bytes() == drm.read_bytes()
    assert report['files']['libpciaccess.so.0']['sha256'] == hashlib.sha256(pci.read_bytes()).hexdigest()
    assert report['system_dependencies'] == ['libc.so.6']
    assert str(tmp_path) not in str(report)
    with pytest.raises(ValueError, match='already exists'):
        linux.collect_dependencies([tool], output)


def test_conflicting_versions_fail_before_copying(tmp_path, monkeypatch):
    one = elf(tmp_path/'one'); two = elf(tmp_path/'two')
    a = elf(tmp_path/'a/libfoo.so.1', marker=b'a')
    b = elf(tmp_path/'b/libfoo.so.1', marker=b'b')
    monkeypatch.setattr(linux, 'dependencies', lambda root: {'libfoo.so.1': a if root == one else b})
    output = tmp_path/'libraries'
    with pytest.raises(ValueError, match='Conflicting Linux library bytes'):
        linux.collect_dependencies([one, two], output)
    assert not output.exists()


def test_dependency_architecture_is_checked(tmp_path, monkeypatch):
    tool = elf(tmp_path/'tool'); wrong = elf(tmp_path/'libfoo.so', machine=183)
    monkeypatch.setattr(linux, 'dependencies', lambda _: {'libfoo.so': wrong})
    with pytest.raises(ValueError, match='wrong architecture'):
        linux.collect_dependencies([tool], tmp_path/'output')


def test_loader_environment_removes_build_host_injections(monkeypatch):
    for name in ('LD_LIBRARY_PATH', 'LD_LIBRARY_PATH_ORIG', 'LD_AUDIT', 'LD_PRELOAD'):
        monkeypatch.setenv(name, '/ambient')
    result = linux.loader_environment()
    assert not any(name in result for name in ('LD_LIBRARY_PATH', 'LD_LIBRARY_PATH_ORIG', 'LD_AUDIT', 'LD_PRELOAD'))
    assert result['LC_ALL'] == 'C'
    assert linux.loader_environment(Path('/bundle é'))['LD_LIBRARY_PATH'] == '/bundle é'


def test_missing_dependency_keeps_name_on_failed_ldd(tmp_path, monkeypatch):
    tool = elf(tmp_path/'tool')
    def run(command, **kwargs):
        assert kwargs['timeout'] == 30
        return subprocess.CompletedProcess(command, 1, 'libdrm.so.2 => not found\n', '')
    monkeypatch.setattr(linux.subprocess, 'run', run)
    with pytest.raises(ValueError, match='Missing Linux dependency: libdrm.so.2'):
        linux.dependencies(tool)


def test_relative_library_paths_remove_build_host_and_keep_wheel_layout(tmp_path):
    bundle = tmp_path/'Moved SDK é'; binary = elf(bundle/'_internal/toolchain/bin/gcc')
    assert linux.relative_search_path(binary, bundle, '/opt/build/lib:$ORIGIN/../lib') == '$ORIGIN:$ORIGIN/../lib:$ORIGIN/../..'
    wheel = elf(bundle/'_internal/PIL/extension.so')
    assert linux.relative_search_path(wheel, bundle, '${ORIGIN}/../pillow.libs') == '$ORIGIN:$ORIGIN/../pillow.libs:$ORIGIN/..'
    assert linux.relative_search_path(wheel, bundle, '$ORIGIN/../../../../outside') == '$ORIGIN:$ORIGIN/..'
    with pytest.raises(ValueError, match='Unsupported'):
        linux.relative_search_path(wheel, bundle, '$ORIGIN/$LIB')


@pytest.mark.parametrize('kind', ['absolute', 'escape', 'broken'])
def test_bundle_rejects_unsafe_symlinks(tmp_path, kind):
    bundle = tmp_path/'bundle'; bundle.mkdir()
    (tmp_path/'outside').write_text('outside')
    (bundle/'target').write_text('inside')
    target = {'absolute': str(bundle/'target'), 'escape': '../outside', 'broken': 'absent'}[kind]
    (bundle/'link').symlink_to(target)
    with pytest.raises(ValueError, match='symlink'):
        linux.checked_links(bundle)


def test_bundle_audit_requires_internal_libraries_for_direct_tools(tmp_path, monkeypatch):
    bundle = tmp_path/'Moved SDK é'; launcher = elf(bundle/'lefony-sdk')
    helper = elf(bundle/'_internal/toolchain/bin/gcc')
    library = elf(bundle/'_internal/libtest.so')
    calls = []
    def dependencies(binary, library_path=None):
        calls.append((binary, library_path))
        return {'libtest.so': library, 'libc.so.6': Path('/lib/libc.so.6')}
    monkeypatch.setattr(linux, 'dependencies', dependencies)
    report = linux.audit_bundle(bundle)
    assert (launcher, None) in calls
    assert (helper, None) in calls
    record = report['files']['_internal/toolchain/bin/gcc']['dependencies']['libtest.so']
    assert record['file'] == '_internal/libtest.so'
    assert report['dynamic_plugins_qualified'] is False
    outside = elf(tmp_path/'external.so')
    library = outside
    with pytest.raises(ValueError, match='external library'):
        linux.audit_bundle(bundle)


def test_helper_relocation_records_changed_hashes(tmp_path, monkeypatch):
    bundle = tmp_path/'bundle'; launcher = elf(bundle/'lefony-sdk', marker=b'embedded archive')
    helper = elf(bundle/'_internal/runtime/qemu'); tool = elf(tmp_path/'patchelf')
    original = launcher.read_bytes(); calls = []
    monkeypatch.setattr(linux, 'relocate_launcher', lambda *args: {'sha256': linux.digest(launcher)})
    monkeypatch.setattr(linux.shutil, 'which', lambda _: str(tool))
    def run(command, **kwargs):
        calls.append(command)
        assert command[-1] == str(helper)
        if '--set-rpath' in command:
            helper.write_bytes(helper.read_bytes() + b'relocated')
        return subprocess.CompletedProcess(command, 0, '/opt/build/lib\n', '')
    monkeypatch.setattr(linux.subprocess, 'run', run)
    report = linux.relocate_bundle(bundle)
    assert launcher.read_bytes() == original
    record = report['files']['_internal/runtime/qemu']
    assert record['input_sha256'] != record['sha256']
    assert record['runpath'] == '$ORIGIN:$ORIGIN/..'
    assert len(calls) == 2


def launcher_archive(tmp_path):
    from PyInstaller.archive.writers import CArchiveWriter
    source = tmp_path/'data.txt';source.write_bytes(b'preserve compressed content\n' * 100)
    archive = tmp_path/'archive.pkg'
    CArchiveWriter(str(archive), [('sample.txt', str(source), True, 'x')], 'libpython3.12.so.1.0')
    bundle = tmp_path/'SDK with spaces é'
    launcher = elf(bundle/'lefony-sdk', marker=b'ELF prefix')
    prefix = launcher.read_bytes();payload = archive.read_bytes()
    launcher.write_bytes(prefix + payload)
    return bundle, launcher, prefix, payload, source.read_bytes()


def fake_launcher_tools(tmp_path, monkeypatch, prefix, payload, *, fail_patch=False, wrong_section=False):
    objcopy = elf(tmp_path/'objcopy')
    monkeypatch.setattr(linux.shutil, 'which', lambda name: str(objcopy))
    def run(command, **kwargs):
        path = Path(command[-1])
        if '--dump-section' in command:
            Path(command[-2].split('=', 1)[1]).write_bytes(b'wrong section' if wrong_section else payload)
        elif '--remove-section' in command:
            path.write_bytes(prefix)
        elif '--add-section' in command:
            data = Path(command[-2].split('=', 1)[1]).read_bytes()
            path.write_bytes(path.read_bytes() + data + b'ELF section table')
        else:
            assert path.read_bytes() == prefix, 'patchelf received the embedded archive'
            if '--set-rpath' in command:
                if fail_patch:raise subprocess.CalledProcessError(1, command)
                assert command[-2] == '$ORIGIN/_internal'
                path.write_bytes(prefix + b'new ELF tables' * 64)
        return subprocess.CompletedProcess(command, 0, '', '')
    monkeypatch.setattr(linux.subprocess, 'run', run)


def test_launcher_relocation_preserves_real_compressed_archive_across_elf_growth(tmp_path, monkeypatch):
    from PyInstaller.archive.readers import CArchiveReader
    bundle, launcher, prefix, payload, content = launcher_archive(tmp_path)
    original = launcher.read_bytes()
    alias = tmp_path/'earlier-launcher';alias.hardlink_to(launcher)
    fake_launcher_tools(tmp_path, monkeypatch, prefix, payload)
    record = linux.relocate_launcher(bundle, '/trusted/patchelf')
    reader = CArchiveReader(str(launcher))
    assert reader.extract('sample.txt') == content
    assert launcher.read_bytes()[reader._start_offset:reader._end_offset] == payload
    assert reader._start_offset > len(prefix)
    assert alias.read_bytes() == original
    assert record['input_sha256'] != record['sha256'] and record['archive_entries'] == 1


def test_failed_launcher_patch_leaves_original_intact(tmp_path, monkeypatch):
    bundle, launcher, prefix, payload, _ = launcher_archive(tmp_path)
    original = launcher.read_bytes()
    fake_launcher_tools(tmp_path, monkeypatch, prefix, payload, fail_patch=True)
    with pytest.raises(subprocess.CalledProcessError):linux.relocate_launcher(bundle, '/trusted/patchelf')
    assert launcher.read_bytes() == original
    assert not list(bundle.glob('.launcher-*'))


def test_launcher_rejects_section_that_does_not_match_archive(tmp_path, monkeypatch):
    bundle, launcher, prefix, payload, _ = launcher_archive(tmp_path)
    original = launcher.read_bytes()
    fake_launcher_tools(tmp_path, monkeypatch, prefix, payload, wrong_section=True)
    with pytest.raises(ValueError, match='section differs'):
        linux.relocate_launcher(bundle, '/unused/patchelf')
    assert launcher.read_bytes() == original


def test_launcher_audit_cannot_hide_system_zlib_with_an_injected_path(tmp_path, monkeypatch):
    bundle = tmp_path/'bundle';launcher = elf(bundle/'lefony-sdk')
    internal = elf(bundle/'_internal/libz.so.1');external = elf(tmp_path/'system/libz.so.1')
    def dependencies(binary, library_path=None):
        if binary == launcher:return {'libz.so.1': internal if library_path else external}
        return {}
    monkeypatch.setattr(linux, 'dependencies', dependencies)
    with pytest.raises(ValueError, match='external library: libz.so.1'):
        linux.audit_bundle(bundle)
