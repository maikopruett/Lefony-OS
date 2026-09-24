#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""OS-owned Home/Apps variants leave a native editor and preserve saved data."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from archive_device import Client as ArchiveClient
from archive_format import inspect
from build import digest, identity, write_json
from cli import package
from preview_data import PUBLIC
from replay import Controls, control_session
from runner import exercise
from workspace import opened


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', type=Path, required=True)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, output / Path(__file__).name)
    qemu, firmware = args.qemu.resolve(), args.firmware.resolve()
    report = {'schema': 1, 'status': 'running', 'physical': 'not_tested', 'sdk_sha256': identity(ROOT / 'sdk'),
              'qemu_sha256': digest(qemu), 'firmware_sha256': digest(firmware), 'cases': []}
    with tempfile.TemporaryDirectory(prefix='lf-system-navigation-') as temporary:
        project = Path(temporary) / 'notebook'
        shutil.copytree(ROOT / 'sdk/examples/notebook', project,
                        ignore=shutil.ignore_patterns('build', '.lefony', 'sdk.lock.json'))
        app = package(project)
        original = None
        try:
            with opened(project, 'navigation') as (media, _):
                for name, key, shifted in (('seed', 'home', False), ('home', 'home', False),
                        ('apps', 'apps', False), ('shift-home', 'home', True), ('shift-apps', 'apps', True)):
                    archive = output / (name + '.lfarchive')
                    observation = {}
                    def controls(channel):
                        with control_session(Controls(channel, output)) as device:
                            if name == 'seed':
                                device.key('ok')
                                device.key('ok')
                            # Enter the editor where Back belongs to the app.
                            device.key('ok')
                            observation['before'] = channel.command('STATE').split(' home_row=')[0]
                            assert observation['before'] == channel.native_state
                            observation['heap_before'] = channel.command('APP DIAG 17')
                            assert observation['heap_before'] != 'VALUE 0'
                            device.execute('screendump', {'filename': str(output / (name + '-editor.ppm'))})
                            if shifted:
                                device.key('shift')
                                observation['modifier_before'] = channel.command('MOD STATE')
                                assert observation['modifier_before'] != 'VALUE 0'
                            device.key(key)
                            observation['after'] = channel.command('STATE').split(' home_row=')[0]
                            assert observation['after'] != channel.native_state, 'System navigation was consumed by the app'
                            # DIAG 0 retains the last program counter after unload.
                            # Unload resets execution result and releases the heap.
                            observation['result_after'] = channel.command('APP DIAG 6')
                            observation['heap_after'] = channel.command('APP DIAG 17')
                            assert observation['result_after'] == 'VALUE 0', 'Native execution was not reset'
                            assert observation['heap_after'] == 'VALUE 0', 'Native heap was not released'
                            assert channel.command('MOD STATE') == 'VALUE 0', 'OS navigation retained modifier state'
                            device.execute('screendump', {'filename': str(output / (name + '-system.ppm'))})
                            channel.app_client.wait()
                            ArchiveClient(channel.app_client).export('notebook', archive, [PUBLIC])
                    runtime = exercise(app, qemu, firmware, workspace=media, controls=controls,
                                       diagnostics_dir=output / 'emulator')
                    assert runtime['result'] == 1 and runtime['os_responsive']
                    wire = inspect(archive, [PUBLIC])
                    entry = next(entry for entry in wire.snapshots[0].entries if entry.path == 'notebook.txt')
                    with archive.open('rb') as stream:
                        stream.seek(entry.content.offset)
                        data = stream.read(entry.content.size)
                    assert data.startswith(b'LFNOTE3\n') and b'2+3*4\n' in data
                    if original is None:original = data
                    assert data == original
                    report['cases'].append({'name': name, 'status': 'passed', 'navigation': observation,
                        'document_sha256': entry.content.sha256, 'archive_sha256': wire.sha256, 'runtime': runtime})
                    write_json(output / 'report.json', report)
                    print('PASS: native system navigation ' + name, flush=True)
            report['status'] = 'passed'
        finally:
            if report['status'] != 'passed':report['status'] = 'failed'
            shutil.copytree(project, output / 'project')
            write_json(output / 'report.json', report)


if __name__ == '__main__':
    main()
