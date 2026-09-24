# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind Linux native and target-library freeze inputs to collected sources."""
import ast
import importlib.metadata
from pathlib import Path

from linux_wheel_native_sources import checksum, scoped
from native_desktop_linux import digest, native


def input_tables(toc):
    if toc.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Linux freeze input table exceeds bound')
    records = {'native': {}, 'non_host': {}}
    def visit(value):
        if not isinstance(value, (tuple, list)):
            return
        if (len(value) == 3 and all(isinstance(x, str) for x in value)
                and value[2] in ('BINARY', 'EXTENSION')):
            target, source, _ = value
            scoped(Path('.'), target)
            source = Path(source).resolve()
            group = records['native' if native(source) else 'non_host']
            record = digest(source)
            for existing in records.values():
                if target in existing and existing[target] != record:
                    raise ValueError('Conflicting Linux freeze input: ' + target)
            group[target] = record
        else:
            for item in value:
                visit(item)
    visit(ast.literal_eval(toc.read_text(encoding='utf-8')))
    if not records['native']:
        raise ValueError('Linux freeze has no native inputs')
    return records


def native_inputs(toc):
    return input_tables(toc)['native']


def bootloader():
    distribution = importlib.metadata.distribution('pyinstaller')
    path = Path(distribution.locate_file('PyInstaller/bootloader/Linux-64bit-intel/run'))
    return distribution.version, digest(path)


def record_bundle(toc, bundle, manifest):
    components = {}
    for component in manifest['components']:
        name = component['component']
        if name in components:
            raise ValueError('Duplicate source component: ' + name)
        components[name] = component
    expected = manifest.get('linux_native_inputs')
    if not isinstance(expected, dict) or not expected:
        raise ValueError('Linux packaging requires its complete native source inventory')
    tables = input_tables(toc)
    actual = tables['native']
    if set(actual) != set(expected):
        raise ValueError('Linux native source inventory differs from the freeze targets')
    records = {}
    for target, value in sorted(actual.items()):
        provider = expected[target]
        checksum(provider['source_sha256'])
        if value != provider['source_sha256']:
            raise ValueError('Linux native input differs from its source inventory: ' + target)
        component = components.get(provider['component'])
        if (not component or not component.get('inputs')
                or component.get('version') != provider['version']):
            raise ValueError('Missing or mismatched Linux source provider: ' + target)
        records[target] = {'input_sha256': value,
            'bundled_sha256': digest(scoped(bundle, '_internal/' + target)),
            'component': provider['component'], 'version': provider['version']}
    expected_other = manifest.get('linux_non_host_inputs')
    if not isinstance(expected_other, dict) or set(expected_other) != set(tables['non_host']):
        raise ValueError('Linux target-library/firmware inventory differs from the freeze targets')
    other_records = {}
    for target, value in sorted(tables['non_host'].items()):
        provider = expected_other[target]
        checksum(provider['source_sha256'])
        component = components.get(provider['component'])
        if (value != provider['source_sha256'] or not component or not component.get('inputs')
                or component.get('version') != provider['version']):
            raise ValueError('Linux target-library/firmware input differs from its source inventory: ' + target)
        other_records[target] = {'input_sha256': value,
            'bundled_sha256': digest(scoped(bundle, '_internal/' + target)),
            'component': provider['component'], 'version': provider['version']}
    version, value = bootloader()
    expected_bootloader = manifest.get('linux_bootloader', {})
    component = components.get('pyinstaller')
    if (expected_bootloader != {'component': 'pyinstaller', 'version': version, 'source_sha256': value}
            or not component or component.get('version') != version or not component.get('inputs')):
        raise ValueError('PyInstaller bootloader differs from its source inventory')
    return {'schema': 1, 'platform': 'linux-x86_64', 'files': records, 'non_host_files': other_records,
            'bootloader': expected_bootloader,
            'launcher_sha256': digest(bundle/'lefony-sdk'),
            'source_rebuild_qualified': False,
            'scope': 'Freeze input/source correspondence, including target libraries; firmware rebuild and complete distribution qualification remain separate'}
