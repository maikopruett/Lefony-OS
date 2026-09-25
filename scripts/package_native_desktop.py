#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a local relocatable desktop SDK with Python, QEMU and ARM compiler.

Run natively on the desired OS/architecture. This creates a local candidate;
publication additionally needs corresponding source and platform qualification.
No credentials or generated project builds are copied into the candidate.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'sdk/tools'))
from signing import public_der
from sdk_environment import openssl_environment
from usb_files import library_name


def contains_home_path(data, home):
    """Match an absolute home path, not a fragment such as unspecified/root/aux."""
    needle = os.fsencode(str(home).rstrip('/\\'))
    if not needle:
        return False
    cursor = 0
    while (cursor := data.find(needle, cursor)) >= 0:
        before = data[cursor-1:cursor] if cursor else b''
        after = data[cursor+len(needle):cursor+len(needle)+1]
        start = (not before or before in b'\0\t\r\n \'"=(:;[<'
                 or data[max(0, cursor-7):cursor] == b'file://')
        end = not after or after in b'/\\\0\t\r\n \'"),;]>'
        # System libraries such as libsystemd contain this default account
        # directory as a complete C string. It identifies no private build.
        # Paths beneath it, and every personal home directory, still fail.
        root_default = needle == b'/root' and (not before or before == b'\0') and after == b'\0'
        if start and end and not root_default:
            return True
        cursor += len(needle)
    return False


def host_settings(system, machine, python_version):
    if system not in ('Darwin', 'Linux', 'Windows'):
        raise ValueError('Desktop packaging supports macOS, Linux and native Windows')
    if system == 'Windows':
        if machine.lower() not in ('amd64', 'x86_64') or python_version < (3, 13):
            raise ValueError('Windows packaging requires native x86-64 Python 3.13 or newer')
        return {'suffix': '.exe', 'keyring': 'keyring.backends.Windows', 'archive': '.zip'}
    return {'suffix': '', 'keyring': 'keyring.backends.macOS' if system == 'Darwin'
            else 'keyring.backends.SecretService', 'archive': '.tar.gz'}


def archive_bundle(bundle, output, system, machine):
    if system == 'Windows':
        archive = output / 'lefony-sdk-windows-x86_64.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as target:
            for path in sorted(bundle.rglob('*')):
                if path.is_symlink():
                    raise ValueError('Windows archive cannot contain symbolic links')
                if path.is_file():
                    target.write(path, 'lefony-sdk/' + path.relative_to(bundle).as_posix())
    else:
        archive = output / f'lefony-sdk-{system.lower()}-{machine}.tar.gz'
        with tarfile.open(archive, 'w:gz') as target:
            target.add(bundle, arcname='lefony-sdk')
    return archive


def smoke_windows_openssl(bundle, environment):
    """Exercise provider loading and RSA with the public emulator fixture."""
    internal = bundle/'_internal'
    program = internal/'toolchain/bin/openssl.exe'
    fixture = internal/'tests/fixtures'
    def run(*arguments, data=None, check=True):
        return subprocess.run([str(program), *map(str, arguments)], input=data,
                              env=environment, cwd=bundle, check=check,
                              capture_output=True, timeout=30)
    providers = run('list', '-providers', '-provider', 'default', '-provider', 'legacy').stdout
    if not all(name in providers.split() for name in (b'default', b'legacy')):
        raise ValueError('Bundled OpenSSL failed to load its default and legacy providers')
    # req consumes openssl.cnf even on OpenSSL versions where dgst can succeed
    # despite a missing or malformed configuration. Reuse the fixture key;
    # emit a CSR to memory, without generating a new identity or certificate.
    request = run('req', '-new', '-key', fixture/'prime_g2_emulator_update_private.pem',
                  '-subj', '/CN=Lefony SDK packaging fixture', '-outform', 'DER').stdout
    if not request:
        raise ValueError('Bundled OpenSSL returned an empty configuration probe')
    payload = b'Lefony SDK packaging smoke; public emulator signing fixture only.\n'
    signature = run('dgst', '-sha256', '-sign', fixture/'prime_g2_emulator_update_private.pem',
                    data=payload).stdout
    if len(signature) != 256:
        raise ValueError('Bundled OpenSSL returned an invalid RSA-2048 signature length')
    with tempfile.TemporaryDirectory(prefix='sdk-openssl-smoke-') as directory:
        path = Path(directory)/'signature'
        path.write_bytes(signature)
        arguments = ('dgst', '-sha256', '-verify', fixture/'prime_g2_emulator_update_public.pem',
                     '-signature', path)
        run(*arguments, data=payload)
        if run(*arguments, data=payload+b'changed', check=False).returncode == 0:
            raise ValueError('Bundled OpenSSL accepted a changed signed payload')
    return {'providers': providers.decode('utf-8'), 'signature_bytes': len(signature),
            'configuration_request_sha256': hashlib.sha256(request).hexdigest(),
            'fixture': 'public-emulator-only', 'signature_verified': True,
            'changed_payload_rejected': True, 'keys_generated': False}


def smoke_bundle(bundle, settings):
    """Execute the packaged CLI and helpers with only bundled/system tool paths."""
    internal = bundle / '_internal'
    environment = dict(os.environ)
    # Use only bundled/system tool paths. QEMU's application-directory DLLs
    # take precedence even if a parent has used SetDllDirectory.
    if settings['suffix']:
        from native_desktop_windows import system_directory
        system = system_directory()
        environment['PATH'] = os.pathsep.join(map(str, (
            internal / 'toolchain/bin', internal, system, system.parent)))
        environment = openssl_environment(internal/'openssl', environment)
    elif platform.system() == 'Linux':
        from native_desktop_linux import loader_environment
        environment = loader_environment()
        environment['PATH'] = '/usr/bin:/bin'
    commands = [
        [bundle / ('lefony-sdk' + settings['suffix']), 'doctor'],
        [internal / ('runtime/qemu-system-arm' + settings['suffix']), '--version'],
        [internal / ('toolchain/bin/arm-none-eabi-gdb' + settings['suffix']), '--configuration'],
        [internal / ('toolchain/bin/openssl' + settings['suffix']), 'version'],
    ]
    results = []
    for command in commands:
        result = subprocess.run(command, env=environment, cwd=bundle, check=True,
                                capture_output=True, text=True, timeout=60)
        results.append(result.stdout)
    doctor = json.loads(results[0])
    if not all(doctor.get(name) is True for name in ('qemu', 'vm_firmware', 'objcopy', 'gdb', 'pillow', 'libusb')):
        raise ValueError('Bundled doctor reports missing required runtime components')
    if '--without-python' not in results[2] or '--target=arm-none-eabi' not in results[2]:
        raise ValueError('Bundled GDB must target ARM without an embedded Python runtime')
    report = {'doctor': doctor, 'qemu': results[1], 'gdb_configuration': results[2],
              'openssl': results[3], 'clean_host_qualified': False}
    if settings['suffix']:
        report['openssl_signing'] = smoke_windows_openssl(bundle, environment)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', type=Path, default=ROOT/('build/qemu-prime-g2/qemu-system-arm' + ('.exe' if os.name == 'nt' else '')))
    parser.add_argument('--firmware', type=Path, default=ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--toolchain', type=Path, required=True, help='GCC installation prefix')
    parser.add_argument('--binutils', type=Path, required=True, help='ARM binutils installation prefix')
    parser.add_argument('--public-key', type=Path, action='append', required=True)
    parser.add_argument('--runtime-library', type=Path, action='append', default=[], help='Explicit dynamically loaded libraries (QEMU process only on Windows), e.g. SDL3 used by SDL2 compatibility')
    parser.add_argument('--dll-directory', type=Path, action='append', default=[], help='Explicit Windows dependency directory; no ambient PATH search')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--emulator-window', type=Path, required=True, help='Native window bundle from build_emulator_window.py')
    parser.add_argument('--openssl',type=Path,required=True,help='Redistributable OpenSSL executable, not the macOS system binary')
    parser.add_argument('--openssl-runtime',type=Path,help='Required on Windows: complete candidate from build_sdk_windows_openssl.py')
    parser.add_argument('--cpython-runtime',type=Path,help='Required on Windows: original reviewed full CPython ZIP')
    parser.add_argument('--source-materials',type=Path,required=True,help='Verified source/notice directory from collect_native_desktop_sources.py')
    parser.add_argument('--project-sources',type=Path,required=True,help='Matching public/QEMU/VM sources and retained firmware rebuild evidence')
    parser.add_argument('--newlib',type=Path,required=True,help='Verified foreground sysroot and corresponding source')
    parser.add_argument('--gdb-runtime',type=Path,required=True,help='Candidate from build_sdk_gdb.py')
    parser.add_argument('--libusb',type=Path,required=True,help='Native redistributable libusb dynamic library')
    args = parser.parse_args()
    try:
        settings = host_settings(platform.system(), platform.machine(), sys.version_info[:2])
    except ValueError as exc:
        parser.error(str(exc))
    from build_emulator_window import verify as verify_window
    suffix = settings['suffix']
    if args.dll_directory and not suffix:
        parser.error('--dll-directory is only used for Windows candidates')
    if bool(args.openssl_runtime) != bool(suffix):
        parser.error('--openssl-runtime is required on Windows and only used there')
    if bool(args.cpython_runtime) != bool(suffix):
        parser.error('--cpython-runtime is required on Windows and only used there')
    if args.cpython_runtime and not args.cpython_runtime.is_file():
        parser.error('missing CPython runtime archive')
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error('output already exists; use a new candidate directory')
    for path in (args.qemu,args.firmware,args.openssl,args.libusb,args.source_materials/"manifest.json",args.gdb_runtime/'candidate.json',args.emulator_window/'window.json',*args.public_key,*args.runtime_library):
        if not path.is_file(): parser.error(f'missing input: {path}')
    try:
        verify_window(args.emulator_window)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(f'invalid desktop window bundle: {exc}')
    if contains_home_path(args.qemu.read_bytes(), Path.home()):
        parser.error('QEMU embeds a private home path; rebuild from neutral source/build paths (see NATIVE-APP-SETUP.md)')
    sources=json.loads((args.source_materials/'manifest.json').read_text())
    if sources.get('platform')!=platform.system().lower()+'-'+platform.machine():
        parser.error('Corresponding source manifest must match the native host')
    trust_version=importlib.metadata.version('truststore')
    trust_sources=[entry for entry in sources['components'] if entry['component']=='truststore']
    if len(trust_sources)!=1 or trust_sources[0].get('version')!=trust_version or not trust_sources[0].get('inputs'):
        parser.error('Native TLS requires matching truststore source and version in the source manifest')
    if not any(path.is_file() for path in (args.source_materials/'truststore/notices').glob('*')):
        parser.error('Native TLS requires truststore license notices')
    for component in sources['components']:
        if component.get('recipe_sha256'):
            recipe=args.source_materials/component['component']/'formula.rb'
            if hashlib.sha256(recipe.read_bytes()).hexdigest()!=component['recipe_sha256']:
                parser.error('Source recipe differs from manifest: '+component['component'])
        for entry in component['inputs']+component.get('installed_notices',[]):
            source=(args.source_materials/entry['file']).resolve()
            if (not source.is_relative_to(args.source_materials.resolve()) or not source.is_file()
                    or hashlib.sha256(source.read_bytes()).hexdigest()!=entry['sha256']):
                parser.error('Corresponding source differs from manifest: '+entry['file'])
    openssl_candidate = None
    if suffix:
        from native_desktop_openssl import verify_candidate
        args.openssl_runtime = args.openssl_runtime.resolve()
        try:
            openssl_candidate = verify_candidate(args.openssl_runtime, args.openssl, sources)
        except ValueError as exc:
            parser.error(str(exc))
    import native_desktop_firmware
    public_key_options = {'program': args.openssl.resolve(),
                          'runtime': args.openssl_runtime/'install' if suffix else None}
    emulator_der = public_der(ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem', **public_key_options)
    firmware_trust = native_desktop_firmware.verify_trust(args.firmware,
        [public_der(key, **public_key_options) for key in args.public_key], emulator_der)
    from pillow_native_sources import supported_host, verify_installation, verify_materials, record_bundle
    pillow_lock = None
    if supported_host():
        try:
            pillow_lock = verify_materials(args.source_materials, sources)
            verify_installation(pillow_lock)
        except ValueError as exc:
            parser.error(str(exc))
    linux_wheel_lock = None
    windows_python_inputs = None
    windows_cpython_inputs = None
    if suffix:
        import windows_python_sources
        import windows_cpython_sources
        import collect_native_windows_sources
        try:
            collect_native_windows_sources.verify_materials(args.source_materials, sources)
            cpython_lock = windows_cpython_sources.verify_materials(args.source_materials, sources)
            windows_cpython_inputs = windows_cpython_sources.verify_installation(cpython_lock, args.cpython_runtime)
            windows_lock = windows_python_sources.verify_materials(args.source_materials, sources)
            windows_python_inputs = windows_python_sources.verify_installation(windows_lock, args.source_materials)
        except ValueError as exc:
            parser.error(str(exc))
    if sources['platform'] == 'linux-x86_64':
        import linux_wheel_native_sources
        try:
            linux_wheel_lock = linux_wheel_native_sources.verify_materials(args.source_materials, sources)
            linux_wheel_native_sources.verify_installation(linux_wheel_lock)
        except ValueError as exc:
            parser.error(str(exc))
    import native_desktop_project as project_sources
    newlib_inputs = project_sources.newlib_record(ROOT/'sdk',args.newlib)
    project_inputs = None
    if suffix:
        project_sources.verify_newlib_materials(ROOT/'sdk',args.source_materials,sources,newlib_inputs)
    project_inputs = project_sources.verify_project(args.project_sources,args.firmware,args.qemu,args.source_materials,sources)
    from build_sdk_gdb import SHA256 as GDB_SOURCE_SHA256
    debugger=json.loads((args.gdb_runtime/'candidate.json').read_text())
    if (debugger.get('platform')!=platform.system() or debugger.get('architecture')!=platform.machine()
            or debugger.get('source_sha256')!=GDB_SOURCE_SHA256):
        parser.error('GDB candidate must match the native host and pinned source')
    debugger_files=debugger.get('files',{})
    if 'bin/arm-none-eabi-gdb' + suffix not in debugger_files:
        parser.error('GDB candidate has no debugger')
    for name,expected in debugger_files.items():
        path=args.gdb_runtime/'install'/name
        if (Path(name).is_absolute() or '..' in Path(name).parts or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest()!=expected):
            parser.error('GDB file differs from its build candidate: '+name)
    gdb_recipe = args.gdb_runtime / 'build_sdk_gdb.py'
    if not gdb_recipe.is_file():
        gdb_recipe = ROOT / 'scripts/build_sdk_gdb.py'
    if hashlib.sha256(gdb_recipe.read_bytes()).hexdigest() != debugger.get('recipe_sha256'):
        parser.error('GDB candidate requires its exact recorded build_sdk_gdb.py recipe')
    for name, expected in debugger.get('recipe_inputs', {}).items():
        source = args.gdb_runtime / name
        if (name != 'native_desktop_windows.py' or not source.is_file()
                or hashlib.sha256(source.read_bytes()).hexdigest() != expected):
            parser.error('GDB build recipe input differs from candidate: ' + name)
    compiler = args.toolchain/('bin/arm-none-eabi-g++' + suffix)
    if subprocess.check_output([compiler,'-dumpfullversion'],text=True,timeout=30).strip()!='16.2.0':
        parser.error('GCC 16.2.0 is required')
    (ROOT / 'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sdk-desktop-stage-', dir=ROOT/'build') as stage_directory:
        stage = Path(stage_directory)
        sdk = stage/'sdk'
        if sdk.exists(): shutil.rmtree(sdk)
        sdk.mkdir()
        allowed={'.py','.h','.s','.ld','.c','.cpp','.json','.md','.service','.timer','.txt','.cmake'}
        for source in sorted((ROOT/'sdk').rglob('*')):
            relative=source.relative_to(ROOT/'sdk')
            if not source.is_file() or source.is_symlink() or source.name in ('compile_commands.json','sdk.lock.json') or any(part in ('build','__pycache__','trust','.lefony','runtime') for part in relative.parts): continue
            example_asset = relative.parts[0]=='examples' and 'assets' in relative.parts and source.suffix in ('.png','.rgb565','.bin')
            skin_asset = relative.parts[:2] == ('assets', 'prime') and source.suffix in ('.png', '.primeskin')
            if not (example_asset or skin_asset) and source.suffix not in allowed and source.name not in ('lefony-sdk','Dockerfile','Dockerfile.toolchain'): continue
            target=sdk/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
        if args.newlib:
            from runtime import bundle_files
            for name,source in bundle_files(ROOT/'sdk',args.newlib).items():
                target=sdk/'runtime/newlib'/name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,target)
        project_sources.verify_newlib_copy(sdk/'runtime/newlib',newlib_inputs)
        if project_inputs is not None:
            from package_native_desktop_sources import project_inputs as archived_project_inputs
            public_manifest, public_inputs = archived_project_inputs(args.project_sources)
            public_archive = dict((name,path) for path,name in public_inputs)[public_manifest['archives']['lefony']['file']]
            project_inputs['public_source_check'] = project_sources.verify_public_sources(public_archive,sdk,ROOT/'scripts')
        (sdk/'trust').mkdir()
        for key in args.public_key:
            identity = hashlib.sha256(public_der(key, program=args.openssl.resolve(),
                runtime=args.openssl_runtime/'install' if suffix else None)).hexdigest()
            shutil.copyfile(key,sdk/'trust'/f'{identity}.pem')
        runtime = stage/'runtime';runtime.mkdir(exist_ok=True)
        usb=stage/'usb';usb.mkdir(exist_ok=True)
        shutil.copyfile(args.libusb,usb/library_name())
        fixtures=stage/'tests/fixtures';fixtures.mkdir(parents=True,exist_ok=True)
        for name in ('prime_g2_emulator_update_private.pem','prime_g2_emulator_update_public.pem'):
            shutil.copyfile(ROOT/'tests/fixtures'/name,fixtures/name)
        shutil.copyfile(args.firmware,runtime/'firmware.elf')
        qemu = runtime / ('qemu-system-arm' + suffix)
        shutil.copyfile(args.qemu, qemu)
        qemu.chmod(args.qemu.stat().st_mode)
        toolchain = stage/'toolchain'
        if toolchain.exists(): shutil.rmtree(toolchain)
        toolchain.mkdir()
        # Explicit compiler/runtime directories only; exclude receipts, caches,
        # package manager metadata and local machine paths in configuration files.
        for prefix in (args.toolchain,args.binutils):
            for name in ('bin','lib','libexec','arm-none-eabi'):
                if (prefix/name).is_dir():
                    shutil.copytree(prefix/name,toolchain/name,dirs_exist_ok=True,symlinks=False,
                                   ignore=shutil.ignore_patterns('install-tools'))
        for name in debugger_files:
            target=toolchain/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(args.gdb_runtime/'install'/name,target)
        shutil.copy2(args.openssl, toolchain / ('bin/openssl' + suffix))
        extra_binaries = list(args.runtime_library)
        openssl_record = None
        qemu_dlls = None
        linux_dependencies = None
        if suffix:
            from native_desktop_windows import collect_dependencies, native_files, system_directory
            from native_desktop_openssl import stage_runtime
            openssl_record = stage_runtime(args.openssl_runtime, openssl_candidate, stage/'openssl')
            # Do not flatten QEMU's MinGW libffi into CPython's DLL directory.
            # Keep this executable and its libraries outside PyInstaller input
            # analysis, which otherwise collects both libffi builds by name.
            qemu_dlls = stage/'qemu-dlls'
            collect_dependencies([args.qemu, *args.runtime_library],
                [args.qemu.parent, *[p.parent for p in args.runtime_library], *args.dll_directory],
                qemu_dlls, system_directory())
            roots = [args.openssl, args.libusb, *native_files(toolchain)]
            roots.extend(native_files(stage/'openssl'))
            search = [args.openssl.parent, args.libusb.parent,
                      args.toolchain/'bin', args.binutils/'bin', args.gdb_runtime/'install/bin',
                      *args.dll_directory]
            dlls = stage / 'windows-dlls'
            collect_dependencies(roots, search, dlls, system_directory())
            extra_binaries = sorted(dlls.iterdir())
        elif platform.system() == 'Linux':
            from native_desktop_linux import collect_dependencies, native_files
            libraries = stage / 'linux-libraries'
            linux_dependencies = collect_dependencies(
                [args.qemu, args.openssl, args.libusb, *args.runtime_library,
                 *native_files(toolchain)], libraries)
            extra_binaries.extend(sorted(libraries.iterdir()))
        from PyInstaller.__main__ import run
        run(['--noconfirm','--clean','--onedir','--noupx','--name','lefony-sdk',
             '--distpath',str(args.output),'--workpath',str(stage/'pyinstaller'),
             '--specpath',str(stage),'--paths',str(ROOT/'sdk/tools'),
             '--add-data',str(sdk)+os.pathsep+'sdk',
             '--add-data',str(runtime/'firmware.elf' if suffix else runtime)+os.pathsep+'runtime',
             '--add-data',str(fixtures)+os.pathsep+'tests/fixtures',
             *([] if suffix else ['--add-binary',str(qemu)+os.pathsep+'runtime']),
             '--add-binary',str(toolchain)+os.pathsep+'toolchain',
             '--add-binary',str(usb/library_name())+os.pathsep+'usb',
             *(['--add-data',str(stage/'openssl')+os.pathsep+'openssl'] if suffix else []),
             '--hidden-import','source','--hidden-import','runner','--hidden-import','signing',
             '--hidden-import','build','--hidden-import','assets','--hidden-import','replay','--hidden-import','workspace',
             '--hidden-import','emulator_usb','--hidden-import','diagnostics','--hidden-import','gdb_transport','--hidden-import','local_transport','--hidden-import','PIL.Image',
             '--hidden-import',settings['keyring'],
             '--hidden-import','truststore',
             *[argument for library in extra_binaries for argument in ('--add-binary',str(library)+os.pathsep+'.')],
             str(ROOT/'sdk/tools/portable_entry.py')])
        bundle=args.output/'lefony-sdk'
        if qemu_dlls is not None:
            destination=bundle/'_internal/runtime'
            destination.mkdir(parents=True,exist_ok=True)
            for source in (qemu, *sorted(qemu_dlls.iterdir())):
                target=destination/source.name
                if target.exists():
                    raise ValueError('Unexpected pre-existing QEMU runtime input: '+source.name)
                shutil.copy2(source,target)
                if hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(source.read_bytes()).digest():
                    raise ValueError('QEMU runtime changed during copying: '+source.name)
        if windows_python_inputs is not None:
            (bundle/'windows-python-inputs.json').write_text(
                json.dumps(windows_python_inputs,indent=2)+'\n',encoding='utf-8',newline='\n')
        if openssl_record is not None:
            from native_desktop_openssl import verify_runtime
            verify_runtime(bundle/'_internal/openssl', openssl_record)
            (bundle/'windows-openssl-runtime.json').write_text(
                json.dumps(openssl_record,indent=2)+'\n',encoding='utf-8',newline='\n')
        if linux_dependencies is not None:
            from native_desktop_linux import relocate_bundle, audit_bundle
            # Record output hashes after repairing ELF library paths, including
            # the launcher's prefix while preserving its exact appended archive.
            relocation = relocate_bundle(bundle)
            audit = audit_bundle(bundle)
            for name, value in (('linux-library-inputs', linux_dependencies),
                                ('linux-relocation', relocation),
                                ('linux-dependencies', audit)):
                (bundle/(name+'.json')).write_text(
                    json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
        if platform.system() == 'Darwin':
            macos_qemu = project_sources.record_macos_qemu(
                stage/'pyinstaller/lefony-sdk/Analysis-00.toc', bundle,
                project_inputs['qemu_input_sha256'])
            (bundle/'macos-qemu-source-inputs.json').write_text(
                json.dumps(macos_qemu,indent=2)+'\n',encoding='utf-8')
        pillow_inputs = None
        if pillow_lock:
            pillow_inputs = record_bundle(stage/'pyinstaller/lefony-sdk/Analysis-00.toc', bundle, pillow_lock)
            (bundle/'pillow-native-inputs.json').write_text(
                json.dumps(pillow_inputs,indent=2)+'\n',encoding='utf-8',newline='\n')
        if linux_wheel_lock:
            linux_wheel_inputs = linux_wheel_native_sources.record_bundle(
                stage/'pyinstaller/lefony-sdk/Analysis-00.toc', bundle, linux_wheel_lock)
            (bundle/'linux-wheel-native-inputs.json').write_text(
                json.dumps(linux_wheel_inputs,indent=2)+'\n',encoding='utf-8',newline='\n')
            import native_desktop_linux_sources
            linux_source_inputs = native_desktop_linux_sources.record_bundle(
                stage/'pyinstaller/lefony-sdk/Analysis-00.toc', bundle, sources)
            linux_source_inputs['source_manifest_sha256'] = hashlib.sha256((args.source_materials/'manifest.json').read_bytes()).hexdigest()
            (bundle/'linux-native-source-inputs.json').write_text(
                json.dumps(linux_source_inputs,indent=2)+'\n',encoding='utf-8',newline='\n')
        window_target = bundle/'_internal/emulator-window'
        shutil.copytree(args.emulator_window, window_target, symlinks=True)
        verify_window(window_target)
        shutil.copyfile(ROOT/'sdk/DESKTOP-README.md',bundle/'README.md')
        for name in ('LICENSE.md','THIRD_PARTY_NOTICES.md'):
            shutil.copyfile(ROOT/name,bundle/name)
        shutil.copytree(ROOT/'LICENSES',bundle/'LICENSES')
        for name in ('LICENSE.md','THIRD_PARTY_NOTICES.md'):
            shutil.copyfile(ROOT/name,bundle/'_internal'/name)
        shutil.copytree(ROOT/'LICENSES',bundle/'_internal/LICENSES')
        docs=bundle/'_internal/docs';docs.mkdir(exist_ok=True)
        for source in (ROOT/'docs').glob('NATIVE-APP-*.md'):
            shutil.copyfile(source,docs/source.name)
        for source in (ROOT/'docs').glob('EMULATOR-*.md'):
            shutil.copyfile(source,docs/source.name)
        for source in (ROOT/'docs').glob('SDK-*.md'):
            shutil.copyfile(source,docs/source.name)
        notices=bundle/'THIRD_PARTY';notices.mkdir()
        for component in sources['components']:
            name=component['component'];source=args.source_materials/name/'notices'
            if source.is_dir():shutil.copytree(source,notices/name)
        gdb_notices=notices/'arm-none-eabi-gdb'
        for source in (args.gdb_runtime/'notices').rglob('*'):
            if source.is_file():
                target=gdb_notices/source.relative_to(args.gdb_runtime/'notices')
                if target.is_file() and target.read_bytes()!=source.read_bytes():
                    raise ValueError('Collected GDB notice differs from the build candidate')
        shutil.copytree(args.gdb_runtime/'notices',gdb_notices,dirs_exist_ok=True)
        shutil.copyfile(args.gdb_runtime/'candidate.json',gdb_notices/'candidate.json')
        gdb_archive=args.gdb_runtime/'gdb-17.2.tar.xz'
        if hashlib.sha256(gdb_archive.read_bytes()).hexdigest()!=GDB_SOURCE_SHA256:
            raise ValueError('GDB corresponding source differs from the pinned archive')
        shutil.copyfile(gdb_archive,args.output/gdb_archive.name)
        shutil.copyfile(gdb_recipe,args.output/'build_sdk_gdb.py')
        for name in debugger.get('recipe_inputs', {}):
            shutil.copyfile(args.gdb_runtime/name, args.output/name)
        gdb_components=[c for c in sources['components'] if c['component']=='arm-none-eabi-gdb']
        if gdb_components:
            expected_inputs={GDB_SOURCE_SHA256,debugger['recipe_sha256'],*debugger.get('recipe_inputs',{}).values()}
            if (len(gdb_components)!=1 or gdb_components[0].get('version')!=debugger['version']
                    or not expected_inputs <= {item['sha256'] for item in gdb_components[0]['inputs']}):
                raise ValueError('Collected GDB sources differ from the build candidate')
        else:
            sources['components'].append({'component':'arm-none-eabi-gdb','version':debugger['version'],
                'recipe':'build_sdk_gdb.py','recipe_sha256':debugger['recipe_sha256'],
                'inputs':[{'file':gdb_archive.name,'url':debugger['source_url'],'sha256':GDB_SOURCE_SHA256}]})
        (notices/'sources.json').write_text(json.dumps(sources,indent=2)+'\n')
        (notices/'README.md').write_text('This development SDK bundles separately licensed components. See the notices in each component directory. Exact upstream archives, Homebrew recipes/patches, patched QEMU and firmware sources are separate downloads beside the binary at https://lefony.com/#developers. The source manifest records component versions and hashes. Build and packaging scripts are included with the SDK source. Python implements host tools only; apps are native ARM C++.\n')
        report={'platform' :platform.system(),'architecture':platform.machine(),
                'compiler':'16.2.0','python':platform.python_version(),'abi':1,
                'physical_install':True,'hardware_qualified':False,'qualification':'experimental development candidate; full host and physical qualification pending',
                'sdk':json.loads((sdk/'contract.json').read_text())['sdk'],
                'qemu_sha256':hashlib.sha256((bundle/('_internal/runtime/qemu-system-arm' + suffix)).read_bytes()).hexdigest(),
                'qemu_input_sha256':hashlib.sha256(args.qemu.read_bytes()).hexdigest(),
                'debugger':{'version':debugger['version'],'source_sha256':debugger['source_sha256'],
                            'bundled':True,'python_scripting':False},
                'libusb_bundled':True,'newlib_bundled':True,
                'https_trust':{'default':'native-system','library':'truststore','version':trust_version,
                               'explicit_ca':'replaces-system-trust','network_qualified':False},
                'firmware_sha256':hashlib.sha256(args.firmware.read_bytes()).hexdigest()}
        report['desktop_window'] = {'qt_version': '6.11.2',
            'manifest_sha256': hashlib.sha256((window_target/'window.json').read_bytes()).hexdigest(),
            'corresponding_sources_qualified': False}
        if pillow_inputs:
            report['pillow_native_inputs_sha256'] = hashlib.sha256((bundle/'pillow-native-inputs.json').read_bytes()).hexdigest()
        if linux_wheel_lock:
            report['linux_wheel_native_inputs_sha256'] = hashlib.sha256((bundle/'linux-wheel-native-inputs.json').read_bytes()).hexdigest()
            report['linux_native_source_inputs_sha256'] = hashlib.sha256((bundle/'linux-native-source-inputs.json').read_bytes()).hexdigest()
        if linux_dependencies is not None:
            for name in ('linux-library-inputs', 'linux-relocation', 'linux-dependencies'):
                report[name.replace('-', '_')+'_sha256'] = hashlib.sha256((bundle/(name+'.json')).read_bytes()).hexdigest()
        if suffix:
            from native_desktop_windows import audit_bundle, system_directory
            audit = audit_bundle(bundle, system_directory())
            (bundle/'windows-dependencies.json').write_text(json.dumps(audit,indent=2)+'\n')
            import native_desktop_windows_sources
            native_sources = native_desktop_windows_sources.record_bundle(bundle, sources, cpython_lock, windows_lock)
            (bundle/'windows-native-source-inputs.json').write_text(json.dumps(native_sources,indent=2)+'\n')
            report['windows_native_source_inputs_sha256'] = hashlib.sha256((bundle/'windows-native-source-inputs.json').read_bytes()).hexdigest()
            windows_cpython_inputs['bundled_files'] = windows_cpython_sources.record_bundle(bundle, cpython_lock)
            (bundle/'windows-cpython-inputs.json').write_text(json.dumps(windows_cpython_inputs,indent=2)+'\n')
            report['windows_cpython_inputs_sha256'] = hashlib.sha256((bundle/'windows-cpython-inputs.json').read_bytes()).hexdigest()
            report['windows_dependencies_sha256'] = hashlib.sha256((bundle/'windows-dependencies.json').read_bytes()).hexdigest()
            report['windows_openssl_runtime_sha256'] = hashlib.sha256((bundle/'windows-openssl-runtime.json').read_bytes()).hexdigest()
            report['windows_python_inputs_sha256'] = hashlib.sha256((bundle/'windows-python-inputs.json').read_bytes()).hexdigest()
        project_sources.verify_newlib_copy(bundle/'_internal/sdk/runtime/newlib',newlib_inputs)
        (bundle/'newlib-inputs.json').write_text(json.dumps(newlib_inputs,indent=2)+'\n')
        report['newlib_inputs_sha256'] = hashlib.sha256((bundle/'newlib-inputs.json').read_bytes()).hexdigest()
        bundled_trust = native_desktop_firmware.verify_trust(bundle/'_internal/runtime/firmware.elf',
            [public_der(key, **public_key_options) for key in sorted((bundle/'_internal/sdk/trust').glob('*.pem'))],
            emulator_der)
        if bundled_trust != firmware_trust:
            raise ValueError('Bundled VM firmware/trust differs from selected inputs')
        (bundle/'firmware-trust-inputs.json').write_text(json.dumps(bundled_trust,indent=2)+'\n')
        report['firmware_trust_inputs_sha256'] = hashlib.sha256((bundle/'firmware-trust-inputs.json').read_bytes()).hexdigest()
        if project_inputs is not None:
            project_inputs['bundled_binary_check'] = project_sources.verify_bundled_project(bundle,project_inputs)
            project_inputs['public_source_check'] = project_sources.verify_public_sources(public_archive,bundle/'_internal/sdk',ROOT/'scripts')
            (bundle/'project-source-inputs.json').write_text(json.dumps(project_inputs,indent=2)+'\n')
            report['project_source_inputs_sha256'] = hashlib.sha256((bundle/'project-source-inputs.json').read_bytes()).hexdigest()
        smoke = smoke_bundle(bundle, settings)
        (bundle/'packaging-smoke.json').write_text(json.dumps(smoke,indent=2)+'\n')
        report['packaging_smoke_sha256'] = hashlib.sha256((bundle/'packaging-smoke.json').read_bytes()).hexdigest()
        (bundle/'candidate.json').write_text(json.dumps(report,indent=2)+'\n')
        files=sorted(p for p in bundle.rglob('*') if p.is_file() and not p.is_symlink())
        for path in files:
            if contains_home_path(path.read_bytes(), Path.home()):
                raise ValueError('Bundle contains a private home path: '+path.relative_to(bundle).as_posix())
        (bundle/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(bundle).as_posix()}\n' for p in files))
        archive=archive_bundle(bundle,args.output,platform.system(),platform.machine())
        print(archive)
        print(hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__=='__main__': main()
