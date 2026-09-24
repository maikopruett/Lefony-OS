#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Measure first pixels from signed Doom on cold synthetic boots, without GDB.

Supply an existing synthetic workspace with the pinned WAD. It is cloned;
physical USB is never opened. Timing is emulator evidence, not physical speed.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'sdk/tools'), str(ROOT / 'scripts')]
from build import digest
from prime_g2_app_runtime import decode
from prime_g2_storage_profile import decode as storage_decode, difference
from replay import Controls, control_session
from runner import exercise
from workspace import opened


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('seed-project', 'package', 'firmware', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--public-key', type=Path, action='append', required=True)
    args = parser.parse_args()
    out = args.output.resolve();out.mkdir(parents=True, exist_ok=False)
    with opened(args.seed_project.resolve(), 'game') as (seed, _):
        media = out / '.lefony/workspaces/game';media.mkdir(parents=True)
        for name in ('workspace.json', 'nand.overlay'):
            shutil.copyfile(seed / name, media / name)
    reports = []
    for run in range(2):
        folder = out / str(run);folder.mkdir()
        measured = {}
        def controls(channel):
            def read(request, length):
                return channel.usb_host.control_in(0xc0, request, 0, 0, length)
            with control_session(Controls(channel, folder)) as normal:
                start = time.monotonic();before = storage_decode(read(0x56, 392))
                while time.monotonic() - start < 180:
                    report = decode(read(0x57, 64))
                    assert not report['fault'] and not report['flags'] & 8, report
                    if report['pixel_frames'] >= 3:
                        break
                    if not (folder / 'loading.png').exists():
                        path = folder / 'loading.ppm'
                        normal.execute('screendump', {'filename': str(path)})
                        with Image.open(path) as im:im.save(folder / 'loading.png')
                    time.sleep(.05)
                else:
                    raise AssertionError('No first frame before the bounded startup deadline')
                after = storage_decode(read(0x56, 392))
                assert report['flags'] & 7 == 7 and report['startup_ms'] > 0, report
                measured.update(runtime=report, storage=difference(before, after),
                                scope='Foreground entry to first public pixel frame; excludes package launch verification')
                time.sleep(1)
                path = folder / 'game.ppm';normal.execute('screendump', {'filename': str(path)})
                with Image.open(path) as im:
                    assert len(im.getcolors(76801) or []) > 128
                    im.save(folder / 'game.png')
                normal.key('home');assert channel.command('PING') == 'PONG'
        with opened(out, 'game') as (media, _):
            result = exercise(args.package.resolve(), ROOT / 'build/qemu-prime-g2/qemu-system-arm',
                              args.firmware.resolve(), controls=controls, workspace=media,
                              public_keys=args.public_key)
        assert result['result'] == 1 and result['os_responsive'], result
        reports.append({'measured': measured, 'result': result})
        print('Cold startup:', measured['runtime']['startup_ms'], 'ms', flush=True)
    (out / 'report.json').write_text(json.dumps({'status': 'passed', 'physical': 'not_tested',
        'firmware_sha256': digest(args.firmware), 'package_sha256': digest(args.package),
        'runs': reports}, indent=2) + '\n')


if __name__ == '__main__':
    main()
