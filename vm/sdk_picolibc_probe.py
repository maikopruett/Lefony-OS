# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated library comparison, never a selectable production SDK profile.

Reuse the actual foreground startup and OS adapter logic. Only syscall symbol
names and the newlib-specific reentrant rename hook differ. No dummy-host or
semihosting archive is linked. Generated adapters retain their original notices.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, identity, lock_value, write_json
from lfapp import elf_segments, pack
from runtime import arguments


def resolve(root):
    root = Path(root).resolve()
    candidate = json.loads((root / 'candidate.json').read_text())
    if (candidate.get('version') != '1.8.12' or
        candidate.get('source_sha256') != '2946ea55b915f7f4555d60bffbaea6a3edc0b8993b7ded3935be9a15cfb7157b' or
        candidate.get('compiler') != '16.2.0'):
        raise ValueError('Unexpected Picolibc comparison input')
    actual = {p.relative_to(root / 'install').as_posix(): digest(p)
              for p in sorted((root / 'install').rglob('*')) if p.is_file()}
    if actual != candidate['files']: raise ValueError('Picolibc files differ from their candidate report')
    if (digest(root / 'picolibc-1.8.12.tar.gz') != candidate['source_sha256'] or
        candidate.get('notices') != {'COPYING.picolibc': digest(root / 'COPYING.picolibc')}):
        raise ValueError('Picolibc source or notices differ from their candidate report')
    required = {'-Dpicocrt=false', '-Dpicocrt-lib=false', '-Dsemihost=false',
                '-Dthread-local-storage=false', '-Dstdio-exit-flush=true', '-Dinitfini-array=false'}
    if not required <= set(candidate['options']): raise ValueError('Incompatible Picolibc comparison options')
    return {'root': root, 'include': root / 'install/include', 'libraries': root / 'install/lib',
        'heap_bytes': 8380416, 'identity': {'name': 'picolibc-comparison-1',
        'version': candidate['version'], 'source_sha256': candidate['source_sha256'],
        'candidate_sha256': digest(root / 'candidate.json'), 'files': actual,
        'notices': candidate['notices'], 'options': candidate['options'],
        'adapter_sha256': digest(Path(__file__)), 'qualified': False}}


def adapters(sdk, output):
    prefix = '/* Picolibc comparison: ABI-name adaptation; original notices preserved. */\n'
    result = []
    for name, names in (('os', ['sbrk', 'getpid', 'kill', 'gettimeofday', 'times']),
                        ('files', ['open', 'close', 'read', 'write', 'lseek', 'stat', 'fstat', 'isatty', 'unlink', 'rename'])):
        original = (sdk / 'lib/newlib' / (name + '.c')).read_text()
        modified = original
        if name == 'files':
            # Lefony files are byte streams. Newlib defines this compatibility
            # flag as zero on ARM; Picolibc omits the non-POSIX name.
            modified = '#include <fcntl.h>\n#ifndef O_BINARY\n#define O_BINARY 0\n#endif\n' + modified
            include = '#include <reent.h>\n'
            hook = '''/* The pinned newlib was built without HAVE_RENAME. Supply its reentrant hook
 * explicitly so rename never falls back to separately committed link/unlink. */
int _rename_r(struct _reent *context,const char *old,const char *next) {
  int result=_rename(old,next);if(result<0) context->_errno=errno;return result;
}
'''
            if modified.count(include) != 1 or modified.count(hook) != 1:
                raise ValueError('Unexpected authoritative file adapter; review Picolibc adaptation')
            modified = modified.replace(include, '').replace(hook, '')
        for symbol in names:
            if not re.search(r'\b_' + symbol + r'\s*\(', original):
                raise ValueError('Missing authoritative syscall: ' + symbol)
        path = output / (name + '.c')
        path.write_text(prefix + ''.join('#define _' + n + ' ' + n + '\n' for n in names) + modified)
        result.append(path)
    return result


def package(project, sdk, root, profile):
    project = project.resolve(); sdk = sdk.resolve()
    runtime = resolve(root); metadata = json.loads((project / 'app.json').read_text())
    config = json.loads((project / 'project.json').read_text())
    if config.get('runtime') != 'picolibc-comparison-1' or config['sources'] != ['src/main.c']:
        raise ValueError('This comparison compiler currently accepts only the shared C conformance fixture')
    output = project / 'build'; output.mkdir()
    generated = output / 'picolibc-adapter'; generated.mkdir()
    sources = [sdk / 'lib/start.s', sdk / 'lib/newlib/start.c', *adapters(sdk, generated),
               project / 'src/main.c', arguments(output, config, metadata)]
    compiler = shutil.which('arm-none-eabi-gcc')
    if not compiler or subprocess.check_output([compiler, '-dumpfullversion'], text=True).strip() != '16.2.0':
        raise ValueError('The comparison requires the pinned compiler')
    flags = ['-mcpu=cortex-a7', '-marm', '-mfpu=neon-vfpv4', '-mfloat-abi=hard',
        '-Og' if profile == 'debug' else '-Os', '-g3', '-ffreestanding', '-fno-unwind-tables',
        '-fno-asynchronous-unwind-tables', '-fno-pic', '-fno-pie', '-ffunction-sections',
        '-fdata-sections', '-Wall', '-Wextra', '-Werror', '-nostdinc',
        f'-ffile-prefix-map={sdk}=/lefony-sdk', f'-ffile-prefix-map={project}=.',
        f'-ffile-prefix-map={runtime["root"]}=/lefony-picolibc', '-I', str(sdk / 'include')]
    if profile == 'debug': flags += ['-DLEFONY_SDK_DEBUG=1']
    for name in ('include', 'include-fixed'):
        path = Path(subprocess.check_output([compiler, '-print-file-name=' + name], text=True).strip())
        if path.is_dir(): flags += ['-isystem', str(path), f'-ffile-prefix-map={path}=/lefony-compiler/{name}']
    flags += ['-isystem', str(runtime['include'])]
    objects = []; commands = []
    for number, source in enumerate(sources):
        obj = output / (str(number) + '.o')
        command = [compiler, *flags, *(['-std=c11'] if source.suffix == '.c' else []),
                   '-c', str(source), '-o', str(obj)]
        subprocess.run(command, check=True, timeout=120); objects.append(str(obj)); commands.append(command)
    debug = output / 'app-debug.elf'; image = output / 'app.elf'
    link = [compiler, *flags, '-nostdlib', '-nostartfiles', '-static', '-Wl,--build-id=none',
            '-Wl,--gc-sections', '-Wl,-z,noexecstack', '-Wl,-z,max-page-size=4096',
            '-Xlinker', '-T', '-Xlinker', str(sdk / 'cmake/foreground.ld'),
            '-Xlinker', '-Map', '-Xlinker', str(output / 'app.map'), *objects,
            '-L', str(runtime['libraries']), '-Wl,--start-group', '-lc', '-lm', '-lgcc',
            '-Wl,--end-group', '-o', str(debug)]
    subprocess.run(link, check=True, timeout=120)
    subprocess.run(['arm-none-eabi-objcopy', '--strip-all', str(debug), str(image)], check=True, timeout=30)
    artifact = output / (metadata['id'] + '-' + metadata['version'] + '.lfapp')
    artifact.write_bytes(pack(metadata, image.read_bytes()))
    _, segments = elf_segments(image.read_bytes())
    write_json(project / 'sdk.lock.json', lock_value(sdk, metadata['abi'], metadata['schema'], runtime))
    write_json(output / 'build.json', {'schema': 1, 'comparison_only': True, 'sdk_sha256': identity(sdk),
        'runtime': runtime['identity'], 'profile': profile, 'commands': commands, 'link': link,
        'resources': {'code_bytes': sum(m for _, _, m, p in segments if p == 5),
                      'static_data_bytes': sum(m for _, _, m, p in segments if p == 6),
                      'initialized_data_bytes': sum(len(d) for _, d, _, p in segments if p == 6),
                      'heap_reserved_bytes': 8380416, 'stack_reserved_bytes': 65536, 'stack_peak_bytes': None},
        'adapter_sources': {p.name: digest(p) for p in generated.iterdir()},
        'source_sha256': digest(project / 'src/main.c'), 'image_sha256': digest(image)})
    return artifact
