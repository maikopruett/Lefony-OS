# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded source exchange. Format 1 carries inert resources and local tests."""
import base64
import hashlib
import json
from pathlib import Path
import re
from lfapp import manifest, require
import project as project_config
import runtime as runtime_profile

MAX_SOURCE = 1024 * 1024
FORMAT = "lefony-source-0"
FORMAT1 = "lefony-source-1"
FORMAT2 = "lefony-source-2"
MAX_SOURCE2 = 8 * 1024 * 1024
MAX_FILES2 = 512
MAX_TOTAL2 = 4 * 1024 * 1024
SOURCE_PATH = r"src/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:cpp|h)"
EXTRA_PATH = r"(?:tests/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.json|assets/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:png|jpg|jpeg|bmp|rgb565|bin|txt|json)|notices/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:txt|md)|sdk\.lock\.json|assets\.json|LICENSE\.md|THIRD_PARTY_NOTICES\.md)"
RESERVED = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.I)


def file_limit(name, version2=False):
    return 262144 if version2 and name.startswith(('src/', 'notices/')) else 65536


def file_bytes(name, content, extended, version2=False):
    if not extended:
        require(isinstance(content, str) and "\0" not in content, "source must be text")
        return content.encode('utf-8')
    require(isinstance(content, dict) and set(content) == {'encoding', 'content', 'sha256'}, "invalid file descriptor")
    text = content['content']
    require(isinstance(text, str) and isinstance(content['sha256'], str) and
            re.fullmatch(r'[a-f0-9]{64}', content['sha256']), "invalid file content/hash")
    if content['encoding'] == 'utf8':
        require('\0' not in text, 'text contains NUL')
        data = text.encode('utf-8')
    else:
        require(content['encoding'] == 'base64' and name.startswith('assets/') and len(text) <= 87384,
                'binary encoding is only supported for bounded assets')
        try:
            data = base64.b64decode(text, validate=True)
        except ValueError:
            require(False, 'invalid base64')
        require(base64.b64encode(data).decode('ascii') == text, 'base64 must be canonical')
    require(len(data) <= file_limit(name, version2), 'source file too large')
    require(hashlib.sha256(data).hexdigest() == content['sha256'], 'file digest mismatch')
    return data


def validate(value):
    require(isinstance(value, dict) and set(value) == {'format', 'manifest', 'files'}, 'invalid source bundle')
    require(value['format'] in (FORMAT, FORMAT1, FORMAT2), 'unsupported source format')
    metadata = manifest(value['manifest'])
    version2 = value['format'] == FORMAT2
    extended = value['format'] != FORMAT
    require(extended or not metadata.get('schema', 0), 'manifest schema 1 requires source format 1')
    files = value['files']
    require(isinstance(files, dict) and 1 <= len(files) <= (MAX_FILES2 if version2 else 64), 'invalid source file count')
    total = 0
    seen = set()
    for name, content in files.items():
        require(isinstance(name, str) and len(name) <= (160 if version2 else 120) and
                (re.fullmatch(project_config.SOURCE_PATH if version2 else SOURCE_PATH, name)
                 or extended and re.fullmatch(EXTRA_PATH, name)
                 or version2 and name == 'project.json'), 'invalid source path')
        if extended:
            require(not any(RESERVED.match(part) for part in name.split('/')), 'platform-reserved source path')
            # Every path component matters: Foo/a.h and foo/b.h collide on
            # case-insensitive hosts even though the complete paths differ.
            for i in range(1, len(name.split('/')) + 1):
                prefix = '/'.join(name.split('/')[:i])
                require(not any(old.lower() == prefix.lower() and old != prefix for old in seen), 'case-colliding source path')
                seen.add(prefix)
        data = file_bytes(name, content, extended, version2)
        require(len(data) <= file_limit(name, version2), 'source file too large')
        total += len(data)
        require(total <= (MAX_TOTAL2 if version2 else 524288), 'invalid total source size')
    if version2:
        if 'project.json' in files:
            config = project_config.parse(file_bytes('project.json', files['project.json'], True).decode('utf-8'))
            project_config.validate(config, files)
            runtime_profile.require_manifest(config, value['manifest'])
        else:
            require(1 <= sum(n.endswith(('.c', '.cpp')) and n.startswith('src/') for n in files) <= 64,
                    'more than 64 translation units requires project.json')
    else:
        require(any(re.fullmatch(SOURCE_PATH, name) and name.endswith('.cpp') for name in files), 'invalid total source size')
    # The whole normalized JSON is also bounded, including escapes/descriptors.
    require(len(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')) <= (MAX_SOURCE2 if version2 else MAX_SOURCE),
            'source bundle too large')
    return value


def encode(value):
    validate(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def decode(data):
    require(len(data) <= MAX_SOURCE2, 'source bundle too large')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate source field')
            result[key] = value
        return result
    value = json.loads(data, object_pairs_hook=unique)
    require(len(data) <= (MAX_SOURCE2 if isinstance(value, dict) and value.get('format') == FORMAT2 else MAX_SOURCE), 'source bundle too large')
    return validate(value)


def collect(project, format=0):
    require(type(format) is int and format in (0, 1, 2), 'unsupported source format')
    project = Path(project)
    require(format == 2 or not ((project / 'project.json').exists() or (project / 'project.json').is_symlink()),
            'configured projects require source --format 2')
    require(format or not ((project / 'assets.json').exists() or (project / 'assets.json').is_symlink()),
            'resource projects require source --format 1 to retain their inputs')
    files = {}
    roots = [project / 'src']
    if format:
        roots.extend(project / name for name in ('assets', 'tests', 'notices', 'sdk.lock.json', 'assets.json', 'LICENSE.md', 'THIRD_PARTY_NOTICES.md'))
    if format == 2:
        roots.append(project / 'project.json')
    total = 0
    for root in roots:
        require(not root.is_symlink(), 'source symlinks are forbidden')
        paths = [root, *sorted(root.rglob('*'))] if root.is_dir() else [root]
        for path in paths:
            require(not path.is_symlink(), 'source symlinks are forbidden')
            if not path.is_file():
                continue
            name = path.relative_to(project).as_posix()
            require(path.stat().st_size <= file_limit(name, format == 2), 'source file too large')
            data = path.read_bytes()
            total += len(data)
            require(total <= (MAX_TOTAL2 if format == 2 else 524288), 'invalid total source size')
            require(len(files) < (MAX_FILES2 if format == 2 else 64), 'invalid source file count')
            if format:
                binary = name.startswith('assets/') and path.suffix not in ('.txt', '.json')
                content = base64.b64encode(data).decode('ascii') if binary else data.decode('utf-8')
                files[name] = {'encoding': 'base64' if binary else 'utf8', 'content': content, 'sha256': hashlib.sha256(data).hexdigest()}
            else:
                files[name] = data.decode('utf-8')
    return encode({'format': (FORMAT, FORMAT1, FORMAT2)[format], 'manifest': json.loads((project / 'app.json').read_text(encoding='utf-8')), 'files': files})


def extract(data, target):
    value = decode(data)
    target = Path(target)
    target.mkdir(parents=True, exist_ok=False)
    (target / 'app.json').write_text(json.dumps(value['manifest']), encoding='utf-8', newline='\n')
    for name, content in value['files'].items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_bytes(name, content, value['format'] != FORMAT, value['format'] == FORMAT2))
    return value
