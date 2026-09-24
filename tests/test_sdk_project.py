# SPDX-License-Identifier: GPL-3.0-or-later
"""Configured ARM builds and independent source-format boundary checks."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
import project as project_config
from build import build
from source import collect, decode, encode, extract, FORMAT2


def descriptor(text):
    return {'encoding': 'utf8', 'content': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}


def bundle():
    return {'format': FORMAT2, 'manifest': {'abi': 1, 'id': 'configured-c', 'name': 'Configured C',
            'version': '1.0.0', 'license': 'CC-BY-NC-SA-4.0'},
            'files': {'src/main.c': descriptor('// C source\n')}}


def test_explicit_large_mixed_project_build_and_source_roundtrip(tmp_path):
    root = tmp_path / 'Configured C é'
    (root / 'src/vendor').mkdir(parents=True)
    config = {'schema': 1, 'sources': ['src/main.cpp'], 'include_dirs': ['src/vendor'],
              'defines': {'VALUE_OFFSET': 7}, 'c_flags': ['-fwrapv'], 'cxx_flags': ['-ffp-contract=off']}
    (root / 'src/vendor/common.h').write_text('#define OFFSET VALUE_OFFSET\n')
    for i in range(80):
        p = f'src/vendor/part_{i}.c'
        (root / p).write_text(f'#include <common.h>\nunsigned part_{i}(void) {{ return {i} + OFFSET; }}\n')
        config['sources'].append(p)
    declarations = '\n'.join(f'extern "C" unsigned part_{i}(void);' for i in range(80))
    expression = ' + '.join(f'part_{i}()' for i in range(80))
    (root / 'src/main.cpp').write_text('#include <lefony/app.h>\n' + declarations + '\n'
        'extern "C" void lefony_event(Lefony::Event,uint32_t,uint32_t) {\n'
        f'  Lefony::fill({{0,0,320,240,{expression}}});\n}}\n')
    (root / 'src/other_platform.c').write_text('THIS PLATFORM MUST NOT BE COMPILED\n')
    (root / 'project.json').write_text(json.dumps(config))
    (root / 'app.json').write_text(json.dumps(bundle()['manifest']))
    (root / 'credentials.txt').write_text('excluded synthetic private file')
    _, image = build(root, ROOT / 'sdk')
    original = image.read_bytes()
    commands = json.loads((root / 'compile_commands.json').read_text())
    assert len(commands) == 81
    assert all('-DVALUE_OFFSET=7' in c['arguments'] for c in commands)
    assert all(('-fwrapv' if c['file'].endswith('.c') else '-ffp-contract=off') in c['arguments'] for c in commands)
    build(root, ROOT / 'sdk')
    assert json.loads((root / 'build/build.json').read_text())['compiled'] == []
    for old in (0, 1):
        with pytest.raises(ValueError, match='format 2'): collect(root, old)
    data = collect(root, 2)
    assert 'credentials.txt' not in decode(data)['files']
    restored = tmp_path / 'Restored project'
    extract(data, restored)
    assert collect(restored, 2) == data
    assert build(restored, ROOT / 'sdk')[1].read_bytes() == original
    config['defines']['VALUE_OFFSET'] = 8
    (root / 'project.json').write_text(json.dumps(config))
    assert build(root, ROOT / 'sdk')[1].read_bytes() != original
    report = json.loads((root / 'build/build.json').read_text())
    assert len(report['compiled']) == 81 and all(p.startswith('src/') for p in report['compiled'])


@pytest.mark.parametrize('name', ['project-v1.json', 'project-v2.json'])
def test_shared_project_configuration_corpus(name):
    corpus = json.loads((ROOT / 'sdk/contracts' / name).read_text())
    for case in corpus['cases']:
        try:
            project_config.validate(project_config.parse(case['text']), case['files'])
            valid = True
        except (ValueError, TypeError): valid = False
        assert valid == case['valid'], case['case']


@pytest.mark.parametrize('case', ['traversal', 'symlink', 'config-symlink', 'missing-source', 'missing-include'])
def test_configured_build_rejects_unsafe_or_missing_inputs(tmp_path, case):
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src/main.c').write_text('void lefony_event(unsigned a,unsigned b,unsigned c){}')
    (tmp_path / 'app.json').write_text(json.dumps(bundle()['manifest']))
    config = {'schema': 1, 'sources': ['src/main.c']}
    if case == 'traversal':config['include_dirs'] = ['src/../../outside']
    elif case == 'symlink':(tmp_path / 'src/external.h').symlink_to(tmp_path / 'app.json')
    elif case == 'missing-source':config['sources'] = ['src/missing.c']
    elif case == 'missing-include':config['include_dirs'] = ['src/missing']
    (tmp_path / 'project.json').write_text(json.dumps(config))
    if case == 'config-symlink':
        (tmp_path / 'project.json').unlink()
        (tmp_path / 'project.json').symlink_to(tmp_path / 'app.json')
    with pytest.raises(ValueError):build(tmp_path, ROOT / 'sdk')


def test_source2_limits_and_old_format_rejection():
    s = bundle()
    s['files']['src/large.h'] = descriptor('a' * 262144)
    assert decode(encode(s)) == s
    for old in ('lefony-source-0', 'lefony-source-1'):
        bad = copy.deepcopy(s);bad['format'] = old
        with pytest.raises(ValueError):encode(bad)
    s['files']['src/large.h'] = descriptor('a' * 262145)
    with pytest.raises(ValueError):encode(s)
    s = bundle()
    for i in range(511):s['files'][f'src/f{i}.h'] = descriptor('// header')
    assert decode(encode(s)) == s
    s['files']['src/overflow.h'] = descriptor('// extra')
    with pytest.raises(ValueError):encode(s)
    s = bundle()
    for i in range(16):s['files'][f'src/big{i}.h'] = descriptor('a' * 262144)
    with pytest.raises(ValueError):encode(s)
    # Escaping control characters can exceed the encoded cap before raw total.
    s = bundle()
    for i in range(6):s['files'][f'src/escaped{i}.h'] = descriptor('\x01' * 262144)
    with pytest.raises(ValueError):encode(s)


def test_source2_requires_declared_large_tree_and_preserves_config_bytes():
    s = bundle()
    for i in range(65):s['files'][f'src/c{i}.c'] = descriptor('// source')
    with pytest.raises(ValueError):encode(s)
    config = {'schema': 1, 'sources': sorted(s['files']), 'defines': {'MESSAGE': '"A B"'}}
    s['files']['project.json'] = descriptor(json.dumps(config, indent=2) + '\n')
    assert decode(encode(s)) == s
    config['sources'].append('src/missing.c')
    s['files']['project.json'] = descriptor(json.dumps(config))
    with pytest.raises(ValueError):encode(s)
