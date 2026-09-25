#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure signed installed-app launches through KPP and Goodix in synthetic QEMU.

Includes package verification and Start callback; excludes installation and the
touch hold before release. Host timings are emulator comparisons, not physical
latency claims. Run baseline and candidate sequentially on the same host.
"""
import argparse
import json
from pathlib import Path
import shutil
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest
from cli import package
from replay import Controls, control_session
from runner import exercise
from workspace import opened


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve();output.mkdir(parents=True, exist_ok=False)
    qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    reports = []
    with tempfile.TemporaryDirectory(prefix='lefony-launch-') as temporary:
        project = Path(temporary) / 'counter'
        shutil.copytree(ROOT / 'sdk/examples/counter', project,
                        ignore=shutil.ignore_patterns('build', '.lefony', 'sdk.lock.json'))
        app = package(project)
        package_hash = digest(app)
        for boot in range(2):
            def controls(channel):
                with control_session(Controls(channel, output)) as normal:
                    for repeat in range(3):
                        for method in ('key', 'touch'):
                            normal.key('apps');channel.wait_for_storage(timeout=10)
                            # One installed app is the twelfth tile. EE selects
                            # it, but pressing EE again on that tile opens it.
                            if 'home_row=3 home_column=2' not in channel.command('STATE'):
                                normal.key('ee')
                            state = channel.command('STATE')
                            assert 'STATE app=0 home_row=3 home_column=2' in state, state
                            if method == 'touch':
                                assert channel.command('TOUCH FRAME 1 0 265 180') == 'OK'
                                time.sleep(.1)
                            start = time.monotonic()
                            if method == 'key': normal.key_edge('ok', True)
                            else: assert channel.command('TOUCH FRAME 0') == 'OK'
                            try:
                                while (channel.command('STATE').split(' home_row=')[0] != channel.native_state or
                                       channel.command('APP DIAG 6') != 'VALUE 1'):
                                    assert time.monotonic() - start < 10, 'launch timed out'
                                    time.sleep(.005)
                                elapsed = (time.monotonic() - start) * 1000
                            finally:
                                if method == 'key': normal.key_edge('ok', False)
                            time.sleep(.1)
                            assert channel.command('APP DIAG 9') == 'VALUE 0', 'app faulted'
                            name = f'boot-{boot}-{method}-{repeat}'
                            normal.run({'steps': [{'capture': name}]}, [])
                            reports.append({'boot': boot, 'method': method, 'repeat': repeat,
                                            'host_elapsed_ms': round(elapsed, 3)})
                            print(name, round(elapsed, 1), 'ms', flush=True)
            with opened(project, 'latency') as (media, _):
                result = exercise(app, qemu, args.firmware.resolve(), controls=controls, workspace=media)
            assert result['result'] == 1 and result['os_responsive'], result
    summary = {method: statistics.median(row['host_elapsed_ms'] for row in reports if row['method'] == method)
               for method in ('key', 'touch')}
    (output / 'report.json').write_text(json.dumps({'status': 'passed', 'physical': 'not_tested',
        'firmware_sha256': digest(args.firmware), 'qemu_sha256': digest(qemu),
        'unsigned_package_sha256': package_hash, 'median_ms': summary, 'runs': reports}, indent=2) + '\n')
    print('Median launch times:', summary, flush=True)


if __name__ == '__main__':
    main()
