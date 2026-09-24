# SPDX-License-Identifier: GPL-3.0-or-later
"""Listing reconciliation, stale reviews and interrupted local file transactions."""
import copy
import io
import json
from pathlib import Path
import struct
import zlib

import pytest
from test_sdk_store_publication import project
from store_client import StoreClient, StoreError
from store_listing import canonical, image
from store_projects import link, write_json
from store_publish import identity, publish
from store_snapshot import sha
import store_listing_sync as sync

ACCOUNT = {'id': 'github:123', 'login': 'author'}


def png(width, height, color):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(
        b'IDAT', zlib.compress((b'\0' + bytes(color) * width) * height)) + chunk(b'IEND', b'')


class Store:
    origin = 'https://store.example'

    def __init__(self, project):
        local, _, self.images = sync.local_listing(project)
        self.current = {'schema': 1, 'app_id': 'hello-app', 'revision': 4, 'hidden': False,
                        'latest_version_key': '000001000000000000', 'release': {'id': 'recorded', 'version': '1.0.0', 'state': 'published'},
                        'content': local}

    def request(self, path, method='GET', body=None):
        assert path == '/sdk/apps/hello-app/listing'
        return copy.deepcopy(self.current)

    def app(self, app_id):
        assert app_id == 'hello-app'
        return {'app': {'id': app_id, 'owner_id': ACCOUNT['id'], 'revision': self.current['revision']}}

    def get_image(self, app_id, digest):
        assert app_id == 'hello-app'
        return self.images[digest]

    def edit(self, **content):
        self.current['revision'] += 1
        self.current['content'].update(content)

    def picture(self, kind, color):
        data, descriptor = image(png(96 if kind == 'icon' else 320, 96 if kind == 'icon' else 240, color), kind)
        self.images[descriptor['sha256']] = data
        return descriptor


def linked(project, *, known=True):
    store = Store(project)
    binding = identity(store, ACCOUNT, 'hello-app')
    write_json(project / '.lefony/store.json', binding)
    write_json(project / '.lefony/store-base.json', {**binding, 'revision': 4, **({'content': store.current['content']} if known else {})})
    return store


def test_pull_merges_disjoint_edits_and_retains_permission_source_and_store_base(project):
    store = linked(project)
    original_app = json.loads((project / 'app.json').read_text())
    original_source = (project / 'src/main.cpp').read_bytes()
    (project / 'store/listing.json').write_text('{"schema":1,"publish_source":false}')
    (project / 'store/release-notes.md').write_text('Local unreleased work\n')
    (project / 'store/author-notes.txt').write_text('Preserve this unrelated file')
    store.edit(description='Updated on website', name='New listing name', repository_url='https://github.com/example/app',
               icon=store.picture('icon', (9, 22, 55)), screenshots=[store.picture('screenshot', (3, 4, 5)), store.picture('screenshot', (8, 7, 6))])
    before = sync.hashes(sync.local_listing(project)[1])
    review = sync.pull(project, store, ACCOUNT, dry_run=True)
    assert review['state'] == 'review' and review['conflicts'] == []
    assert sync.hashes(sync.local_listing(project)[1]) == before
    assert '&lt;script&gt;literal text&lt;/script&gt;' in Path(review['preview']).read_text()
    result = sync.pull(project, store, ACCOUNT, plan_id=review['plan_id'])
    assert result['state'] == 'applied'
    content, _, _ = sync.local_listing(project)
    assert content == {**store.current['content'], 'release_notes': 'Local unreleased work'}
    updated_app = json.loads((project / 'app.json').read_text())
    assert updated_app == {**original_app, 'name': 'New listing name'}
    assert (project / 'src/main.cpp').read_bytes() == original_source
    assert json.loads((project / 'store/listing.json').read_text())['publish_source'] is False
    assert (project / 'store/author-notes.txt').read_text() == 'Preserve this unrelated file'
    assert sorted(p.name for p in (project / 'store/screenshots').glob('*.png')) == ['01.png', '02.png']
    assert json.loads((project / '.lefony/store-base.json').read_text())['content'] == store.current['content']
    store.edit(release_notes='Different website notes')
    next_review = sync.pull(project, store, ACCOUNT)
    assert next_review['conflicts'] == ['release_notes']
    assert sync.pull(project, store, ACCOUNT, plan_id=next_review['plan_id'], take_remote=['release_notes'])['state'] == 'applied'


@pytest.mark.parametrize('known', [True, False])
def test_conflicts_need_explicit_choices_without_destroying_local_edits(project, known):
    store = linked(project, known=known)
    (project / 'store/description.md').write_text('Unpublished local text')
    store.edit(description='Website text')
    before = sync.hashes(sync.local_listing(project)[1])
    result = sync.pull(project, store, ACCOUNT)
    assert result['state'] == 'conflicts' and result['conflicts'] == ['description']
    assert sync.hashes(sync.local_listing(project)[1]) == before
    result = sync.pull(project, store, ACCOUNT, plan_id=result['plan_id'], take_local=['description'])
    assert result['state'] == 'applied'
    assert (project / 'store/description.md').read_text() == 'Unpublished local text'
    assert json.loads((project / '.lefony/store-base.json').read_text())['content']['description'] == 'Website text'


@pytest.mark.parametrize('side', ['local', 'remote', 'identity'])
def test_review_rejects_intervening_changes_on_either_side(project, side):
    store = linked(project)
    store.edit(description='Remote text')
    result = sync.pull(project, store, ACCOUNT, dry_run=True)
    if side == 'local':
        with (project / 'store/description.md').open('a') as stream:
            stream.write(' ')  # Raw bytes changed even though normalized text did not.
    elif side == 'remote':
        store.edit(release_notes='Arrived after review')
    before = sync.hashes(sync.local_listing(project)[1])
    with pytest.raises(ValueError, match='changed|different store'):
        sync.pull(project, store, {'id': 'another'} if side == 'identity' else ACCOUNT, plan_id=result['plan_id'])
    assert sync.hashes(sync.local_listing(project)[1]) == before


@pytest.mark.parametrize('crash', [False, True])
def test_failed_and_interrupted_apply_restore_exact_original_bytes(project, monkeypatch, crash):
    store = linked(project)
    store.edit(name='Updated', description='Remote description', release_notes='Remote notes')
    before = sync.hashes(sync.local_listing(project)[1])
    review = sync.pull(project, store, ACCOUNT, dry_run=True)
    replace = sync.replace_file
    count = 0
    def fail_once(*args):
        nonlocal count
        count += 1
        if count == 2:
            raise KeyboardInterrupt() if crash else OSError('Simulated full disk')
        return replace(*args)
    monkeypatch.setattr(sync, 'replace_file', fail_once)
    with pytest.raises(KeyboardInterrupt if crash else OSError):
        sync.pull(project, store, ACCOUNT, plan_id=review['plan_id'])
    if crash:
        with pytest.raises(StoreError, match='needs recovery'):
            publish(project, None, None, None, store, ACCOUNT)
        assert sync.recover(project, review['plan_id'])['state'] == 'rolled_back'
    assert sync.hashes(sync.local_listing(project)[1]) == before


def test_recovery_never_overwrites_edits_made_after_a_crash(project, monkeypatch):
    store = linked(project)
    store.edit(name='Remote name', description='Remote description')
    review = sync.pull(project, store, ACCOUNT, dry_run=True)
    replace = sync.replace_file
    def crash(project, name, expected, data):
        if name == 'store/description.md':
            raise KeyboardInterrupt()
        replace(project, name, expected, data)
    monkeypatch.setattr(sync, 'replace_file', crash)
    with pytest.raises(KeyboardInterrupt):
        sync.pull(project, store, ACCOUNT, plan_id=review['plan_id'])
    (project / 'store/description.md').write_text('User recovery edit')
    with pytest.raises(ValueError, match='edited after interrupted pull'):
        sync.recover(project, review['plan_id'])
    assert (project / 'store/description.md').read_text() == 'User recovery edit'


@pytest.mark.parametrize('damage', ['symlink', 'media', 'incomplete', 'conflicting_choices'])
def test_pull_rejects_unsafe_or_incomplete_inputs(project, tmp_path, damage):
    store = linked(project)
    store.edit(icon=store.picture('icon', (7, 8, 9)))
    if damage == 'symlink':
        path = project / 'store/icon.png'
        outside = tmp_path / 'outside.png'
        path.rename(outside)
        path.symlink_to(outside)
    elif damage == 'media':
        store.images[store.current['content']['icon']['sha256']] = png(96, 96, (2, 2, 2))
    elif damage == 'incomplete':
        store.current['content']['icon'] = None
    with pytest.raises(ValueError):
        sync.pull(project, store, ACCOUNT, take_local=['icon'] if damage == 'conflicting_choices' else [], take_remote=['icon'])


def test_first_link_records_exact_content_and_repeat_link_does_not_acknowledge_edits(project, tmp_path):
    store = Store(project)
    link(project, store, ACCOUNT, 'hello-app', state_root=tmp_path / 'registry')
    before = (project / '.lefony/store-base.json').read_bytes()
    assert json.loads(before)['content'] == store.current['content']
    store.edit(description='New remote edit')
    link(project, store, ACCOUNT, 'hello-app', state_root=tmp_path / 'registry')
    assert (project / '.lefony/store-base.json').read_bytes() == before


def test_maximum_unicode_listing_can_be_reviewed_and_applied(project):
    (project / 'store/description.md').write_text('\u754c' * 2000)
    (project / 'store/release-notes.md').write_text('\u754c' * 4000)
    store = linked(project)
    store.edit(description='\u6587' * 2000, release_notes='\u6587' * 4000)
    review = sync.pull(project, store, ACCOUNT, dry_run=True)
    assert sync.pull(project, store, ACCOUNT, plan_id=review['plan_id'])['state'] == 'applied'
    assert sync.local_listing(project)[0] == store.current['content']


def test_image_download_checks_exact_endpoint_headers_digest_and_status(monkeypatch):
    data = png(96, 96, (0, 1, 2))
    digest = sha(data)
    client = StoreClient('https://store.example', token='lfsdk1_' + 'a' * 64)
    calls = []
    def response(content=data, code=200, kind='image/png'):
        return code, kind, digest, 0, content
    def transport(request, ca_file):
        calls.append(request)
        return response()
    monkeypatch.setattr('store_client.exchange', transport)
    assert client.get_image('hello-app', digest) == data
    assert calls[0].full_url == 'https://store.example/api/store/sdk/apps/hello-app/listing/media/' + digest
    assert calls[0].get_header('Authorization') == 'Bearer ' + client.token
    assert calls[0].get_header('Cookie') is None and calls[0].get_header('Origin') is None
    for content, code, kind in [(b'wrong', 200, 'image/png'), (data, 302, 'image/png'), (data, 200, 'text/html')]:
        monkeypatch.setattr('store_client.exchange', lambda *a, **k: response(content, code, kind))
        with pytest.raises(StoreError):
            client.get_image('hello-app', digest)
    with pytest.raises(StoreError):
        client.get_image('https://elsewhere.example', digest)


def test_short_and_detailed_descriptions_merge_independently(project):
    store = linked(project)
    config = json.loads((project / 'store/listing.json').read_text())
    config['short_description'] = 'My concise catalog text.'
    (project / 'store/listing.json').write_text(json.dumps(config))
    store.edit(description='Detailed instructions from the website.')
    result = sync.pull(project, store, ACCOUNT)
    assert result['state'] == 'applied'
    current = sync.local_listing(project)[0]
    assert current['short_description'] == 'My concise catalog text.'
    assert current['description'] == 'Detailed instructions from the website.'
    store.edit(short_description='A different website summary.')
    review = sync.pull(project, store, ACCOUNT, dry_run=True)
    assert review['conflicts'] == ['short_description']
    assert sync.pull(project, store, ACCOUNT, plan_id=review['plan_id'], take_remote=['short_description'])['state'] == 'applied'
    assert json.loads((project / 'store/listing.json').read_text())['short_description'] == 'A different website summary.'


def test_pulling_legacy_project_persists_summary_when_only_details_change(project):
    config = json.loads((project / 'store/listing.json').read_text())
    del config['short_description']
    (project / 'store/listing.json').write_text(json.dumps(config))
    store = linked(project)
    summary = store.current['content']['short_description']
    store.edit(description='New detailed text.')
    assert sync.pull(project, store, ACCOUNT)['state'] == 'applied'
    assert sync.local_listing(project)[0]['short_description'] == summary
    assert json.loads((project / 'store/listing.json').read_text())['short_description'] == summary
