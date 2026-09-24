#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""External ordinary C++ main: initializers, arguments, files, cleanup and cold boot."""
import json
import argparse
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, write_json
from cli import package
from runner import exercise
from replay import Controls
from workspace import opened


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path, default=ROOT / 'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/sdk-main/arm')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cases = []
    for mode in ('clean', 'failure'):
        with tempfile.TemporaryDirectory(prefix='lefony-main-') as temp:
            project = Path(temp)
            (project / 'src').mkdir()
            shutil.copyfile(ROOT / 'tests/native/sdk_main.cpp', project / 'src/main.cpp')
            metadata = json.loads((ROOT / 'sdk/examples/c-main/app.json').read_text())
            metadata.update(id='main-proof', name='Conventional main')
            write_json(project / 'app.json', metadata)
            write_json(project / 'project.json', {'schema':2, 'runtime':'foreground-newlib-1',
                'sources':['src/main.cpp'], 'arguments':[mode, 'quoted "text"', 'back\\slash']})
            app = package(project)
            retained = output / mode
            retained.mkdir(exist_ok=True)
            for name in ('app-debug.elf', 'app.elf', 'app.map', app.name, 'build.json'):
                shutil.copyfile(project / 'build' / name, retained / name)
            for name in ('app.json', 'project.json', 'sdk.lock.json'):
                shutil.copyfile(project / name, retained / name)
            helper = project / 'fixture'
            helper.mkdir()
            reader = runpy.run_path(str(ROOT / 'vm/test-sdk-documents.py'))['fixture'](helper)
            for cold in (False, True):
                status_evidence = {}
                def controls(channel):
                    normal = Controls(channel, retained)
                    try:
                        deadline = time.monotonic() + 60
                        while not int(channel.command('APP DIAG 15').split()[1]):
                            fault = int(channel.command('APP DIAG 9').split()[1])
                            if fault:
                                pc = int(channel.command('APP DIAG 10').split()[1])
                                raise AssertionError(subprocess.check_output(['arm-none-eabi-addr2line', '-f',
                                    '-e', str(project / 'build/app-debug.elf'), hex(pc)], text=True))
                            assert time.monotonic() < deadline, 'main/cleanup exceeded deadline'
                            time.sleep(.025)
                        assert int(channel.command('APP DIAG 9').split()[1]) == 0
                        status = int(channel.command('APP DIAG 21').split()[1])
                        assert status == (7 if mode == 'failure' else 0)
                        status_evidence['program_exit_status'] = status
                        normal.key('home')
                    finally:
                        normal.close()
                with opened(project, 'main') as (workspace, _):
                    result = exercise(app, ROOT / 'build/qemu-prime-g2/qemu-system-arm',
                        args.firmware.resolve(), workspace=workspace, controls=controls)
                    destination = retained / ('cold-order.bin' if cold else 'order.bin')
                    subprocess.run([reader, 'export-file', workspace / 'nand.overlay', 'main-proof',
                        'order', destination], check=True, stdout=subprocess.DEVNULL, timeout=30)
                    assert destination.read_bytes() == b'MAD', 'main/atexit/destructor order or file durability failed'
                assert result['result'] == 1 and result['os_responsive'], result
                cases.append({'mode':mode, 'cold':cold, 'runtime':result, 'cleanup_order':'MAD',
                    'order_sha256':digest(destination), **status_evidence})
                print('PASS:', mode, 'cold' if cold else 'first', flush=True)
    write_json(output / 'report.json', {'schema':1, 'status':'passed', 'physical':'not_tested',
        'firmware_sha256':digest(args.firmware),
        'profile':'foreground-newlib-1 through the ordinary SDK builder', 'cases':cases,
        'sources':{p:digest(ROOT / p) for p in ['vm/test-sdk-main.py','tests/native/sdk_main.cpp',
          'sdk/lib/newlib/start.c','sdk/lib/newlib/os.c','sdk/lib/newlib/files.c','sdk/cmake/foreground.ld',
          'sdk/tools/build.py','sdk/tools/project.py','sdk/tools/runtime.py']}})


if __name__ == '__main__':
    main()
