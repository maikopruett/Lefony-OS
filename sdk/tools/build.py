# SPDX-License-Identifier: GPL-3.0-or-later
"""Pinned, incremental native builds. No hooks, downloads or device operations."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from contextlib import contextmanager
from lfapp import canonical, elf_segments, manifest
import project as project_config
import runtime as runtime_profile


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(sdk):
    files = [sdk / 'contract.json']
    for directory in ('include', 'lib', 'cmake', 'tools', 'contracts'):
        files.extend(p for p in (sdk / directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    return hashlib.sha256(canonical({p.relative_to(sdk).as_posix(): digest(p)
                                     for p in sorted(files)})).hexdigest()


def contract(sdk):
    return json.loads((sdk / 'contract.json').read_text(encoding='utf-8'))


def lock_value(sdk, abi, package_schema=0, runtime=None):
    spec = contract(sdk)
    math_manifest = sdk / 'lib/vendor/openbsd-math/manifest.json'
    dependency = json.loads(math_manifest.read_text(encoding='utf-8'))
    result = {'schema': 1, 'sdk': spec['sdk'], 'sdk_sha256': identity(sdk),
            'compiler': spec['compiler'], 'abi': abi, 'package_schema': package_schema,
            'resources': [{'schema': 1, 'converter': 'lefony-rgb565-1', 'pillow': '12.3.0'}], 'dependencies': [{'name': 'openbsd-math', 'source_revision': dependency['source_revision'],
                                               'manifest_sha256': digest(math_manifest)}]}
    if runtime:
        result['dependencies'].append(runtime['identity'])
    return result


def write_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    temporary.replace(path)


def project_lock(project, sdk):
    metadata = manifest(json.loads((project / 'app.json').read_text(encoding='utf-8')))
    config = project_config.load(project)
    runtime_profile.require_manifest(config, metadata)
    runtime = runtime_profile.resolve(sdk) if runtime_profile.selected(config) else None
    return lock_value(sdk, metadata['abi'], metadata.get('schema', 0), runtime)


@contextmanager
def exclusive(path):
    try:
        path.mkdir()
    except FileExistsError:
        raise ValueError(f'{path.name} is locked by another operation; if it crashed, remove the lock after confirming it stopped') from None
    try:
        yield
    finally:
        path.rmdir()


def build(project, sdk, profile='release'):
    project = project.resolve()
    spec = contract(sdk)
    if profile not in ('debug', 'release'):
        raise ValueError('profile must be debug or release')
    metadata = manifest(json.loads((project / 'app.json').read_text(encoding='utf-8')))
    compiler = shutil.which('arm-none-eabi-g++')
    objcopy = shutil.which('arm-none-eabi-objcopy')
    if not compiler or not objcopy:
        raise ValueError('arm-none-eabi-g++ and arm-none-eabi-objcopy are required; run doctor')
    version = subprocess.check_output([compiler, '-dumpfullversion'], text=True, encoding='utf-8', timeout=10).strip()
    if version != spec['compiler']:
        raise ValueError(f"SDK pins GCC {spec['compiler']}; found {version}")
    for path in [project / 'src', *(project / 'src').rglob('*')]:
        if path.is_symlink():
            raise ValueError('source symlinks are forbidden')
    config = project_config.load(project)
    runtime_profile.require_manifest(config, metadata)
    runtime = runtime_profile.resolve(sdk) if runtime_profile.selected(config) else None
    if config is not None:
        project_config.validate(config, {p.relative_to(project).as_posix()
                                        for p in (project / 'src').rglob('*') if p.is_file()})
        sources = [project / p for p in sorted(config['sources'])]
    else:
        sources = sorted(p for p in (project / 'src').rglob('*')
                         if p.is_file() and p.suffix in ('.c', '.cpp'))
    if not sources:
        raise ValueError('no C or C++ sources under src/')
    if config is None and len(sources) > 64:
        raise ValueError('more than 64 translation units requires project.json (up to 256)')
    c_compiler = None
    if runtime or any(source.suffix == '.c' for source in sources):
        c_compiler = shutil.which('arm-none-eabi-gcc')
        if not c_compiler:
            raise ValueError('C projects require arm-none-eabi-gcc from the pinned SDK toolchain')
        c_version = subprocess.check_output([c_compiler, '-dumpfullversion'], text=True, encoding='utf-8', timeout=10).strip()
        if c_version != spec['compiler']:
            raise ValueError(f"SDK pins GCC {spec['compiler']}; C compiler reports {c_version}")
    from assets import prepare, write_generated
    bundle, asset_report = prepare(project)
    expected = lock_value(sdk, metadata['abi'], metadata.get('schema', 0), runtime)
    lock = project / 'sdk.lock.json'
    if lock.exists() and json.loads(lock.read_text(encoding='utf-8')) != expected:
        raise ValueError('sdk.lock.json does not match this SDK/ABI; select the matching SDK or explicitly run lock --update')
    output = project / 'build'
    output.mkdir(exist_ok=True)
    with exclusive(output / '.build-lock'):
        if not lock.exists():
            write_json(lock, expected)
        (output / 'build.json').unlink(missing_ok=True)
        generated = write_generated(output, bundle)
        runtime_args = runtime_profile.arguments(output, config, metadata) if runtime else None
        objdir = output / profile
        objdir.mkdir(exist_ok=True)
        state_path = objdir / 'cache.json'
        try:
            previous = json.loads(state_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            previous = {}
        flags = ['-std=c++17', '-mcpu=cortex-a7', '-marm', '-mfpu=neon-vfpv4', '-mfloat-abi=hard',
                 '-Og' if profile == 'debug' else '-Os', '-g3', '-ffreestanding', '-fno-exceptions',
                 '-fno-rtti', '-fno-threadsafe-statics', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
                 '-fno-pic', '-fno-pie', '-ffunction-sections', '-fdata-sections', '-Wall', '-Wextra', '-Werror',
                 f'-ffile-prefix-map={sdk}=/lefony-sdk', f'-ffile-prefix-map={project}=.',
                 '-I', str(sdk / 'include')]
        if profile == 'debug':
            flags += ['-DLEFONY_SDK_DEBUG=1']
        if runtime:
            # Compiler-owned headers (notably stdatomic/stdint/stddef) must
            # precede libc's alternatives, as in the compiler's normal search.
            # Disable ambient target sysroots so only this pinned profile is
            # used after the compiler headers.
            flags += ['-nostdinc']
            for name in ('include', 'include-fixed'):
                directory = Path(subprocess.check_output([c_compiler, '-print-file-name=' + name],
                                 text=True, encoding='utf-8', timeout=10).strip())
                if directory.is_dir():
                    flags += ['-isystem', str(directory),
                              f'-ffile-prefix-map={directory}=/lefony-compiler/{name}']
                elif name == 'include':
                    raise ValueError('pinned compiler builtin headers are missing')
            flags += ['-isystem', str(runtime['include']),
                      f'-ffile-prefix-map={runtime["root"]}=/lefony-newlib']
        headers = {str(p.relative_to(project)): digest(p) for p in sorted((project / 'src').rglob('*'))
                   if p.is_file() and p.suffix not in ('.c', '.cpp')}
        common = {'sdk': expected['sdk_sha256'], 'compiler': digest(compiler), 'flags': flags,
                  'headers': headers, 'runtime': runtime['identity'] if runtime else None}
        state, commands, objects, compiled = {}, [], [], []
        library_sources = [sdk / 'lib/start.s', *sorted((sdk / 'lib/newlib').glob('*.c'))] if runtime else [
            sdk / 'lib/start.s', sdk / 'lib/memory.cpp']
        library_sources += sorted((sdk / 'lib/vendor/openbsd-math').glob('*.c'))
        for source in [*library_sources, *sources, *([generated] if generated else []),
                       *([runtime_args] if runtime_args else [])]:
            library = source in library_sources
            name = 'sdk/' + source.relative_to(sdk / 'lib').as_posix() if library else source.relative_to(project).as_posix()
            obj = objdir / (hashlib.sha256(name.encode()).hexdigest()[:16] + '.o')
            # Relative source names plus prefix maps make debug information relocatable.
            relative = str(source) if library else source.relative_to(project).as_posix()
            compile_flags = flags
            driver = compiler
            if not library and source.suffix == '.c':
                driver = c_compiler
                compile_flags = [flag for flag in flags if flag not in
                                 ('-std=c++17', '-fno-exceptions', '-fno-rtti', '-fno-threadsafe-statics')]
                compile_flags = [*compile_flags, '-std=c11']
            if library and source.suffix == '.c':
                compile_flags = [flag for flag in flags if flag not in
                                 ('-std=c++17', '-fno-exceptions', '-fno-rtti', '-fno-threadsafe-statics')]
                # Preserve the upstream C source. Its private compatibility
                # headers never enter an app translation unit's include path.
                if runtime and source.parent == sdk / 'lib/newlib':
                    driver = c_compiler
                    compile_flags = [*compile_flags, '-std=c11']
                    if config.get('defines',{}).get('LEFONY_PROFILE_HEAP')==1:
                        compile_flags += ['-DLEFONY_PROFILE_HEAP=1']
                else:
                    compile_flags = [*compile_flags, '-x', 'c', '-std=c11', '-ffp-contract=off', '-fno-strict-aliasing',
                                     '-fwrapv', '-w', '-I', str(sdk / 'lib/math_compat')]
            if not library and source not in (generated, runtime_args):
                compile_flags = [*compile_flags, *project_config.compiler_flags(config, 'c' if source.suffix == '.c' else 'cxx')]
            command = [driver, *compile_flags, '-MMD', '-MP', '-c', relative, '-o', str(obj)]
            signature = hashlib.sha256(canonical({'common': common, 'source': digest(source),
                                                'driver': digest(driver), 'compile_flags': compile_flags})).hexdigest()
            if previous.get(name) != signature or not obj.exists():
                subprocess.run(command, cwd=project, check=True, timeout=120)
                compiled.append(name)
            state[name] = signature
            objects.append(obj)
            if not library and source != runtime_args:
                commands.append({'directory': str(project), 'file': str(source), 'arguments': command})
        debug = output / 'app-debug.elf'
        image = output / 'app.elf'
        linker = sdk / ('cmake/foreground.ld' if runtime else 'cmake/app.ld')
        libraries = ['-L', str(runtime['libraries']), '-Wl,--start-group', '-lc', '-lm', '-lgcc',
                     '-Wl,--end-group'] if runtime else ['-lgcc']
        link = [compiler, *flags, '-nostdlib', '-nostartfiles', '-static', '-Wl,--build-id=none',
                '-Wl,--gc-sections', '-Wl,-z,noexecstack', '-Wl,-z,max-page-size=4096',
                '-Xlinker', '-T', '-Xlinker', str(linker),
                '-Xlinker', '-Map', '-Xlinker', str(output / 'app.map'),
                *map(str, objects), *libraries, '-o', str(debug)]
        subprocess.run(link, cwd=project, check=True, timeout=120)
        subprocess.run([objcopy, '--strip-all', str(debug), str(image)], check=True, timeout=30)
        _, segments = elf_segments(image.read_bytes())
        resources = {'code_bytes': sum(m for _, _, m, p in segments if p == 5),
                     'static_data_bytes': sum(m for _, _, m, p in segments if p == 6),
                     'initialized_data_bytes': sum(len(d) for _, d, _, p in segments if p == 6),
                     'stack_reserved_bytes': spec['limits']['stack_bytes'],
                     'surface_bytes': spec['limits']['width'] * spec['limits']['height'] * 2,
                     'heap': 'app-owned; included in static_data_bytes', 'stack_peak_bytes': None}
        if runtime:
            resources.update(heap='public foreground reservation; allocator metadata shares this capacity',
                             heap_reserved_bytes=runtime['heap_bytes'])
        if config and config.get('defines',{}).get('LEFONY_PROFILE_HEAP')==1:
            from heap_profile import address
            from lfapp import pack
            location=address(pack(metadata,image.read_bytes()))
            if location is None:raise ValueError('Heap diagnostic record is missing from the linked image')
            resources.update(heap_profile='newlib-mallinfo-at-unlock',heap_profile_address=location)
        write_json(state_path, state)
        write_json(project / 'compile_commands.json', commands)
        write_json(output / 'build.json', {'schema': 1, 'sdk': spec['sdk'], 'sdk_sha256': expected['sdk_sha256'],
                   'compiler': version, 'languages': sorted({('c11' if p.suffix == '.c' else 'c++17') for p in sources}),
                   'abi': metadata['abi'], 'profile': profile, 'project': config,
                   'runtime': runtime['identity'] if runtime else {'name': 'callback'},
                   'image_sha256': digest(image), 'debug_sha256': digest(debug),
                   'source_sha256': hashlib.sha256(canonical({'manifest': metadata, 'project': config,
                       'files': {p.relative_to(project).as_posix(): digest(p) for p in sources},
                       'headers': headers, 'assets': asset_report['inputs']})).hexdigest(),
                   'resources': {**resources, 'embedded_resource_bytes': asset_report['bytes']},
                   'assets': asset_report, 'compiled': compiled, 'link': link})
    return metadata, image
