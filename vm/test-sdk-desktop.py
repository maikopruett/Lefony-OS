#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify a relocated macOS SDK without network, Homebrew or checkout access."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
import archive_format
from build import identity
from preview_data import Checkpoints, PUBLIC


def notebook_fields(run, project, evidence):
    """Exercise touch editing through the frozen preview and inspect saved bytes."""
    fixtures = project / 'field-fixtures'
    fixtures.mkdir()
    initial = b'LFNOTE3\nL\n0 0 07\n2+3*4\n'
    (fixtures / 'notebook.txt').write_bytes(initial)
    steps = [{'key': 'ok'}]
    def touch(*contacts):
        steps.append({'touch': [list(contact) for contact in contacts]})
    def tap(x, y):
        touch((1, x, y)); touch()
    tap(32, 80)
    steps.append({'key': 'seven'})
    touch((1, 32, 80)); touch((1, 46, 80)); touch()
    steps.append({'key': 'nine'})
    # Cancel selection by leaving the field, adding a contact, or changing ID.
    for contacts in (((1, 60, 205),), ((1, 32, 80), (2, 50, 80)), ((2, 32, 80),)):
        touch((1, 18, 80)); touch(*contacts); touch()
    touch((1, 18, 80)); steps.append({'key': 'right'}); touch()
    steps.append({'key': 'two'})
    tap(60, 205); tap(260, 205); tap(60, 80)
    scenarios = {'field-edit': steps, 'field-cold': [{'key': 'ok'}]}
    expected = {'notebook.txt': b'LFNOTE3\nL\n0 0 07\n2+9*24\n',
                'export.txt': b'# Notebook DEG AUTO 7 / x=1\n2+9*24 = 218\n'}
    results = []
    for name, scenario in scenarios.items():
        path = project / 'tests' / (name + '.json')
        path.write_text(json.dumps({'schema': 1, 'name': name, 'steps': scenario}) + '\n', encoding='utf-8')
        arguments = ['preview', '--once', '--scenario', 'tests/' + path.name]
        if name == 'field-edit':
            arguments += ['--reset-data', '--fixture-dir', str(fixtures)]
        run(*arguments, cwd=project)
        preview = project / 'build/preview'
        state = json.loads((preview / 'status.json').read_text())
        assert state['status'] == 'ready' and not state['layout']['overflow'], state
        nodes = {node['id']: node for node in state['layout']['nodes']}
        assert nodes[50]['name'] == 'Edit expression' and nodes[10]['name'] == '2+9*24', nodes
        saved = evidence / ('notebook-' + name)
        shutil.copytree(preview, saved)
        store = Checkpoints(project); receipt = store.read(); archive_path = store.path(receipt)
        archive = archive_format.inspect(archive_path, [PUBLIC])
        assert archive.sha256 == receipt['archive'] and len(archive.snapshots) == 1
        entries = {entry.path: entry for entry in archive.snapshots[0].entries}
        with archive_path.open('rb') as stream:
            for filename, value in expected.items():
                part = entries[filename].content; stream.seek(part.offset)
                assert stream.read(part.size) == value, (name, filename)
                (saved / filename).write_bytes(value)
        shutil.copyfile(archive_path, saved / 'saved.lfarchive')
        results.append({'phase': name, 'checkpoint': receipt, 'timings': state['timings'],
                        'files': {key: hashlib.sha256(value).hexdigest() for key, value in expected.items()}})
        print('PASS: frozen Notebook ' + name, flush=True)
    assert (fixtures / 'notebook.txt').read_bytes() == initial, 'Preview changed its input fixture'
    return results


def paragraph_preview(run, project, evidence, template):
    """Use the frozen SDK to inspect wrapped text and preserve unreadable data."""
    scenario = project / 'tests' / 'wrapped.json'
    arguments = ['preview', '--once', '--scenario', 'tests/wrapped.json']
    if template == 'notebook':
        original = b'LFNOTE4\nfuture document bytes\n'
        fixtures = project / 'recovery-fixtures'
        fixtures.mkdir()
        (fixtures / 'notebook.txt').write_bytes(original)
        arguments += ['--reset-data', '--fixture-dir', str(fixtures)]
        steps = [{'touch': [[1, 30, 205]]}, {'touch': []}]
    else:
        steps = ([{'touch': [[1, 260, 20]]}, {'touch': []}]
                 + [{'key': 'down'}] * 7 + [{'key': 'ok'}])
    scenario.write_text(json.dumps({'schema': 1, 'name': 'wrapped', 'steps': steps}) + '\n', encoding='utf-8')
    run(*arguments, cwd=project)
    preview = project / 'build/preview'
    state = json.loads((preview / 'status.json').read_text())
    assert state['status'] == 'ready' and not state['layout']['overflow'], state
    nodes = {node['id']: node for node in state['layout']['nodes']}
    saved = evidence / (template + '-paragraphs')
    shutil.copytree(preview, saved)
    result = {'template': template, 'status': 'passed', 'timings': state['timings']}
    if template == 'notebook':
        assert nodes[53]['name'].startswith('The original file is unchanged.'), nodes
        assert not nodes[1]['state'] & 1 and not nodes[4]['state'] & 1, nodes
        store = Checkpoints(project); receipt = store.read(); archive_path = store.path(receipt)
        archive = archive_format.inspect(archive_path, [PUBLIC])
        assert archive.sha256 == receipt['archive'] and len(archive.snapshots) == 1
        entries = {entry.path: entry for entry in archive.snapshots[0].entries}
        part = entries['notebook.txt'].content
        with archive_path.open('rb') as stream:
            stream.seek(part.offset)
            assert stream.read(part.size) == original, 'Recovery preview changed the unreadable document'
        assert (fixtures / 'notebook.txt').read_bytes() == original
        (saved / 'notebook.txt').write_bytes(original)
        shutil.copyfile(archive_path, saved / 'saved.lfarchive')
        result.update(checkpoint=receipt, document_sha256=hashlib.sha256(original).hexdigest())
    else:
        assert nodes[50]['name'] == 'Wrapped text', nodes
        assert {76, 77, 78} <= nodes.keys(), nodes
        assert not nodes[77]['state'] & 1 and nodes[78]['state'] & 16, nodes
        assert all(nodes[id]['file'] == 'src/main.cpp' and nodes[id]['line'] > 0 for id in (76, 77, 78))
    print('PASS: frozen ' + template + ' paragraphs', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/sdk-desktop-release-qualification')
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    evidence = args.output.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    for line in (bundle / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == digest, name
    sdk_identity = identity(bundle / '_internal/sdk')
    assert sdk_identity == identity(ROOT / 'sdk'), 'Frozen SDK must match the checkout being qualified'
    profile = ('(version 1)(allow default)(deny network-outbound (remote ip "*:*"))'
               '(deny file-read* (subpath "/opt/homebrew"))'
               '(deny process-exec (subpath "/opt/homebrew"))'
               f'(deny file-read* (subpath {json.dumps(str(ROOT))}))')
    results = []
    field_results = []
    paragraph_results = []
    with tempfile.TemporaryDirectory(prefix='lf-desktop-', dir='/tmp') as folder:
        folder = Path(folder)
        relocated = folder / 'SDK with spaces é'
        shutil.copytree(bundle, relocated, symlinks=True)
        program = relocated / 'lefony-sdk'
        env = {**os.environ, 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'}
        cmake = shutil.which('cmake')
        assert cmake, 'External CMake is required for the bundle integration check'

        def run(*arguments, cwd=folder):
            value = subprocess.run(['/usr/bin/sandbox-exec', '-p', profile, str(program),
                                    *map(str, arguments)], cwd=cwd, env=env,
                                   capture_output=True, text=True, timeout=240)
            with (evidence / 'commands.log').open('a') as log:
                log.write(' '.join(map(str, arguments)) + '\n' + value.stdout + value.stderr)
            if value.returncode:
                # Keep synthetic project/media evidence before the temporary
                # workspace closes; an unsuccessful launch must be diagnosable.
                failure = evidence / 'failure'
                failure.mkdir(exist_ok=True)
                if Path(cwd)!=folder and Path(cwd).is_relative_to(folder):
                    shutil.copytree(cwd,failure/Path(cwd).name,dirs_exist_ok=True)
                if (folder/'workspace.tar.gz').is_file():
                    shutil.copyfile(folder/'workspace.tar.gz',failure/'workspace.tar.gz')
                (failure/'command.json').write_text(json.dumps({'argv':list(map(str,arguments)),
                    'exit_code':value.returncode,'sdk_identity':sdk_identity},indent=2)+'\n')
            assert value.returncode == 0, value.stdout + value.stderr
            return value.stdout

        doctor = json.loads(run('doctor'))
        assert doctor['gdb'] and doctor['libusb']
        for template in ('basic', 'pocket-lab', 'forms-tables', 'graph-explorer', 'reference-cards', 'c-main', 'notebook', 'ui-gallery'):
            project = folder / ('App é ' + template)
            run('new', project, '--template', template)
            run('build', '--profile', 'debug', cwd=project)
            run('test', '--headless', '--workspace', 'installed', cwd=project)
            report = json.loads((project / 'build/run.json').read_text())
            assert report['status'] == 'passed', report
            source_format = 2 if template in ('c-main', 'notebook', 'ui-gallery') else 1
            run('source', '--format', str(source_format), cwd=project)
            source = json.loads((project / 'build/app.lfsrc').read_text())
            assert source['format'] == 'lefony-source-' + str(source_format)
            if template == 'reference-cards':
                assert source['files']['assets/book.png']['encoding'] == 'base64'
            if template == 'pocket-lab':
                run('workspace', 'clone', 'installed', 'cloned', cwd=project)
                run('workspace', 'export', 'cloned', folder / 'workspace.tar.gz', cwd=project)
                run('workspace', 'restore', 'restored', folder / 'workspace.tar.gz', cwd=project)
                run('workspace', 'info', 'restored', cwd=project)
                run('test', '--headless', '--suite', 'startup', '--workspace', 'restored', cwd=project)
            if template in ('notebook', 'ui-gallery'):
                run('preview', '--once', '--scenario', 'tests/edit.json' if template == 'notebook' else 'tests/startup.json', cwd=project)
                preview = json.loads((project / 'build/preview/status.json').read_text())
                assert preview['status'] == 'ready' and preview['layout']['nodes'], preview
                shutil.copytree(project / 'build/preview', evidence / (template + '-preview'), dirs_exist_ok=True)
                if template == 'notebook':
                    field_results = notebook_fields(run, project, evidence)
                paragraph_results.append(paragraph_preview(run, project, evidence, template))
            if template == 'c-main':
                script = project / 'build/debug.gdb'
                def debugger():
                    deadline = time.monotonic() + 60
                    while not script.exists():
                        assert time.monotonic() < deadline, 'Frozen debug setup deadline'
                        time.sleep(.05)
                    log = run('debugger', '--batch', '--execute', 'bt', '--execute', 'info args',
                              '--execute', 'stepi', '--execute', 'detach', cwd=project)
                    assert 'main (' in log and 'argc = 2' in log and 'src/main.c' in log, log
                    return log
                with (evidence / 'debug-session.log').open('w') as log:
                    session = subprocess.Popen(['/usr/bin/sandbox-exec', '-p', profile, str(program),
                        '--project', str(project), 'debug', '--headless'], env=env, cwd=folder,
                        stdout=log, stderr=subprocess.STDOUT)
                    try:
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                            pool.submit(debugger).result(timeout=120)
                        assert session.poll() is None
                    finally:
                        session.send_signal(signal.SIGINT); session.wait(timeout=30)
                # CMake itself is an optional external host tool. Only this
                # configuration check runs outside the restricted SDK sandbox.
                cmake_dir = project / 'build/cmake'
                with (evidence / 'cmake.log').open('w') as log:
                    for command in (
                        [cmake, '-S', str(project), '-B', str(cmake_dir),
                         '-DLEFONY_SDK_ROOT=' + str(relocated / '_internal/sdk'),
                         '-DCMAKE_DISABLE_FIND_PACKAGE_Python3=TRUE',
                         '-DCMAKE_MAKE_PROGRAM=/usr/bin/make'],
                        [cmake, '--build', str(cmake_dir)]):
                        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       check=True, timeout=120)
            results.append({'template': template, 'status': 'passed', 'test': report})
            print('PASS: relocated offline desktop ' + template, flush=True)
    (evidence / 'report.json').write_text(json.dumps({
        'schema': 1, 'status': 'passed', 'platform': 'darwin-arm64',
        'sdk_identity': sdk_identity, 'notebook_fields': field_results,
        'paragraphs': paragraph_results,
        'bundle_checksums_sha256': hashlib.sha256((bundle / 'SHA256SUMS').read_bytes()).hexdigest(),
        'network': 'denied', 'homebrew_and_checkout_access': 'denied',
        'cmake': 'separate external-host-tool check; Python discovery disabled; outside SDK sandbox',
        'candidate': json.loads((bundle / 'candidate.json').read_text()), 'cases': results,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
