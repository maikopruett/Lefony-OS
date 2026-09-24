#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual minigzip ARM reads under modeled BCH errors and full shared media.

Offline setup only uses disposable PG2OVL1 storage and the production littlefs
engine. The guest keeps the normal heap, file adapters and commit/abort paths.
A constructor gate allows QEMU fault setup before main; it replaces no syscall.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, identity, write_json
from cli import package
from files_device import FileClient
from replay import Controls
from runner import exercise
from workspace import opened

CASES = ('read-compress', 'read-decompress', 'corrected-compress', 'full-compress', 'full-decompress')
GATE = '''// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// Emulator qualification only: pause before main until model setup is ready.
#include <lefony/foreground.h>
volatile unsigned lefony_media_gate;
__attribute__((constructor)) static void media_ready(void) {
  while (!lefony_media_gate) lefony_program_yield();
}
'''


def qtest(normal, command):
    normal.qtest.file.write((command + '\n').encode())
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        reply = normal.qtest.file.readline(4096)
        if reply.startswith(b'IRQ'): continue
        assert reply.startswith(b'OK'), (command, reply)
        return reply.decode().strip()
    raise TimeoutError('QEMU fault-register command timed out')


def fault(normal, info, kind):
    # These are the existing QEMU model's test registers, not physical NAND
    # controls. Address provenance: prime_g2/registers.h and the QEMU model.
    values = ((0x01806134, info['page']), (0x01806138, info['page_offset'] | 1 << 16),
              (0x01806130, kind))
    result = []
    for address, value in values:
        write = qtest(normal, f'writel {address:#x} {value:#x}')
        read = qtest(normal, f'readl {address:#x}')
        assert int(read.split()[1], 16) == value, (address, value, read)
        result.append({'address': address, 'value': value, 'write': write, 'read': read})
    return result


def release(normal, elf, folder):
    endpoint = normal.channel.session_directory / 'media-gdb'
    normal.execute('human-monitor-command', {'command-line': 'gdbserver unix:' + str(endpoint) + ',server=on,wait=off'})
    script = folder / 'start.gdb'
    script.write_text('set pagination off\nset confirm off\nfile ' + json.dumps(str(elf)) +
        '\ntarget remote ' + str(endpoint) + '\nset variable lefony_media_gate=1\nprint lefony_media_gate\ndetach\nquit\n')
    result = subprocess.run([shutil.which('arm-none-eabi-gdb'), '-q', '-nx', '-batch', '-x', str(script)],
                            capture_output=True, text=True, timeout=30)
    (folder / 'start.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and '$1 = 1' in result.stdout, result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', nargs='+', choices=CASES)
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True)
    firmware = args.firmware.resolve(); qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    source_names = ['vm/test-sdk-minigzip-media.py', 'tests/native/app_document_fixture.cpp',
                    'tests/native/app_storage.cpp', 'tests/native/app_documents.cpp', 'vm/test-sdk-documents.py',
                    'scripts/prepare_sdk_minigzip.py', 'sdk/ports/minigzip/source.json']
    report = {'schema': 1, 'status': 'running', 'physical': 'not_tested', 'sdk_sha256': identity(ROOT / 'sdk'),
              'firmware_sha256': digest(firmware), 'qemu_sha256': digest(qemu), 'cases': [],
              'sources': {n: digest(ROOT / n) for n in source_names}}
    write_json(output / 'report.json', report)
    raw = b''.join(hashlib.sha256(i.to_bytes(4, 'little')).digest() for i in range(8193))
    compressed = gzip.compress(raw, mtime=0)
    previous = b'Previous committed destination\n'; sentinel = b'Unrelated existing file\n'
    spec = json.loads((ROOT / 'sdk/ports/minigzip/source.json').read_text())
    archive = ROOT / ('build/sdk-1.0-upstream/zlib-' + spec['version'] + '.tar.gz')
    prepare = runpy.run_path(str(ROOT / 'scripts/prepare_sdk_minigzip.py'))['prepare']
    try:
        with tempfile.TemporaryDirectory(prefix='lefony-media-') as temp:
            directory = Path(temp); helper = directory / 'helper'; helper.mkdir()
            fixture = runpy.run_path(str(ROOT / 'vm/test-sdk-documents.py'))['fixture'](helper)
            for case in args.cases or CASES:
                decompress = case.endswith('decompress'); full = case.startswith('full-'); corrected = case.startswith('corrected-')
                input_name, output_name = ('input.gz', 'input') if decompress else ('input', 'input.gz')
                content = compressed if decompress else raw
                project = directory / case; prepare(project, archive, ['-d', input_name] if decompress else [input_name])
                (project / 'src/media_gate.c').write_text(GATE)
                config = json.loads((project / 'project.json').read_text());config['sources'].append('src/media_gate.c')
                write_json(project / 'project.json', config)
                artifact = package(project, 'debug'); retained = output / case; retained.mkdir()
                for name in ('app-debug.elf', 'build.json', artifact.name): shutil.copyfile(project / 'build' / name, retained / name)
                for name in ('app.json', 'project.json', 'sdk.lock.json'): shutil.copyfile(project / name, retained / name)
                shutil.copyfile(project / 'src/media_gate.c', retained / 'media_gate.c')
                phases = ['seed', 'initial', 'cold'] + ([] if corrected else ['retry', 'retry-cold'])
                with opened(project, 'media') as (workspace, _):
                    media = None
                    for phase in phases:
                        folder = retained / phase;folder.mkdir();measured = {};before = {}
                        if phase == 'initial':
                            if full:
                                measured['fill'] = json.loads(subprocess.check_output([fixture, 'fill-shared', workspace / 'nand.overlay'], text=True, timeout=90))
                                assert measured['fill']['available'] == 0
                            else:
                                image_hash = digest(workspace / 'nand.overlay')
                                media = json.loads(subprocess.check_output([fixture, 'file-media', workspace / 'nand.overlay',
                                    'minigzip', input_name, str(128 * 1024 - 128 + 65536)], text=True, timeout=30))
                                assert digest(workspace / 'nand.overlay') == image_hash, 'Inspection changed storage'
                                write_json(retained / 'input-media.json', media)
                        if phase == 'retry' and full:
                            measured['release'] = json.loads(subprocess.check_output([fixture, 'release-shared', workspace / 'nand.overlay'], text=True, timeout=90))
                            assert measured['release']['available'] > 1024 * 1024
                        def setup(client):
                            if phase == 'seed': return
                            files = FileClient(client);before.update(files.info('minigzip'))
                            assert before['quota_committed_bytes'] < 1024 * 1024
                            if full and phase in ('initial', 'cold'): assert before['shared_available_bytes'] == 0
                            files.export_file('minigzip', output_name, folder / 'before-output')
                            expected = previous if phase == 'initial' or not corrected and phase in ('cold', 'retry') else (raw if decompress else gzip.compress(raw, mtime=0))
                            got = (folder / 'before-output').read_bytes()
                            if expected == previous: assert got == previous
                            else: assert (got if decompress else gzip.decompress(got)) == raw
                        def controls(channel):
                            normal = Controls(channel, folder)
                            try:
                                injected = not full and phase in ('initial', 'cold') and (not corrected or phase == 'initial')
                                if injected: measured['fault_registers'] = fault(normal, media, 1 if corrected else 2)
                                release(normal, retained / 'app-debug.elf', folder)
                                start = time.monotonic()
                                while channel.command('APP DIAG 15') == 'VALUE 0':
                                    assert channel.command('APP DIAG 9') == 'VALUE 0', 'ARM app fault'
                                    assert time.monotonic() - start < 180, 'Media workload deadline'
                                    time.sleep(.025)
                                code = int(channel.command('APP DIAG 21').split()[1])
                                expected = 0 if phase == 'retry' or corrected and phase == 'initial' else 1
                                assert code == expected, (case, phase, code, expected)
                                measured.update(exit_status=code, program_wall_seconds=time.monotonic() - start)
                                if injected: measured['fault_clear'] = fault(normal, media, 0)
                                normal.key('home');channel.wait_for_storage(timeout=60)
                                files = FileClient(channel.app_client)
                                if phase == 'seed':
                                    for path, value in ((input_name, content), (output_name, previous), ('legacy.part', sentinel)):
                                        local = folder / ('import-' + path);local.write_bytes(value)
                                        files.import_file('minigzip', path, local)
                                    measured['seed'] = files.info('minigzip');return
                                after = files.info('minigzip');entries = {e['path'] for e in files.list('minigzip')['entries']}
                                for path, name in ((output_name, 'output'), ('legacy.part', 'sentinel')):
                                    files.export_file('minigzip', path, folder / name)
                                assert (folder / 'sentinel').read_bytes() == sentinel
                                failed = not corrected and phase in ('initial', 'cold')
                                if failed:
                                    assert (folder / 'output').read_bytes() == previous and after['generation'] == before['generation']
                                    files.export_file('minigzip', input_name, folder / 'input-retained')
                                    assert (folder / 'input-retained').read_bytes() == content
                                else:
                                    got = (folder / 'output').read_bytes();assert (got if decompress else gzip.decompress(got)) == raw
                                assert entries == {output_name, 'legacy.part'} | ({input_name} if failed else set())
                                if phase in ('retry-cold',) or corrected and phase == 'cold': assert after['generation'] == before['generation']
                                measured.update(before=before, after=after, output_sha256=digest(folder / 'output'), entries=sorted(entries))
                            finally: normal.close()
                        result = exercise(artifact, qemu, firmware, workspace=workspace, prepare_workspace=setup, controls=controls)
                        assert result['result'] == 1 and result['os_responsive'], result
                        report['cases'].append({'case': case, 'phase': phase, 'runtime': result, **measured})
                        write_json(output / 'report.json', report);print('PASS:', case, phase, flush=True)
        assert report['sources'] == {n: digest(ROOT / n) for n in source_names}, 'Source changed during validation'
        assert report['sdk_sha256'] == identity(ROOT / 'sdk'), 'SDK changed during validation'
        report['status'] = 'passed';write_json(output / 'report.json', report)
    except BaseException as exc:
        report.update(status='failed', error=str(exc));write_json(output / 'report.json', report);raise


if __name__ == '__main__': main()
