#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real main-entry debugging, exit failures and raw/installed callback relaunch."""
import concurrent.futures
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, write_json
from cli import package
from replay import Controls, test_project
from runner import exercise
from workspace import opened


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/sdk-main/developer')
    parser.add_argument('--firmware', type=Path, default=ROOT / 'dist/lefony-os-prime-g2-vm-native.elf')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    firmware = args.firmware.resolve()
    gdb = shutil.which('arm-none-eabi-gdb')
    assert gdb, 'real GDB is required for this qualification'
    cases = []
    with tempfile.TemporaryDirectory(prefix='sdk-main-developer-') as temp:
        project = Path(temp) / 'C project é'
        subprocess.run([sys.executable, str(ROOT / 'sdk/tools/cli.py'), 'new', str(project),
                        '--template', 'c-main'], check=True, timeout=30, stdout=subprocess.DEVNULL)
        app = package(project, 'debug')
        script = project / 'build/debug.gdb'
        def debugger():
            end = time.monotonic() + 60
            while not script.exists():
                assert time.monotonic() < end, 'debug setup deadline'
                time.sleep(.025)
            result = subprocess.run([gdb, '--nx', '--batch', '-x', str(script), '-ex', 'bt',
                                     '-ex', 'info args', '-ex', 'stepi', '-ex', 'info registers pc',
                                     '-ex', 'detach'], capture_output=True, text=True, timeout=60)
            log = result.stdout + result.stderr
            (output / 'gdb-main.log').write_text(log)
            assert result.returncode == 0, log
            assert 'main (' in log and 'src/main.c' in log and 'argc = 2' in log and 'pc ' in log, log
            assert 'corrupt stack' not in log, log
        def completed(channel):
            normal = Controls(channel, output)
            try:
                normal.run({'steps': [{'program_exit': 0}]}, [])
            finally:
                normal.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(debugger)
            result = exercise(app, qemu, firmware, debug_project=project, debug_timeout=65, controls=completed)
            future.result()
        assert result['program']['exit_status'] == 0 and result['os_responsive'], result
        cases.append({'case': 'main-source-breakpoint-arguments-step', 'runtime': result})
        print('PASS: external main breakpoint before one-shot entry, arguments and stepping', flush=True)

        (project / 'src/main.c').write_text('int main(void) { return 7; }\n')
        app = package(project)
        write_json(project / 'tests/exit.json', {'schema': 1, 'name': 'exit-status',
                   'steps': [{'program_exit': 0}]})
        assert test_project(project, app, qemu, firmware, 'tests/exit.json') == 1
        failed = json.loads((project / 'build/run.json').read_text())
        assert 'exited with 7, expected 0' in failed['cases'][0]['error'], failed
        cases.append({'case': 'nonzero-exit-rejected', 'report': failed})
        write_json(project / 'tests/exit.json', {'schema': 1, 'name': 'exit-status',
                   'steps': [{'program_exit': 7}, {'relaunch': True}, {'program_exit': 7}]})
        assert test_project(project, app, qemu, firmware, 'tests/exit.json') == 0
        cases.append({'case': 'explicit-failed-exit-and-relaunch',
                      'report': json.loads((project / 'build/run.json').read_text())})
        print('PASS: nonzero exit is rejected unless asserted; failed main relaunches', flush=True)

        callback = Path(temp) / 'Callback'
        subprocess.run([sys.executable, str(ROOT / 'sdk/tools/cli.py'), 'new', str(callback)],
                       check=True, timeout=30, stdout=subprocess.DEVNULL)
        (callback / 'src/main.cpp').write_text('''#include <lefony/app.h>
static unsigned touched;
extern "C" void lefony_event(Lefony::Event event,uint32_t,uint32_t) {
  if(event==Lefony::Event::Key) touched=1;
  if(event==Lefony::Event::Start || event==Lefony::Event::Key)
    Lefony::fill({0,0,320,240,touched?Lefony::White:Lefony::Green});
}
''')
        write_json(callback / 'tests/relaunch.json', {'schema': 1, 'name': 'callback-relaunch',
            'steps': [{'capture': 'first'}, {'key': 'ok'}, {'capture': 'changed'},
                      {'different': ['first', 'changed']}, {'relaunch': True},
                      {'capture': 'new'}, {'same': ['first', 'new']}]})
        app = package(callback)
        for installed in (False, True):
            if installed:
                with opened(callback, 'installed') as (workspace, _):
                    assert test_project(callback, app, qemu, firmware, 'tests/relaunch.json', workspace=workspace) == 0
            else:
                assert test_project(callback, app, qemu, firmware, 'tests/relaunch.json') == 0
            cases.append({'case': 'installed-callback-relaunch' if installed else 'raw-callback-relaunch',
                          'report': json.loads((callback / 'build/run.json').read_text())})
        print('PASS: callback relaunch resets app globals from active raw and installed previews', flush=True)
    write_json(output / 'report.json', {'schema': 1, 'status': 'passed', 'physical': 'not_tested', 'cases': cases,
        'sources': {name: digest(ROOT / name) for name in ('sdk/tools/runner.py', 'sdk/tools/replay.py',
                    'sdk/tools/diagnostics.py', 'sdk/tools/build.py', 'vm/test-sdk-main-developer.py')}})


if __name__ == '__main__':
    main()
