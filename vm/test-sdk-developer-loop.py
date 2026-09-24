#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""External-project, real ARM debugger and cold-workspace acceptance."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from cli import package, SDK
from diagnostics import symbolize
from runner import exercise
from replay import Controls,test_project
from workspace import opened, manage, restore
from build import write_json


def main():
    qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    firmware = ROOT / 'dist/lefony-os-prime-g2-vm-native.elf'
    evidence = ROOT / 'build/sdk-developer-loop'
    evidence.mkdir(exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix='lefony project é ') as folder:
        project = Path(folder) / 'app with spaces'
        subprocess.run([sys.executable, str(SDK / 'tools/cli.py'), 'new', str(project), '--template', 'pocket-lab'], check=True)
        path = package(project)
        # Explicit normal keypad input stores 123. Inspect both cold runs at the
        # same graph pixel; app status text intentionally changes after restore.
        def controls(round):
            def run(channel):
                d = Controls(channel, evidence)
                try:
                    if round == 0:
                        d.key('one');d.key('two');d.key('three');d.key('ok')
                    time.sleep(.3)
                    d.execute('screendump', {'filename': str(evidence / f'cold-{round}.ppm')})
                    from PIL import Image
                    with Image.open(evidence / f'cold-{round}.ppm') as frame:
                        assert frame.convert('RGB').getpixel((20, 150)) == (33,166,66), '123 sample was not retained'
                finally:
                    d.close()
            return run
        for round in range(2):
            with opened(project, 'persistent') as (directory, _):
                result = exercise(path, qemu, firmware, controls=controls(round), workspace=directory)
                assert result['result'] == 1 and result['os_responsive']
                results.append(result)
        exported = Path(folder) / 'data.zip'
        manage(project, 'export', 'persistent', exported)
        restore(project, 'restored', exported)
        with opened(project, 'restored') as (directory, _):
            result = exercise(path, qemu, firmware, controls=controls(2), workspace=directory)
            assert result['result'] == 1
            results.append(result)
        print('PASS: external project, normal key input, cold restart, workspace export/restore', flush=True)

        # Actual GDB, with a source breakpoint and instruction step. No test
        # UART event bypass is used for user-visible app functionality above.
        gdb = shutil.which('arm-none-eabi-gdb')
        if not gdb:
            raise RuntimeError('arm-none-eabi-gdb is required for debugger qualification')
        path = package(project, 'debug')
        script = project / 'build/debug.gdb'
        def debugger():
            deadline = time.monotonic() + 40
            while not script.exists():
                if time.monotonic() > deadline:
                    raise RuntimeError('SDK did not prepare the GDB session')
                time.sleep(.05)
            run = subprocess.run([gdb, '--nx', '--batch', '-x', str(script), '-ex', 'bt', '-ex', 'info line',
                                  '-ex', 'stepi', '-ex', 'info registers pc', '-ex', 'detach'],
                                 capture_output=True, text=True, timeout=40)
            (evidence / 'gdb.log').write_text(run.stdout + run.stderr)
            assert run.returncode == 0, run.stdout + run.stderr
            assert 'lefony_event' in run.stdout and 'src/main.cpp' in run.stdout and 'pc ' in run.stdout
            assert 'corrupt stack' not in run.stdout
            return {'case': 'gdb-source-breakpoint-step', 'status': 'passed',
                    'log_sha256': hashlib.sha256(run.stdout.encode()).hexdigest()}
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(debugger)
            result = exercise(path, qemu, firmware, debug_project=project, debug_timeout=50)
            assert result['result'] == 1 and result['validation'] == 'debug-session'
            results.append(future.result())
        print('PASS: real GDB source breakpoint, stack, line information, registers and stepping', flush=True)

        # An app fault produces a source-located PC with matching symbols.
        (project / 'src/main.cpp').write_text('#include <lefony/app.h>\nextern "C" void lefony_event(Lefony::Event,uint32_t,uint32_t) { asm volatile("udf #0"); }\n')
        path = package(project, 'debug')
        result = exercise(path, qemu, firmware)
        assert result['result'] == -11 and result['fault']['pc']
        symbols = symbolize(project, path, result['fault']['pc'])
        assert any('src/main.cpp:2' in item for item in symbols['symbol']), symbols
        results.append({'case': 'symbolized-fault', 'status': 'passed', 'runtime': result, 'symbols': symbols})
        print('PASS: undefined instruction reports the exact source line and OS recovers', flush=True)
        (project / 'src/main.cpp').write_text('#include <lefony/app.h>\nextern "C" void lefony_event(Lefony::Event event,uint32_t,uint32_t) { if(event==Lefony::Event::Key) asm volatile("udf #0"); }\n')
        write_json(project / 'tests/fault.json', {'schema': 1, 'name': 'fault-report',
                   'steps': [{'key': 'ok'}, {'key': 'back'}, {'relaunch': True}]})
        path = package(project)
        assert test_project(project, path, qemu, firmware, 'tests/fault.json') == 1
        failed = json.loads((project / 'build/run.json').read_text())
        assert failed['summary']['failed'] == 1 and failed['cases'][0]['steps'][0]['status'] == 'failed'
        assert len(failed['cases'][0]['steps']) == 1, 'replay continued after a fault'
        results.append({'case': 'fault-report-not-masked-by-relaunch', 'status': 'passed'})
        print('PASS: replay reports a fault as failure and does not hide it by relaunching', flush=True)
    write_json(evidence / 'report.json', {'schema': 1, 'validation': 'developer-local',
               'physical': 'not_tested', 'status': 'passed', 'cases': results})


if __name__ == '__main__':
    main()
