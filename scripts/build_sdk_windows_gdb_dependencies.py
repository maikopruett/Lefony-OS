#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-build static Windows x86-64 GMP, MPFR and Expat for the pinned GDB.

Consumes the exact retained Ubuntu source materials used by the Linux SDK.
dpkg-source applies their downstream patches. No downloads, system installs or
Windows execution; keep the resulting source archives/notices with distribution.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

from build_sdk_gdb import build_directory, digest, host_configuration
from build_sdk_linux_toolchain import run_step

LOCK = Path(__file__).with_name('sdk-windows') / 'gdb-dependencies.json'


def retain_recipes(output):
    recipes = {'build_sdk_windows_gdb_dependencies.py': Path(__file__),
               'build_sdk_gdb.py': Path(__file__).with_name('build_sdk_gdb.py'),
               'build_sdk_linux_toolchain.py': Path(__file__).with_name('build_sdk_linux_toolchain.py'),
               'sdk-windows/gdb-dependencies.json': LOCK}
    for name, path in recipes.items():
        destination = output/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    return {name: digest(path) for name, path in recipes.items()}


def copy_sources(materials, output):
    pins = json.loads(LOCK.read_text())
    # Verify every input before beginning any extraction/build command.
    for component in pins.values():
        folder = materials / component['directory'] / 'archives'
        for name, checksum in component['archives'].items():
            path = folder / name
            if (not path.is_file() or path.is_symlink()
                    or path.stat().st_size > 64 * 1024**2 or digest(path) != checksum):
                raise ValueError('Windows GDB source differs from the pinned input: ' + name)
    for name, component in pins.items():
        folder = output / name
        folder.mkdir()
        for filename in component['archives']:
            shutil.copyfile(materials/component['directory']/'archives'/filename, folder/filename)
            if digest(folder/filename) != component['archives'][filename]:
                raise ValueError('Windows GDB source changed during copy: ' + filename)
    return pins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--materials', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work-parent', type=Path, required=True)
    parser.add_argument('--cross-prefix', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    if os.name == 'nt' or not 1 <= args.jobs <= 32:
        parser.error('Use a Unix build host and 1–32 jobs')
    parent = args.work_parent.resolve()
    if not parent.is_dir() or any(c.isspace() for c in str(parent)):
        parser.error('--work-parent must be an existing directory without whitespace')
    output = args.output.resolve()
    if output.exists():
        parser.error('Use a new output directory; existing candidates are retained')
    _, tools, _, _, _ = host_configuration(True, args.cross_prefix)
    for command in ('make', 'dpkg-source', 'autoreconf'):
        if not shutil.which(command):
            parser.error('Missing build tool: ' + command)
    output.mkdir(parents=True)
    recipes = retain_recipes(output)
    sources = output/'sources'; sources.mkdir()
    commands = []
    report = {'schema': 1, 'status': 'running', 'platform': 'Windows',
              'architecture': 'AMD64', 'execution_checked': False,
              'recipes': recipes,
              'build_host': {'platform': platform.system(), 'architecture': platform.machine()},
              'cross_tools': {key: {'path': path, 'sha256': digest(Path(path))}
                              for key, path in tools.items()}}
    def save():
        (output/'candidate.json').write_text(json.dumps(report, indent=2) + '\n')
    save()
    try:
        report['sources'] = copy_sources(args.materials.resolve(), sources)
        install = output/'install'
        with build_directory(output, parent) as scratch:
            # Fix embedded source paths while retaining the actual command paths.
            flags = '-O2 -g0 -ffile-prefix-map=' + str(scratch) + '=/lefony-windows-deps'
            env = {**os.environ, **tools, 'CFLAGS': flags, 'CXXFLAGS': flags, 'LC_ALL': 'C'}
            for key in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH', 'PKG_CONFIG_PATH'):
                env.pop(key, None)
            for name, component in report['sources'].items():
                source = scratch/name
                dsc = next((sources/name).glob('*.dsc'))
                def run(label, command, cwd=scratch):
                    run_step(name+'-'+label, command, cwd, env, output, commands, timeout=1800)
                run('extract', ['dpkg-source', '-x', dsc, source])
                configure_source = source/component['configure_directory']
                # GMP's Debian patch removes excluded documentation from
                # configure.ac; its shipped configure still references it.
                if name == 'gmp':
                    run('autoreconf', ['autoreconf', '-fiv'], configure_source)
                elif name == 'expat':
                    # Upstream also adjusts expat_config.h.in after autoheader.
                    run('buildconf', ['bash', './buildconf.sh', '-f'], configure_source)
                guess = next(configure_source.rglob('config.guess'))
                build = subprocess.check_output(['sh', guess], text=True, timeout=10).strip()
                work = scratch/(name+'-build'); work.mkdir()
                configure = [configure_source/'configure', '--build='+build,
                             '--host=x86_64-w64-mingw32', '--prefix='+str(install),
                             '--disable-shared', '--enable-static']
                if name == 'mpfr':
                    configure += ['--with-gmp='+str(install)]
                if name == 'expat':
                    configure += ['--without-xmlwf', '--without-examples', '--without-tests', '--without-docbook']
                run('configure', configure, work)
                run('build', ['make', '-j'+str(args.jobs)], work)
                run('install', ['make', 'install'], work)
                notices = sources/name/'notices'; notices.mkdir()
                for path in sorted(source.rglob('*')):
                    if path.is_file() and (path.name.startswith(('COPYING', 'LICENSE'))
                                           or path.relative_to(source).as_posix() == 'debian/copyright'):
                        target = notices/path.relative_to(source)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(path, target)
            for name in ('gmp', 'mpfr', 'expat'):
                if not (install/'lib'/('lib'+name+'.a')).is_file():
                    raise ValueError('Missing Windows static library: ' + name)
        report.update(status='passed',
                      files={p.relative_to(install).as_posix(): digest(p)
                             for p in sorted(install.rglob('*')) if p.is_file()})
        save()
    except BaseException as error:
        report.update(status='failed', error=str(error) or type(error).__name__); save(); raise
    print(json.dumps({'status': report['status'], 'files': len(report['files'])}))


if __name__ == '__main__':
    main()
