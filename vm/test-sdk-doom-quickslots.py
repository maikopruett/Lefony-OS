#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Normal Doom quick-save/load, cancellation and cold named-slot recovery.

Only copied synthetic media is used. GDB observes matching symbols at hardware
breakpoints; it never calls guest functions or writes game/storage variables.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, identity, write_json
from cli import package
from files_device import FileClient
from replay import Controls
import runner
from workspace import opened
from sdk_doom_probe import DoomProbe

spec = importlib.util.spec_from_file_location('doom_reset', Path(__file__).with_name('test-sdk-doom-reset.py'))
reset = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset)
prior = reset.prior
APP = 'doom-proof'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('seed-project', 'output', 'firmware', 'firmware-debug'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True)
    project = out / 'project'
    shutil.copytree(args.seed_project, project,
                    ignore=shutil.ignore_patterns('build', '.lefony', 'sdk.lock.json', 'compile_commands.json'))
    app = package(project)
    assert prior.load_segments(args.firmware) == prior.load_segments(args.firmware_debug)
    assert prior.load_segments(project / 'build/app.elf') == prior.load_segments(project / 'build/app-debug.elf')
    metadata = json.loads((project / 'app.json').read_text(encoding='utf-8'))
    assert metadata['id'] == APP and metadata['version'] == '0.2.1'
    source_names = ('vm/test-sdk-doom-quickslots.py', 'vm/test-sdk-doom-reset.py',
                    'vm/test-sdk-doom-interruption.py', 'vm/sdk_doom_probe.py',
                    'sdk/ports/doom/platform.c', 'scripts/prepare_sdk_doom.py',
                    'sdk/tools/runner.py', 'sdk/tools/files_device.py')
    report = {'status': 'running', 'cases': [], 'sdk_sha256': identity(ROOT / 'sdk'),
              'package_sha256': digest(app), 'elf_sha256': digest(project / 'build/app.elf'),
              'debug_sha256': digest(project / 'build/app-debug.elf'),
              'firmware_sha256': digest(args.firmware), 'firmware_debug_sha256': digest(args.firmware_debug),
              'qemu_sha256': digest(ROOT / 'build/qemu-prime-g2/qemu-system-arm'),
              'sources': {name: digest(ROOT / name) for name in source_names},
              'physical': 'not_tested', 'timing': 'instrumented emulator; not a performance measurement'}
    for name in source_names:
        target = out / 'sources' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    workspace = project / '.lefony/workspaces/quickslots'
    with opened(args.seed_project.resolve(), 'game') as (seed, _):
        workspace.mkdir(parents=True)
        for name in ('workspace.json', 'nand.overlay'):
            shutil.copyfile(seed / name, workspace / name)
        report['seed_overlay_sha256'] = digest(seed / 'nand.overlay')
    baseline, expected_pose, previous_save = None, None, None
    quick_slot = quick_path = None
    start_generation = None
    for phase in ('select-load-cancel', 'cold-replace-load', 'cold-final'):
        folder = out / phase
        folder.mkdir()
        records = {}
        print('START:', phase, flush=True)

        def snapshot(client, name):
            nonlocal baseline, start_generation, quick_slot, quick_path
            files = FileClient(client, timeout=180)
            data = {}
            for path, filename in ((prior.SAVE, 'original.dsg'), ('default.cfg', 'default.cfg'),
                                   ('doomgenericdoom.cfg', 'extra.cfg')):
                target = folder / (name + '-' + filename)
                files.export_file(APP, path, target)
                data[path] = target.read_bytes()
            info = files.info(APP)
            entries = files.list(APP, '.savegame')['entries']
            records[name + '_saves'] = entries
            retained = ([entry['path'] for entry in entries if entry['kind'] == 'file'] if baseline is None
                        else [path for path in baseline if path.startswith('.savegame/')])
            for index, path in enumerate(sorted(retained)):
                if path == prior.SAVE:
                    continue
                target = folder / (name + f'-retained-{index}.dsg')
                files.export_file(APP, path, target)
                data[path] = target.read_bytes()
            if baseline is None:
                assert phase == 'select-load-cancel' and name == 'before'
                paths = {entry['path'] for entry in entries}
                assert prior.SAVE in paths
                quick_slot = next((slot for slot in range(1, 6) if f'.savegame/doomsav{slot}.dsg' not in paths), None)
                assert quick_slot is not None, 'The seed needs an unused named-save slot'
                quick_path = f'.savegame/doomsav{quick_slot}.dsg'
                report['quick_slot'], report['quick_path'] = quick_slot, quick_path
                baseline, start_generation = data, info['generation']
            else:
                assert data == baseline, 'Original save or configuration changed'
            if not (phase == 'select-load-cancel' and name == 'before'):
                target = folder / (name + '-quick.dsg')
                files.export_file(APP, quick_path, target)
                records[name + '_quick_sha256'] = digest(target)
                assert target.stat().st_size > 1000
                if name == 'before' or phase == 'cold-final':
                    assert target.read_bytes() == previous_save
            return info

        def prepare(client):
            records['before'] = snapshot(client, 'before')
            expected = start_generation + {'select-load-cancel': 0, 'cold-replace-load': 1, 'cold-final': 3}[phase]
            assert records['before']['generation'] == expected

        def controls(channel):
            nonlocal expected_pose, previous_save
            normal = Controls(channel, folder)
            probe = DoomProbe(normal, project / 'build/app-debug.elf', folder,
                              fields={'quickslot': 'quickSaveSlot', 'item': 'itemOn',
                                      'saving': prior.FIELDS['saving'],
                                      'angle': 'players[consoleplayer].mo ? players[consoleplayer].mo->angle : 0'})

            def settle(label, witness):
                return probe.until(label, lambda s: not s['menu'] and not s['message'] and
                                   not s['save_entry'] and not s['save_request'] and not s['saving'] and
                                   not s['save_error'] and s['action'] == 0 and s['tics'] > witness['tics'])

            def confirm(label, symbol):
                value = prior.at_breakpoint(normal, probe, args.firmware_debug, folder, label, symbol,
                                            {**prior.POSE_FIELDS, 'tics': 'gametic'})
                records[label] = value
                settle(label + '-finished', value)
                return {key: value[key] for key in prior.POSE_FIELDS}

            def turn(label, key):
                before = probe.read(label + '-before')
                try:
                    normal.keys([key])
                    probe.until(label, lambda s: s['angle'] != before['angle'] and s['tics'] > before['tics'] + 4)
                finally:
                    normal.keys([])
                after = probe.read(label + '-released')
                probe.until(label + '-settled', lambda s: s['tics'] > after['tics'] + 4)

            def select_slot(label, slot):
                for _ in range(6):
                    state = probe.read(label)
                    if state['item'] == slot:
                        return
                    normal.key('down')
                raise AssertionError('Requested save/load slot was not selected')

            def select_quick(label):
                normal.key('plot')
                probe.until(label + '-menu', lambda s: s['menu'] and s['quickslot'] == -2)
                select_slot(label + '-slot', quick_slot)
                normal.key('ok')
                probe.until(label + '-name', lambda s: s['save_entry'])
                for _ in range(24):
                    normal.key('backspace')
                for key in ('four', 'five'):
                    normal.key(key)
                pose = confirm(label, 'P_WriteSaveGameEOF')
                assert probe.read(label + '-selected')['quickslot'] == quick_slot
                return pose

            def quick_load(label, pose):
                normal.key('view')
                probe.until(label + '-confirmation', lambda s: s['message'] and s['quickslot'] == quick_slot)
                assert confirm(label, 'P_ReadSaveGameEOF') == pose
                probe.capture(label)

            try:
                ready = probe.until('ready', lambda s: s['state'] == 0 and s['health'] > 0 and s['tics'] > 2)
                assert ready['quickslot'] == -1, ready
                if phase != 'select-load-cancel':
                    normal.key('view')
                    probe.until('no-selected-quickslot', lambda s: s['message'] and s['quickslot'] == -1)
                    probe.capture('no-selected-quickslot')
                    normal.key('ok')
                    probe.until('no-slot-dismissed', lambda s: not s['message'] and not s['menu'])
                normal.key('symb')
                probe.until('load-menu', lambda s: s['menu'])
                select_slot('load-slot', 0 if phase == 'select-load-cancel' else quick_slot)
                loaded = confirm('named-load', 'P_ReadSaveGameEOF')
                if expected_pose is not None:
                    assert loaded == expected_pose
                if phase == 'select-load-cancel':
                    turn('first-turn', 'right')
                    expected_pose = select_quick('first-quick-save')
                    turn('leave-first-save', 'left')
                    quick_load('first-quick-load', expected_pose)
                    turn('cancelled-position', 'right')
                    normal.key('plot')
                    confirmation = probe.until('cancel-save-confirmation', lambda s: s['message'] and s['quickslot'] == quick_slot)
                    normal.key('back')
                    settle('save-cancelled', confirmation)
                    probe.capture('save-cancelled')
                elif phase == 'cold-replace-load':
                    turn('second-turn', 'left')
                    select_quick('reselected-quick-save')
                    turn('replacement-turn', 'right')
                    normal.key('plot')
                    probe.until('replace-confirmation', lambda s: s['message'] and s['quickslot'] == quick_slot)
                    expected_pose = confirm('replaced-quick-save', 'P_WriteSaveGameEOF')
                    turn('leave-replacement', 'left')
                    quick_load('replacement-quick-load', expected_pose)
                normal.key('home')
                channel.app_client.wait()
                records['closed'] = snapshot(channel.app_client, 'closed')
                expected = start_generation + (1 if phase == 'select-load-cancel' else 3)
                assert records['closed']['generation'] == expected, records['closed']
                current = (folder / 'closed-quick.dsg').read_bytes()
                if phase == 'cold-replace-load':
                    assert current != previous_save
                previous_save = current
                records['expected_pose'] = expected_pose
                if phase == 'cold-final':
                    print('CHECK: complete public WAD export', flush=True)
                    wad = folder / 'freedoom1.wad'
                    FileClient(channel.app_client, timeout=180).export_file(APP, 'freedoom1.wad', wad)
                    expected = json.loads((ROOT / 'sdk/ports/doom/assets.json').read_text())['files']['freedoom1.wad']
                    assert wad.stat().st_size == expected['bytes'] and digest(wad) == expected['sha256']
                    records['wad'] = {'bytes': wad.stat().st_size, 'sha256': digest(wad)}
            finally:
                records['observations'] = probe.records
                write_json(folder / 'observations.json', records)
                normal.close()

        try:
            with opened(project, 'quickslots') as (media, _), reset.existing_install(records):
                runtime = runner.exercise(app, ROOT / 'build/qemu-prime-g2/qemu-system-arm', args.firmware,
                                          workspace=media, prepare_workspace=prepare, controls=controls,
                                          measure_resources=True)
                assert runtime['result'] == 1 and runtime['os_responsive'] and runtime['fault'] is None, runtime
                records['overlay_sha256'] = digest(media / 'nand.overlay')
            report['cases'].append({'phase': phase, 'records': records, 'runtime': runtime})
            write_json(out / 'report.json', report)
            print('PASS:', phase, flush=True)
        except BaseException as error:
            report.update(status='failed', failed_phase=phase, error={'type': type(error).__name__, 'message': str(error)[:4096]})
            write_json(out / 'report.json', report)
            raise
    report['status'] = 'passed'
    write_json(out / 'report.json', report)


if __name__ == '__main__':
    main()
