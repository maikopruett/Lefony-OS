# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit foreground library selection; no downloads or project build hooks."""
import hashlib
import json
import os
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected(config):
    return config is not None and config.get('runtime') == 'foreground-newlib-1'


def require_manifest(config, metadata):
    if selected(config) and (metadata.get('schema') != 1 or metadata.get('minimum_api', 0) < 3
                             or not metadata.get('required_capabilities', 0) & 16):
        raise ValueError('foreground-newlib-1 requires manifest schema 1, minimum_api >= 3 and required capability 16')


def resolve(sdk, directory=None):
    configured = directory or os.environ.get('LEFONY_SDK_NEWLIB')
    bundled = sdk / 'runtime/newlib'
    root = Path(configured).expanduser().resolve() if configured else (
        bundled if bundled.is_dir() else sdk.parent / 'build/sdk-newlib')
    report = root / 'candidate.json'
    if not report.is_file():
        raise ValueError('foreground-newlib-1 requires its pinned newlib sysroot; '
                         'build scripts/build_sdk_newlib.py from the SDK kit, or set LEFONY_SDK_NEWLIB to its output')
    candidate = json.loads(report.read_text(encoding='utf-8'))
    spec = json.loads((sdk / 'contracts/newlib.json').read_text(encoding='utf-8'))
    compiler = json.loads((sdk / 'contract.json').read_text(encoding='utf-8'))['compiler']
    for key in ('version', 'source_sha256', 'target', 'configure_options', 'source_adjustments'):
        if candidate.get(key) != spec[key]:
            raise ValueError('newlib candidate has incompatible ' + key)
    if candidate.get('compiler') != compiler:
        raise ValueError('newlib candidate compiler differs from the SDK pin')
    includes = root / 'install/arm-none-eabi/include'
    libraries = root / 'install/arm-none-eabi/lib'
    actual_headers = {p.relative_to(includes).as_posix(): digest(p)
                      for p in sorted(includes.rglob('*')) if p.is_file()}
    if not actual_headers or actual_headers != candidate.get('headers'):
        raise ValueError('newlib headers differ from their build report; rebuild the pinned sysroot')
    if actual_headers.get('sys/reent.h') != spec['source_adjustments']['stdio-descriptor-32-v1']['after_sha256']:
        raise ValueError('newlib FILE descriptors are incompatible; rebuild the pinned sysroot')
    pinned = {}
    for name in ('libc.a', 'libm.a'):
        path = libraries / name
        if not path.is_file() or digest(path) != candidate.get('libraries', {}).get(name, {}).get('sha256'):
            raise ValueError('newlib library differs from its build report: ' + name)
        pinned[name] = digest(path)
    notice = root / 'COPYING.NEWLIB'
    if not notice.is_file() or digest(notice) != candidate.get('license_sha256'):
        raise ValueError('newlib license notice differs from its build report')
    identity = {'name': spec['profile'], 'version': spec['version'], 'target': spec['target'],
                'source_sha256': spec['source_sha256'], 'source_adjustments': spec['source_adjustments'], 'libraries': pinned,
                'headers_sha256': hashlib.sha256(json.dumps(actual_headers, sort_keys=True,
                    separators=(',', ':')).encode()).hexdigest(), 'license_sha256': digest(notice)}
    return {'root': root, 'include': includes, 'libraries': libraries, 'identity': identity,
            'heap_bytes': spec['heap_bytes']}


def bundle_files(sdk, directory):
    runtime = resolve(sdk, directory)
    root = runtime['root']
    archive = root / ('newlib-' + runtime['identity']['version'] + '.tar.gz')
    if not archive.is_file() or digest(archive) != runtime['identity']['source_sha256']:
        raise ValueError('bundling newlib requires its exact source archive beside candidate.json')
    result = {name: root / name for name in ('candidate.json', 'COPYING.NEWLIB', archive.name)}
    result.update({'install/arm-none-eabi/include/' + p.relative_to(runtime['include']).as_posix(): p
                   for p in runtime['include'].rglob('*') if p.is_file()})
    result.update({'install/arm-none-eabi/lib/' + name: runtime['libraries'] / name
                   for name in ('libc.a', 'libm.a')})
    return result


def arguments(output, config, metadata):
    # The original declaration template/output has an additional MIT grant
    # from Maiko Pruett; see LICENSE.md. The generator itself remains GPL-3.0.
    # Input argument values retain their own terms.
    values = [metadata['id'], *config.get('arguments', [])]
    text = '''/* Generated startup arguments; edit project.json.
 * Original declaration template: SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT
 * Input argument values retain their own terms.
 *
 * MIT License
 * Copyright (c) 2026 Maiko Pruett
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
'''
    for i, value in enumerate(values):
        text += f'static char argument_{i}[] = {json.dumps(value)};\n'
    text += 'char *lefony_main_argv[] = {' + ','.join('argument_' + str(i) for i in range(len(values))) + ',0};\n'
    text += f'int lefony_main_argc = {len(values)};\n'
    path = output / 'runtime-arguments.c'
    if not path.exists() or path.read_text(encoding='utf-8') != text:
        path.write_text(text, encoding='utf-8', newline='\n')
    return path
