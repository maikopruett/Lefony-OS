#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""SDK archive I/O diagnostics on an unreadable canonical record in the ARM VM.

Uses normal signed installation and the real SDK CLI/USB session. A read-only
fixture locates a FILE2 page in disposable storage; QEMU's existing BCH fault
registers make it temporarily unreadable. No recovery authority is fabricated.
"""
import argparse
from contextlib import nullcontext, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
import archive_device as archive
import cli
from build import digest, identity, write_json
from replay import Controls
from runner import exercise
from signing import sign
from workspace import opened

APP = 'archive-media'
KEY = ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem'
PUBLIC = ROOT / 'tests/fixtures/prime_g2_emulator_update_public.pem'


def command(transport, *args):
    previous, argv = archive.ArchiveUSB, sys.argv
    out, err = io.StringIO(), io.StringIO()
    try:
        # Only select the synthetic USB transport. Parsing, archive validation,
        # client requests, firmware decisions and errors remain the real path.
        archive.ArchiveUSB = lambda: nullcontext(transport)
        sys.argv = ['lefony-sdk', 'archive', *map(str, args)]
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main()
        return {'exit_status': code, 'stdout': out.getvalue(), 'stderr': err.getvalue()}
    finally:
        archive.ArchiveUSB, sys.argv = previous, argv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True)
    firmware = args.firmware.resolve(); qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    sources = ['vm/test-sdk-archive-media.py', 'vm/test-sdk-minigzip-media.py', 'vm/test-sdk-documents.py',
               'tests/native/app_document_fixture.cpp', 'tests/native/app_storage.cpp', 'tests/native/app_documents.cpp',
               'ports/lefony-prime-g2/ion/src/prime_g2/app_archive_source.cpp',
               'ports/lefony-prime-g2/ion/src/prime_g2/app_archive_session.cpp']
    report = {'schema': 1, 'status': 'running', 'physical': 'not_tested', 'sdk_sha256': identity(ROOT / 'sdk'),
              'firmware_sha256': digest(firmware), 'qemu_sha256': digest(qemu), 'cases': [],
              'sources': {name: digest(ROOT / name) for name in sources}}
    write_json(output / 'report.json', report)
    fault = runpy.run_path(str(ROOT / 'vm/test-sdk-minigzip-media.py'))['fault']
    try:
        with tempfile.TemporaryDirectory(prefix='lefony-archive-media-') as temp:
            project = Path(temp) / 'project'; (project / 'src').mkdir(parents=True)
            (project / 'src/main.c').write_text('/* SPDX-License-Identifier: MIT */\nint main(void) { return 0; }\n')
            write_json(project / 'project.json', {'schema': 2, 'runtime': 'foreground-newlib-1', 'sources': ['src/main.c']})
            write_json(project / 'app.json', {'abi': 1, 'id': APP, 'name': 'Archive Media', 'version': '1.0.0',
                'license': 'MIT', 'schema': 1, 'minimum_api': 3, 'required_capabilities': 24,
                'optional_capabilities': 0, 'data_schema': 0})
            pkg = cli.package(project)
            artifact = output / 'app.lfapp'; artifact.write_bytes(sign(pkg.read_bytes(), KEY))
            for name in ('app-debug.elf', 'app.elf', 'build.json'):
                shutil.copyfile(project / 'build' / name, output / name)
            for name in ('app.json', 'project.json', 'sdk.lock.json'):
                shutil.copyfile(project / name, output / name)
            shutil.copyfile(project / 'src/main.c', output / 'main.c')
            helper = Path(temp) / 'helper'; helper.mkdir()
            fixture = runpy.run_path(str(ROOT / 'vm/test-sdk-documents.py'))['fixture'](helper)
            backup = output / 'original.lfarchive'; baseline = {}; media = None
            with opened(project, 'media') as (workspace, _):
                for phase in ('seed', 'fault', 'cold'):
                    folder = output / phase; folder.mkdir(); observed = {}
                    if phase == 'fault':
                        before = digest(workspace / 'nand.overlay')
                        media = json.loads(subprocess.check_output([fixture, 'canonical-media', workspace / 'nand.overlay', APP],
                                                                  text=True, timeout=30))
                        assert digest(workspace / 'nand.overlay') == before, 'Read-only fixture changed storage'
                        assert media['generation'] == baseline['generation']
                        write_json(output / 'canonical-media.json', media)

                    def controls(channel):
                        normal = Controls(channel, folder); client = archive.Client(channel.app_client)
                        try:
                            normal.run({'steps': [{'program_exit': 0}]}, [])
                            normal.key('home'); channel.wait_for_storage(timeout=60)
                            before = client.info(APP)
                            if phase == 'seed':
                                baseline.update(before)
                                observed['export'] = client.export(APP, backup, [PUBLIC])
                                assert observed['export']['signatures_checked']
                                observed['info'] = before
                                return
                            assert before == baseline
                            overlay_hash = digest(workspace / 'nand.overlay'); backup_hash = digest(backup)
                            destination = folder / 'existing.lfarchive'; previous = b'Previous host backup\n'
                            destination.write_bytes(previous)
                            requests = [('info', APP), ('info', APP, '--include-unreadable'),
                                        ('export', APP, destination, '--public-key', PUBLIC, '--replace'),
                                        ('restore', backup, '--public-key', PUBLIC, '--repair-code')]
                            try:
                                observed['fault_registers'] = fault(normal, media, 2)
                                failures = []
                                for request in requests:
                                    result = command(channel.app_client.transport, *request)
                                    assert result['exit_status'] == 1 and not result['stdout'], result
                                    assert result['stderr'].strip() == 'lefony-sdk: Archive: storage I/O failed', result
                                    status = client.status()
                                    assert status['state'] == archive.FAILED and status['error'] == 10, status
                                    failures.append({'command': request[0], 'repair': '--repair-code' in request or
                                        '--include-unreadable' in request, **result})
                                    assert destination.read_bytes() == previous
                                    assert digest(backup) == backup_hash
                                    assert digest(workspace / 'nand.overlay') == overlay_hash, 'Failed archive operation wrote storage'
                                    assert not list(folder.glob('*.partial'))
                                observed['failures'] = failures
                            finally:
                                observed['fault_clear'] = fault(normal, media, 0)
                            observed['after'] = client.info(APP); assert observed['after'] == baseline
                            result = command(channel.app_client.transport, 'export', APP, destination, '--public-key', PUBLIC, '--replace')
                            assert result['exit_status'] == 0 and not result['stderr'], result
                            assert destination.read_bytes() == backup.read_bytes()
                            assert digest(workspace / 'nand.overlay') == overlay_hash
                            observed['retry_export'] = json.loads(result['stdout'])
                            observed['overlay_sha256'] = overlay_hash
                            assert channel.command('PING') == 'PONG'
                        finally:
                            normal.close()

                    result = exercise(artifact, qemu, firmware, workspace=workspace, controls=controls, public_keys=[PUBLIC])
                    assert result['result'] == 1 and result['os_responsive'], result
                    shutil.copyfile(workspace / 'nand.overlay', folder / 'nand.overlay')
                    report['cases'].append({'case': phase, 'runtime': result, **observed})
                    write_json(output / 'report.json', report); print('PASS:', phase, flush=True)
        assert report['sources'] == {name: digest(ROOT / name) for name in sources}, 'Source changed during validation'
        assert report['sdk_sha256'] == identity(ROOT / 'sdk'), 'SDK changed during validation'
        report['status'] = 'passed'; write_json(output / 'report.json', report)
    except BaseException as exc:
        report.update(status='failed', error=str(exc)); write_json(output / 'report.json', report); raise


if __name__ == '__main__':
    main()
