# SPDX-License-Identifier: GPL-3.0-or-later
"""Publication contracts, input isolation and exact-package/report binding."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
import build
import source
from store_listing import image, listing, parse_json
from store_snapshot import prepare, source_inputs, store_inputs, verify
from store_submission import submission_manifest
from test_native_app_package import image as elf_image

CORPUS = json.loads((ROOT / 'sdk/contracts/store-publication-v1.json').read_text())


@pytest.mark.parametrize('case', CORPUS['listing_cases'], ids=lambda c: c['case'])
def test_listing_contract(case):
    call = lambda: listing(case['config'], case['description'], case['release_notes'])
    if case['valid']:
        assert call()['publish_source'] is True
        if case['case'] == 'unicode-trimming':
            assert call() == {'schema': 1, 'publish_source': True, 'description': 'Hello 🌍', 'release_notes': ''}
        else:
            assert call()['description'] == case['description']
            assert call()['release_notes'] == case['release_notes']
    else:
        with pytest.raises(ValueError): call()


@pytest.mark.parametrize('case', CORPUS['image_cases'], ids=lambda c: c['case'])
def test_listing_png_contract(case):
    call = lambda: image(base64.b64decode(case['base64']), case['kind'])
    if case['valid']:
        clean, descriptor = call()
        assert hashlib.sha256(clean).hexdigest() == descriptor['sha256'] == case['clean_sha256']
    else:
        with pytest.raises(ValueError): call()


@pytest.mark.parametrize('case', CORPUS['manifest_cases'], ids=lambda c: c['case'])
def test_submission_contract(case):
    if case['valid']:
        assert submission_manifest(case['value']) == case['value']
    else:
        with pytest.raises(ValueError): submission_manifest(case['value'])


@pytest.fixture
def project(tmp_path, monkeypatch):
    path = tmp_path / 'External project'
    shutil.copytree(ROOT / 'sdk/templates/basic', path)
    (path / 'store/listing.json').write_text('{"schema":1,"publish_source":true,"short_description":"A local example."}')
    (path / 'store/description.md').write_text('<script>literal text</script>\nA local example.')
    images = {c['case']: base64.b64decode(c['base64']) for c in CORPUS['image_cases'] if c['valid']}
    (path / 'store/icon.png').write_bytes(images['strip-private-text'])
    (path / 'store/screenshots/02-main.png').write_bytes(images['smallest-screenshot'])
    (path / 'tests/nested').mkdir()
    (path / 'tests/nested/other.json').write_text('{"schema":1,"name":"nested-test","steps":[{"capture":"screen"}]}')
    (tmp_path / 'qemu').write_bytes(b'synthetic emulator identity')
    (tmp_path / 'firmware').write_bytes(b'synthetic VM identity')
    monkeypatch.setattr(build, 'identity', lambda sdk: 'a' * 64)
    monkeypatch.setattr(build, 'project_lock', lambda path, sdk: {'schema': 1, 'sdk_sha256': 'a' * 64})
    return path


def compile_fixture(snapshot, sdk, profile):
    assert profile == 'release'
    target = snapshot / 'build'
    target.mkdir(exist_ok=True)
    (target / 'app.elf').write_bytes(elf_image())
    return json.loads((snapshot / 'app.json').read_text()), target / 'app.elf'


def test_fixture(snapshot, package, qemu, firmware):
    report = {'schema': 1, 'validation': 'developer-local', 'independently_verified': False,
              'status': 'passed', 'target': 'prime_g2_vm', 'sdk_sha256': build.identity(ROOT / 'sdk'),
              'package_sha256': build.digest(package), 'qemu_sha256': build.digest(qemu), 'firmware_sha256': build.digest(firmware),
              'private_local_path': '/private/never/upload/this', 'cases': []}
    for path in sorted((snapshot / 'tests').rglob('*.json')):
        report['cases'].append({'name': json.loads(path.read_text())['name'], 'status': 'passed', 'assertions': 2,
                                'test_sha256': build.digest(path), 'runtime': {'private': 'never-upload-runtime'}})
    report['summary'] = {'passed': len(report['cases']), 'failed': 0, 'skipped': 0}
    (snapshot / 'build/run.json').write_text(json.dumps(report))
    return 0
test_fixture.__test__ = False


def prepared(project, **kwargs):
    return prepare(project, ROOT / 'sdk', project.parent / 'qemu', project.parent / 'firmware',
                   compiler=kwargs.pop('compiler', compile_fixture), tester=kwargs.pop('tester', test_fixture), emit=lambda _: None, **kwargs)


def test_snapshot_allowlist_and_no_private_report_upload(project):
    for name in ('.git/config', '.env', 'build/device-capture.bin', '.lefony/credential.json', 'unrelated/private.txt'):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('never-upload-secret')
    result = prepared(project)
    attempt = Path(result['directory'])
    submission = verify(attempt)
    assert result['published'] is False and result['test_summary']['passed'] == 2
    assert len(submission['files']) == 5
    data = source.decode((attempt / 'upload/source.lfsrc').read_bytes())
    assert set(data['files']) == {'src/main.cpp', 'tests/interaction.json', 'tests/nested/other.json', 'sdk.lock.json'}
    assert (attempt / 'upload/icon.png').read_bytes() != (project / 'store/icon.png').read_bytes()
    uploaded = b''.join(p.read_bytes() for p in (attempt / 'upload').rglob('*') if p.is_file())
    assert b'never-upload' not in uploaded and str(project).encode() not in uploaded and b'Private metadata' not in uploaded
    preview = (attempt / 'index.html').read_text()
    assert '&lt;script&gt;literal text&lt;/script&gt;' in preview and '<script>' not in preview
    assert not (project / 'sdk.lock.json').exists()  # first build pins only the snapshot


def test_later_edits_do_not_change_a_tested_attempt(project):
    def run(snapshot, package, qemu, firmware):
        (project / 'src/main.cpp').write_text('// next attempt')
        (project / 'store/description.md').write_text('Next description')
        (project / 'store/screenshots/02-main.png').unlink()
        return test_fixture(snapshot, package, qemu, firmware)
    result = prepared(project, tester=run)
    submission = verify(Path(result['directory']))
    assert submission['listing']['description'].endswith('A local example.')
    assert '// next attempt' not in (Path(result['directory']) / 'upload/source.lfsrc').read_text()


def test_repeat_snapshot_has_identical_manifest_and_artifacts(project):
    first, second = prepared(project), prepared(project)
    assert first['attempt_id'] != second['attempt_id']
    assert first['submission_sha256'] == second['submission_sha256']
    a, b = Path(first['directory']), Path(second['directory'])
    for item in verify(a)['files']:
        assert (a / 'upload' / item['path']).read_bytes() == (b / 'upload' / item['path']).read_bytes()


@pytest.mark.parametrize('name', ['app.json', 'src/main.cpp', 'src', 'tests', 'store/icon.png', 'store/screenshots', 'store/listing.json'])
def test_symlinks_are_rejected_before_any_build(project, name):
    path = project / name
    destination = project.parent / 'external'
    path.rename(destination)
    path.symlink_to(destination, target_is_directory=destination.is_dir())
    with pytest.raises(ValueError): prepared(project)
    assert not (project / '.lefony/publish').exists()


@pytest.mark.parametrize('kind', ['fifo', 'oversize', 'duplicate-json', 'nested-escape', 'secret-extension'])
def test_invalid_source_entries_fail_closed(project, kind):
    if kind == 'fifo':
        if not hasattr(os, 'mkfifo'): pytest.skip('POSIX FIFO fixture')
        os.mkfifo(project / 'src/pipe.c')
    elif kind == 'oversize': (project / 'src/main.cpp').write_bytes(b'x' * 262145)
    elif kind == 'duplicate-json': (project / 'app.json').write_text('{"id":"a","id":"b"}')
    elif kind == 'nested-escape':
        (project / 'src/private').symlink_to(project.parent, target_is_directory=True)
    else: (project / 'src/token.pem').write_text('private content')
    with pytest.raises(ValueError): source_inputs(project)


@pytest.mark.parametrize('kind', ['description', 'permission', 'missing-icon', 'no-screenshot', 'too-many', 'bad-name', 'bad-image'])
def test_actionable_listing_preflight(project, kind):
    if kind == 'description': (project / 'store/description.md').write_text('')
    elif kind == 'permission': (project / 'store/listing.json').write_text('{"schema":1,"publish_source":false}')
    elif kind == 'missing-icon': (project / 'store/icon.png').unlink()
    elif kind == 'no-screenshot': (project / 'store/screenshots/02-main.png').unlink()
    elif kind == 'too-many':
        for i in range(6): (project / f'store/screenshots/image{i}.png').write_bytes(b'')
    elif kind == 'bad-name': (project / 'store/screenshots/private.txt').write_text('secret')
    else: (project / 'store/icon.png').write_bytes(b'not PNG')
    with pytest.raises(ValueError, match='store/'): store_inputs(project)


@pytest.mark.parametrize('kind', ['package', 'source', 'sdk', 'wrong-report-hash', 'failed', 'cancelled', 'running', 'cancelled-case', 'not-run-case', 'skipped-test'])
def test_changed_or_failed_test_inputs_cannot_produce_a_ready_attempt(project, monkeypatch, kind):
    def run(snapshot, package, qemu, firmware):
        result = test_fixture(snapshot, package, qemu, firmware)
        if kind in ('package', 'source'):
            path = package if kind == 'package' else snapshot / 'src/main.cpp'
            path.chmod(0o644); path.write_bytes(b'changed')
        elif kind == 'sdk': monkeypatch.setattr(build, 'identity', lambda sdk: 'b' * 64)
        else:
            path = snapshot / 'build/run.json'; value = json.loads(path.read_text())
            if kind == 'wrong-report-hash': value['package_sha256'] = '0' * 64
            elif kind == 'failed': value['status'] = 'failed'; result = 1
            elif kind in ('cancelled', 'running'): value['status'] = kind
            elif kind in ('cancelled-case', 'not-run-case'): value['cases'][0]['status'] = 'cancelled' if kind == 'cancelled-case' else 'not_run'
            else: value['cases'][0]['status'] = 'skipped'
            path.write_text(json.dumps(value))
        return result
    with pytest.raises(ValueError): prepared(project, tester=run)
    attempts = list((project / '.lefony/publish').iterdir())
    assert len(attempts) == 1 and not (attempts[0] / 'submission.json').exists()


def test_interrupted_publication_records_incomplete_snapshot_without_reusing_project_pass(project, monkeypatch):
    import replay
    (project / 'build').mkdir()
    old = b'{"status":"passed","old_project_report":true}'
    (project / 'build/run.json').write_bytes(old)
    def cancel(*args, **kwargs):raise KeyboardInterrupt
    monkeypatch.setattr(replay, 'exercise', cancel)
    with pytest.raises(KeyboardInterrupt):
        prepared(project, tester=replay.test_project)
    attempt, = (project / '.lefony/publish').iterdir()
    report = json.loads((attempt / 'project/build/run.json').read_text())
    assert report['status'] == 'cancelled' and 'old_project_report' not in report
    assert report['cases'][0]['status'] == 'cancelled'
    assert report['cases'][1]['status'] == 'not_run'
    assert (project / 'build/run.json').read_bytes() == old
    assert (attempt / 'test.log').is_file()
    assert not (attempt / 'submission.json').exists() and not (attempt / 'upload/report.json').exists()
    with pytest.raises(ValueError, match='required file is missing'):
        verify(attempt)


@pytest.mark.parametrize('target', ['upload/package.lfapp', 'upload/icon.png', 'upload/report.json', 'inputs/store/description.md', 'inputs.json'])
def test_prepared_attempt_integrity_is_rechecked(project, target):
    result = prepared(project)
    attempt = Path(result['directory'])
    path = attempt / target
    path.chmod(0o644); path.write_bytes(path.read_bytes() + b'x')
    with pytest.raises(ValueError): verify(attempt)


def test_duplicate_json_rejected():
    with pytest.raises(ValueError, match='Duplicate'): parse_json(b'{"schema":1,"schema":1}')
    with pytest.raises(ValueError): parse_json(b'{"schema":NaN}')


def test_case_collisions_in_publication_source(project):
    # A case-insensitive host cannot physically create both names. Exercise the
    # serialized source boundary, which must also reject archives from Linux.
    value = source.decode(source_inputs(project))
    value['files']['src/Main.cpp'] = copy.deepcopy(value['files']['src/main.cpp'])
    with pytest.raises(ValueError, match='case-colliding'): source.encode(value)


def test_existing_lock_is_not_silently_updated(project):
    (project / 'sdk.lock.json').write_text('{"sdk_sha256":"different"}')
    with pytest.raises(ValueError, match='lock --update'): prepared(project)
    assert json.loads((project / 'sdk.lock.json').read_text()) == {'sdk_sha256': 'different'}


@pytest.mark.parametrize('kind', ['listing', 'report-source', 'report-schema'])
def test_integrity_also_checks_relationships_between_valid_json_files(project, kind):
    from store_listing import canonical
    attempt = Path(prepared(project)['directory'])
    path = attempt / 'submission.json'
    submission = json.loads(path.read_text())
    if kind == 'listing':
        submission['listing']['description'] = 'Unrelated to the recorded snapshot'
    else:
        report_path = attempt / 'upload/report.json'
        report = json.loads(report_path.read_text())
        if kind == 'report-source': report['source_sha256'] = '0' * 64
        else: report['schema'] = True
        report_path.chmod(0o644); report_path.write_bytes(canonical(report))
        submission['files'][2].update(bytes=report_path.stat().st_size, sha256=build.digest(report_path))
    path.chmod(0o644); path.write_bytes(canonical(submission))
    with pytest.raises(ValueError): verify(attempt)


def test_manifest_mutation_does_not_alias_corpus():
    value = copy.deepcopy(CORPUS['manifest_cases'][0]['value'])
    value['files'].reverse()
    with pytest.raises(ValueError): submission_manifest(value)


def test_store_snapshot_carries_short_description_and_rejects_explicit_empty(project):
    value, *_ = store_inputs(project)
    assert value['short_description'] == 'A local example.'
    assert value['description'].endswith('A local example.')
    config = json.loads((project / 'store/listing.json').read_text())
    config['short_description'] = ''
    (project / 'store/listing.json').write_text(json.dumps(config))
    with pytest.raises(ValueError, match='Short description'):
        store_inputs(project)
