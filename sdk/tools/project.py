# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned, inert project configuration shared by builds and source exchange."""
import json
from pathlib import Path
import re

MAX_UNITS = 256
MAX_CONFIG_BYTES = 65536
SOURCE_PATH = r'src/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:c|cpp|h|hpp|inc)'
DIRECTORY = r'src(?:/[A-Za-z0-9_-]+)*'
FLAGS = {'-fwrapv', '-fno-strict-aliasing', '-ffp-contract=off', '-Wno-error'}
RESERVED = re.compile(r'(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', re.I)


def require(condition, message):
    if not condition:
        raise ValueError('project.json: ' + message)


def parse(text):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'duplicate field')
            value[key] = item
        return value
    require(len(text.encode('utf-8')) <= MAX_CONFIG_BYTES, 'configuration exceeds 64 KiB')
    return json.loads(text, object_pairs_hook=unique)


def valid_path(value, pattern):
    return (isinstance(value, str) and len(value) <= 160 and re.fullmatch(pattern, value)
            and not any(RESERVED.match(p) for p in value.split('/')))


def validate(value, files=None):
    require(isinstance(value, dict) and {'schema', 'sources'} <= set(value), 'missing schema or sources')
    require(type(value['schema']) is int and value['schema'] in (1, 2), 'unsupported schema')
    fields = {'schema', 'sources', 'include_dirs', 'defines', 'c_flags', 'cxx_flags'}
    if value['schema'] == 2:
        fields |= {'runtime', 'arguments'}
        require(value.get('runtime') == 'foreground-newlib-1', 'unsupported runtime')
        arguments = value.get('arguments', [])
        require(isinstance(arguments, list) and len(arguments) <= 16 and
                all(isinstance(a, str) and len(a) <= 128 and
                    all(32 <= ord(c) <= 126 for c in a) for a in arguments), 'invalid main arguments')
    require(set(value) <= fields,
            'unsupported fields; build hooks are not supported')
    sources = value['sources']
    require(isinstance(sources, list) and 1 <= len(sources) <= MAX_UNITS, 'expected 1–256 translation units')
    require(all(valid_path(p, SOURCE_PATH) and p.endswith(('.c', '.cpp')) for p in sources), 'invalid source path')
    require(len({p.lower() for p in sources}) == len(sources), 'duplicate/case-colliding translation unit')
    includes = value.get('include_dirs', [])
    require(isinstance(includes, list) and len(includes) <= 32
            and all(valid_path(p, DIRECTORY) for p in includes), 'invalid include directories')
    require(len({p.lower() for p in includes}) == len(includes), 'duplicate include directory')
    defines = value.get('defines', {})
    require(isinstance(defines, dict) and len(defines) <= 64, 'invalid defines')
    for key, item in defines.items():
        require(isinstance(key, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', key), 'invalid define name')
        require((type(item) is int and -2147483648 <= item <= 2147483647)
                or (isinstance(item, str) and len(item) <= 128
                    and all(32 <= ord(c) <= 126 for c in item)), 'invalid define value')
    if 'LEFONY_PROFILE_HEAP' in defines:
        enabled=defines['LEFONY_PROFILE_HEAP']
        require(type(enabled) is int and enabled in (0,1), 'LEFONY_PROFILE_HEAP must be 0 or 1')
        require(not enabled or value['schema']==2, 'heap profiling requires foreground-newlib-1')
    for key in ('c_flags', 'cxx_flags'):
        flags = value.get(key, [])
        require(isinstance(flags, list) and len(flags) <= len(FLAGS)
                and all(isinstance(f, str) and f in FLAGS for f in flags), 'unsupported ' + key)
        require(len(set(flags)) == len(flags), 'duplicate ' + key)
    if files is not None:
        require(all(p in files for p in sources), 'declared source is missing from the project')
        require(all(any(p.startswith(d + '/') for p in files) for d in includes), 'declared include directory is missing')
    return value


def load(directory):
    path = Path(directory) / 'project.json'
    require(not path.is_symlink(), 'configuration symlinks are forbidden')
    if not path.exists():
        return None
    require(path.is_file() and path.stat().st_size <= MAX_CONFIG_BYTES, 'configuration exceeds 64 KiB')
    return validate(parse(path.read_text(encoding='utf-8')))


def compiler_flags(config, language):
    if config is None:
        return []
    return [arg for d in config.get('include_dirs', []) for arg in ('-I', d)] + [
        '-D' + key + '=' + str(value) for key, value in sorted(config.get('defines', {}).items())
    ] + config.get('c_flags' if language == 'c' else 'cxx_flags', [])
