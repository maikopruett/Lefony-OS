#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real CLI signals, ARM cold data and interrupted publication preparation.

Only private process groups and synthetic emulator workspaces are used. The
source harness exports saved data through the actual modeled USB archive API.
No account, remote service or physical calculator is contacted.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from archive_device import Client as ArchiveClient
from archive_format import inspect
from build import identity, write_json
from preview_data import PUBLIC
from replay import Controls
from runner import exercise
from store_snapshot import verify
from workspace import opened


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def group_members(group):
    output = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,pgid=,comm='], text=True, timeout=10)
    members = []
    for line in output.splitlines():
        values = line.strip().split(None, 3)
        if len(values) == 4 and int(values[2]) == group:
            members.append({'pid': int(values[0]), 'parent': int(values[1]), 'command': values[3]})
    return members


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--qemu', type=Path)
    parser.add_argument('--firmware', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--key-only', action='store_true', help='interrupt during an acknowledged KPP Shift press')
    parser.add_argument('--reference-bundle', action='store_true', help='key-only comparison against a recorded older bundle')
    args = parser.parse_args()
    assert not args.reference_bundle or args.bundle and args.key_only
    assert sys.platform == 'darwin', 'This harness uses the macOS sandbox'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, output / Path(__file__).name)
    report = {'schema': 1, 'status': 'running', 'sdk_sha256': identity(ROOT / 'sdk'),
              'mode': 'frozen' if args.bundle else 'source', 'network': 'denied',
              'physical': 'not_tested', 'key_only': args.key_only, 'commands': [], 'cases': [], 'data': []}
    write_json(output / 'report.json', report)
    with tempfile.TemporaryDirectory(prefix='lf-replay-cancel-', dir='/tmp') as temporary:
        folder = Path(temporary)
        profile = '(version 1)(allow default)(deny network-outbound (remote ip "*:*"))'
        environment = dict(os.environ)
        if args.bundle:
            bundle = args.bundle.resolve()
            for line in (bundle / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
                expected, name = line.split('  ', 1)
                assert digest(bundle / name) == expected, name
            bundled_identity = identity(bundle / '_internal/sdk')
            if args.reference_bundle:
                report['reference_source_sdk_sha256'] = report['sdk_sha256']
                report['sdk_sha256'] = bundled_identity
                report['qualification'] = 'reference comparison; not current-source qualification'
            else:
                assert bundled_identity == report['sdk_sha256']
            report['bundle_checksums_sha256'] = digest(bundle / 'SHA256SUMS')
            relocated = folder / 'SDK with spaces é'
            shutil.copytree(bundle, relocated, symlinks=True)
            executable = [str(relocated / 'lefony-sdk')]
            qemu = relocated / '_internal/runtime/qemu-system-arm'
            firmware = relocated / '_internal/runtime/firmware.elf'
            profile += ('(deny file-read* (subpath "/opt/homebrew"))'
                        '(deny process-exec (subpath "/opt/homebrew"))'
                        f'(deny file-read* (subpath {json.dumps(str(ROOT))}))')
            environment['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'
        else:
            assert args.qemu and args.firmware, 'Source qualification requires explicit QEMU and firmware'
            executable = [sys.executable, str(ROOT / 'sdk/tools/cli.py')]
            qemu, firmware = args.qemu.resolve(), args.firmware.resolve()
        report.update(qemu_sha256=digest(qemu), firmware_sha256=digest(firmware))
        project = folder / 'Notebook é'

        def command(*arguments, expected=0, interrupt=None, ready=None, in_project=True):
            number = len(report['commands'])
            entry = {'arguments': list(map(str, arguments)), 'interrupt': interrupt}
            report['commands'].append(entry)
            started = time.monotonic()
            with (output / f'{number:02d}.stdout').open('wb') as stdout, (output / f'{number:02d}.stderr').open('wb') as stderr:
                process = subprocess.Popen(['/usr/bin/sandbox-exec', '-p', profile, *executable, *map(str, arguments)],
                    cwd=project if in_project else folder, env=environment, stdin=subprocess.DEVNULL,
                    stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    assert os.getpgid(process.pid) == process.pid
                    entry['process_group'] = process.pid
                    if interrupt:
                        deadline = time.monotonic() + 120
                        while not ready():
                            assert process.poll() is None, 'CLI exited before the requested interruption point'
                            assert time.monotonic() < deadline, 'CLI did not reach the interruption point'
                            time.sleep(.05)
                        # The captured ARM frame precedes a long explicit replay wait.
                        time.sleep(.03 if interrupt == 'key-disconnect' else .3)
                        assert process.poll() is None
                        entry['group_before_signal'] = group_members(process.pid)
                        assert any(row['command'].endswith('qemu-system-arm') for row in entry['group_before_signal'])
                        if interrupt == 'key-disconnect':
                            qemu_child, = [row['pid'] for row in entry['group_before_signal'] if row['command'].endswith('qemu-system-arm')]
                            os.kill(qemu_child, signal.SIGKILL)
                            time.sleep(.02)
                            process.send_signal(signal.SIGINT)
                            entry['signal_order'] = ['QEMU SIGKILL', 'CLI SIGINT during key hold']
                        elif interrupt == 'process':
                            process.send_signal(signal.SIGINT)
                        else:
                            os.killpg(process.pid, signal.SIGKILL if interrupt == 'kill' else signal.SIGINT)
                    entry['exit_code'] = process.wait(timeout=30 if interrupt else 180)
                    deadline = time.monotonic() + 5
                    while group_members(process.pid) and time.monotonic() < deadline:
                        time.sleep(.05)
                    entry['remaining_group'] = group_members(process.pid)
                    assert not entry['remaining_group'], 'CLI left a child process running'
                    assert entry['exit_code'] == expected, f'CLI exit {entry["exit_code"]}; see command {number} logs'
                finally:
                    if process.poll() is None or group_members(process.pid):
                        try:os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:pass
                    process.wait(timeout=10)
                    entry['elapsed_seconds'] = time.monotonic() - started
                    write_json(output / 'report.json', report)

        def runtime_arguments():
            return ('--qemu', qemu, '--firmware', firmware)

        def saved_data(name):
            archive = output / (name + '.lfarchive')
            package, = (project / 'build').glob('*.lfapp')
            def controls(channel):
                device = Controls(channel, output)
                try:
                    device.key('home')
                    channel.app_client.wait()
                    ArchiveClient(channel.app_client).export('notebook', archive, [PUBLIC])
                finally:
                    device.close()
            with opened(project, 'installed') as (media, _):
                runtime = exercise(package, qemu, firmware, workspace=media, controls=controls,
                                   diagnostics_dir=output / 'probe-emulator')
            wire = inspect(archive, [PUBLIC])
            entry = next(item for item in wire.snapshots[0].entries if item.path == 'notebook.txt')
            with archive.open('rb') as stream:
                stream.seek(entry.content.offset)
                data = stream.read(entry.content.size)
            assert data.startswith(b'LFNOTE3\nD\n') and b'2+3*4\n' in data
            assert runtime['result'] == 1 and runtime['os_responsive']
            record = {'name': name, 'document_sha256': entry.content.sha256, 'archive_sha256': wire.sha256,
                      'oracle': 'source harness, public modeled USB archive, cold ARM launch', 'runtime': runtime}
            report['data'].append(record)
            return data

        def incomplete(path, name, killed=False):
            value = json.loads(path.read_text(encoding='utf-8'))
            assert value['status'] == ('running' if killed else 'cancelled'), value
            expected = ['passed', 'running' if killed else 'cancelled', 'not_run']
            assert [case['status'] for case in value['cases']] == expected, value
            assert value['summary']['passed'] == 1 and value['summary']['not_run'] == 1
            if not killed:
                assert value['cases'][1]['steps'][-1]['status'] == 'cancelled'
            write_json(output / (name + '.json'), value)
            report['cases'].append({'name': name, 'status': 'passed', 'observed_status': value['status']})
            print('PASS: replay lifecycle ' + name, flush=True)

        try:
            command('new', project, '--template', 'notebook', in_project=False)
            if args.key_only:
                from replay import KEYS
                shutil.rmtree(project / 'tests')
                (project / 'tests').mkdir()
                for number, name in enumerate(('first', 'second', 'third')):
                    steps = [{'capture': 'ready' if name == 'second' else name}]
                    write_json(project / 'tests' / f'{number}.json', {'schema': 1, 'name': name, 'steps': steps})
                command('test', '--headless', *runtime_arguments())
                write_json(project / 'tests/1.json', {'schema': 1, 'name': 'second',
                    'steps': [{'capture': 'ready'}, {'key': 'shift'}, {'wait_ms': 5000}]})
                marker = project / 'build/tests/second/ready.ppm'
                marker.unlink()
                trace = folder / 'qtest-key.log'
                wrapper = folder / 'qemu key observer'
                # Keep QEMU's default unbuffered stderr qtest logger. Only
                # remove the runner's log suppression; all model input bytes
                # still traverse the original qtest socket and KPP device.
                wrapper.write_text('#!/bin/zsh\ntypeset -a forwarded\ninteger skip=0\n'
                    'for arg in "$@"; do\n if (( skip )); then skip=0; continue; fi\n'
                    ' if [[ "$arg" == "-qtest-log" ]]; then skip=1; continue; fi\n'
                    ' forwarded+=("$arg")\ndone\nexec ' + shlex.quote(str(qemu)) +
                    ' "${forwarded[@]}" 2>' + shlex.quote(str(trace)) + '\n', encoding='utf-8')
                wrapper.chmod(0o700)
                row, col = KEYS['shift']
                pressed = f'writew 0x020b8008 {(row << 8) | col | 0x8000:#x}'.encode()
                released = f'writew 0x020b8008 {(row << 8) | col:#x}'.encode()
                def key_ready():
                    if not marker.exists() or not trace.exists():return False
                    data = trace.read_bytes()
                    if pressed not in data:return False
                    after = data.split(pressed, 1)[1]
                    assert released not in after, 'Observer missed the key-down interval'
                    if b'OK' not in after:return False
                    (output / 'key-before-signal.log').write_bytes(data)
                    return True
                # Stop the owned QEMU then interrupt the CLI during the same
                # acknowledged key hold. This makes failed release deterministic.
                command('test', '--headless', '--qemu', wrapper, '--firmware', firmware,
                        expected=130, interrupt='key-disconnect', ready=key_ready)
                shutil.copyfile(trace, output / 'qtest-key.log')
                shutil.copyfile(wrapper, output / 'key-wrapper.sh')
                incomplete(project / 'build/run.json', 'key-disconnect')
                assert any(case['cleanup_errors'] for case in json.loads((project / 'build/run.json').read_text())['cases']
                           if 'cleanup_errors' in case)
                command('test', '--headless', *runtime_arguments())
                assert json.loads((project / 'build/run.json').read_text())['status'] == 'passed'
                report['status'] = 'passed'
                return
            command('test', '--headless', '--suite', 'tests/edit.json', '--workspace', 'installed', *runtime_arguments())
            original = saved_data('original')
            shutil.rmtree(project / 'tests')  # Only the fresh fixture project's template scenarios.
            (project / 'tests').mkdir()
            for number, name in enumerate(('first', 'second', 'third')):
                write_json(project / 'tests' / f'{number}.json', {'schema': 1, 'name': name,
                    'steps': [{'capture': 'interrupt-ready' if name == 'second' else name}, {'wait_ms': 20}]})
            write_json(project / 'recovery.json', {'schema': 1, 'name': 'recovery', 'steps': [{'capture': 'cold'}]})
            command('test', '--headless', '--workspace', 'installed', *runtime_arguments())
            assert json.loads((project / 'build/run.json').read_text())['status'] == 'passed'
            write_json(project / 'tests/1.json', {'schema': 1, 'name': 'second',
                'steps': [{'capture': 'interrupt-ready'}, *[{'wait_ms': 5000}] * 5]})
            marker = project / 'build/tests/second/interrupt-ready.ppm'
            for mode in ('process', 'group', 'kill'):
                marker.unlink(missing_ok=True)
                command('test', '--headless', '--workspace', 'installed', *runtime_arguments(),
                        expected=-signal.SIGKILL if mode == 'kill' else 130, interrupt=mode, ready=marker.exists)
                incomplete(project / 'build/run.json', mode, killed=mode == 'kill')
                if mode == 'kill':
                    killed_group = report['commands'][-1]['process_group']
                    command('test', '--headless', '--suite', 'recovery.json', '--workspace', 'installed',
                            *runtime_arguments(), expected=1)
                    assert 'locked by another operation' in (output / f'{len(report["commands"])-1:02d}.stderr').read_text()
                    assert json.loads((project / 'build/run.json').read_text())['status'] == 'running'
                    # Exercise the existing documented manual recovery, only
                    # for this private fixture after verifying its whole group
                    # has stopped. Never infer liveness from the lock itself.
                    assert not group_members(killed_group)
                    lock = project / '.lefony/workspaces/installed/.lock'
                    assert lock.is_dir() and not lock.is_symlink()
                    lock.rmdir()
                    report['manual_workspace_unlock'] = {'after_verified_group_exit': killed_group,
                        'path': '.lefony/workspaces/installed/.lock', 'operation': 'remove empty directory'}
                command('test', '--headless', '--suite', 'recovery.json', '--workspace', 'installed', *runtime_arguments())
                assert saved_data('after-' + mode) == original
            from PIL import Image
            corpus = json.loads((ROOT / 'sdk/contracts/store-publication-v1.json').read_text())
            fixture = next(case for case in corpus['image_cases'] if case['case'] == 'strip-private-text')
            (project / 'store/icon.png').write_bytes(base64.b64decode(fixture['base64']))
            with Image.open(project / 'build/tests/recovery/cold.ppm') as frame:
                frame.save(project / 'store/screenshots/notebook.png')
            (project / 'store/description.md').write_text('Synthetic Notebook cancellation qualification.', encoding='utf-8')
            write_json(project / 'store/listing.json', {'schema': 1, 'publish_source': True})
            root_pass = (project / 'build/run.json').read_bytes()
            publication = project / '.lefony/publish'
            def prepared_ready():
                if not publication.exists():return False
                attempts = list(publication.iterdir())
                assert len(attempts) <= 1
                return bool(attempts and (attempts[0] / 'project/build/tests/second/interrupt-ready.ppm').is_file())
            command('publish', '--dry-run', *runtime_arguments(), expected=130, interrupt='group', ready=prepared_ready)
            attempt, = publication.iterdir()
            incomplete(attempt / 'project/build/run.json', 'publication-cancelled')
            failed_report = (attempt / 'project/build/run.json').read_bytes()
            assert (project / 'build/run.json').read_bytes() == root_pass
            assert not (attempt / 'submission.json').exists() and not (attempt / 'upload/report.json').exists()
            try:verify(attempt)
            except ValueError:pass
            else:raise AssertionError('Incomplete publication was accepted as resumable')
            write_json(project / 'tests/1.json', {'schema': 1, 'name': 'second',
                'steps': [{'capture': 'interrupt-ready'}, {'wait_ms': 20}]})
            command('publish', '--dry-run', *runtime_arguments())
            finished, = [path for path in publication.iterdir() if path != attempt]
            submission = verify(finished)
            prepared = json.loads((finished / 'upload/report.json').read_text())
            assert prepared['status'] == 'passed' and prepared['summary'] == {'passed': 3, 'failed': 0, 'skipped': 0}
            assert (attempt / 'project/build/run.json').read_bytes() == failed_report
            assert not (attempt / 'submission.json').exists()
            report['cases'].append({'name': 'fresh-publication-after-cancellation', 'status': 'passed',
                                    'submission_sha256': digest(finished / 'submission.json'), 'files': len(submission['files'])})
            print('PASS: replay lifecycle fresh-publication-after-cancellation', flush=True)
            report['status'] = 'passed'
        finally:
            if report['status'] != 'passed':report['status'] = 'failed'
            for source, name in ((folder / 'qemu key observer', 'key-wrapper.sh'), (folder / 'qtest-key.log', 'qtest-key.log')):
                if source.exists():shutil.copyfile(source, output / name)
            if project.exists():shutil.copytree(project, output / 'project', symlinks=True)
            write_json(output / 'report.json', report)


if __name__ == '__main__':
    main()
