#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Minigzip public file exchange, full quota, real heap pressure and Home cleanup."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
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

LIMIT = 32 * 1024 * 1024
PRESSURE = '''// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// Synthetic qualification input: consume real app heap without replacing malloc.
#include <stdlib.h>
volatile unsigned lefony_pressure_bytes;
static void *held[256];
__attribute__((constructor)) static void pressure(void) {
    unsigned count;
    for (count=0;count<256;count++) {
        held[count]=malloc(32768);
        if (!held[count]) break;
        lefony_pressure_bytes+=32768;
    }
    if (count) {free(held[count-1]);lefony_pressure_bytes-=32768;}
}
'''


def observe(normal, elf, expressions, folder, name):
    """Pause/read/detach only: no calls, breakpoints, registers or memory writes."""
    endpoint = Path(normal.channel.socket.getpeername()).parent / 'minigzip-gdb'
    normal.execute('human-monitor-command', {'command-line': 'gdbserver unix:' + str(endpoint) + ',server=on,wait=off'})
    script = folder / (name + '.gdb')
    script.write_text('set pagination off\nset confirm off\nfile ' + json.dumps(str(elf.resolve())) +
                      '\ntarget remote ' + str(endpoint) + '\n' +
                      ''.join('print ' + e + '\n' for e in expressions) + 'detach\nquit\n')
    result = subprocess.run([shutil.which('arm-none-eabi-gdb'), '-q', '-nx', '-batch', '-x', str(script)],
                            capture_output=True, text=True, timeout=30)
    (folder / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', nargs='+', help='Run named cases from the fixed workload set')
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True)
    firmware = args.firmware.resolve()
    qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    spec = json.loads((ROOT / 'sdk/ports/minigzip/source.json').read_text())
    archive = ROOT / ('build/sdk-1.0-upstream/zlib-' + spec['version'] + '.tar.gz')
    prepare = runpy.run_path(str(ROOT / 'scripts/prepare_sdk_minigzip.py'))['prepare']
    inputs = b''.join(hashlib.sha256(i.to_bytes(4, 'little')).digest() for i in range(8193))
    known = gzip.compress(inputs, compresslevel=6, mtime=0)
    bad = bytearray(known); bad[-8] ^= 1
    old = b'Previous committed destination\n'
    sentinel = b'Existing legacy partial file; not owned by this invocation\n'
    definitions = [
        ('compress', False, inputs, old, False, False, False, False),
        ('decompress', True, known, old, False, False, False, False),
        ('empty-compress', False, b'', old, False, False, False, False),
        ('empty-decompress', True, gzip.compress(b'', mtime=0), old, False, False, False, False),
        ('stdout', False, inputs, old, False, True, False, False),
        ('stdin', False, inputs, old, False, True, False, False),
        ('quota-compress', False, inputs, bytes(len(known)), True, False, False, False),
        ('quota-footer', False, inputs, bytes(len(known)-1), True, True, False, False),
        ('quota-replace', True, known, bytes(len(inputs)), True, False, False, False),
        ('quota-growth', True, known, old, True, True, False, False),
        ('corrupt', True, bytes(bad), old, False, True, False, False),
        ('truncated', True, known[:-8], old, False, True, False, False),
        ('heap-compress', False, inputs, old, False, True, True, False),
        ('heap-decompress', True, known, old, False, True, True, False),
        ('home', False, inputs * 8, old, False, False, False, True),
    ]
    assert len({d[0] for d in definitions}) == len(definitions), 'Duplicate workload name'
    if args.cases:
        assert set(args.cases) <= {d[0] for d in definitions}, 'Unknown workload case'
        definitions = [d for d in definitions if d[0] in args.cases]
    source_names = ['scripts/prepare_sdk_minigzip.py', 'sdk/ports/minigzip/source.json',
                    'vm/test-sdk-minigzip-workflows.py', 'sdk/lib/newlib/files.c']
    report = {'schema': 1, 'status': 'running', 'physical': 'not_tested', 'sdk_sha256': identity(ROOT / 'sdk'),
              'firmware_sha256': digest(firmware), 'qemu_sha256': digest(qemu), 'cases': [],
              'sources': {n: digest(ROOT / n) for n in source_names}}
    write_json(output / 'report.json', report)
    try:
        with tempfile.TemporaryDirectory(prefix='minigzip-workflows-') as temp:
            directory = Path(temp); helper = directory / 'helper'; helper.mkdir()
            fixture = runpy.run_path(str(ROOT / 'vm/test-sdk-documents.py'))['fixture'](helper)
            for name, decompress, data, previous, quota, failure, pressure, interrupt in definitions:
                project = directory / name
                input_name, output_name = ('input.gz', 'input') if decompress else ('input', 'input.gz')
                arguments = ['-c', input_name] if name == 'stdout' else [] if name == 'stdin' else ['-d', input_name] if decompress else [input_name]
                prepare(project, archive, arguments)
                if pressure:
                    (project / 'src/pressure.c').write_text(PRESSURE)
                    config = json.loads((project / 'project.json').read_text())
                    config['sources'].append('src/pressure.c'); write_json(project / 'project.json', config)
                artifact = package(project, 'debug'); retained = output / name; retained.mkdir()
                for n in ('app-debug.elf', 'build.json', artifact.name):
                    shutil.copyfile(project / 'build' / n, retained / n)
                phases = (['seed'] if quota else []) + ['initial', 'cold']
                if name in ('quota-growth', 'corrupt', 'truncated'): phases += ['retry', 'retry-cold']
                with opened(project, 'user-files') as (workspace, _):
                    for phase in phases:
                        folder = retained / phase; folder.mkdir(); measured = {}
                        before = {}
                        if quota and phase == 'initial':
                            filler = directory / 'filler'
                            filler.write_bytes(bytes(LIMIT - len(data) - len(previous) - len(sentinel)))
                            subprocess.run([fixture, 'put-file', workspace / 'nand.overlay', 'minigzip', 'filler', filler],
                                           check=True, stdout=subprocess.DEVNULL, timeout=90)
                        def import_bytes(client, path, value, replace=False):
                            local = folder / ('import-' + path); local.write_bytes(value)
                            measured.setdefault('imports', []).append(FileClient(client).import_file('minigzip', path, local, replace=replace))
                        def setup(client):
                            if phase == 'initial':
                                for path, value in ((input_name, data), (output_name, previous), ('legacy.part', sentinel)):
                                    import_bytes(client, path, value)
                            elif phase == 'retry':
                                if quota: import_bytes(client, 'filler', b'', replace=True)
                                else: import_bytes(client, input_name, known, replace=True)
                            before.update(FileClient(client).info('minigzip'))
                            if quota and phase == 'initial': assert before['quota_committed_bytes'] == LIMIT
                            # Cold inspection happens before the program can consume or replace files.
                            if phase in ('cold', 'retry-cold'):
                                for path in (output_name, 'legacy.part'):
                                    FileClient(client).export_file('minigzip', path, folder / ('before-' + path))
                                assert (folder / 'before-legacy.part').read_bytes() == sentinel
                                expected = (retained / ('initial' if phase == 'cold' else 'retry') / 'output').read_bytes()
                                assert (folder / ('before-' + output_name)).read_bytes() == expected
                        def controls(channel):
                            normal = Controls(channel, folder)
                            try:
                                started = time.monotonic()
                                if interrupt and phase == 'initial':
                                    owner = "'PrimeG2::AppManagement::(anonymous namespace)::"
                                    expressions = [owner + "sFiles'.m_phase", owner + "sVolume'.m_files.m_position"]
                                    sample = 0
                                    while True:
                                        sample += 1
                                        assert channel.command('APP DIAG 15') == 'VALUE 0', 'Work completed before interruption'
                                        text = observe(normal, firmware.with_name(firmware.stem + '-debug.elf'), expressions,
                                                       folder, 'write-progress-' + str(sample))
                                        match = re.search(r'\$2 = (\d+)', text)
                                        if match and int(match[1]) >= 32768 and re.search(r'Phase::(?:Read|Write)\b', text):
                                            measured['interrupted_after_staged_bytes'] = int(match[1]); break
                                        assert time.monotonic() - started < 90, 'No in-progress write observed'
                                else:
                                    while channel.command('APP DIAG 15') == 'VALUE 0':
                                        assert channel.command('APP DIAG 9') == 'VALUE 0', 'ARM app fault'
                                        assert time.monotonic() - started < 180, 'Program completion deadline'
                                        time.sleep(.025)
                                    code = int(channel.command('APP DIAG 21').split()[1]); measured['exit_status'] = code
                                    expected_status = 1 if phase == 'seed' or pressure or (failure and phase in ('initial', 'cold')) or phase == 'retry-cold' or (phase == 'cold' and not interrupt) else 0
                                    assert code == expected_status, (name, phase, code, expected_status)
                                    if pressure:
                                        text = observe(normal, retained / 'app-debug.elf', ['lefony_pressure_bytes'], folder, 'heap')
                                        used = int(re.search(r'\$1 = (\d+)', text)[1]); assert used > 7 * 1024 * 1024
                                        measured['retained_heap_bytes'] = used
                                measured['program_wall_seconds'] = time.monotonic() - started
                                assert channel.command('APP DIAG 9') == 'VALUE 0'
                                normal.key('home'); channel.wait_for_storage(timeout=60)
                                files = FileClient(channel.app_client); after = files.info('minigzip')
                                entries = {e['path'] for e in files.list('minigzip')['entries']}
                                if phase == 'seed': assert not entries; return
                                for path, target in ((output_name, 'output'), ('legacy.part', 'legacy.part')):
                                    files.export_file('minigzip', path, folder / target)
                                assert (folder / 'legacy.part').read_bytes() == sentinel
                                kept = pressure or (failure and phase in ('initial', 'cold')) or (interrupt and phase == 'initial')
                                if kept:
                                    assert (folder / 'output').read_bytes() == previous
                                    assert after['generation'] == before['generation'], 'Failed/aborted output changed committed root'
                                    files.export_file('minigzip', input_name, folder / 'input-retained')
                                    assert (folder / 'input-retained').read_bytes() == data
                                else:
                                    content = (folder / 'output').read_bytes()
                                    expected = inputs if name in ('corrupt', 'truncated') else gzip.decompress(data) if decompress else data
                                    assert (content if decompress else gzip.decompress(content)) == expected
                                    assert input_name not in entries, 'Successful conversion did not remove input'
                                assert entries == {output_name, 'legacy.part'} | ({input_name} if kept else set()) | ({'filler'} if quota else set())
                                if phase == 'retry-cold' or (phase == 'cold' and not interrupt):
                                    assert after['generation'] == before['generation'], 'Cold failed launch changed committed data'
                                measured.update(before=before, after=after, output_sha256=digest(folder / 'output'), entries=sorted(entries))
                            finally: normal.close()
                        result = exercise(artifact, qemu, firmware, workspace=workspace, prepare_workspace=setup, controls=controls)
                        assert result['result'] == 1 and result['os_responsive'], result
                        preceding = next((c for c in report['cases'] if c['case'] == name), None)
                        if preceding:
                            assert result['package_sha256'] == preceding['runtime']['package_sha256'], 'Retry changed the installed package'
                        report['cases'].append({'case': name, 'phase': phase, 'runtime': result, **measured})
                        write_json(output / 'report.json', report); print('PASS:', name, phase, flush=True)
            assert report['sources'] == {n: digest(ROOT / n) for n in source_names}, 'Source changed during validation'
            assert report['sdk_sha256'] == identity(ROOT / 'sdk'), 'SDK changed during validation'
            report['status'] = 'passed'; write_json(output / 'report.json', report)
    except Exception as exc:
        report.update(status='failed', error=str(exc)); write_json(output / 'report.json', report); raise


if __name__ == '__main__':
    main()
