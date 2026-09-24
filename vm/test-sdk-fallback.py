#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run new public UI helpers against an explicitly selected older VM reader."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from cli import package
from replay import test_project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-firmware', type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / 'build/sdk-ui-fallback'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sdk-fallback-') as folder:
        project = Path(folder) / 'forms'
        shutil.copytree(ROOT / 'sdk/examples/forms-tables', project,
                        ignore=shutil.ignore_patterns('build', '.lefony', 'sdk.lock.json', 'compile_commands.json', 'tests'))
        (project / 'tests').mkdir()
        steps = [{'key': 'ok'}, {'touch': [[0,230,160]]}, {'touch': []}, {'capture': 'table'},
                 {'touch': [[0,70,70]]}, {'touch': []}, {'capture': 'modal'},
                 {'different': ['table','modal']}, {'touch': [[0,230,154]]}, {'touch': []},
                 {'capture': 'restored'}, {'same': ['table','restored']},
                 {'touch': [[0,70,220]]}, {'touch': []}, {'capture': 'form'}, {'key': 'back'}]
        (project / 'tests/fallback.json').write_text(json.dumps({'schema': 1, 'name': 'fallback', 'steps': steps}))
        # Probe returns from these exact old services are checked inside a real
        # protected app, not inferred solely from the filename/version label.
        source = project / 'src/main.cpp'
        content = source.read_text().replace('void start() {', '''void start() {
  Lefony::InputSnapshot snapshot;
  if(Lefony::readInput(snapshot)!=-3 || Lefony::navigationDepth(0)!=-3) asm volatile("udf #0");''')
        source.write_text(content)
        result = test_project(project, package(project), ROOT / 'build/qemu-prime-g2/qemu-system-arm', args.old_firmware.resolve())
        (output / 'report.json').write_bytes((project / 'build/run.json').read_bytes())
        assert result == 0
        for name in ('table','modal','restored','form'):
            (output / (name+'.ppm')).write_bytes((project / 'build/tests/fallback' / (name+'.ppm')).read_bytes())
        print('PASS: new UI app handles unsupported input/navigation services and works through base key/Goodix plus software Back/Cancel')


if __name__ == '__main__':
    main()
