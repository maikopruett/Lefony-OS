# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit folder publication and resumable exact-byte uploads. No device I/O."""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat
import time

from lfapp import manifest
from store_client import StoreError
from store_listing import canonical, parse_json, require, submission_content
from store_projects import bind_project, safe_directory, write_json
from store_snapshot import no_link, prepare, read_file, sha, verify

UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')
MAX_REVISION = 9007199254740991
CHUNK = 262144


def revision(value):
    return type(value) is int and 0 <= value <= MAX_REVISION


def identity(client, account, app_id):
    return {'schema': 1, 'origin': client.origin, 'account_id': account['id'], 'app_id': app_id}


def local_json(project, name):
    path = project / name
    if not path.exists() and not path.is_symlink():
        return None
    return parse_json(read_file(project, name, 65536))


@contextmanager
def publication_lock(project):
    directory = project / '.lefony'
    safe_directory(directory)
    path = directory / 'publish.lock'
    if path.exists() or path.is_symlink():
        info = path.lstat()
        require(no_link(info) and stat.S_ISREG(info.st_mode), 'Publication lock must be a regular file')
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0), 0o600)
    locked = False
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'Publication lock must be a regular file')
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b'\0')
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError:
            raise StoreError('Another publication operation is using this project.') from None
        yield
    finally:
        if locked:
            if os.name == 'nt':
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def retry(call, *, emit, sleep):
    for index in range(3):
        try:
            return call()
        except StoreError as error:
            if index == 2 or error.status not in (0, 408, 429, 500, 502, 503, 504):
                raise
            delay = max(index + 1, min(60, error.retry_after))
            emit(f'Store request interrupted; retrying the same operation in {delay} seconds…')
            sleep(delay)


def baseline(project, client, account, app_id):
    expected = identity(client, account, app_id)
    linked = local_json(project, '.lefony/store.json')
    if linked is not None and linked != expected:
        raise StoreError('Project is linked to a different store, account or app. Use project unlink before changing identity.')
    current = client.request('/sdk/apps/' + app_id + '/publication')
    require(current.get('app_id') == app_id and type(current.get('exists')) is bool and revision(current.get('revision')),
            'Store returned an invalid listing revision')
    if not current['exists']:
        require(current['revision'] == 0, 'Invalid new-app revision')
        return 0
    saved = local_json(project, '.lefony/store-base.json')
    if not isinstance(saved, dict) or {key: saved.get(key) for key in expected} != expected or not revision(saved.get('revision')):
        raise StoreError('Link this owned app with lefony-sdk project link ' + app_id + ' to record its current listing revision before publishing an update.')
    if saved['revision'] != current['revision']:
        raise StoreError(f"Listing changed from revision {saved['revision']} to {current['revision']}. Review and merge the website changes before publishing.", 409, details={'current': current})
    return saved['revision']


def attempt_path(project, identifier):
    require(isinstance(identifier, str) and UUID.fullmatch(identifier), 'Use the saved local attempt UUID')
    path = project / '.lefony/publish' / identifier
    for parent in (project / '.lefony', path.parent, path):
        require(parent.exists() and no_link(parent.lstat()) and parent.is_dir(), 'Publication attempt must be a directory without links')
    return path


def remote_record(project, attempt, client, account, submission):
    expected = {**identity(client, account, submission['app']['id']), 'submission_sha256': sha(canonical(submission))}
    saved = local_json(project, '.lefony/publish/' + attempt.name + '/remote.json')
    if saved is None:
        return None, expected
    require(isinstance(saved, dict) and set(saved) <= set(expected) | {'base_revision', 'upload_id'} and
            all(saved.get(key) == value for key, value in expected.items()) and revision(saved.get('base_revision')) and
            ('upload_id' not in saved or isinstance(saved['upload_id'], str) and UUID.fullmatch(saved['upload_id'])),
            'Saved upload belongs to different bytes, store, account or app; it was not resumed')
    return saved, expected


def accepted(project, attempt, client, account, submission, response):
    release = response.get('release')
    require(response.get('schema') == 1 and response.get('state') == 'accepted' and isinstance(release, dict), 'Store did not return a publication receipt')
    expected = {'app_id': submission['app']['id'], 'version': submission['app']['version'],
                'submission_hash': sha(canonical(submission)), 'source_sha256': submission['files'][0]['sha256'],
                'unsigned_package_sha256': submission['files'][1]['sha256'], 'local_report_sha256': submission['files'][2]['sha256']}
    require(all(release.get(k) == v for k, v in expected.items()) and isinstance(release.get('id'), str) and UUID.fullmatch(release['id']) and
            isinstance(release.get('package_sha256'), str) and DIGEST.fullmatch(release['package_sha256']) and
            release.get('state') in ('published', 'withdrawn') and type(release.get('available')) is bool and
            revision(release.get('publication_revision')) and revision(release.get('revision')) and
            release['publication_revision'] <= release['revision'], 'Store receipt does not match the tested submission')
    binding = identity(client, account, submission['app']['id'])
    # A retry of an older receipt must never advance the local baseline past
    # edits made later in the browser, or roll back a newer successful publish.
    result = {'state': 'accepted', 'published': release['available'], 'attempt_id': attempt.name,
            'release': release, 'app_url': client.origin + '/#apps/' + expected['app_id']}
    try:
        write_json(attempt / 'receipt.json', response)
        old = local_json(project, '.lefony/store-base.json')
        if local_json(project, '.lefony/store.json') == binding and (old is None or
                isinstance(old, dict) and all(old.get(k) == v for k, v in binding.items()) and
                revision(old.get('revision')) and old['revision'] <= release['publication_revision']):
            write_json(project / '.lefony/store-base.json', {**binding, 'revision': release['publication_revision'],
                                                         'content': submission_content(submission)})
    except (OSError, ValueError):
        # The remote transaction already committed. A full disk or changed
        # local metadata cannot turn a published release into a failed upload.
        result['warning'] = 'Release accepted, but local tracking could not be saved. Restore local write access and run publish --status ' + attempt.name + '.'
    return result


def checked_status(response, saved, submission):
    require(response.get('schema') == 1 and response.get('upload_id') == saved['upload_id'] and
            response.get('state') in ('uploading', 'finalizing', 'accepted', 'cancelled', 'expired', 'invalid', 'conflict'),
            'Store returned an invalid upload status')
    if response['state'] == 'accepted':
        return response
    require(response.get('submission_sha256') == saved['submission_sha256'] and response.get('base_revision') == saved['base_revision'] and
            response.get('chunk_bytes') == CHUNK and type(response.get('expires_at')) is int and
            type(response.get('retry_after')) is int and 0 <= response['retry_after'] <= 120,
            'Store upload does not match this attempt')
    files, parts = response.get('files'), response.get('parts')
    require(isinstance(files, list) and len(files) <= len(submission['files']) and isinstance(parts, list) and len(parts) <= 64,
            'Store returned an invalid uploaded-file list')
    seen = set()
    for row in files:
        require(isinstance(row, dict) and type(row.get('file_index')) is int and 0 <= row['file_index'] < len(submission['files']), 'Invalid completed file')
        index = row['file_index']; descriptor = submission['files'][index]
        require(index not in seen and row.get('bytes') == descriptor['bytes'] and row.get('hash') == descriptor['sha256'], 'Completed file differs from submission')
        seen.add(index)
    seen = set()
    for row in parts:
        require(isinstance(row, dict) and type(row.get('file_index')) is int and 0 <= row['file_index'] < len(submission['files']) and
                type(row.get('part_index')) is int and 0 <= row['part_index'] < 32, 'Invalid uploaded chunk')
        key = (row['file_index'], row['part_index']); size = min(CHUNK, submission['files'][key[0]]['bytes'] - key[1] * CHUNK)
        require(key not in seen and size > 0 and row.get('bytes') == size and isinstance(row.get('hash'), str) and DIGEST.fullmatch(row['hash']), 'Invalid uploaded chunk size or digest')
        seen.add(key)
    return response


def transfer(project, attempt, client, account, *, base_revision=None, operation='resume', emit=print, sleep=time.sleep, state_root=None):
    if operation == 'resume':
        submission = verify(attempt)
    else:
        from store_submission import submission_manifest
        submission = submission_manifest(parse_json(read_file(attempt, 'submission.json', 65536)))
    saved, expected = remote_record(project, attempt, client, account, submission)
    call = lambda action: retry(action, emit=emit, sleep=sleep)
    if saved is None:
        if operation != 'resume':
            return {'state': 'prepared', 'published': False, 'attempt_id': attempt.name}
        base_revision = baseline(project, client, account, submission['app']['id']) if base_revision is None else base_revision
        saved = {**expected, 'base_revision': base_revision}
        bind_project(project, client.origin, account['id'], submission['app']['id'], state_root=state_root)
        write_json(attempt / 'remote.json', saved)
    if operation == 'resume':
        require(local_json(project, '.lefony/store.json') == identity(client, account, submission['app']['id']),
                'Project identity changed; relink the original app before resuming this attempt')
    response = None
    if 'upload_id' in saved:
        try:
            response = checked_status(call(lambda: client.request('/sdk/uploads/' + saved['upload_id'])), saved, submission)
        except StoreError as error:
            if error.status != 404:
                raise
            # A cleaned accepted attempt still has a durable receipt. The
            # read-only lookup below retrieves it without creating new staging.
    if response and response['state'] == 'accepted':
        return accepted(project, attempt, client, account, submission, response)
    if response is None:
        query = '/sdk/receipts?app_id=' + submission['app']['id'] + '&version=' + submission['app']['version'] + '&submission_sha256=' + saved['submission_sha256']
        try:
            return accepted(project, attempt, client, account, submission, call(lambda: client.request(query)))
        except StoreError as error:
            if error.status != 404:
                raise
            if 'upload_id' in saved and operation == 'resume':
                raise StoreError('Staging was removed and no accepted receipt exists. Review the listing and prepare a fresh publication attempt.', 410) from None
    if operation == 'status':
        return {'attempt_id': attempt.name, 'published': False, **(response or {'state': 'not_found'})}
    if operation == 'cancel':
        if not response:
            return {'state': 'not_found', 'published': False, 'attempt_id': attempt.name}
        result = call(lambda: client.request('/sdk/uploads/' + saved['upload_id'] + '/cancel', 'POST', {}))
        if result.get('state') == 'accepted':
            return accepted(project, attempt, client, account, submission, result)
        require(result.get('state') == 'cancelled' and result.get('upload_id') == saved['upload_id'], 'Store did not confirm upload cancellation')
        return {'state': 'cancelled', 'published': False, 'attempt_id': attempt.name}
    if response is None:
        response = call(lambda: client.request('/sdk/uploads', 'POST', {'schema': 1, 'base_revision': saved['base_revision'], 'submission': submission}))
        if response.get('state') == 'accepted':
            return accepted(project, attempt, client, account, submission, response)
        require(isinstance(response.get('upload_id'), str) and UUID.fullmatch(response['upload_id']), 'Store returned an invalid upload ID')
        saved['upload_id'] = response['upload_id']
        write_json(attempt / 'remote.json', saved)
        response = checked_status(response, saved, submission)
    if response['state'] not in ('uploading', 'finalizing'):
        raise StoreError('Upload is ' + response['state'] + '. Review the listing and prepare a new publication attempt.', 409)
    prefix = '/sdk/uploads/' + saved['upload_id']
    if response['state'] == 'uploading':
        uploaded = {(part['file_index'], part['part_index']): part for part in response['parts']}
        complete = {entry['file_index'] for entry in response['files']}
        for index, descriptor in enumerate(submission['files']):
            data = read_file(attempt, 'upload/' + descriptor['path'], descriptor['bytes'])
            require(len(data) == descriptor['bytes'] and sha(data) == descriptor['sha256'], 'Prepared artifact changed before upload')
            for part, start in enumerate(range(0, len(data), CHUNK)):
                chunk = data[start:start + CHUNK]
                previous = uploaded.get((index, part))
                if previous:
                    require(previous['hash'] == sha(chunk), 'Recorded remote chunk differs from this attempt')
                elif index not in complete:
                    ack = call(lambda: client.put_chunk(prefix + f'/files/{index}/parts/{part}', chunk))
                    require(ack.get('upload_id') == saved['upload_id'] and ack.get('file_index') == index and ack.get('part_index') == part and
                            ack.get('bytes') == len(chunk) and ack.get('sha256') == sha(chunk), 'Store did not acknowledge the exact chunk')
            if index not in complete:
                ack = call(lambda: client.request(prefix + f'/files/{index}/complete', 'POST', {}))
                require(ack.get('upload_id') == saved['upload_id'] and ack.get('file_index') == index and ack.get('bytes') == len(data) and
                        ack.get('sha256') == descriptor['sha256'], 'Store did not acknowledge the completed file')
            emit('Uploaded and verified ' + descriptor['path'] + '.')
    verify(attempt)
    try:
        result = call(lambda: client.request(prefix + '/finalize', 'POST', {}))
    except StoreError as error:
        if error.status == 409 and error.retry_after:
            return {'state': 'finalizing', 'published': False, 'attempt_id': attempt.name, 'retry_after': error.retry_after}
        raise
    return accepted(project, attempt, client, account, submission, result)


def publish(project, sdk, qemu, firmware, client, account, *, attempt_id=None, operation='resume', emit=print, sleep=time.sleep, state_root=None):
    project = Path(project).absolute()
    require(project.exists() and no_link(project.lstat()) and project.is_dir(), 'Project must be a directory without links')
    project = project.resolve()
    with publication_lock(project):
        from store_listing_sync import pending
        pending(project)
        captured = None
        if attempt_id is None:
            app = manifest(parse_json(read_file(project, 'app.json', 4096)))
            captured = baseline(project, client, account, app['id'])
            prepared = prepare(project, sdk, qemu, firmware, emit=emit)
            require(prepared['app_id'] == app['id'], 'App identity changed during publication preflight; review the prepared attempt')
            attempt_id = prepared['attempt_id']
        attempt = attempt_path(project, attempt_id)
        emit('Publication attempt ' + attempt_id + '; use publish --resume ' + attempt_id + ' after interruption.')
        return transfer(project, attempt, client, account, base_revision=captured, operation=operation, emit=emit, sleep=sleep, state_root=state_root)
