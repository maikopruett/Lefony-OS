#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""CLI half of scripts/test-sdk-accounts.ts in the website repository.

Uses a synthetic in-memory credential backend and real verified local TLS.
No real keychain, store account, publication or calculator is accessed.
"""
import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import webbrowser

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--ca-file', type=Path, required=True)
    parser.add_argument('--sdk', type=Path, default=ROOT / 'sdk')
    args = parser.parse_args()
    sys.path.insert(0, str(args.sdk.resolve() / 'tools'))
    # The browser is driven by the paired Playwright test from the printed URL.
    webbrowser.open = lambda _: True
    import cli
    import store_credentials
    import store_projects
    from store_client import StoreClient, StoreError
    from source import collect

    class MemoryKeyring:
        values = {}
        def get_password(self, service, user): return self.values.get((service, user))
        def set_password(self, service, user, value): self.values[service, user] = value
        def delete_password(self, service, user): self.values.pop((service, user), None)
    backend = MemoryKeyring()
    store_credentials.platform_backend = lambda: backend
    options = ['--store-origin', args.origin, '--store-ca-file', str(args.ca_file)]
    def command(words, project=None, expected=0, visible=False):
        sys.argv = ['lefony-sdk', *(['--project', str(project)] if project else []), *words, *options]
        output = io.StringIO()
        with contextlib.nullcontext() if visible else contextlib.redirect_stdout(output):
            status = cli.main()
        assert status == expected, (words, status, output.getvalue())
        return None if visible or expected else json.loads(output.getvalue())

    # A certificate failure sends no authenticated HTTP request.
    try: StoreClient(args.origin, token='lfsdk1_' + '01' * 32).request('/sdk/me')
    except StoreError: pass
    else: raise AssertionError('Untrusted TLS accepted')
    try: StoreClient(args.origin, ca_file=args.ca_file, token='lfsdk1_' + '01' * 32).request('/sdk/test-redirect')
    except StoreError as error: assert error.status == 302
    else: raise AssertionError('Redirect accepted')

    with tempfile.TemporaryDirectory(prefix='lefony-account-project-') as tmp:
        root = Path(tmp).resolve()
        store_projects.state_directory = lambda: root / 'private-state'
        project = root / 'Local app'; (project / 'src').mkdir(parents=True)
        (project / 'src/main.cpp').write_text('extern "C" void lefony_event() {}\n')
        (project / 'app.json').write_text(json.dumps({'abi': 1, 'id': 'app-00', 'name': 'Sample', 'version': '1.0.0', 'license': 'MIT'}))
        source = collect(project)
        command(['login', '--label', 'SDK browser journey'], visible=True)
        identity = command(['whoami']); assert identity['account'] == {'id': 'github:123', 'login': 'publisher'}
        apps = command(['apps', 'list'])['apps']; assert len(apps) == 55
        history = command(['apps', 'show', 'app-00']); assert len(history['releases']) == 52
        assert command(['project', 'link', 'app-00'], project)['account_id'] == 'github:123'
        assert command(['project', 'list'])['projects'][0]['linked']
        assert collect(project) == source
        assert str(root) not in (project / '.lefony/store.json').read_text()
        command(['apps', 'show', 'other-app'], expected=1)
        print('READY_FOR_REVOCATION', flush=True)
        assert sys.stdin.readline().strip() == 'revoked'
        command(['whoami'], expected=1)
        assert not backend.values
        print('READY_FOR_SECOND_ACCOUNT', flush=True)
        assert sys.stdin.readline().strip() == 'continue'
        command(['login', '--label', 'Second SDK account'], visible=True)
        assert command(['whoami'])['account']['id'] == 'github:456'
        assert [a['id'] for a in command(['apps', 'list'])['apps']] == ['other-app']
        assert command(['project', 'list'])['projects'] == []
        command(['project', 'link', 'app-00'], project, expected=1)
        assert json.loads((project / '.lefony/store.json').read_text())['account_id'] == 'github:123'
        assert command(['logout']) == {'signed_out': True}
        assert not backend.values
        # Offline unlink never constructs a network client or keyring backend.
        sys.argv = ['lefony-sdk', '--project', str(project), 'project', 'unlink']
        assert cli.main() == 0
        assert collect(project) == source
        print('PASS: CLI accounts, pagination, linkage, revocation and account isolation', flush=True)


if __name__ == '__main__': main()
