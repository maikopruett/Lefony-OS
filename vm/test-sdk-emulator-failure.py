#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Frozen macOS ARM launches, restored media and a real QEMU startup failure."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import identity, write_json
from archive_format import inspect
from preview_data import Checkpoints, PUBLIC


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert sys.platform == 'darwin', 'This qualification uses the macOS sandbox'
    bundle = args.bundle.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, output / Path(__file__).name)
    for line in (bundle / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        assert digest(bundle / name) == expected, name
    sdk_identity = identity(bundle / '_internal/sdk')
    assert sdk_identity == identity(ROOT / 'sdk')
    report = {'schema': 1, 'status': 'running', 'sdk_sha256': sdk_identity,
              'bundle_checksums_sha256': digest(bundle / 'SHA256SUMS'),
              'candidate': json.loads((bundle / 'candidate.json').read_text(encoding='utf-8')),
              'commands': [], 'cases': [], 'physical': 'not_tested',
              'network_checkout_homebrew': 'denied'}
    write_json(output / 'report.json', report)
    profile = ('(version 1)(allow default)(deny network-outbound (remote ip "*:*"))'
               '(deny file-read* (subpath "/opt/homebrew"))'
               '(deny process-exec (subpath "/opt/homebrew"))'
               f'(deny file-read* (subpath {json.dumps(str(ROOT))}))')
    environment = {**os.environ, 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'}
    with tempfile.TemporaryDirectory(prefix='lf-failure-', dir='/tmp') as directory:
        folder = Path(directory)
        relocated = folder / 'SDK with spaces é'
        shutil.copytree(bundle, relocated, symlinks=True)
        project = folder / 'Pocket Lab é'
        projects = [(project, 'project')]

        def command(*arguments, expected=0, in_project=True):
            number = len(report['commands'])
            started = time.monotonic()
            result = subprocess.run(['/usr/bin/sandbox-exec', '-p', profile,
                str(relocated / 'lefony-sdk'), *map(str, arguments)],
                cwd=project if in_project else folder, env=environment,
                capture_output=True, timeout=180)
            (output / f'{number:02d}.stdout').write_bytes(result.stdout)
            (output / f'{number:02d}.stderr').write_bytes(result.stderr)
            report['commands'].append({'arguments': list(map(str, arguments)),
                'exit_code': result.returncode, 'elapsed_seconds': time.monotonic() - started})
            write_json(output / 'report.json', report)
            assert result.returncode == expected, result.stdout + result.stderr
            return result

        try:
            command('new', project, '--template', 'pocket-lab', in_project=False)
            command('build', '--profile', 'debug')
            command('test', '--headless', '--workspace', 'installed')
            command('workspace', 'clone', 'installed', 'cloned')
            archive = folder / 'workspace.tar.gz'
            command('workspace', 'export', 'cloned', archive)
            command('workspace', 'restore', 'restored', archive)
            command('workspace', 'info', 'restored')
            package_hash = None

            def launch(name, *extra, expected=0):
                nonlocal package_hash
                result = command('test', '--headless', '--suite', 'startup',
                                 '--workspace', 'restored', *extra, expected=expected)
                state = json.loads((project / 'build/run.json').read_text(encoding='utf-8'))
                write_json(output / (name + '.json'), state)
                if not expected:
                    assert state['result'] == 1 and state['os_responsive'], state
                    assert state['persistence'] == 'installed-workspace'
                    if package_hash is None:
                        package_hash = state['package_sha256']
                    assert state['package_sha256'] == package_hash
                report['cases'].append({'name': name, 'status': 'passed', 'run': state})
                print('PASS: frozen emulator ' + name, flush=True)
                return result, state

            for repeat in range(3):
                launch('restored-' + str(repeat + 1))
            qemu = relocated / '_internal/runtime/qemu-system-arm'
            wrapper = folder / 'qemu diagnostic failure'
            # Fill more than a pipe before executing the actual bundled QEMU.
            # Its invalid machine is a deterministic host startup error. This
            # does not model a guest fault or explain any earlier spontaneous exit.
            wrapper.write_text('#!/bin/sh\n/usr/bin/head -c 262144 /dev/zero >&2\n'
                'printf "\\nLEFONY intentional diagnostic fixture\\n" >&2\n'
                'exec ' + shlex.quote(str(qemu)) + ' "$@" -machine lefony-diagnostic-invalid\n',
                encoding='utf-8', newline='\n')
            wrapper.chmod(0o700)
            result, failed = launch('startup-failure', '--qemu', wrapper, expected=1)
            assert failed['status'] == 'failed' and failed['result'] is None
            assert not failed['os_responsive']
            failure = failed['emulator_failure']
            assert failure['phase'] == 'boot' and failure['command'] is None
            assert failure['identities']['sdk_sha256'] == sdk_identity
            assert failure['identities']['package_sha256'] == package_hash
            assert failure['identities']['qemu_sha256'] == digest(wrapper)
            assert failure['identities']['firmware_sha256'] == digest(relocated / '_internal/runtime/firmware.elf')
            process = failure['process']
            assert process['exit_at_failure'] == process['exit_after_cleanup'] == 1
            assert process['cleanup_action'] == 'already-exited'
            assert process['stderr_complete'] and process['stderr_truncated']
            assert process['stderr_bytes'] > 262144 and process['stderr_retained_bytes'] == 65536
            diagnostics = project / 'build/emulator' / failure['directory']
            assert json.loads((diagnostics / 'failure.json').read_text(encoding='utf-8')) == failure
            for name, entry in failure['logs'].items():
                assert (diagnostics / name).stat().st_size == entry['bytes']
                assert digest(diagnostics / name) == entry['sha256']
            assert b'lefony-diagnostic-invalid' in (diagnostics / 'stderr.log').read_bytes()
            assert len(result.stderr) < 10000
            assert str(folder) not in json.dumps(failure)
            launch('restored-after-failure')
            assert len(list((project / 'build/emulator').glob('failure-*/failure.json'))) == 1
            report['qemu_sha256'] = digest(qemu)
            report['failure_wrapper_sha256'] = digest(wrapper)
            report['workspace_archive_sha256'] = digest(archive)
            project = folder / 'Notebook é'
            projects.append((project, 'notebook-project'))
            command('new', project, '--template', 'notebook', in_project=False)
            write_json(project / 'tests/reopen.json', {'schema': 1, 'name': 'reopen',
                                                       'steps': [{'capture': 'reopened'}]})

            def preview(name, scenario, *extra, expected=0):
                command('preview', '--once', '--scenario', scenario, *extra, expected=expected)
                path = project / 'build/preview'
                state = json.loads((path / 'status.json').read_text(encoding='utf-8'))
                assert state['status'] == ('failed' if expected else 'ready'), state
                checkpoints = Checkpoints(project)
                receipt = checkpoints.read()
                archive = checkpoints.path(receipt)
                wire = inspect(archive, [PUBLIC])
                entry = next(entry for entry in wire.snapshots[0].entries if entry.path == 'notebook.txt')
                with archive.open('rb') as stream:
                    stream.seek(entry.content.offset)
                    data = stream.read(entry.content.size)
                assert data.startswith(b'LFNOTE3\nD\n') and b'2+3*4\n' in data
                kept = output / name
                shutil.copytree(path, kept, ignore=shutil.ignore_patterns('.lock'))
                record = {'name': name, 'status': 'passed', 'preview_status': state['status'],
                          'document_sha256': entry.content.sha256, 'frame_sha256': digest(path / 'frame.png'),
                          'archive_sha256': wire.sha256, 'receipt': receipt}
                report['cases'].append(record)
                print('PASS: frozen emulator ' + name, flush=True)
                return state, record

            preview('notebook-edit', 'tests/edit.json')
            _, previous = preview('notebook-cold', 'tests/reopen.json')
            failed, retained = preview('notebook-emulator-failure', 'tests/reopen.json',
                                       '--qemu', wrapper, expected=1)
            assert failed['emulator_failure']['process']['exit_after_cleanup'] == 1
            page = (project / 'build/preview/index.html').read_text(encoding='utf-8')
            assert 'STALE' in page and 'href="emulator/failure-' in page
            for name in ('document_sha256', 'frame_sha256', 'archive_sha256', 'receipt'):
                assert retained[name] == previous[name], name
            failed, retained = preview('notebook-validation-failure', '../invalid.json', expected=1)
            assert 'emulator_failure' not in failed
            page = (project / 'build/preview/index.html').read_text(encoding='utf-8')
            assert 'STALE' in page and 'href="emulator/failure-' not in page
            for name in ('document_sha256', 'frame_sha256', 'archive_sha256', 'receipt'):
                assert retained[name] == previous[name], name
            _, restored = preview('notebook-repaired', 'tests/reopen.json')
            assert restored['document_sha256'] == previous['document_sha256']
            assert restored['frame_sha256'] == previous['frame_sha256']
            report['status'] = 'passed'
        finally:
            if report['status'] != 'passed':
                report['status'] = 'failed'
            for project, name in projects:
                if project.exists():
                    shutil.copytree(project, output / name, symlinks=True)
            if (folder / 'workspace.tar.gz').exists():
                shutil.copyfile(folder / 'workspace.tar.gz', output / 'workspace.tar.gz')
            if (folder / 'qemu diagnostic failure').exists():
                shutil.copyfile(folder / 'qemu diagnostic failure', output / 'failure-wrapper.sh')
            write_json(output / 'report.json', report)


if __name__ == '__main__':
    main()
