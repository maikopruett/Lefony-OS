# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare one immutable, allowlisted local publication attempt. No network/device I/O."""
from contextlib import redirect_stdout
import hashlib
import html
import os
from pathlib import Path
import re
import stat
import uuid

import source
from lfapp import manifest, pack, unpack, compatible
from store_listing import canonical, image, listing, parse_json, require, short_description_fallback

SOURCE_ROOTS = ('src', 'assets', 'tests', 'notices', 'sdk.lock.json', 'assets.json',
                'LICENSE.md', 'THIRD_PARTY_NOTICES.md', 'project.json')
REPORT_LIMIT = 65536
MANIFEST_LIMIT = 65536
PACKAGE_LIMIT = 2101312


def sha(data):
    return hashlib.sha256(data).hexdigest()


def no_link(info):
    return not stat.S_ISLNK(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400)


def read_file(root, name, maximum):
    """Bounded regular-file reads; reject links/reparse points and in-flight edits."""
    parts = name.split('/')
    require(parts and all(p not in ('', '.', '..') and '\\' not in p for p in parts), 'Unsafe snapshot path')
    directory = Path(root)
    try:
        for part in parts[:-1]:
            directory /= part
            info = directory.lstat()
            require(no_link(info) and stat.S_ISDIR(info.st_mode), name + ': directories must not be links')
        path = directory / parts[-1]
        before = path.lstat()
        require(no_link(before) and stat.S_ISREG(before.st_mode), name + ': expected a regular file without links')
        require(before.st_size <= maximum, f'{name}: exceeds {maximum} bytes')
        # POSIX walks beneath an open root; replacing an ancestor with a symlink
        # cannot redirect a read. Windows checks reparse attributes at each level.
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
        if os.open in os.supports_dir_fd:
            parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                for part in parts[:-1]:
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                    os.close(parent)
                    parent = child
                fd = os.open(parts[-1], flags, dir_fd=parent)
            finally:
                os.close(parent)
        else:
            fd = os.open(path, flags)
        with os.fdopen(fd, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            require(no_link(opened) and stat.S_ISREG(opened.st_mode) and
                    (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), name + ': changed while being snapshotted; retry')
            data = stream.read(maximum + 1)
            after = os.fstat(stream.fileno())
        require(len(data) <= maximum and (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns) and len(data) == after.st_size,
                name + ': changed while being snapshotted; retry')
        return data
    except FileNotFoundError:
        raise ValueError(name + ': required file is missing') from None


def source_inputs(project):
    metadata = manifest(parse_json(read_file(project, 'app.json', 4096)))
    require(metadata['abi'] == 1, 'app.json: store publication requires ABI 1')
    compatible(metadata)
    files, total = {}, 0
    pending = list(reversed(SOURCE_ROOTS))
    entries = 0
    while pending:
        name = pending.pop()
        path = project / name
        try:
            info = path.lstat()
        except FileNotFoundError:
            require(name in SOURCE_ROOTS and name != 'src', name + ': missing source input')
            continue
        entries += 1
        require(entries <= 1024, 'Source tree has too many entries')
        require(no_link(info), name + ': source links/reparse points are forbidden')
        if stat.S_ISDIR(info.st_mode):
            require(name in ('src', 'assets', 'tests', 'notices') or '/' in name, name + ': expected a file')
            # Bound enumeration before sorting, even for an enormous directory.
            children = []
            with os.scandir(path) as iterator:
                for entry in iterator:
                    require(len(children) + entries + len(pending) < 1024, 'Source tree has too many entries')
                    children.append(name + '/' + entry.name)
            pending.extend(reversed(sorted(children)))
            continue
        require(stat.S_ISREG(info.st_mode), name + ': unsupported source entry')
        data = read_file(project, name, source.file_limit(name, True))
        total += len(data)
        require(total <= source.MAX_TOTAL2 and len(files) < source.MAX_FILES2, 'Source tree exceeds publication limits')
        binary = name.startswith('assets/') and path.suffix not in ('.txt', '.json')
        import base64
        files[name] = {'encoding': 'base64' if binary else 'utf8',
                       'content': base64.b64encode(data).decode('ascii') if binary else data.decode('utf-8'), 'sha256': sha(data)}
    return source.encode({'format': source.FORMAT2, 'manifest': metadata, 'files': files})


def store_inputs(project):
    raw = {}
    for name, maximum in (('listing.json', 8192), ('description.md', 16000), ('release-notes.md', 32000), ('icon.png', 262144)):
        raw['store/' + name] = read_file(project, 'store/' + name, maximum)
    value = listing(parse_json(raw['store/listing.json']), raw['store/description.md'].decode('utf-8'),
                    raw['store/release-notes.md'].decode('utf-8'))
    directory = project / 'store/screenshots'
    require(directory.exists() and no_link(directory.lstat()) and directory.is_dir(),
            'store/screenshots: add 1–5 PNG screenshots')
    names = []
    with os.scandir(directory) as iterator:
        for entry in iterator:
            if entry.name in ('.gitkeep', 'README.md'):
                continue
            require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.png', entry.name) and
                    not source.RESERVED.match(entry.name),
                    'store/screenshots: use PNG filenames with ASCII letters, numbers, hyphens or underscores')
            names.append(entry.name)
            require(len(names) <= 5, 'store/screenshots: at most five screenshots are allowed')
    require(names and len({n.lower() for n in names}) == len(names),
            'store/screenshots: add 1–5 screenshots without case-colliding filenames')
    for name in sorted(names):
        raw['store/screenshots/' + name] = read_file(project, 'store/screenshots/' + name, 1048576)
    media = []
    for name in ['store/icon.png', *sorted(p for p in raw if p.startswith('store/screenshots/'))]:
        try:
            clean, info = image(raw[name], 'icon' if name == 'store/icon.png' else 'screenshot')
        except ValueError as exc:
            raise ValueError(name + ': ' + str(exc)) from None
        media.append((name, clean, info))
    return value, raw, media


def put(root, name, data, readonly=False):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if readonly:
        path.chmod(0o444)
    return path


def private_attempt(project):
    parent = project
    for name in ('.lefony', 'publish'):
        parent /= name
        parent.mkdir(mode=0o700, exist_ok=True)
        info = parent.lstat()
        require(no_link(info) and stat.S_ISDIR(info.st_mode), '.lefony/publish must be a local directory without links')
    attempt = parent / str(uuid.uuid4())
    attempt.mkdir(mode=0o700)
    return attempt


def report_summary(report, source_value, package_hash, dependency_hashes):
    """Upload a strict assertion, never raw logs, tracebacks, paths or captures."""
    require(isinstance(report, dict) and type(report.get('schema')) is int and report['schema'] == 1 and report.get('status') == 'passed' and
            report.get('validation') == 'developer-local' and report.get('independently_verified') is False and
            report.get('package_sha256') == package_hash and report.get('target') == 'prime_g2_vm' and
            all(report.get(key) == value for key, value in dependency_hashes.items()),
            'Local ARM report does not match the tested package and dependencies')
    cases = report.get('cases')
    require(isinstance(cases, list) and 1 <= len(cases) <= 33, 'Invalid local ARM report cases')
    result = []
    tests = {name: descriptor['sha256'] for name, descriptor in source_value['files'].items() if name.startswith('tests/') and name.endswith('.json')}
    tested = []
    for case in cases:
        require(isinstance(case, dict) and isinstance(case.get('name'), str) and
                re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,47}', case['name']) and case.get('status') in ('passed', 'skipped'),
                'Local ARM report contains an invalid or failed case')
        item = {'name': case['name'], 'status': case['status']}
        if case['status'] == 'passed':
            require(type(case.get('assertions')) is int and 0 <= case['assertions'] <= 256, 'Invalid local assertion count')
            item['assertions'] = case['assertions']
        if 'test_sha256' in case:
            require(case['test_sha256'] in tests.values() and case['status'] == 'passed', 'Local report does not cover the snapshotted tests')
            item['test_sha256'] = case['test_sha256']
            tested.append(case['test_sha256'])
        result.append(item)
    require(sorted(tested) == sorted(tests.values()) and any(c['status'] == 'passed' for c in result),
            'Local report does not cover every snapshotted replay')
    summary = {state: sum(c['status'] == state for c in result) for state in ('passed', 'failed', 'skipped')}
    require(report.get('summary') == summary and len({c['name'] for c in result}) == len(result), 'Inconsistent local report summary')
    return {'schema': 1, 'validation': 'developer-local', 'independently_verified': False,
            'status': 'passed', 'profile': 'release', 'target': 'prime_g2_vm', 'physical': 'not_tested',
            'package_sha256': package_hash, 'source_sha256': sha(source.encode(source_value)),
            **dependency_hashes, 'cases': result, 'summary': summary}


def preview(attempt, submission):
    esc = lambda value: html.escape(str(value), quote=True)
    pictures = ''.join(f'<figure><img src="upload/{esc(f["path"])}" alt="{esc(f["path"])}"><figcaption>{esc(f["path"])} · {f["width"]} × {f["height"]}</figcaption></figure>'
                       for f in submission['files'] if 'width' in f)
    rows = ''.join(f'<tr><td>{esc(f["path"])}</td><td>{f["bytes"]:,}</td><td><code>{f["sha256"]}</code></td></tr>' for f in submission['files'])
    body = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{esc(submission['app']['name'])} — publication preview</title><style>body{{font:16px system-ui;margin:40px auto;padding:0 20px;max-width:1050px;color:#16382b;background:#f6faf7}}h1{{margin-bottom:8px}}p,pre{{line-height:1.6}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}}.media{{display:flex;flex-wrap:wrap;gap:20px}}figure{{margin:0}}img{{max-width:320px;max-height:240px;object-fit:contain;border:1px solid #b8cdbf;background:white}}figcaption{{font-size:13px}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #b8cdbf}}code{{font-size:12px;overflow-wrap:anywhere}}.notice{{padding:16px;background:#e0efe5;border-radius:8px}}@media(max-width:600px){{body{{margin:20px auto}}td,th{{padding:6px;font-size:13px}}}}</style>
<h1>{esc(submission['app']['name'])}</h1><p>{esc(submission['app']['id'])} · version {esc(submission['app']['version'])} · {esc(submission['app']['license'])}</p>
<p class="notice">Prepared locally before upload. This package passed local ARM testing; the result is a developer assertion, not independent or physical validation. For current store status, run <code>lefony-sdk publish --status {esc(attempt.name)}</code> from the original project.</p>
<h2>Short description</h2><pre>{esc(submission['listing'].get('short_description', short_description_fallback(submission['listing']['description'])))}</pre><h2>Detailed description</h2><pre>{esc(submission['listing']['description'])}</pre><h2>Release notes</h2><pre>{esc(submission['listing']['release_notes'])}</pre>
<h2>Listing media</h2><div class="media">{pictures}</div><h2>Exact upload contents</h2><table><thead><tr><th>File</th><th>Bytes</th><th>SHA-256</th></tr></thead><tbody>{rows}</tbody></table>
<p>Source publication is enabled. Text is displayed literally; Markdown and HTML are not executed.</p></html>'''
    put(attempt, 'index.html', body.encode('utf-8'), True)


def prepare(project, sdk, qemu, firmware, *, emit=print, compiler=None, tester=None):
    """Build and test only copied inputs. Preserve failures locally for diagnosis."""
    import build
    from replay import test_project
    project = Path(project).absolute()
    require(no_link(project.lstat()) and project.is_dir(), 'Project must be a directory without links')
    project = project.resolve()
    source_data = source_inputs(project)
    from bundled_data import prepare as prepare_data, unpack as unpack_data
    data_spec, data_parts = prepare_data(project)
    metadata, raw_store, media = store_inputs(project)
    qemu, firmware = Path(qemu).resolve(), Path(firmware).resolve()
    require(qemu.is_file() and firmware.is_file(), 'Select the custom QEMU executable and matching VM firmware')
    dependencies = {'sdk_sha256': build.identity(sdk), 'qemu_sha256': build.digest(qemu), 'firmware_sha256': build.digest(firmware)}
    attempt = private_attempt(project)
    emit('Preparing local publication snapshot: ' + str(attempt))
    try:
        source.extract(source_data, attempt / 'project')
        snapshot = attempt / 'project'
        expected_lock = build.project_lock(snapshot, sdk)
        lock = snapshot / 'sdk.lock.json'
        if lock.exists():
            require(parse_json(lock.read_bytes()) == expected_lock,
                    'sdk.lock.json does not match this SDK; select the pinned SDK or explicitly run lock --update')
        else:
            put(snapshot, 'sdk.lock.json', canonical(expected_lock))
        source_data = source_inputs(snapshot)
        source_value = source.decode(source_data)
        if data_spec:
            for item, data in unpack_data(data_spec, [part for _, part in data_parts]):
                put(snapshot, 'data/' + item['path'], data, True)
        for path in snapshot.rglob('*'):
            if path.is_file():
                path.chmod(0o444)
        put(attempt, 'inputs/source.lfsrc', source_data, True)
        inputs = {'source.lfsrc': {'bytes': len(source_data), 'sha256': sha(source_data)}}
        for name, data in raw_store.items():
            put(attempt, 'inputs/' + name, data, True)
            inputs[name] = {'bytes': len(data), 'sha256': sha(data)}
        for name, data in data_parts:
            put(attempt, 'inputs/' + name, data, True)
            inputs[name] = {'bytes': len(data), 'sha256': sha(data)}
        inputs_data = canonical({'schema': 1, 'files': inputs, **dependencies})
        put(attempt, 'inputs.json', inputs_data, True)
        files = []
        def artifact(name, data, dimensions=None):
            path = put(attempt, 'upload/' + name, data, True)
            files.append({'path': name, 'bytes': len(data), 'sha256': sha(data), **(dimensions or {})})
            return path
        artifact('source.lfsrc', source_data)
        emit('Building the snapshotted project (release profile)…')
        with (attempt / 'build.log').open('w', encoding='utf-8', newline='\n') as log, redirect_stdout(log):
            app, elf = (compiler or build.build)(snapshot, sdk, 'release')
        require(app == source_value['manifest'], 'Build manifest differs from the snapshot')
        package = pack(app, elf.read_bytes())
        unpack(package)
        package_path = artifact('package.lfapp', package)
        emit('Testing the exact package through normal ARM emulator input…')
        with (attempt / 'test.log').open('w', encoding='utf-8', newline='\n') as log, redirect_stdout(log):
            outcome = (tester or test_project)(snapshot, package_path, qemu, firmware)
        require(outcome == 0, 'Local ARM tests failed; see ' + str(attempt / 'test.log'))
        report = report_summary(parse_json(read_file(snapshot, 'build/run.json', 4 * 1024 * 1024)), source_value, sha(package), dependencies)
        # Source, fixture, tool and tested bytes must stay stable throughout this
        # attempt. Normal edits to the original project do not affect the copy.
        require(source_inputs(snapshot) == source_data and read_file(attempt, 'upload/package.lfapp', PACKAGE_LIMIT) == package,
                'Snapshotted source or tested package changed; create another attempt')
        require(build.identity(sdk) == dependencies['sdk_sha256'] and build.digest(qemu) == dependencies['qemu_sha256'] and
                build.digest(firmware) == dependencies['firmware_sha256'], 'SDK, QEMU or firmware changed during testing; retry')
        artifact('report.json', canonical(report))
        for index, (_, data, info) in enumerate(media):
            artifact('icon.png' if index == 0 else f'screenshots/{index:02d}.png', data,
                     {'width': info['width'], 'height': info['height']})
        for name, data in data_parts:
            artifact(name, data)
        submission = {'schema': 2 if data_spec else 1, **({'data': data_spec} if data_spec else {}), 'app': app, 'listing': metadata, 'inputs_sha256': sha(inputs_data), 'files': files}
        put(attempt, 'submission.json', canonical(submission), True)
        verify(attempt)
        preview(attempt, submission)
        emit('Ready for local review: ' + str(attempt / 'index.html'))
        return {'state': 'prepared', 'published': False, 'attempt_id': attempt.name, 'directory': str(attempt),
                'submission_sha256': sha(canonical(submission)), 'app_id': app['id'], 'version': app['version'],
                'package_sha256': sha(package), 'upload_bytes': sum(f['bytes'] for f in files), 'test_summary': report['summary']}
    except BaseException:
        emit('Publication snapshot did not complete; diagnostics retained at ' + str(attempt))
        raise


def verify(attempt):
    """Recheck exact bytes before an eventual upload/resume; no recursive upload."""
    from store_submission import submission_manifest
    attempt = Path(attempt)
    data = read_file(attempt, 'submission.json', MANIFEST_LIMIT)
    submission = submission_manifest(parse_json(data))
    require(canonical(submission) == data, 'Submission manifest must be canonical JSON')
    artifacts = {}
    for item in submission['files']:
        payload = read_file(attempt, 'upload/' + item['path'], item['bytes'])
        require(len(payload) == item['bytes'] and sha(payload) == item['sha256'], item['path'] + ': snapshot digest mismatch')
        artifacts[item['path']] = payload
        if 'width' in item:
            clean, info = image(payload, 'icon' if item['path'] == 'icon.png' else 'screenshot')
            require(clean == payload and all(item[key] == info[key] for key in ('width', 'height')), 'Snapshot image is not normalized')
    value = source.decode(artifacts['source.lfsrc'])
    app, _ = unpack(artifacts['package.lfapp'])
    require(app == value['manifest'] == submission['app'], 'Package/source/listing identity mismatch')
    proof_data = read_file(attempt, 'inputs.json', MANIFEST_LIMIT)
    require(sha(proof_data) == submission['inputs_sha256'], 'Input manifest digest mismatch')
    proof = parse_json(proof_data)
    require(isinstance(proof, dict) and set(proof) == {'schema', 'files', 'sdk_sha256', 'qemu_sha256', 'firmware_sha256'} and
            type(proof['schema']) is int and proof['schema'] == 1 and isinstance(proof['files'], dict) and
            6 <= len(proof['files']) <= 12, 'Invalid snapshot input proof')
    require(all(isinstance(proof[key], str) and re.fullmatch(r'[0-9a-f]{64}', proof[key])
                for key in ('sdk_sha256', 'qemu_sha256', 'firmware_sha256')), 'Invalid snapshot dependency digest')
    raw = {}
    for name, item in proof['files'].items():
        require(name == 'source.lfsrc' or re.fullmatch(r'data/0[01]\.gzpart', name) or name in ('store/listing.json', 'store/description.md', 'store/release-notes.md', 'store/icon.png') or
                re.fullmatch(r'store/screenshots/[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.png', name), 'Unsafe input proof path')
        require(isinstance(item, dict) and set(item) == {'bytes', 'sha256'} and type(item['bytes']) is int and
                0 <= item['bytes'] <= source.MAX_SOURCE2, 'Invalid input proof size')
        payload = read_file(attempt, 'inputs/' + name, item['bytes'])
        require(len(payload) == item['bytes'] and sha(payload) == item['sha256'], name + ': input changed after snapshot')
        raw[name] = payload
    expected_names = {'source.lfsrc', 'store/listing.json', 'store/description.md', 'store/release-notes.md', 'store/icon.png'}
    data_names = sorted(name for name in raw if name.startswith('data/'))
    if submission['schema'] == 2:
        from bundled_data import unpack as unpack_data, CONFIG
        require(parse_json(value['files'][CONFIG]['content'].encode()) == submission['data'], 'Bundled data descriptor differs from source')
        unpack_data(submission['data'], [artifacts[name] for name in data_names])
        require(all(raw[name] == artifacts[name] for name in data_names), 'Bundled input changed')
    else:
        require(not data_names, 'Unexpected bundled data')
    screenshot_names = sorted(name for name in raw if name.startswith('store/screenshots/'))
    require(set(raw) == expected_names | set(screenshot_names) | set(data_names) and len(screenshot_names) == len(submission['files']) - len(data_names) - 4,
            'Incomplete input snapshot')
    require(listing(parse_json(raw['store/listing.json']), raw['store/description.md'].decode('utf-8'),
                    raw['store/release-notes.md'].decode('utf-8')) == submission['listing'], 'Listing differs from the input snapshot')
    for index, name in enumerate(['store/icon.png', *screenshot_names]):
        clean, _ = image(raw[name], 'icon' if index == 0 else 'screenshot')
        target = 'icon.png' if index == 0 else f'screenshots/{index:02d}.png'
        require(clean == artifacts[target], 'Listing image differs from the input snapshot')
    require(read_file(attempt, 'inputs/source.lfsrc', source.MAX_SOURCE2) == artifacts['source.lfsrc'], 'Source differs from input snapshot')
    report = parse_json(artifacts['report.json'])
    dependencies = {key: proof[key] for key in ('sdk_sha256', 'qemu_sha256', 'firmware_sha256')}
    require(report_summary(report, value, sha(artifacts['package.lfapp']), dependencies) == report, 'Invalid publication report')
    return submission
