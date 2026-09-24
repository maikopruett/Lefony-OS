#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual publish CLI/ARM half of the website's isolated TLS/D1/R2 journey."""
import argparse
import atexit
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid

from sdk_frozen_access import command_prefix

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--ca-file', type=Path, required=True)
    parser.add_argument('--seed-attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sdk', type=Path, default=ROOT / 'sdk')
    parser.add_argument('--qemu', type=Path, required=True)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, help='Relocated macOS or Linux desktop SDK')
    parser.add_argument('--native-credentials', action='store_true', help='Use and remove temporary fixture-origin platform credentials')
    parser.add_argument('--deny-root', type=Path, action='append', default=[])
    parser.add_argument('--access-launcher', type=Path, help='Required native Linux Landlock launcher')
    parser.add_argument('--interpreter', type=Path, help='Explicit interpreter for frozen Linux tools')
    parser.add_argument('--isolated-secret-service', type=Path, help='Linux requires its new private GNOME fixture control directory')
    parser.add_argument('--fixture-public-key', type=Path, help='Explicit public emulator test key for the local signed download only')
    args = parser.parse_args()
    sys.path.insert(0, str(args.sdk.resolve() / 'tools'))
    import cli
    import store_credentials
    import store_projects
    import store_mutations
    from store_credentials import Credentials
    from store_snapshot import verify
    from build import digest, identity
    from signing import public_der

    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    frozen = args.bundle.resolve() if args.bundle else None
    candidate = None
    fixture = None
    credential_audits = []
    fixture_trust = []
    fixture_key_sha256 = None
    if frozen:
        assert platform.system() in ('Darwin', 'Linux') and args.native_credentials
        if platform.system() == 'Linux':
            assert args.access_launcher and args.isolated_secret_service and os.environ.get('DBUS_SESSION_BUS_ADDRESS')
            fixture = args.isolated_secret_service.resolve(strict=True)
            ready = json.loads((fixture / 'ready.json').read_text())
            assert ready['schema'] == 1 and ready['isolated_test_service'] is True
            assert ready['bus_address'] == os.environ['DBUS_SESSION_BUS_ADDRESS']
            assert isinstance(ready['nonce'], str) and len(ready['nonce']) == 64
            os.environ['XDG_STATE_HOME'] = str(root / 'private-state')
        assert identity(frozen / '_internal/sdk') == identity(args.sdk)
        for line in (frozen / 'SHA256SUMS').read_text().splitlines():
            sha, name = line.split('  ', 1); assert digest(frozen / name) == sha, name
        candidate = json.loads((frozen / 'candidate.json').read_text())
        assert digest(args.firmware) == candidate['firmware_sha256']
        assert digest(args.qemu) == candidate['qemu_sha256']
        if args.fixture_public_key:
            fixture_der = public_der(args.fixture_public_key)
            assert fixture_der == public_der(ROOT / 'tests/fixtures/prime_g2_emulator_update_public.pem'), 'Only the public emulator fixture key is allowed here'
            fixture_key_sha256 = hashlib.sha256(fixture_der).hexdigest()
            bundled_keys = [public_der(path) for path in (frozen / '_internal/sdk/trust').glob('*.pem')]
            if fixture_der not in bundled_keys:
                fixture_trust = ['--public-key', str(args.fixture_public_key.resolve())]
    project = root / 'External upload é'
    shutil.copytree(args.seed_attempt / 'project', project, ignore=shutil.ignore_patterns('build', '.lefony', 'sdk.lock.json'))
    shutil.copytree(args.seed_attempt / 'inputs/store', project / 'store')
    for path in project.rglob('*'):
        if path.is_file(): path.chmod(0o644)
    metadata = json.loads((project / 'app.json').read_text())
    metadata.update(id='upload-counter', version='1.0.0')
    (project / 'app.json').write_text(json.dumps(metadata))
    for name in ('.git/config', '.env', 'build/private-capture', '.lefony/private.json'):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('EXCLUDED-PUBLISH-CLIENT-SECRET')

    class MemoryKeyring:
        values = {}
        def get_password(self, service, user): return self.values.get((service, user))
        def set_password(self, service, user, value): self.values[service, user] = value
        def delete_password(self, service, user): self.values.pop((service, user), None)
    backend = MemoryKeyring()
    native_credentials = None
    native_directories = []
    if frozen:
        if platform.system() == 'Darwin':
            native_credentials = Credentials(args.origin)
            assert native_credentials.read() is None, 'Fixture origin already has native credentials'
        state_root = store_projects.state_directory()
        for index in (1, 2):
            account_id = f'github:{index}'
            native_directories.append(store_projects.registry_directory(state_root, args.origin, account_id))
            binding = {'schema': 1, 'origin': args.origin, 'account_id': account_id, 'app_id': 'upload-counter'}
            native_directories.append(state_root / 'operations' / hashlib.sha256(store_mutations.canonical(binding)).hexdigest())
        assert all(not path.exists() and not path.is_symlink() for path in native_directories), 'Fixture origin already has native project state'
    else:
        store_credentials.platform_backend = lambda: backend
        store_projects.state_directory = lambda: root / 'private-state'
        store_mutations.state_directory = lambda: root / 'private-state'
    def account(index):
        if frozen:
            command(['login', '--no-browser', '--label', f'Frozen publication author {index}'], plain=True)
            value = command(['whoami'])
            assert value['account'] == {'id': f'github:{index}', 'login': f'author{index}'}
            return
        Credentials(args.origin).save({'schema': 1, 'token': 'lfsdk1_' + ('ab' if index == 1 else 'cd') * 32,
            'account': {'id': f'github:{index}', 'login': f'author{index}'},
            'session_id': ('11111111-1111-4111-8111-111111111111' if index == 1 else '22222222-2222-4222-8222-222222222222'),
            'expires_at': 9999999999})
    options = ['--store-origin', args.origin, '--store-ca-file', str(args.ca_file)]
    runtime = ['--qemu', str(args.qemu), '--firmware', str(args.firmware)]
    commands = []
    environment = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'LEFONY_SDK_NEWLIB')}
    environment['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'
    prefix, access = command_prefix(ROOT, frozen, root, launcher=args.access_launcher,
                                    interpreter=args.interpreter) if frozen else ([], {})
    if frozen and platform.system() == 'Darwin':
        prefix[2] += ''.join(f'(deny file-read* (subpath {json.dumps(str(p.resolve()))}))' for p in args.deny_root)
    if frozen and platform.system() == 'Linux':
        separator = prefix.index('--')
        prefix[separator:separator] = ['--read', str(args.ca_file.resolve(strict=True))]
        if args.fixture_public_key:
            prefix[separator:separator] = ['--read', str(args.fixture_public_key.resolve(strict=True))]
    def frozen_command(words):
        invocation = [*prefix, str(frozen / 'lefony-sdk'), '--project', str(project),
                      *words, *(options if words[0] not in ('inspect', 'launch') else [])]
        process = subprocess.Popen(invocation, cwd=root, env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=300)
            return process.returncode, stdout, stderr
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try: process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.communicate(timeout=5)
    def command(words, expected=0, json_result=False, plain=False):
        if frozen:
            status, text, errors = frozen_command(words)
        else:
            sys.argv = ['lefony-sdk', '--project', str(project), *words, *options]
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status = cli.main()
            text, errors = stdout.getvalue(), stderr.getvalue()
        assert not re.search(r'lfsdk1_[0-9a-f]{64}', text + errors), 'Credential appeared in command output'
        (root / f'command-{len(commands) + 1}.log').write_text(text + errors)
        commands.append({'args': words, 'exit_code': status})
        assert status == expected, (words, text[-3000:], errors)
        print('CLI step ' + str(len(commands)) + ' passed: ' + ' '.join(words[:2]), flush=True)
        if expected and not json_result:
            return errors
        if plain: return text
        # Progress lines precede the one final pretty-printed result object.
        position = text.find('{\n')
        assert position >= 0, text
        return json.loads(text[position:])

    def credential_control(operation, **values):
        assert fixture is not None
        identifier = uuid.uuid4().hex
        temporary, destination = fixture / 'command.partial', fixture / 'command.json'
        assert not temporary.exists() and not destination.exists()
        temporary.write_text(json.dumps({'id': identifier, 'nonce': ready['nonce'],
            'operation': operation, **values}))
        temporary.chmod(0o600); temporary.replace(destination)
        response = fixture / (identifier + '.json'); deadline = time.monotonic() + 30
        while not response.exists():
            assert time.monotonic() < deadline, 'Private credential control timed out'
            time.sleep(.05)
        audit = json.loads(response.read_text())
        assert audit['id'] == identifier and audit['operation'] == operation and audit['status'] == 'passed'
        credential_audits.append(audit)
        return audit

    def native_empty():
        if native_credentials is not None:
            return native_credentials.read() is None
        # Inspect only the declared private fixture before using the SDK. A
        # whoami probe could clear a pre-existing revoked session.
        return credential_control('audit', service='Lefony SDK: ' + args.origin)['items'] == 0

    def native_cleanup():
        if not frozen: return
        result = {'logout_command_passed': False, 'credentials_removed': False, 'fixture_project_records_removed': False}
        try:
            command(['logout'])
            assert native_empty()
            result['logout_command_passed'] = True
        finally:
            # This origin was empty before the test and belongs to its local
            # fixture only. Preserve cleanup evidence even if the server failed.
            if native_credentials is not None and native_credentials.read() is not None:
                native_credentials.clear()
            result['credentials_removed'] = native_empty()
            for path in native_directories:
                if path.exists():
                    target = root / 'native-state' / path.parent.name / path.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(path, target)
                    shutil.rmtree(path)
            result['fixture_project_records_removed'] = all(not p.exists() for p in native_directories)
            if fixture is not None and result['credentials_removed']:
                result['fixture_shutdown'] = credential_control('shutdown')['credentials_removed']
            (root / 'native-cleanup.json').write_text(json.dumps(result, indent=2) + '\n')
    if frozen:
        assert native_empty(), 'Fixture origin already has native credentials'
        atexit.register(native_cleanup)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    account(1)

    initial = command(['publish', *runtime], expected=1)
    assert 'securely' in initial
    attempts = sorted((project / '.lefony/publish').iterdir())
    assert len(attempts) == 1
    first = attempts[0]
    progress = command(['publish', '--status', first.name])
    assert progress['state'] == 'uploading' and len(progress['parts']) == 1
    # Ordinary edits after preparation cannot change what resumes.
    (project / 'store/description.md').write_text('Changes for release two. <script>Literal.</script>')
    first_result = command(['publish', '--resume', first.name])
    assert first_result['published'] and first_result['release']['version'] == '1.0.0'
    assert command(['publish', '--resume', first.name])['release']['id'] == first_result['release']['id']
    metadata['version'] = '1.1.0'
    (project / 'app.json').write_text(json.dumps(metadata))
    (project / 'store/release-notes.md').write_text('Second release through the same CLI.')
    second_result = command(['publish', *runtime])
    assert second_result['published'] and second_result['release']['version'] == '1.1.0'
    assert second_result['release']['id'] != first_result['release']['id']
    base_path = project / '.lefony/store-base.json'
    newest_baseline = base_path.read_bytes()
    assert command(['publish', '--resume', first.name])['release']['id'] == first_result['release']['id']
    assert base_path.read_bytes() == newest_baseline
    library = command(['apps', 'show', 'upload-counter'])
    assert {release['version'] for release in library['releases']} == {'1.0.0', '1.1.0'}
    account(2)
    assert 'different bytes, store, account' in command(['publish', '--resume', first.name], expected=1)
    command(['apps', 'show', 'upload-counter'], expected=1)
    account(1)
    # Prepare a third exact ARM-tested version for the website path. Then make
    # local edits before the website accepts it, so the merge has a real conflict.
    metadata['version'] = '1.2.0'
    (project / 'app.json').write_text(json.dumps(metadata))
    (project / 'store/description.md').write_text('Third release submitted through the website.')
    (project / 'store/release-notes.md').write_text('Website release notes.')
    third = command(['publish', '--dry-run', *runtime])
    metadata['version'] = '1.1.0'
    (project / 'app.json').write_text(json.dumps(metadata))
    (project / 'store/description.md').write_text('Local unpublished description.')
    (project / 'store/release-notes.md').write_text('Second release through the same CLI.')
    (project / 'store/listing.json').write_text('{"schema":1,"publish_source":false}')
    (project / 'store/icon.png').unlink()
    print('READY_FOR_WEBSITE_LISTING_UPDATE ' + third['attempt_id'], flush=True)
    assert sys.stdin.readline().strip() == 'website-updated'
    assert 'Listing changed' in command(['publish', *runtime], expected=1)
    review = command(['listing', 'pull', '--dry-run', '--take-remote', 'icon'], expected=1, json_result=True)
    assert review['state'] == 'conflicts' and review['conflicts'] == ['description']
    merged = command(['listing', 'pull', '--plan', review['plan_id'], '--take-local', 'description'])
    assert merged['state'] == 'applied' and (project / 'store/icon.png').is_file()
    assert (project / 'store/description.md').read_text() == 'Local unpublished description.'
    assert (project / 'store/release-notes.md').read_text().strip() == 'Website release notes.'
    assert json.loads((project / 'store/listing.json').read_text())['publish_source'] is False
    assert json.loads((project / 'app.json').read_text())['version'] == '1.1.0'
    newest_baseline = base_path.read_bytes()
    assert json.loads(newest_baseline)['content']['description'] == 'Third release submitted through the website.'
    listing_review = command(['listing', 'push', '--dry-run'])
    assert listing_review['state'] == 'review' and set(listing_review['changes']) == {'description'}
    assert 'Saved operation:' in command(['listing', 'push'], expected=1)
    edits = list((project / '.lefony/operations').iterdir())
    assert len(edits) == 1
    edit = command(['listing', 'push', '--status', edits[0].name])
    assert edit['state'] == 'accepted' and edit['operation']['kind'] == 'listing'
    assert edit['operation']['content']['description'] == 'Local unpublished description.'
    assert json.loads((project / 'store/listing.json').read_text())['publish_source'] is False
    print('READY_FOR_BROWSER_METADATA', flush=True)
    assert sys.stdin.readline().strip() == 'metadata-updated'
    assert command(['listing', 'push'], expected=1, json_result=True)['state'] == 'conflicts'
    assert command(['listing', 'pull'])['state'] == 'applied'
    assert (project / 'store/release-notes.md').read_text() == 'Browser metadata correction.\n'
    newest_baseline = base_path.read_bytes()
    assert command(['listing', 'push', '--status', edits[0].name])['operation'] == edit['operation']
    assert base_path.read_bytes() == newest_baseline
    print('READY_FOR_SDK_WITHDRAWAL', flush=True)
    assert sys.stdin.readline().strip() == 'withdraw-now'
    assert command(['apps', 'withdraw', 'upload-counter', '--dry-run'])['state'] == 'review'
    withdrawal = command(['apps', 'withdraw', 'upload-counter'])
    assert withdrawal['state'] == 'accepted' and withdrawal['current']['active'] == 0
    assert 'Listing changed' in command(['publish', *runtime], expected=1)
    status = command(['publish', '--status', first.name])
    assert not status['published'] and status['release']['state'] == 'withdrawn'
    assert base_path.read_bytes() == newest_baseline
    # A fresh immutable version after withdrawal must stay published when an
    # old withdrawal receipt is replayed. Pull acknowledges the changed state.
    assert command(['listing', 'pull'])['state'] == 'applied'
    metadata['version'] = '1.3.0'
    (project / 'app.json').write_text(json.dumps(metadata))
    (project / 'store/listing.json').write_text('{"schema":1,"publish_source":true}')
    fourth = command(['publish', *runtime])
    assert fourth['published'] and fourth['release']['version'] == '1.3.0'
    replay = command(['apps', 'withdraw', 'upload-counter', '--resume', withdrawal['operation_id']])
    assert replay['operation'] == withdrawal['operation'] and replay['current']['active'] == 1
    print('READY_FOR_STAGING_CLEANUP', flush=True)
    assert sys.stdin.readline().strip() == 'cleaned'
    accepted_run = None
    if frozen:
        accepted = root / 'accepted.lfapp'
        inspection = command(['inspect', str(accepted), *fixture_trust])
        assert inspection['signature'] == 'verified' and inspection['id'] == 'upload-counter' and inspection['version'] == '1.3.0'
        assert inspection['payload_sha256'] == hashlib.sha256(accepted.read_bytes()[352:]).hexdigest()
        accepted_run = command(['launch', str(accepted), '--test', '--headless', *runtime, *fixture_trust])
        assert accepted_run['result'] == 1 and accepted_run['os_responsive']
        assert accepted_run['package_sha256'] == digest(accepted)
    assert command(['publish', '--status', first.name])['release']['id'] == first_result['release']['id']
    assert not command(['publish', '--cancel', first.name])['published']
    evidence = []
    for attempt in sorted((project / '.lefony/publish').iterdir()):
        submission = verify(attempt)
        report = json.loads((attempt / 'upload/report.json').read_text())
        assert report['summary'] == {'passed': 2, 'failed': 0, 'skipped': 0}
        for item in submission['files']:
            data = (attempt / 'upload' / item['path']).read_bytes()
            assert b'EXCLUDED-PUBLISH-CLIENT-SECRET' not in data and str(project).encode() not in data
        evidence.append({'attempt_id': attempt.name, 'submission_sha256': digest(attempt / 'submission.json'),
            'source_sha256': submission['files'][0]['sha256'], 'unsigned_package_sha256': submission['files'][1]['sha256'],
            'report_sha256': submission['files'][2]['sha256'], 'test_summary': report['summary'],
            'receipt': json.loads((attempt / 'receipt.json').read_text())['release'] if (attempt / 'receipt.json').exists() else None})
    assert len(evidence) == 4
    if frozen:
        native_cleanup(); atexit.unregister(native_cleanup)
        for line in (frozen / 'SHA256SUMS').read_text().splitlines():
            sha, name = line.split('  ', 1); assert digest(frozen / name) == sha, name
    (root / 'report.json').write_text(json.dumps({'schema': 1, 'status': 'passed', 'physical': 'not_tested',
        'credentials': ('native-Keychain-fixture' if platform.system() == 'Darwin' else 'native-Secret-Service-fixture') if frozen else 'memory-fixture',
        'credential_audits': credential_audits, 'access': access, 'host_machine': platform.machine(), 'native_clean_host_qualified': False,
        'interpreter_sha256': digest(args.interpreter) if args.interpreter else None,
        'harness_sha256': digest(Path(__file__)), 'tls': 'verified-local-certificate', 'sdk_sha256': identity(args.sdk),
        'frozen_candidate': candidate, 'bundle_checksums_sha256': digest(frozen / 'SHA256SUMS') if frozen else None,
        'homebrew_and_checkout_access': 'denied for frozen commands' if frozen else 'not_enforced',
        'accepted_download_runtime': accepted_run, 'fixture_public_key_sha256': fixture_key_sha256,
        'explicit_fixture_public_key': bool(fixture_trust),
        'firmware_sha256': digest(args.firmware), 'qemu_sha256': digest(args.qemu), 'commands': commands, 'attempts': evidence,
        'listing_operation': edit['operation'], 'withdrawal': withdrawal['operation'], 'republished_release': fourth['release']}, indent=2) + '\n')
    print('PASS: actual publish CLI, exact ARM packages, website update/pull/merge, interrupted upload, stale edits and account separation', flush=True)


if __name__ == '__main__':
    main()
