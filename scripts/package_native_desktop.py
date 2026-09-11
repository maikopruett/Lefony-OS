#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a local relocatable desktop SDK with Python, QEMU and ARM compiler.

Run natively on the desired OS/architecture. This creates a local candidate;
publication additionally needs corresponding source and platform qualification.
No credentials or generated project builds are copied into the candidate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'sdk/tools'))
from signing import public_der


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', type=Path, default=ROOT/'build/qemu-prime-g2/qemu-system-arm')
    parser.add_argument('--firmware', type=Path, default=ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--toolchain', type=Path, required=True, help='GCC installation prefix')
    parser.add_argument('--binutils', type=Path, required=True, help='ARM binutils installation prefix')
    parser.add_argument('--public-key', type=Path, action='append', required=True)
    parser.add_argument('--runtime-library', type=Path, action='append', default=[], help='Libraries loaded with dlopen, e.g. SDL3 used by SDL2 compatibility')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--openssl',type=Path,required=True,help='Redistributable OpenSSL executable, not the macOS system binary')
    parser.add_argument('--source-materials',type=Path,required=True,help='Verified source/notice directory from collect_native_desktop_sources.py')
    args = parser.parse_args()
    if platform.system() not in ('Darwin','Linux'):
        parser.error('This socket-based SDK currently supports macOS and Linux')
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error('output already exists; use a new candidate directory')
    for path in (args.qemu,args.firmware,args.openssl,args.source_materials/"manifest.json",*args.public_key):
        if not path.is_file(): parser.error(f'missing input: {path}')
    if str(Path.home()).encode() in args.qemu.read_bytes():
        parser.error('QEMU embeds a private home path; rebuild from neutral source/build paths (see NATIVE-APP-SETUP.md)')
    compiler = args.toolchain/'bin/arm-none-eabi-g++'
    if subprocess.check_output([compiler,'-dumpfullversion'],text=True).strip()!='16.2.0':
        parser.error('GCC 16.2.0 is required')
    stage = ROOT/'build/sdk-desktop-stage'
    stage.mkdir(exist_ok=True)
    sdk = stage/'sdk'
    if sdk.exists(): shutil.rmtree(sdk)
    sdk.mkdir()
    allowed={'.py','.h','.s','.ld','.cpp','.json','.md','.service','.timer','.txt'}
    for source in sorted((ROOT/'sdk').rglob('*')):
        relative=source.relative_to(ROOT/'sdk')
        if not source.is_file() or source.is_symlink() or any(part in ('build','__pycache__','trust') for part in relative.parts): continue
        if source.suffix not in allowed and source.name not in ('lefony-sdk','Dockerfile','Dockerfile.toolchain'): continue
        target=sdk/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    (sdk/'trust').mkdir()
    for key in args.public_key:
        identity = hashlib.sha256(public_der(key)).hexdigest()
        shutil.copyfile(key,sdk/'trust'/f'{identity}.pem')
    runtime = stage/'runtime';runtime.mkdir(exist_ok=True)
    shutil.copyfile(args.firmware,runtime/'firmware.elf')
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
    from PyInstaller.__main__ import run
    run(['--noconfirm','--clean','--onedir','--noupx','--name','lefony-sdk',
         '--distpath',str(args.output),'--workpath',str(stage/'pyinstaller'),
         '--specpath',str(stage),'--paths',str(ROOT/'sdk/tools'),
         '--add-data',str(sdk)+os.pathsep+'sdk',
         '--add-data',str(runtime)+os.pathsep+'runtime',
         '--add-binary',str(args.qemu.resolve())+os.pathsep+'runtime',
         '--add-binary',str(toolchain)+os.pathsep+'toolchain',
         '--add-binary',str(args.openssl.resolve())+os.pathsep+'toolchain/bin',
         '--hidden-import','source','--hidden-import','runner','--hidden-import','signing',
         *[argument for library in args.runtime_library for argument in ('--add-binary',str(library)+os.pathsep+'.')],
         str(ROOT/'sdk/tools/portable_entry.py')])
    bundle=args.output/'lefony-sdk'
    shutil.copyfile(ROOT/'sdk/DESKTOP-README.md',bundle/'README.md')
    subprocess.run([bundle/'_internal/runtime/qemu-system-arm','--version'],check=True,timeout=30)
    for name in ('LICENSE.md','THIRD_PARTY_NOTICES.md'):
        shutil.copyfile(ROOT/name,bundle/name)
    shutil.copytree(ROOT/'LICENSES',bundle/'LICENSES')
    for name in ('LICENSE.md','THIRD_PARTY_NOTICES.md'):
        shutil.copyfile(ROOT/name,bundle/'_internal'/name)
    shutil.copytree(ROOT/'LICENSES',bundle/'_internal/LICENSES')
    docs=bundle/'_internal/docs';docs.mkdir(exist_ok=True)
    for source in (ROOT/'docs').glob('NATIVE-APP-*.md'):
        shutil.copyfile(source,docs/source.name)
    sources=json.loads((args.source_materials/'manifest.json').read_text())
    notices=bundle/'THIRD_PARTY';notices.mkdir()
    for component in sources['components']:
        name=component['component'];source=args.source_materials/name/'notices'
        if source.is_dir():shutil.copytree(source,notices/name)
    (notices/'sources.json').write_text(json.dumps(sources,indent=2)+'\n')
    (notices/'README.md').write_text('This development SDK bundles separately licensed components. See the notices in each component directory. Exact upstream archives, Homebrew recipes/patches, patched QEMU and firmware sources are separate downloads beside the binary at https://lefony.com/#developers. The source manifest records component versions and hashes. Build and packaging scripts are included with the SDK source. Python implements host tools only; apps are native ARM C++.\n')
    report={'platform' :platform.system(),'architecture':platform.machine(),
            'compiler':'16.2.0','python':platform.python_version(),'abi':1,
            'physical_install':True,'hardware_qualified':False,'qualification':'local candidate',
            'firmware_sha256':hashlib.sha256(args.firmware.read_bytes()).hexdigest()}
    (bundle/'candidate.json').write_text(json.dumps(report,indent=2)+'\n')
    files=sorted(p for p in bundle.rglob('*') if p.is_file() and not p.is_symlink())
    for path in files:
        if str(Path.home()).encode() in path.read_bytes():
            raise ValueError('Bundle contains a private home path: '+path.relative_to(bundle).as_posix())
    (bundle/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(bundle).as_posix()}\n' for p in files))
    archive=args.output/f'lefony-sdk-{platform.system().lower()}-{platform.machine()}.tar.gz'
    with tarfile.open(archive,'w:gz') as output: output.add(bundle,arcname='lefony-sdk')
    print(archive)
    print(hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__=='__main__': main()
