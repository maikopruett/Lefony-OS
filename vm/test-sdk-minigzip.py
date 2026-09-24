#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the existing minigzip C tool on signed ARM packages and real FILE4 data."""
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
from build import digest, write_json
from cli import package
from replay import Controls
from runner import exercise
from source import collect, extract
from workspace import opened


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/sdk-minigzip/arm')
    parser.add_argument('--firmware',type=Path,default=ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--measure-resources',action='store_true')
    parser.add_argument('--profile-heap',action='store_true',help='Build the temporary project with newlib heap diagnostics; requires --measure-resources')
    args = parser.parse_args()
    if args.profile_heap and not args.measure_resources:parser.error('--profile-heap requires --measure-resources')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    prepare = runpy.run_path(str(ROOT / 'scripts/prepare_sdk_minigzip.py'))['prepare']
    spec = json.loads((ROOT / 'sdk/ports/minigzip/source.json').read_text())
    archive = ROOT / ('build/sdk-1.0-upstream/zlib-' + spec['version'] + '.tar.gz')
    cases = []
    with tempfile.TemporaryDirectory(prefix='lefony-minigzip-') as temp:
        folder = Path(temp)
        project = folder / 'Existing C tool é'
        prepare(project, archive, ['input.dat'])
        if args.profile_heap:
            config=json.loads((project/'project.json').read_text())
            config.setdefault('defines',{})['LEFONY_PROFILE_HEAP']=1
            write_json(project/'project.json',config)
        helper = folder / 'helper'
        helper.mkdir()
        fixture = runpy.run_path(str(ROOT / 'vm/test-sdk-documents.py'))['fixture'](helper)
        # Mixed repeated and deterministic non-repeating data; input and gzip
        # output both exceed the legacy 64 KiB store and transfer boundaries.
        data = b''.join(hashlib.sha256(i.to_bytes(4, 'little')).digest() for i in range(8193))
        (output / 'input.dat').write_bytes(data)
        known = gzip.compress(data, mtime=0)
        (output / 'known.gz').write_bytes(known)
        (output / 'truncated.gz').write_bytes(known[:-8])
        corrupt = bytearray(known)
        corrupt[-8] ^= 1  # CRC corruption; content and trailer are both checked.
        (output / 'corrupt.gz').write_bytes(corrupt)
        previous = b'previous committed destination\n'
        (output / 'previous').write_bytes(previous)

        with opened(project, 'files') as (workspace, _):
            def put(name, path):
                subprocess.run([fixture, 'put-file', workspace / 'nand.overlay', 'minigzip', name, path],
                               check=True, timeout=90, stdout=subprocess.DEVNULL)
                copied = folder / 'seed-check'
                subprocess.run([fixture, 'export-file', workspace / 'nand.overlay', 'minigzip', name, copied],
                               check=True, timeout=90, stdout=subprocess.DEVNULL)
                assert copied.read_bytes() == path.read_bytes(), 'seeded file content differs from fixture'

            def read(name, destination):
                path = output / destination
                subprocess.run([fixture, 'export-file', workspace / 'nand.overlay', 'minigzip', name, path],
                               check=True, timeout=90, stdout=subprocess.DEVNULL)
                return path.read_bytes()

            def run(name, arguments, status, version=None):
                config = json.loads((project / 'project.json').read_text())
                config['arguments'] = arguments
                write_json(project / 'project.json', config)
                metadata = json.loads((project / 'app.json').read_text())
                metadata['version'] = '0.1.' + str(len(cases) if version is None else version)
                write_json(project / 'app.json', metadata)
                app = package(project)
                retained = output / name
                retained.mkdir(exist_ok=True)
                for entry in ('app-debug.elf', 'app.elf', 'app.map', app.name, 'build.json'):
                    shutil.copyfile(project / 'build' / entry, retained / entry)
                for entry in ('app.json', 'project.json', 'sdk.lock.json'):
                    shutil.copyfile(project / entry, retained / entry)
                measured = {}
                def controls(channel):
                    normal = Controls(channel, retained)
                    try:
                        start = time.monotonic()
                        while not int(channel.command('APP DIAG 15').split()[1]):
                            fault = int(channel.command('APP DIAG 9').split()[1])
                            assert fault == 0, ('ARM minigzip fault', fault, channel.command('APP DIAG 10'))
                            assert time.monotonic() - start < 120, 'minigzip completion deadline'
                            time.sleep(.025)
                        code = int(channel.command('APP DIAG 21').split()[1])
                        if code >= 2**31: code -= 2**32
                        assert code == status, (name, code, status)
                        measured.update(exit_status=code, modeled_wall_seconds=time.monotonic()-start,
                                        preemptions=int(channel.command('APP DIAG 12').split()[1]))
                        normal.key('home')
                    finally:
                        normal.close()
                result = exercise(app, ROOT / 'build/qemu-prime-g2/qemu-system-arm',
                                  args.firmware, workspace=workspace, controls=controls, measure_resources=args.measure_resources)
                assert result['result'] == 1 and result['os_responsive'], result
                if args.profile_heap:assert result['resources']['heap']['status'] in ('observed','not_observed'),result
                cases.append({'case': name, 'runtime': result, **measured})
                write_json(output / 'progress.json', {'status': 'in_progress', 'cases': cases})
                print('PASS:', name, flush=True)

            run('missing-input', ['input.dat'], 1)
            put('input.dat', output / 'input.dat')
            run('compress-large-file', ['input.dat'], 0)
            compressed = read('input.dat.gz', 'arm.gz')
            assert len(compressed) > 65536 and gzip.decompress(compressed) == data
            # The next invocation cold-boots and installs an ordinary higher
            # package version, preserving the same app's FILE4 data.
            run('cold-decompress-update', ['-d', 'input.dat.gz'], 0)
            assert read('input.dat', 'arm-output.dat') == data
            put('known.gz', output / 'known.gz')
            run('host-produced-gzip', ['-d', 'known.gz'], 0)
            assert read('known', 'known-output.dat') == data
            for kind in ('truncated', 'corrupt'):
                put(kind + '.gz', output / (kind + '.gz'))
                put(kind, output / 'previous')
                failed_version = len(cases)
                run(kind + '-input', ['-d', kind + '.gz'], 1)
                assert read(kind, kind + '-retained') == previous
                assert read(kind + '.gz', kind + '-retained.gz') == (output / (kind + '.gz')).read_bytes()
                failed_package = cases[-1]['runtime']['package_sha256']
                # Nonzero first-run exit deliberately retains pending upgrade
                # recovery state. Fix the fixture input and retry the identical
                # package before asking the installer for another version.
                put(kind + '.gz', output / 'known.gz')
                run(kind + '-corrected-retry', ['-d', kind + '.gz'], 0, version=failed_version)
                assert cases[-1]['runtime']['package_sha256'] == failed_package
                assert read(kind, kind + '-corrected') == data
            run('path-error', ['-d', '../outside.gz'], 1)
            source = collect(project, 2)
            (output / 'minigzip.lfsrc').write_bytes(source)
            restored = folder / 'Restored C project'
            extract(source, restored)
            original = (project / 'build/app.elf').read_bytes()
            package(restored)
            assert (restored / 'build/app.elf').read_bytes() == original
            report = {'schema': 1, 'status': 'passed', 'physical': 'not_tested',
                      'program': spec['program'], 'version': spec['version'],
                      'archive_sha256': spec['archive_sha256'], 'cases': cases,
                      'input': {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()},
                      'compressed': {'bytes': len(compressed), 'sha256': hashlib.sha256(compressed).hexdigest()},
                      'source_roundtrip': 'identical ARM image', 'source_sha256': digest(output / 'minigzip.lfsrc'),
                      'sources': {name: digest(ROOT / name) for name in (
                          'scripts/prepare_sdk_minigzip.py', 'sdk/ports/minigzip/source.json',
                          'sdk/tools/build.py', 'sdk/lib/newlib/files.c', 'sdk/lib/newlib/start.c',
                          'vm/test-sdk-minigzip.py', 'tests/native/app_document_fixture.cpp')}}
            write_json(output / 'report.json', report)
    print('PASS: existing minigzip, streamed gzip, cold upgrade/reopen, corrupt/truncated errors and exact source rebuild', flush=True)


if __name__ == '__main__':
    main()
