#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Frozen private signing/install/recovery on ARM with normal OS key consent.

The actual relocated macOS executable builds and signs packages, creates its
temporary identities and manages keys/install through an exclusive model socket.
The source harness supplies synthetic media/input and independently reads saved
data. No physical USB, network, private release key or in-process CLI replacement.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import shutil
import subprocess
import sys
import tempfile
import time

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'sdk/tools'))
from build import digest, identity, write_json
from data_device import DataClient
from files_device import FileClient
from keys_device import Client as Keys
from replay import Controls, load
from runner import exercise
from sdk_notebook_probe import wait_notebook
from signing import verify
from workspace import opened


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--unreadable', action='store_true', help='also qualify partial backups and fresh-scan repair under modeled NAND read faults')
    args = parser.parse_args();bundle = args.bundle.resolve();output = args.output.resolve()
    assert platform.system() == 'Darwin', 'This denied-access harness currently requires macOS'
    output.mkdir(parents=True, exist_ok=False)
    for line in (bundle/'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1);assert digest(bundle/name) == expected, name
    sdk_identity = identity(bundle/'_internal/sdk')
    assert identity(ROOT/'sdk') == sdk_identity, 'Harness and frozen SDK sources must match'
    source_names = ['vm/test-sdk-frozen-keys.py', 'vm/test-sdk-documents.py', 'vm/sdk_notebook_probe.py',
                    'tests/native/app_document_fixture.cpp', 'sdk/tools/cli.py', 'sdk/tools/signing.py',
                    'sdk/tools/keys_device.py', 'sdk/tools/emulator_usb.py', 'sdk/tools/runner.py',
                    'vm/test-sdk-key-media.py', 'vm/test-sdk-minigzip-media.py', 'sdk/tools/key_snapshot.py']
    sources = {name: digest(ROOT/name) for name in source_names}
    report = {'schema': 1, 'status': 'running', 'sdk_identity': sdk_identity,
              'candidate': json.loads((bundle/'candidate.json').read_text()), 'sources': sources,
              'bundle_checksums_sha256': digest(bundle/'SHA256SUMS'),
              'frozen_access': 'outbound IP network, Homebrew and checkout denied', 'physical': 'not_tested',
              'commands': [], 'cases': []}
    write_json(output/'report.json', report)
    profile = ('(version 1)(allow default)(deny network-outbound (remote ip "*:*"))'
               '(deny file-read* (subpath "/opt/homebrew"))(deny process-exec (subpath "/opt/homebrew"))'
               f'(deny file-read* (subpath {json.dumps(str(ROOT))}))')
    # Use the desktop harness's IP-network denial; private AF_UNIX model IPC
    # remains available without allowing TCP/HTTPS traffic.
    env = {**os.environ, 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'}
    expected_document = b'LFNOTE3\nD\n0 0 07\n2+3*4\n'
    expected_export = b'# Notebook DEG AUTO 7 / x=1\n2+3*4 = 14\n'
    try:
        with tempfile.TemporaryDirectory(prefix='lf-private-', dir='/tmp') as temporary:
            temp = Path(temporary);relocated = temp/'SDK privé';shutil.copytree(bundle, relocated, symlinks=True)
            program = relocated/'lefony-sdk';qemu = relocated/'_internal/runtime/qemu-system-arm'
            firmware = relocated/'_internal/runtime/firmware.elf';logs = temp/'logs';logs.mkdir()
            report['firmware_sha256'] = digest(firmware);report['qemu_sha256'] = digest(qemu)
            private = {};public = {};fingerprints = {};artifacts = {};steps = []

            def record(name, **detail):
                report['cases'].append({'case': name, 'status': 'passed', **detail})
                write_json(output/'report.json', report);print('PASS: frozen keys '+name, flush=True)

            def run(arguments, *, expected=0, normal=None, socket=None, approval=None, fingerprint=None, before_consent=None):
                number = len(report['commands']);stem = f'{number:02d}'
                stdout = logs/(stem+'.stdout');stderr = logs/(stem+'.stderr')
                command = ['/usr/bin/sandbox-exec', '-p', profile, str(program), *map(str, arguments)]
                started = time.monotonic();acted = False;last_frame = None;stable = None
                before = None
                if normal:
                    normal.execute('screendump', {'filename': str(logs/'before.ppm')})
                    with Image.open(logs/'before.ppm') as frame:before = frame.crop((0,0,320,50)).tobytes()
                with stdout.open('w') as out, stderr.open('w') as err:
                    process = subprocess.Popen(command, cwd=temp, env=env, stdout=out, stderr=err)
                    try:
                        while process.poll() is None:
                            assert time.monotonic()-started < 160, ('Frozen command timed out', arguments)
                            if approval and not acted and 'Request nonce:' in stderr.read_text():
                                assert fingerprint in stderr.read_text(), 'Host consent omitted expected identity'
                                frame_path = logs/(stem+'-consent.ppm')
                                normal.execute('screendump', {'filename': str(frame_path)})
                                with Image.open(frame_path) as frame:
                                    pixels = frame.tobytes();title = frame.crop((0,0,320,50)).tobytes()
                                now = time.monotonic()
                                if title != before and pixels == last_frame:
                                    if stable is not None and now-stable >= .6:
                                        with Image.open(frame_path) as frame:frame.save(output/(stem+'-consent.png'))
                                        if before_consent:before_consent()
                                        normal.key_edge(approval, True);time.sleep(.25);normal.key_edge(approval, False)
                                        acted = True
                                else:stable = now
                                last_frame = pixels
                            time.sleep(.03)
                        process.wait(timeout=5)
                    finally:
                        if process.poll() is None:
                            process.terminate()
                            try:process.wait(timeout=5)
                            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                entry = {'argv': list(map(str, arguments)), 'exit_code': process.returncode,
                         'expected_exit': expected, 'seconds': round(time.monotonic()-started, 3),
                         'normal_consent_key': approval if acted else None}
                report['commands'].append(entry)
                for path in (stdout, stderr):shutil.copyfile(path, output/path.name)
                write_json(output/'report.json', report)
                assert process.returncode == expected, (arguments, process.returncode, stderr.read_text())
                if approval:assert acted, ('Consent screen was not exercised', arguments)
                content = stdout.read_text()
                return json.loads(content) if content.lstrip().startswith('{') else content, stderr.read_text()

            project = temp/'Private Notebook é';bootstrap = temp/'Bootstrap'
            run(['new', project, '--template', 'notebook']);run(['new', bootstrap, '--template', 'counter'])
            metadata = json.loads((bootstrap/'app.json').read_text());metadata.update(id='store-counter')
            write_json(bootstrap/'app.json', metadata);run(['--project', bootstrap, 'package'])
            start = next((bootstrap/'build').glob('store-counter-*.lfapp'))
            shutil.copyfile(start, output/'bootstrap.lfapp')
            for key in ('a', 'b'):
                private[key] = temp/(key+'-private.pem');public[key] = temp/(key+'-public.pem')
                result, _ = run(['keys', 'generate', '--private-key', private[key], '--public-key', public[key]])
                fingerprints[key] = result['fingerprint'];assert private[key].stat().st_mode & 0o777 == 0o600
                shutil.copyfile(public[key], output/public[key].name)
            before = digest(private['a'])
            run(['keys', 'generate', '--private-key', private['a'], '--public-key', public['a']], expected=1)
            assert digest(private['a']) == before
            for key, version in (('a', '1.0.0'), ('b', '1.1.0')):
                metadata = json.loads((project/'app.json').read_text());metadata.update(id='private-notebook', version=version)
                write_json(project/'app.json', metadata);run(['--project', project, 'package'])
                unsigned = project/'build'/f'private-notebook-{version}.lfapp';signed = temp/(key+'-signed.lfapp')
                result, _ = run(['sign', unsigned, '--private-key', private[key], '--output', signed])
                assert result['signer'] == fingerprints[key] and result['sha256'] == digest(signed)
                assert verify(signed.read_bytes(), [public[key]])[0]['version'] == version
                artifacts[key] = signed;shutil.copyfile(signed, output/signed.name)
                shutil.copyfile(unsigned, output/(key+'-unsigned.lfapp'))
                shutil.copyfile(project/'build/app-debug.elf', output/(key+'.elf'))
            record('local-key-generation-and-verified-signing-without-host-tools')
            fixture_dir = temp/'fixture';fixture_dir.mkdir()
            fixture = runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](fixture_dir)
            fault = runpy.run_path(str(ROOT/'vm/test-sdk-minigzip-media.py'))['fault']
            compare_snapshot = runpy.run_path(str(ROOT/'vm/test-sdk-key-media.py'))['compare_snapshot']
            original_root = None;registry_media = None
            phases = ('installed', 'cold', 'damaged', 'repaired-cold') + (('unreadable', 'unreadable-cold') if args.unreadable else ())
            for phase in phases:
                folder = output/phase;folder.mkdir()
                with opened(project, 'private-install') as (media, _):
                    if phase == 'damaged':
                        subprocess.run([fixture, 'corrupt-keys', media/'nand.overlay'], check=True, timeout=30)
                    if phase == 'unreadable':
                        before = digest(media/'nand.overlay')
                        registry_media = json.loads(subprocess.check_output([fixture, 'key-media', media/'nand.overlay'], text=True, timeout=30))
                        assert digest(media/'nand.overlay') == before
                        write_json(folder/'key-media.json', registry_media)

                    def controls(channel):
                        normal = Controls(channel, folder);app = channel.app_client
                        keys = Keys(app.transport);files = FileClient(app);data = DataClient(app)
                        def home():
                            normal.key('home');app.wait();normal.key('back')
                        def device(arguments, **options):
                            with channel.usb_host.lend_connection() as socket:
                                args = ([arguments[0], '--emulator-usb', socket, *arguments[1:]] if arguments[0]=='keys'
                                        else [*arguments, '--emulator-usb', socket])
                                value = run(args, normal=normal, socket=socket, **options)
                            if options.get('approval'):normal.key('back');app.wait()
                            return value
                        def change(operation, key, **options):
                            args = ['keys', operation]
                            args += (['--public-key', public[key], '--label', 'Frozen '+key.upper()] if operation=='enroll'
                                     else [fingerprints[key]])
                            return device(args, fingerprint=fingerprints[key], **options)[0]
                        def install(key, recover=False, **options):
                            args = ['install', artifacts[key], '--public-key', public[key]]
                            if recover:args += ['--recover-signer']
                            return device(args, fingerprint=fingerprints[key], **options)
                        def launch(allowed=True):
                            entry = next(e for e in app.catalog() if e['id']=='private-notebook')
                            result = channel.command(f"APP OPEN {entry['slot']}")
                            assert (result=='OK') == allowed, (entry, result)
                            if allowed:wait_notebook(normal, steps)
                        def saved(name):
                            for path, expected in (('notebook.txt', expected_document), ('export.txt', expected_export)):
                                target = folder/(name+'-'+path);files.export_file('private-notebook', path, target)
                                assert target.read_bytes() == expected, name
                        try:
                            home()
                            if phase == 'installed':
                                assert device(['keys', 'status'])[0]['registry'] == 'empty'
                                assert change('enroll', 'a', approval='back', expected=1)['state'] == 'cancelled'
                                assert device(['keys', 'list'])[0]['keys'] == []
                                assert change('enroll', 'a', approval='ok')['state'] == 'complete'
                                assert install('a')[0]['version'] == '1.0.0'
                                launch()
                                for step in load(project/'tests/edit.json')['steps']:
                                    normal.run({'steps': [step]}, steps)
                                    if step.get('key')=='ok' or step.get('touch')==[]:wait_notebook(normal, steps)
                                home();saved('original')
                                record('cancelled-enrollment-approved-install-and-normal-Notebook-edit')
                                assert change('enroll', 'b', approval='ok')['state'] == 'complete'
                                _, error = install('b', expected=1);assert 'error 10' in error, error
                                app.write(0x60);app.wait();normal.key('back');saved('takeover-refused')
                                assert change('revoke', 'a', approval='ok')['state'] == 'complete'
                                assert device(['keys', 'list'])[0]['keys'][0]['state'] == 'revoked'
                                launch(False);saved('revoked')
                                result = change('remove', 'a', expected=1)
                                assert result['error'] == 'key_required_by_installed_or_unreadable_apps'
                                _, error = install('b', recover=True, approval='back', expected=1)
                                assert 'cancelled' in error;saved('cancelled-recovery')
                                assert install('b', recover=True, approval='ok')[0]['version'] == '1.1.0'
                                assert data.info('private-notebook')['pending_upgrade']
                                saved('pending');launch();home();saved('accepted')
                                assert not data.info('private-notebook')['pending_upgrade']
                                assert change('remove', 'a', approval='ok')['state'] == 'complete'
                                result = change('revoke', 'b', approval='back', expected=1)
                                assert result['state'] == 'cancelled'
                                record('revocation-signer-ownership-cancelled-and-approved-lost-key-recovery')
                                record('old-key-removal-after-document-acceptance-preserves-data')
                            elif phase == 'unreadable':
                                overlay = digest(media/'nand.overlay');fault(normal, registry_media, 2)
                                original = bytes.fromhex(registry_media['original_hex'])
                                backup = temp/'partial.keys'
                                result, _ = device(['keys', 'backup-unreadable', backup])
                                assert result['status'] == 'partially_backed_up'
                                snapshot = compare_snapshot(backup, original)
                                assert result['sha256'] == snapshot['sha256']
                                assert digest(media/'nand.overlay') == overlay
                                shutil.copyfile(backup, folder/backup.name)
                                device(['keys', 'repair-unreadable', '--public-key', public['b'], '--label', 'Restored B',
                                        '--backup', backup], expected=1)
                                assert digest(media/'nand.overlay') == overlay
                                record('read-only-partial-backup-and-existing-destination-refusal', snapshot=snapshot)
                                for action in ('cancel', 'clear', 'move', 'approve'):
                                    fault(normal, registry_media, 2);backup = temp/('partial-'+action+'.keys')
                                    def change_fault():
                                        if action == 'clear':fault(normal, registry_media, 0)
                                        if action == 'move':fault(normal, {**registry_media, 'page': registry_media['page']+1}, 2)
                                    result, messages = device(['keys', 'repair-unreadable', '--public-key', public['b'],
                                                              '--label', 'Restored B', '--backup', backup],
                                                             expected=0 if action=='approve' else 1,
                                                             approval='back' if action=='cancel' else 'ok',
                                                             fingerprint=fingerprints['b'], before_consent=change_fault)
                                    assert compare_snapshot(backup, original) == snapshot
                                    shutil.copyfile(backup, folder/backup.name)
                                    if action == 'approve':
                                        assert result['state'] == 'complete' and snapshot['sha256'] in messages
                                        assert keys.keys()['keys'][0]['fingerprint'] == fingerprints['b']
                                        saved('partial-repaired')
                                    else:
                                        assert result['state'] == ('cancelled' if action=='cancel' else 'failed')
                                        if action != 'cancel':assert result['error'] == ('registry_fully_readable' if action=='clear' else 'stale_registry')
                                        assert digest(media/'nand.overlay') == overlay
                                    record('partial-repair-'+action+'-with-exact-backup')
                            elif phase == 'damaged':
                                assert device(['keys', 'status'])[0]['registry'] == 'corrupt'
                                damaged = keys.damage_info()
                                for name, approval, expected in (('cancelled', 'back', 1), ('repaired', 'ok', 0)):
                                    backup = temp/(name+'.keys')
                                    result, messages = device(['keys', 'repair', '--public-key', public['b'], '--label', 'Restored B',
                                                              '--backup', backup], approval=approval,
                                                             fingerprint=fingerprints['b'], expected=expected)
                                    assert result['state'] == ('cancelled' if expected else 'complete')
                                    assert digest(backup) == damaged['sha256'] and damaged['sha256'] in messages
                                    shutil.copyfile(backup, folder/backup.name)
                                assert (folder/'cancelled.keys').read_bytes() == (folder/'repaired.keys').read_bytes()
                                saved('repaired');record('verified-damaged-backup-cancel-and-approved-registry-repair')
                            else:
                                if phase == 'unreadable-cold':fault(normal, registry_media, 2)
                                values = device(['keys', 'list'])[0]
                                assert len(values['keys']) == 1 and values['keys'][0]['fingerprint'] == fingerprints['b']
                                assert values['keys'][0]['state'] == 'active'
                                if phase in ('repaired-cold', 'unreadable-cold'):assert values['serial'] == 1
                                launch();normal.run({'steps': [{'capture': phase}]}, steps)
                                home();saved(phase);record(phase+'-trust-launch-and-exact-saved-data')
                        finally:
                            if registry_media:fault(normal, registry_media, 0)
                            normal.close();write_json(folder/'steps.json', steps)
                    runtime = exercise(start, qemu, firmware, workspace=media, controls=controls)
                    assert runtime['result'] == 1 and runtime['os_responsive'], runtime
                    write_json(folder/'runtime.json', runtime)
                    shutil.copyfile(media/'nand.overlay', folder/'nand.overlay')
                    root = json.loads(subprocess.check_output([fixture, 'inspect-app', media/'nand.overlay', 'private-notebook'],
                                                             text=True, timeout=30))
                    write_json(folder/'independent-root.json', root)
                    if original_root is None:original_root = root
                    else:assert root == original_root, ('Unexpected package/data mutation', phase, root, original_root)
            report['temporary_private_keys'] = 'created solely for synthetic qualification; removed with temporary directory'
        assert sources == {name: digest(ROOT/name) for name in source_names}
        assert sdk_identity == identity(ROOT/'sdk')
        report['status'] = 'passed';write_json(output/'report.json', report)
    except BaseException as error:
        report.update(status='failed', error=str(error));write_json(output/'report.json', report);raise


if __name__ == '__main__':main()
