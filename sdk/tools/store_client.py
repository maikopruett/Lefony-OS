# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded HTTPS access to the SDK store API. Never follows redirects."""
import json
import hashlib
import re
from urllib.parse import urlsplit, urlencode
from urllib.request import Request
from store_http import exchange, TransportError

DEFAULT_ORIGIN = 'https://lefony.com'
TOKEN = re.compile(r'lfsdk1_[0-9a-f]{64}\Z')
APP_ID = re.compile(r'[a-z][a-z0-9-]{0,47}\Z')


class StoreError(ValueError):
    def __init__(self, message, status=0, retry_after=0, details=None):
        super().__init__(message)
        self.status, self.retry_after = status, retry_after
        self.details = details


def store_origin(value):
    if not isinstance(value, str) or not value.isascii() or any(ord(c) <= 32 or c == '\\' for c in value):
        raise StoreError('Use an exact HTTPS store origin, without a path or credentials.')
    url = urlsplit(value)
    try:
        port = url.port
    except ValueError:
        raise StoreError('Invalid store port.') from None
    if url.scheme != 'https' or not url.hostname or url.username is not None or url.password is not None or url.path not in ('', '/') or url.query or url.fragment or port == 0:
        raise StoreError('Use an exact HTTPS store origin, without a path or credentials.')
    host = '[' + url.hostname.lower() + ']' if ':' in url.hostname else url.hostname.lower()
    return 'https://' + host + (':' + str(port) if port not in (None, 443) else '')


class StoreClient:
    def __init__(self, origin=DEFAULT_ORIGIN, *, ca_file=None, token=None):
        self.origin = store_origin(origin)
        self.token = token
        # Certificate setup and verification belong inside the killable worker.
        self.ca_file = ca_file

    def request(self, path, method='GET', body=None, *, authenticated=True):
        from store_listing import canonical
        data = None if body is None else canonical(body)
        maximum = 65536 if path == '/sdk/uploads' and method == 'POST' else 16384
        if method == 'PUT' and re.fullmatch(r'/sdk/apps/[a-z][a-z0-9-]{0,47}/listing', path):
            maximum = 8388608
        if data is not None and len(data) > maximum:
            raise StoreError('SDK store request is too large.')
        return self._request(path, method, data, authenticated=authenticated)

    def put_chunk(self, path, data):
        if not re.fullmatch(r'/sdk/uploads/[0-9a-f-]{36}/files/[0-8]/parts/(?:[0-9]|[12][0-9]|3[01])', path) or not isinstance(data, bytes) or not 1 <= len(data) <= 262144:
            raise StoreError('Invalid SDK upload chunk.')
        return self._request(path, 'PUT', data, chunk=True)

    def get_image(self, app_id, digest):
        if not isinstance(app_id, str) or not APP_ID.fullmatch(app_id) or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise StoreError('Invalid owned listing image.')
        return self._request('/sdk/apps/' + app_id + '/listing/media/' + digest, 'GET', None, image_digest=digest)

    def _request(self, path, method, data, *, authenticated=True, chunk=False, image_digest=None):
        if not re.fullmatch(r'/sdk/[a-zA-Z0-9./?=&_-]+', path) or len(path) > 512 or any(p in ('.', '..') for p in path.split('?', 1)[0].split('/')):
            raise StoreError('Invalid SDK store endpoint.')
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json', 'User-Agent': 'Lefony-SDK/1', 'X-Lefony-Listing-Fields': 'descriptions'}
        if chunk:
            headers.update({'Content-Type': 'application/octet-stream', 'X-Lefony-SHA256': hashlib.sha256(data).hexdigest()})
        if image_digest:
            headers['Accept'] = 'image/png'
        if authenticated:
            if not isinstance(self.token, str) or not TOKEN.fullmatch(self.token):
                raise StoreError('Sign in with lefony-sdk login.')
            headers['Authorization'] = 'Bearer ' + self.token
        request = Request(self.origin + '/api/store' + path, data=data, method=method, headers=headers)
        try:
            status, content_type, digest, retry_after, raw = exchange(request, self.ca_file)
        except TransportError as exc:
            raise StoreError(str(exc), exc.status) from None
        if image_digest and 200 <= status < 300:
            if status != 200 or content_type != 'image/png' or digest != image_digest or hashlib.sha256(raw).hexdigest() != image_digest:
                raise StoreError('Listing image did not match its recorded digest.', status)
            return raw
        if content_type != 'application/json':
            raise StoreError('Store returned an invalid response.', status)
        try:
            result = json.loads(raw.decode('utf-8'))
        except (UnicodeError, ValueError):
            raise StoreError('Store returned invalid JSON.', status) from None
        if not isinstance(result, dict):
            raise StoreError('Store returned an invalid response.', status)
        if status >= 400:
            message = result.get('error')
            if not isinstance(message, str) or len(message) > 500 or any(ord(c) < 32 for c in message) or (self.token and self.token in message):
                message = 'Store request failed.'
            retry = result.get('retry_after', retry_after)
            if isinstance(retry, str) and re.fullmatch(r'[0-9]{1,3}', retry):
                retry = int(retry)
            raise StoreError(message, status, retry if type(retry) is int and 0 <= retry <= 120 else 0, result)
        return result

    def apps(self):
        result, after = [], ''
        while True:
            page = self.request('/sdk/apps' + ('?' + urlencode({'after': after}) if after else ''))
            rows, next_page = page.get('apps'), page.get('next')
            if not isinstance(rows, list) or len(rows) > 50:
                raise StoreError('Store returned an invalid app page.')
            previous = after
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not APP_ID.fullmatch(row['id']) or row['id'] <= previous:
                    raise StoreError('Store returned an invalid app page.')
                previous = row['id']
            result.extend(rows)
            if next_page is None:
                return result
            if not rows or next_page != previous or next_page <= after:
                raise StoreError('Store returned an invalid pagination cursor.')
            after = next_page

    def app(self, app_id):
        if not APP_ID.fullmatch(app_id):
            raise StoreError('Invalid app ID.')
        result, after = None, ''
        while True:
            page = self.request('/sdk/apps/' + app_id + ('?' + urlencode({'after': after}) if after else ''))
            app, rows, next_page = page.get('app'), page.get('releases'), page.get('next')
            if not isinstance(app, dict) or app.get('id') != app_id or not isinstance(rows, list) or len(rows) > 50:
                raise StoreError('Store returned an invalid app history.')
            if result is None:
                result = {'app': app, 'releases': []}
            elif app.get('owner_id') != result['app'].get('owner_id'):
                raise StoreError('App ownership changed during this request. Refresh and try again.')
            previous = after
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,80}', row['id']) or row['id'] <= previous:
                    raise StoreError('Store returned an invalid release page.')
                previous = row['id']
            result['releases'].extend(rows)
            if next_page is None:
                return result
            if not rows or next_page != previous or next_page <= after:
                raise StoreError('Store returned an invalid pagination cursor.')
            after = next_page
