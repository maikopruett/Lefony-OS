#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""ARM preview, inspection and USB in private paths with spaces and punctuation."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, write_json
from preview import once
import runner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    original = runner.session_directory
    cases = []
    with tempfile.TemporaryDirectory(prefix='sdk-host-paths-') as folder:
        project = Path(folder) / 'App é, \' " $HOME `false` ; %PATH%'
        shutil.copytree(ROOT / 'sdk/examples/ui-gallery', project,
                        ignore=shutil.ignore_patterns('build', '.lefony', 'sdk.lock.json'))
        try:
            for unusual in (False, True):
                if unusual:
                    runner.session_directory = lambda: tempfile.TemporaryDirectory(prefix='lf é,\'" $;', dir='/tmp')
                value = once(project, qemu, args.firmware.resolve(), scenario=Path('tests/startup.json'), fresh_data=True)
                assert value['status'] == 'ready', value.get('error')
                assert value['layout']['nodes'] and not value['layout']['overflow']
                target = output / ('punctuation' if unusual else 'ordinary')
                shutil.copytree(project / 'build/preview', target)
                cases.append({'case': target.name, 'frame_sha256': digest(target / 'frame.png'), 'preview': value})
        finally:
            runner.session_directory = original
    assert cases[0]['frame_sha256'] == cases[1]['frame_sha256']
    assert cases[0]['preview']['layout']['nodes'] == cases[1]['preview']['layout']['nodes']
    write_json(output / 'report.json', {'schema': 1, 'status': 'passed', 'cases': cases,
        'host': sys.platform, 'native_windows': 'not_tested', 'physical': 'not_tested',
        'firmware_sha256': digest(args.firmware), 'qemu_sha256': digest(qemu),
        'sources': {name: digest(ROOT / name) for name in ('sdk/tools/gdb_transport.py',
            'sdk/tools/local_transport.py', 'sdk/tools/preview.py', 'sdk/tools/runner.py',
            'vm/test-sdk-host-paths.py')}})
    print('PASS: ARM input/layout/USB in punctuation paths; identical pixels and nodes', flush=True)


if __name__ == '__main__':
    main()
