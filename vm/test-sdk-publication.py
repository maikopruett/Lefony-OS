#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real CLI source snapshot/build/ARM test/media preview, optionally from a relocated SDK."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, write_json
from store_snapshot import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, default=ROOT / 'sdk')
    parser.add_argument('--qemu', type=Path, default=ROOT / 'build/qemu-prime-g2/qemu-system-arm')
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sdk, firmware, qemu = args.sdk.resolve(), args.firmware.resolve(), args.qemu.resolve()
    # macOS sandbox denies IP network access while retaining QEMU's local Unix
    # sockets. This is evidence of offline behavior, not a simulated HTTP test.
    prefix = ['/usr/bin/sandbox-exec', '-p', '(version 1)(allow default)(deny network-outbound (remote ip "*:*"))'] if sys.platform == 'darwin' else []
    cli = [*prefix, sys.executable, str(sdk / 'tools/cli.py')]
    environment = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'LEFONY_SDK_NEWLIB')}
    project = output / 'External publication é'
    commands = []
    def run(arguments, expected=0):
        command = [*cli, *arguments]
        log_path = output / f'command-{len(commands) + 1}.log'
        with log_path.open('w') as log:
            completed = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=240)
        commands.append({'args': arguments, 'exit_code': completed.returncode, 'log': log_path.name})
        assert completed.returncode == expected, log_path.read_text()[-8000:]
    run(['new', str(project)])
    assert (project / 'store/screenshots/README.md').is_file()
    assert '/.lefony/' in (project / '.gitignore').read_text()
    (project / 'store/listing.json').write_text('{"schema":1,"publish_source":true}')
    (project / 'store/description.md').write_text('Actual ARM counter input. <script>Displayed literally.</script>')
    runtime = ['--qemu', str(qemu), '--firmware', str(firmware)]
    run(['--project', str(project), 'publish', '--dry-run', *runtime], 1)
    assert not (project / '.lefony/publish').exists()
    # Obtain a real app frame for the listing fixture, then let publication
    # independently rebuild and exercise its copied source and exact package.
    run(['--project', str(project), 'test', *runtime])
    from PIL import Image
    with Image.open(project / 'build/tests/counter-input/initial.ppm') as frame:
        frame.convert('RGB').save(project / 'store/screenshots/01-main.png')
        frame.crop((0, 0, 64, 64)).convert('RGB').save(project / 'store/icon.png')
    (project / 'tests/nested').mkdir()
    (project / 'tests/nested/second.json').write_text(json.dumps({'schema':1,'name':'nested-publication',
        'steps':[{'capture':'before'},{'key':'ok'},{'capture':'after'},{'different':['before','after']}]}))
    for name in ('.git/config', '.env', 'build/private-capture.bin', '.lefony/private-credential.json'):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('EXCLUDED-PUBLICATION-SECRET')
    results = []
    for _ in range(2):
        run(['--project', str(project), 'publish', '--dry-run', *runtime])
    for attempt in sorted((project / '.lefony/publish').iterdir()):
        submission = verify(attempt)
        report = json.loads((attempt / 'upload/report.json').read_text())
        assert report['summary'] == {'passed':2,'failed':0,'skipped':0}
        assert report['package_sha256'] == digest(attempt / 'upload/package.lfapp')
        for file in submission['files']:
            data = (attempt / 'upload' / file['path']).read_bytes()
            assert b'EXCLUDED-PUBLICATION-SECRET' not in data and str(project).encode() not in data
        results.append({'attempt': attempt.name, 'submission_sha256': digest(attempt / 'submission.json'),
                        'package_sha256': report['package_sha256'], 'source_sha256': report['source_sha256'], 'summary': report['summary']})
    assert len(results) == 2 and results[0]['submission_sha256'] == results[1]['submission_sha256']
    # Keep the fixed submission intact while editing/deleting original inputs.
    (project / 'store/description.md').write_text('Next attempt only')
    (project / 'src/main.cpp').write_text('// deliberately unfinished next edit\n')
    for attempt in (project / '.lefony/publish').iterdir():
        assert verify(attempt)['listing']['description'].startswith('Actual ARM counter')
    write_json(output / 'report.json', {'schema':1,'status':'passed','network_outbound':'denied' if prefix else 'not_enforced',
        'firmware_sha256':digest(firmware),'qemu_sha256':digest(qemu),'sdk_sha256':json.loads((project/'sdk.lock.json').read_text())['sdk_sha256'],
        'host':sys.platform,'physical':'not_tested','publication':'not_performed','commands':commands,'attempts':results})
    print('PASS: offline real CLI, deterministic snapshots, exact ARM package tests, private-file exclusion and retained attempts', flush=True)


if __name__ == '__main__':
    main()
