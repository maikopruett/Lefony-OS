#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Production FILE3 loading, saves and package upgrades on signed ARM apps.

Seeds conversion with the real host-compiled storage engine. App runtime writes
then traverse the actual guest engine; no new syscall/capability is claimed.
"""
import hashlib
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / 'ports/lefony-prime-g2/ion/src/prime_g2'
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, lock_value, write_json
from cli import package
from replay import Controls
from runner import exercise
from signing import sign
from workspace import opened


def fixture(directory):
    backend = (ROOT / 'tests/native/app_storage.cpp').read_text()
    (directory / 'app_storage_fixture.h').write_text(
        backend[backend.index('struct PowerCut'):backend.index('static void finish')])
    raw = (ROOT / 'tests/native/app_documents.cpp').read_text()
    (directory / 'app_raw_fixture.h').write_text(raw[raw.index('struct Raw {'):raw.index('\nint main()')])
    flags = ['-DLFS_NO_MALLOC', '-DLFS_NO_DEBUG', '-DLFS_NO_WARN', '-DLFS_NO_ERROR', '-DLFS_NO_ASSERT',
             '-O1', '-g', '-I', str(PORT), '-I', str(directory)]
    objects = []
    for name in ('lfs', 'lfs_util'):
        obj = directory / (name + '.o')
        subprocess.run([shutil.which('cc'), '-std=c99', *flags, '-DLFS_DEFINES=littlefs_compat/defines.h',
                        '-c', str(PORT / f'littlefs/{name}.c'), '-o', str(obj)], check=True, timeout=60)
        objects.append(str(obj))
    binary = directory / 'document-fixture'
    subprocess.run([shutil.which('c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags,
                    str(ROOT / 'tests/native/app_document_fixture.cpp'), str(PORT / 'app_storage.cpp'),
                    str(PORT / 'app_document_store.cpp'), str(PORT / 'app_root_record.cpp'), str(PORT / 'app_file_store.cpp'), str(PORT / 'legacy_app_storage.cpp'),
                    *objects, '-o', str(binary)], check=True, timeout=60)
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files', action='store_true', help='Use FILE4 and preserve a streamed asset across every guest save/upgrade')
    parser.add_argument('--firmware', type=Path, default=ROOT / 'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--output', type=Path, help='Keep candidate evidence separate from previous runs')
    args = parser.parse_args()
    output = args.output or ROOT / ('build/sdk-large-files/arm' if args.files else 'build/sdk-production-documents')
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    firmware = args.firmware.resolve()
    cases = []
    with tempfile.TemporaryDirectory(prefix='lefony-documents-') as temporary:
        directory = Path(temporary)
        reader = fixture(directory)
        project = directory / 'project'
        (project / 'src').mkdir(parents=True)
        (project / 'src/main.cpp').write_text('''
#include <lefony/app.h>
static uint32_t value;
extern "C" void lefony_event(Lefony::Event event,uint32_t first,uint32_t) {
  if(event==Lefony::Event::Start && Lefony::readData(0,&value,4)!=4) asm volatile("udf #0");
  if(event==Lefony::Event::Key && first==static_cast<uint32_t>(Lefony::Key::Confirm)) {
    value++;if(Lefony::writeData(0,&value,4)!=4) asm volatile("udf #0");
  }
  Lefony::fill({0,0,320,240,value==14?Lefony::White:value==15?Lefony::Green:0});
}
''')
        def inspect(overlay):
            result = json.loads(subprocess.check_output([reader, 'inspect', overlay], text=True, timeout=30))
            if args.files:
                expected = hashlib.sha256(bytes((i * 131) & 255 for i in range(128 * 1024 - 128 + 17))).hexdigest()
                assert result['format'] == 4 and result['file_sha256'] == expected
            return result
        for release in (1, 2):
            write_json(project / 'app.json', {'abi': 1, 'id': 'document-arm', 'name': 'Document ARM',
                       'version': f'{release}.0.0', 'license': 'CC-BY-NC-SA-4.0'})
            artifact = package(project)
            signed = sign(artifact.read_bytes(), ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem')
            expected_hash = hashlib.sha256(signed).hexdigest()
            with opened(project, 'documents') as (workspace, _):
                overlay = workspace / 'nand.overlay'
                if release == 1:
                    seeded = directory / 'seed.lfapp';seeded.write_bytes(signed)
                    subprocess.run([reader, 'seed-files' if args.files else 'seed', seeded, overlay], check=True, timeout=30, capture_output=True)
                    initial = inspect(overlay)
                    assert initial['value'] == 14 and initial['package_generation'] == 2
                before = inspect(overlay)
                launched = {}
                def controls(channel):
                    launched.update(inspect(overlay))
                    assert launched['package_sha256'] == expected_hash
                    assert launched['value'] == 13 + release
                    if release == 2:
                        assert launched['pending_upgrade'] == 1 and launched['previous_package'] == before['package_generation']
                    normal = Controls(channel, output)
                    try:
                        normal.run({'steps': [{'capture': f'before-{release}'},
                            {'pixel': [f'before-{release}', 20, 20, [255,255,255] if release == 1 else [33,166,66]]},
                            {'key': 'ok'}, {'capture': f'after-{release}'},
                            {'pixel': [f'after-{release}', 20, 20, [33,166,66] if release == 1 else [0,0,0]]}]}, [])
                    finally:
                        normal.close()
                result = exercise(artifact, qemu, firmware, workspace=workspace, controls=controls)
                assert result['result'] == 1 and result['os_responsive']
                after = inspect(overlay)
                assert after['value'] == 14 + release and after['package_sha256'] == expected_hash
                assert after['package_generation'] == launched['package_generation']
                assert after['data_generation'] != launched['data_generation'] and after['pending_upgrade'] == 0
                assert after['high_version'] == [release, 0, 0]
                cases.append({'release': release, 'before': before, 'launched': launched, 'after': after, 'runtime': result})
                stable_overlay = overlay.read_bytes()
        # Branch from the same accepted release to exercise close policy without
        # replacing a failed release or bypassing the anti-downgrade watermark.
        for mode in ('clean-close', 'schema-mismatch', 'faulted-close'):
            mutation = {
                'clean-close': '',
                'schema-mismatch': 'if(Lefony::writeData(0,&value,4)!=-1) asm volatile("udf #0");',
                'faulted-close': 'value++;if(Lefony::writeData(0,&value,4)!=4) return;asm volatile("udf #0");',
            }[mode]
            (project / 'src/main.cpp').write_text('''
#include <lefony/app.h>
static uint32_t value;
extern "C" void lefony_event(Lefony::Event event,uint32_t first,uint32_t) {
  if(event==Lefony::Event::Start && (Lefony::readData(0,&value,4)!=4 || value!=16)) asm volatile("udf #0");
  if(event==Lefony::Event::Key && first==static_cast<uint32_t>(Lefony::Key::Confirm)) {
    ''' + mutation + '''
    Lefony::fill({0,0,320,240,Lefony::Green});
  }
}
''')
            metadata = {'abi': 1, 'id': 'document-arm', 'name': 'Document ARM',
                        'version': '3.0.0', 'license': 'CC-BY-NC-SA-4.0'}
            if mode == 'schema-mismatch':
                metadata.update(schema=1, minimum_api=1, required_capabilities=0,
                                optional_capabilities=0, data_schema=1)
            write_json(project / 'app.json', metadata)
            # This temporary test project deliberately switches package schemas.
            write_json(project / 'sdk.lock.json', lock_value(ROOT / 'sdk', 1, metadata.get('schema', 0)))
            artifact = package(project)
            signed = sign(artifact.read_bytes(), ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem')
            expected_hash = hashlib.sha256(signed).hexdigest()
            with opened(project, mode) as (workspace, _):
                overlay = workspace / 'nand.overlay'
                overlay.write_bytes(stable_overlay)
                before = inspect(overlay)
                launched = {}
                def controls(channel):
                    launched.update(inspect(overlay))
                    assert launched['pending_upgrade'] == 1 and launched['value'] == 16
                    assert launched['previous_package'] == before['package_generation']
                    assert launched['package_sha256'] == expected_hash
                    normal = Controls(channel, output)
                    try:
                        normal.key('ok')
                        if mode != 'faulted-close':
                            normal.run({'steps': [{'capture': mode}, {'pixel': [mode, 20, 20, [33,166,66]]}]}, [])
                    finally:
                        normal.close()
                result = exercise(artifact, qemu, firmware, workspace=workspace, controls=controls)
                assert result['os_responsive']
                if mode == 'faulted-close':
                    assert result['result'] < 0, result
                else:
                    assert result['result'] == 1, result
                after = inspect(overlay)
                assert after['value'] == 16 and after['data_generation'] == before['data_generation']
                if mode == 'clean-close':
                    assert after['serial'] == launched['serial'] + 1 and after['pending_upgrade'] == 0
                    assert after['previous_package'] == 0 and after['package_sha256'] == expected_hash
                else:
                    assert after == launched, (mode, after, launched)
                cases.append({'case': mode, 'before': before, 'launched': launched, 'after': after, 'runtime': result})
    sources = ['ports/lefony-prime-g2/ion/src/prime_g2/' + name for name in
               ('app_storage.h', 'app_storage.cpp', 'app_document_store.h', 'app_document_store.cpp',
                'app_file_index.h', 'app_file_store.h', 'app_file_store.cpp',
                'app_document_root.h', 'app_root_record.h', 'app_root_record.cpp', 'app_management.cpp')]
    sources += ['tests/native/app_document_fixture.cpp', 'tests/native/app_storage.cpp', 'vm/test-sdk-documents.py']
    write_json(output / 'arm-report.json', {'schema': 1, 'status': 'passed', 'physical': 'not_tested',
               'firmware_sha256': digest(firmware), 'qemu_sha256': digest(qemu),
               'conversion': 'production engine on host synthetic fixture', 'cases': cases,
               'sources': {path: digest(ROOT / path) for path in sources}})
    print('PASS: signed FILE3 ARM load, data-only Close, cold reopen, USB upgrade, schema-0 acceptance, schema mismatch and faulted Close')


if __name__ == '__main__':
    main()
