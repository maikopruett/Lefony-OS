#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Create a deterministic standalone SDK source kit from an explicit allowlist."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import tarfile
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))


def package(output, newlib=None):
    files={}
    for directory in ('tools','include','lib','cmake','templates','examples','publisher','contracts','assets'):
        for path in sorted((ROOT/'sdk'/directory).rglob('*')):
            if not path.is_file() or path.is_symlink() or path.name in ('compile_commands.json','sdk.lock.json') or any(part in ('build','__pycache__','.lefony') for part in path.relative_to(ROOT/'sdk').parts):
                continue
            example_asset = directory == 'examples' and 'assets' in path.relative_to(ROOT/'sdk/examples').parts and path.suffix in ('.png','.rgb565','.bin')
            skin_asset = directory == 'assets' and path.relative_to(ROOT/'sdk/assets').parts[0] == 'prime' and path.suffix in ('.png', '.primeskin')
            if not (example_asset or skin_asset) and path.suffix not in ('.py','.h','.s','.ld','.c','.cpp','.json','.md','.service','.timer','.txt','.cmake') and path.name not in ('lefony-sdk','Dockerfile','Dockerfile.toolchain'):
                continue
            files['sdk/'+path.relative_to(ROOT/'sdk').as_posix()]=(path.read_bytes(),0o755 if path.name=='lefony-sdk' else 0o644)
    for name in ('.dockerignore','scripts/package_native_sdk.py','scripts/vendor_sdk_math.py','LICENSE.md','THIRD_PARTY_NOTICES.md','sdk/README.md','sdk/API.md','sdk/FILE-EXCHANGE.md','docs/NATIVE-APP-FILE-EXCHANGE.md','docs/EMULATOR-SKINS.md','sdk/TESTING.md','sdk/contract.json','sdk/publisher/README.md','docs/NATIVE-APP-SDK-STATUS.md','docs/NATIVE-APP-SDK-PLAN.md','docs/NATIVE-APP-SDK-MATURITY-PLAN.md','docs/NATIVE-APP-CAPABILITIES.md','docs/NATIVE-APP-PACKAGE-FORMAT.md','docs/NATIVE-APP-SETUP.md','docs/NATIVE-APP-SETUP-LEGACY.md','docs/NATIVE-APP-STORAGE.md','sdk/requirements-desktop.txt','sdk/DESKTOP-README.md',
                 'docs/NATIVE-APP-MATURITY-EVIDENCE.md','docs/NATIVE-APP-ARCHITECTURE.md','docs/NATIVE-APP-CONTRACT-EXTENSIONS.md',
                 'tests/fixtures/prime_g2_emulator_update_private.pem','tests/fixtures/prime_g2_emulator_update_public.pem'):
        files[name]=((ROOT/name).read_bytes(),0o644)
    for path in sorted((ROOT/'LICENSES').glob('*.txt')):
        files['LICENSES/'+path.name]=(path.read_bytes(),0o644)
    for name in ('sdk/HOSTS.md','sdk/C-RUNTIME.md','sdk/C-LIBRARY.md','sdk/C-DEVELOPMENT.md','sdk/FOREGROUND.md','sdk/FILES.md','sdk/DATA.md','sdk/DATA-RECOVERY.md','sdk/INPUT.md','sdk/UI.md','sdk/SYSTEM.md','sdk/CHANNEL.md','sdk/ACCOUNTS.md','sdk/PUBLISHING.md','sdk/KEYS.md','docs/NATIVE-APP-DEVELOPER-KEYS.md',
                 'docs/NATIVE-APP-ARCHIVES.md','docs/NATIVE-APP-ROOT-RECOVERY.md','sdk/ARCHIVES.md','docs/NATIVE-APP-C-LIBRARY-COMPARISON.md',
                 'sdk/PROJECTS.md','scripts/build_sdk_newlib.py','scripts/build_sdk_gdb.py','scripts/native_desktop_windows.py','scripts/native_desktop_linux.py',
                 'scripts/build_sdk_linux_toolchain.py','scripts/build_sdk_linux_cross.py','scripts/build_sdk_linux_qemu.py',
                 'scripts/build_sdk_windows_gdb_dependencies.py','scripts/sdk-windows/gdb-dependencies.json','scripts/sdk-windows/Dockerfile.gdb-cross',
                 'scripts/build_sdk_windows_compiler_dependencies.py','scripts/sdk-windows/compiler-dependencies.json',
                 'scripts/build_sdk_windows_libusb.py',
                 'scripts/build_sdk_windows_openssl.py','scripts/sdk-windows/openssl-mingw-avx512.patch',
                 'scripts/sdk-windows/openssl-portable-getenv.patch','scripts/native_desktop_openssl.py',
                 'scripts/package_native_desktop.py','scripts/package_native_desktop_sources.py','scripts/build_emulator_window.py','scripts/emulator_window_sources.py',
                 'sdk/requirements-emulator.txt','docs/EMULATOR-DESKTOP.md','vm/test-emulator-window.py',
                 'docs/images/emulator-sdk.png',
                 'scripts/windows_python_sources.py','scripts/windows_python_sources.json',
                 'scripts/windows_cpython_sources.py','scripts/windows_cpython_sources.json',
                 'scripts/collect_native_windows_sources.py','scripts/native_desktop_windows_sources.py','scripts/native_desktop_project.py','scripts/native_desktop_firmware.py',
                 'scripts/sdk-windows/native-components.json',
                 'scripts/sdk-windows/requirements-python-x86_64.txt',
                 'scripts/sdk-windows/README.md',
                 'scripts/build_sdk_windows_qemu_dependencies.py','scripts/build_sdk_windows_qemu.py',
                 'scripts/sdk-windows/qemu-dependencies.json','scripts/sdk-windows/Dockerfile.qemu-cross',
                 'scripts/sdk-linux/Dockerfile','scripts/sdk-linux/Dockerfile.cross','scripts/sdk-linux/Dockerfile.gdb-cross','scripts/sdk-linux/Dockerfile.qemu-cross','scripts/sdk-linux/Dockerfile.desktop',
                 'scripts/sdk-linux/requirements-python-x86_64.txt',
                 'scripts/collect_native_linux_sources.py','scripts/sdk-linux/ubuntu-noble.sources',
                 'scripts/collect_native_linux_python_sources.py','scripts/collect_native_desktop_sources.py',
                 'scripts/linux_wheel_native_sources.py','scripts/linux_wheel_native_sources.json','scripts/native_desktop_linux_sources.py',
                 'scripts/pillow_native_sources.py','scripts/pillow_native_sources.json','scripts/prepare_sdk_minigzip.py',
                 'sdk/ports/minigzip/source.json','sdk/ports/minigzip/README.md','sdk/ports/minigzip/AGENTS.md',
                 'docs/NATIVE-APP-SDK-1.0-PLAN.md','docs/NATIVE-APP-SDK-1.0-PROGRESS.md','docs/NATIVE-APP-LINKED-LICENSE-REVIEW.md',
                 'scripts/fetch_sdk_doom.py','scripts/prepare_sdk_doom.py','scripts/probe_sdk_doom.py',
                 'sdk/ports/doom/source.json','sdk/ports/doom/assets.json',
                 'sdk/ports/doom/platform.c','sdk/ports/doom/output.c','sdk/ports/doom/output.h','sdk/ports/doom/README.md',
                 'sdk/ports/doom/THIRD_PARTY_NOTICES.md'):
        files[name]=((ROOT/name).read_bytes(),0o644)
    if newlib:
        from runtime import bundle_files
        for name,path in bundle_files(ROOT/'sdk',newlib).items():
            files['sdk/runtime/newlib/'+name]=(path.read_bytes(),0o644)
    files['sdk/trust/app-signing.pem']=((ROOT/'ports/lefony-prime-g2/app-signing.pub').read_bytes(),0o644)
    files['SHA256SUMS']=(''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name,(data,_) in sorted(files.items())).encode(),0o644)
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('wb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as compressed, tarfile.open(fileobj=compressed,mode='w') as archive:
        for name,(data,mode) in sorted(files.items()):
            item=tarfile.TarInfo('lefony-native-sdk/'+name); item.size=len(data); item.mode=mode
            archive.addfile(item,io.BytesIO(data))
    print(output)
    print(hashlib.sha256(output.read_bytes()).hexdigest())

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--newlib',type=Path,help='Include the verified ARM sysroot, notices and exact source archive')
    args=parser.parse_args()
    package(args.output,args.newlib)
