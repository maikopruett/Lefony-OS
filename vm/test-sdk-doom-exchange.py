#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Import real Doom user assets over SDK USB, then launch and cold-export them.

Only synthetic workspaces are used. No fixture writes file data into NAND.
Transfer wall times describe this model/host run, not physical USB throughput.
"""
import argparse
import json
from pathlib import Path
import runpy
import shutil
import sys
import time
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, write_json
from cli import package
from device import DeviceError
from files_device import FileClient
from replay import Controls
from runner import exercise
from workspace import opened


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/sdk-file-exchange/doom')
    parser.add_argument('--inputs', type=Path, default=ROOT / 'build/sdk-1.0-upstream')
    parser.add_argument('--firmware', type=Path, default=ROOT / 'dist/lefony-os-prime-g2-vm-native.elf')
    args = parser.parse_args()
    output = args.output.resolve()
    # Preserve failed workspaces and reports for diagnosis, including interrupted
    # transfers. A repeat run explicitly selects a new output directory.
    if output.exists():
        raise ValueError('Existing evidence was preserved; choose a new --output directory')
    spec = json.loads((ROOT / 'sdk/ports/doom/assets.json').read_text())['files']['freedoom1.wad']
    asset = args.inputs.resolve() / 'freedoom1.wad'
    assert asset.stat().st_size == spec['bytes'] and digest(asset) == spec['sha256']
    output.mkdir(parents=True)
    # Bind both launches to the same executed candidate while other SDK work
    # continues. Retain inputs at the start, including on an interrupted run.
    firmware = output / 'firmware.elf'; shutil.copyfile(args.firmware.resolve(), firmware)
    qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'; qemu_hash = digest(qemu)
    sources = ['vm/test-sdk-doom-exchange.py', 'scripts/prepare_sdk_doom.py', 'sdk/ports/doom/platform.c',
               'sdk/tools/files_device.py', 'sdk/tools/runner.py', 'sdk/tools/emulator_usb.py',
               *['ports/lefony-prime-g2/ion/src/prime_g2/' + name for name in
                 ('app_file_exchange.cpp', 'app_file_session.cpp', 'app_file_store.cpp', 'app_management.cpp', 'usb_diagnostics.cpp')]]
    source_hashes = {}
    for name in sources:
        target = output / 'source' / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target); source_hashes[name] = digest(target)
    execution = {'sources':source_hashes, 'firmware_sha256':digest(firmware), 'qemu_sha256':qemu_hash}
    write_json(output / 'execution.json', execution)
    project = output / 'project'
    runpy.run_path(str(ROOT / 'scripts/prepare_sdk_doom.py'))['prepare'](
        project, args.inputs.resolve() / 'doomgeneric')
    artifact = package(project)
    cases = []
    started = time.monotonic()

    def record(name, **details):
        cases.append({'case': name, **details})
        write_json(output / 'progress.json', {'status': 'in_progress', 'cases': cases})
        print('PASS:', name, flush=True)

    def progress(name):
        last = -1
        begin = time.monotonic()
        def update(done, total):
            nonlocal last
            megabyte = done // (1024 * 1024)
            if megabyte != last or done == total:
                last = megabyte
                print(f'{name}: {done}/{total} bytes, {time.monotonic()-begin:.1f}s', flush=True)
        return update

    def capture(normal, name):
        path = output / (name + '.ppm')
        normal.execute('screendump', {'filename': str(path)})
        with Image.open(path) as image:
            picture = image.convert('RGB')
        picture.save(output / (name + '.png'))
        return picture

    def play(channel, normal, prefix):
        def value(index):
            return int(channel.command(f'APP DIAG {index}').split()[1])
        deadline = time.monotonic() + 180
        while True:
            assert not value(9), ('Doom fault', value(10))
            assert not value(15), ('Doom exited', value(21))
            picture = capture(normal, prefix + '-world')
            colors = len(picture.crop((0, 20, 320, 220)).getcolors(64001) or [])
            if colors > 128:
                break
            assert time.monotonic() < deadline, ('Doom loading deadline', colors)
            time.sleep(.2)
        normal.keys(['up'])
        time.sleep(1)
        normal.keys([])
        time.sleep(.3)
        moved = capture(normal, prefix + '-movement')
        assert moved.tobytes() != picture.tobytes()
        assert not value(9) and not value(15)
        record(prefix + '-launch-and-normal-input', colors=colors,
               qualification='asset consumption and changed frame; semantic gameplay is tested separately')

    for cold in (False, True):
        def controls(channel):
            normal = Controls(channel, output)
            client = channel.app_client
            files = FileClient(client)
            try:
                if cold:
                    play(channel, normal, 'cold')
                    normal.key('home')
                    client.wait()
                    begin = time.monotonic()
                    result = files.export_file('doom-proof', 'freedoom1.wad', output / 'cold-export.wad',
                                               progress=progress('cold WAD export'))
                    assert result['bytes'] == spec['bytes'] and result['sha256'] == spec['sha256']
                    assert digest(output / 'cold-export.wad') == spec['sha256']
                    record('cold-USB-export-exact-WAD', seconds=time.monotonic()-begin, report=result)
                    return

                normal.run({'steps': [{'program_exit': -1}]}, [])
                capture(normal, 'missing-wad')
                record('missing-WAD-visible-error')
                normal.key('home')
                client.wait()
                before = files.info('doom-proof')
                begin = time.monotonic()
                result = files.import_file('doom-proof', 'freedoom1.wad', asset,
                                           progress=progress('WAD import'))
                assert result['bytes'] == spec['bytes'] and result['sha256'] == spec['sha256']
                record('USB-import-exact-WAD', seconds=time.monotonic()-begin, report=result, before=before)
                info = files.info('doom-proof')
                assert info['file_bytes'] >= spec['bytes']
                entries = files.list('doom-proof')['entries']
                assert {'path': 'freedoom1.wad', 'kind': 'file', 'bytes': spec['bytes']} in entries

                # Reject quota overflow through the public transfer client and
                # firmware. The sparse local file costs no large test allocation.
                too_large = output / 'over-quota.bin'
                with too_large.open('wb') as stream:
                    stream.truncate(info['quota_remaining_bytes'] + 1)
                try:
                    files.import_file('doom-proof', 'over-quota.bin', too_large)
                except DeviceError as error:
                    assert 'quota exceeded' in str(error), error
                else:
                    raise AssertionError('Import exceeded the app quota')
                client.wait()
                assert files.info('doom-proof')['generation'] == info['generation']
                record('quota-refusal-preserves-root')

                # Cancel a real partial replacement, not an already-cancelled
                # prehash. The old 28 MB asset must still launch and cold-export.
                transferred = 0
                def partial(done, total):
                    nonlocal transferred
                    transferred = done
                try:
                    files.import_file('doom-proof', 'freedoom1.wad', asset, replace=True,
                                      cancelled=lambda: transferred >= 1024*1024, progress=partial)
                except DeviceError as error:
                    assert 'cancel' in str(error), error
                else:
                    raise AssertionError('Cancelled WAD replacement committed')
                client.wait()
                assert transferred >= 1024*1024
                assert files.info('doom-proof')['generation'] == info['generation']
                record('partial-WAD-replacement-cancelled', transferred_bytes=transferred)
                assert channel.command(f'APP OPEN {channel.installed_slot}') == 'OK'
                play(channel, normal, 'imported')
            finally:
                normal.close()
        try:
            assert digest(qemu) == qemu_hash, 'QEMU changed between launches'
            with opened(project, 'usb-assets') as (workspace, _):
                result = exercise(artifact, qemu, firmware, workspace=workspace, controls=controls)
        except BaseException as error:
            write_json(output / 'failure-report.json', {'schema':1, 'status':'failed', 'physical':'not_tested',
                'error':str(error), 'cases':cases, 'cold':cold, **execution})
            raise
        assert result['result'] == 1 and result['os_responsive'], result
        record('runtime', cold=cold, report=result)

    for name in ('app-debug.elf', 'app.elf', 'build.json', artifact.name):
        shutil.copyfile(project / 'build' / name, output / name)
    write_json(output / 'report.json', {'schema': 1, 'status': 'passed', 'physical': 'not_tested',
        'wall_seconds': time.monotonic()-started, 'timing': 'model/host only; not physical throughput',
        'cases': cases, 'wad': spec, **execution})


if __name__ == '__main__':
    main()
