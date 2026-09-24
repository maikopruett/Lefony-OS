# SPDX-License-Identifier: GPL-3.0-or-later
"""Only the platform credential store; no file or plugin-based token fallback."""
import json
import platform
import re
from store_client import StoreError, TOKEN, store_origin


def credential(value):
    if not isinstance(value, dict) or set(value) != {'schema', 'token', 'account', 'session_id', 'expires_at'} or value['schema'] != 1:
        raise StoreError('Invalid saved SDK session. Run lefony-sdk login again.')
    account = value['account']
    if not isinstance(account, dict) or set(account) != {'id', 'login'} or not isinstance(account['id'], str) or not re.fullmatch(r'github:[1-9][0-9]{0,19}', account['id']) or not isinstance(account['login'], str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,39}', account['login']):
        raise StoreError('Invalid SDK account identity.')
    if not isinstance(value['token'], str) or not TOKEN.fullmatch(value['token']) or not isinstance(value['session_id'], str) or not re.fullmatch(r'[0-9a-f-]{36}', value['session_id']) or type(value['expires_at']) is not int or value['expires_at'] <= 0:
        raise StoreError('Invalid saved SDK session. Run lefony-sdk login again.')
    return value


def platform_backend():
    try:
        # Select trusted built-in implementations directly. Do not load a user's
        # keyring config/entry-point backend, which may be a plaintext file store.
        system = platform.system()
        if system == 'Darwin':
            from keyring.backends.macOS import Keyring
        elif system == 'Windows':
            from keyring.backends.Windows import WinVaultKeyring as Keyring
        elif system == 'Linux':
            from keyring.backends.SecretService import Keyring
        else:
            raise StoreError('SDK account storage supports macOS, Windows and Linux Secret Service.')
        backend = Keyring()
        if backend.priority <= 0:
            raise StoreError('The platform credential store is unavailable.')
        return backend
    except StoreError:
        raise
    except Exception:
        raise StoreError('Platform credential storage is unavailable. Install the SDK account dependencies and unlock Keychain, Credential Manager or Linux Secret Service.') from None


class Credentials:
    def __init__(self, origin, *, backend=None):
        self.service = 'Lefony SDK: ' + store_origin(origin)
        self.backend = backend if backend is not None else platform_backend()

    def read(self):
        try:
            raw = self.backend.get_password(self.service, 'active')
        except Exception:
            raise StoreError('Could not read the SDK session from platform credential storage.') from None
        if raw is None:
            return None
        if not isinstance(raw, str) or len(raw) > 4096:
            raise StoreError('Invalid saved SDK credential.')
        try:
            return credential(json.loads(raw))
        except (ValueError, TypeError):
            raise StoreError('Invalid saved SDK credential. Use SDK access on the website to revoke it, then sign in again.') from None

    def save(self, value):
        raw = json.dumps(credential(value), sort_keys=True, separators=(',', ':'))
        try:
            self.backend.set_password(self.service, 'active', raw)
        except Exception:
            raise StoreError('Could not save the SDK session in platform credential storage.') from None

    def clear(self):
        try:
            if self.backend.get_password(self.service, 'active') is not None:
                self.backend.delete_password(self.service, 'active')
        except Exception:
            raise StoreError('Could not remove the local SDK credential. Remote revocation may already have succeeded; retry logout.') from None
