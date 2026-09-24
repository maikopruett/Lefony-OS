#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Kill the owned Doom VM at observed save boundaries, then boot without install.

Only synthetic media is used. Normal keypad input drives the signed ARM app;
GDB reads state at temporary hardware breakpoints. SIGKILL loses guest volatile
state after completed modeled NAND writes. It does not model torn programming,
host power loss, electrical behavior or flash endurance.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, identity, write_json
from cli import package
from device import Client
from files_device import FileClient, REQUEST, INFO, EXPORT, LIST
from replay import Controls
import runner
from signing import sign, verify
from workspace import opened
from sdk_doom_probe import DoomProbe

spec = importlib.util.spec_from_file_location('doom_interruption', Path(__file__).with_name('test-sdk-doom-interruption.py'))
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
SAVE, POSE_FIELDS = prior.SAVE, prior.POSE_FIELDS
FIELDS = {**prior.FIELDS, 'angle': 'players[consoleplayer].mo ? ' + POSE_FIELDS['angle'] + ' : 0',
          'reference_open': prior.VOLUME + '.m_documents.m_open',
          'committing_root': prior.VOLUME +
          '.m_documents.m_phase == PrimeG2::AppDocumentStore::Store::Phase::Commit'}
CASES = ('staging', 'verification', 'before-rename', 'after-rename')


class AbruptStop(BaseException):
    """Unwind the runner without its normal Home/diagnostic/storage drain."""


class OwnedChannel(runner.Channel):
    def __init__(self, path, process, timeout=30):
        super().__init__(path, process, timeout)
        self.owned_process = process


@contextmanager
def existing_install(records):
    """Test-local runner adapter: authenticate/read back, never reinstall/repair."""
    original_write = Client.write

    def read_existing(client, content, keys):
        metadata, _ = verify(content, keys)
        client.require_compatible(metadata)
        matches = [entry for entry in client.catalog() if entry['id'] == metadata['id']]
        assert len(matches) == 1, matches
        entry = matches[0]
        assert entry['version'] == metadata['version'] and entry['bytes'] == len(content), entry
        actual = client.read_package(entry['slot'], entry['bytes'])
        assert actual == content, 'Cold-boot package differs; no repair was attempted'
        records['existing_install'] = {'catalog': entry, 'sha256': hashlib.sha256(actual).hexdigest(),
                                       'action': 'public-readback-only'}
        return entry

    def read_only_write(client, request, data=b'', argument=0):
        # USB uses OUT requests to select/read/ack a download. Allow only those
        # public read sessions, including their error-path cancellation.
        assert request in (0x6a, 0x71, 0x73, 0x75), ('unexpected USB mutation', request)
        if request == 0x71:
            assert REQUEST.unpack(data)[2] in (INFO, EXPORT, LIST), 'Unexpected file mutation'
        key = hex(request)
        records.setdefault('host_requests', {})[key] = records.get('host_requests', {}).get(key, 0) + 1
        return original_write(client, request, data, argument)

    with patch.object(runner, 'Channel', OwnedChannel), patch.object(Client, 'install', read_existing), \
            patch.object(Client, 'write', read_only_write):
        yield


def printf_fields(label, fields):
    return 'printf "' + label + ' ' + ','.join(['%d'] * len(fields)) + '\\n", ' + \
           ', '.join('(' + value + ')' for value in fields.values())


def read_fields(text, label, fields):
    found = re.search(r'^' + label + r' ([0-9,\-]+)$', text, re.M)
    assert found, text
    return dict(zip(fields, map(int, found[1].split(',')), strict=True))


def stop_at_save(normal, probe, firmware_debug, folder, case, previous_bytes):
    """Hold the CPU at a witnessed cut, then kill exactly this runner's process."""
    session = normal.channel.session_directory
    assert not any(c.isspace() for c in str(session))
    armed, hit = session / 'reset-armed', session / 'reset-hit'
    quoted = str(firmware_debug.resolve()).replace('\\', '\\\\').replace('"', '\\"')
    commands = ['set pagination off', 'set confirm off', 'add-symbol-file "' + quoted + '"',
                'set language c++', 'target remote ' + str(probe.endpoint),
                'thbreak ' + ('P_ArchiveThinkers' if case == 'staging' else 'P_WriteSaveGameEOF'),
                f'dump binary memory {armed} &gametic &gametic+1', 'continue',
                printf_fields('SERIALIZED', POSE_FIELDS)]
    if case != 'staging':
        if case == 'verification':
            target = "'PrimeG2::AppDocumentStore::Store::checkReference()'"
            # The cursor can still describe the preceding metadata check on
            # phase entry. An open reference resets it before actual reads.
            condition = FIELDS['verifying'] + ' && ' + FIELDS['reference_open'] + \
                        ' && ' + prior.VOLUME + '.m_documents.m_cursor >= 2048'
        else:
            target = '*lfs_rename'
            condition = prior.VOLUME + \
                     '.m_documents.m_phase == PrimeG2::AppDocumentStore::Store::Phase::Commit && ' + \
                     prior.VOLUME + '.m_files.m_phase == PrimeG2::AppFileStore::Store::Phase::Commit'
        # Separating location and condition avoids GDB's linespec parser
        # confusing quoted anonymous-namespace names with location syntax.
        commands += ['thbreak ' + target, 'condition $bpnum ' + condition,
                     'continue', printf_fields('BOUNDARY', FIELDS)]
        if case == 'after-rename':
            # Hardware-break at the observed return address, avoiding GDB's
            # ordinary finish command and its possible software breakpoint.
            commands += ['thbreak *($lr & ~1)', 'continue', 'printf "RENAME_RETURN %d\\n", $r0']
    commands += [printf_fields('WITNESS', FIELDS), 'bt 4',
                 f'dump binary memory {hit} &gametic &gametic+1']
    # A command file stops on the first setup error. Separate -ex arguments
    # would keep executing later continue commands after a rejected breakpoint.
    script = folder / 'reset.gdb'
    script.write_text('\n'.join(commands) + '\n', encoding='utf-8', newline='\n')
    argv = [shutil.which('arm-none-eabi-gdb'), '-q', '-nx', str(probe.elf.resolve()), '-x', str(script)]
    log = folder / 'reset-breakpoint.log'
    process = normal.channel.owned_process
    assert process is not None and process.poll() is None
    with log.open('w', encoding='utf-8') as stream:
        gdb = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=stream, stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8')

        def wait_marker(path, seconds):
            deadline = time.monotonic() + seconds
            while not path.exists():
                text = log.read_text(encoding='utf-8')
                assert gdb.poll() is None and process.poll() is None and time.monotonic() < deadline and '\n(gdb)' not in text, text
                time.sleep(.02)

        try:
            wait_marker(armed, 30)
            normal.key_edge('ok', True)
            time.sleep(.25)
            normal.key_edge('ok', False)
            wait_marker(hit, 180)
            text = log.read_text(encoding='utf-8')
            witness = read_fields(text, 'WITNESS', FIELDS)
            serialized = read_fields(text, 'SERIALIZED', POSE_FIELDS)
            assert witness['saving'] and witness['writer'], witness
            if case == 'staging':
                assert 0 < witness['staged'] < previous_bytes and not witness['verifying'], witness
            else:
                boundary = read_fields(text, 'BOUNDARY', FIELDS)
                assert boundary['saving'] and boundary['writer'] and boundary['staged'] > 0, boundary
                if case == 'verification':
                    assert boundary['verifying'] and boundary['reference_open'] and boundary['document_cursor'] >= 2048, boundary
                else:
                    assert boundary['committing_root'] and not boundary['verifying'], boundary
                if case == 'after-rename':
                    assert re.search(r'^RENAME_RETURN 0$', text, re.M), text
                    assert 'PrimeG2::AppDocumentStore::Store::step' in text, text
            process.kill()
            assert process.wait(timeout=10) == -signal.SIGKILL
            stderr = process.stderr.read().decode('utf-8', errors='replace')
            (folder / 'qemu-stderr.log').write_text(stderr, encoding='utf-8')
            gdb.communicate('quit\n', timeout=15)
            return {'witness': witness, 'serialized_pose': serialized, 'process_returncode': process.returncode,
                    'gdb_returncode': gdb.returncode, 'stop': 'SIGKILL while CPU held at hardware breakpoint',
                    'cleanup': 'no guest Home, quit, flush or storage drain'}
        finally:
            if gdb.poll() is None:
                gdb.send_signal(signal.SIGINT)
                try:
                    gdb.communicate('detach\nquit\n', timeout=10)
                except subprocess.TimeoutExpired:
                    gdb.kill()
                    gdb.communicate(timeout=5)
            if process.poll() is None:
                normal.key_edge('ok', False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('seed-project', 'output', 'firmware', 'firmware-debug'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--cases', nargs='+', choices=CASES, default=list(CASES))
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True)
    assert prior.load_segments(args.firmware) == prior.load_segments(args.firmware_debug), 'Mismatched firmware symbols'
    project = out / 'project'
    shutil.copytree(args.seed_project, project,
                    ignore=shutil.ignore_patterns('build', '.lefony', 'sdk.lock.json', 'compile_commands.json'))
    dest = project / '.lefony/workspaces/game'
    dest.mkdir(parents=True)
    with opened(args.seed_project.resolve(), 'game') as (seed, _):
        for name in ('workspace.json', 'nand.overlay'):
            shutil.copyfile(seed / name, dest / name)
    app = package(project)
    assert prior.load_segments(project / 'build/app.elf') == prior.load_segments(project / 'build/app-debug.elf')
    signed = sign(app.read_bytes(), ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem')
    assert hashlib.sha256(signed).hexdigest() == json.loads((dest / 'workspace.json').read_text(encoding='utf-8'))['package_sha256']
    report = {'status': 'running', 'cases': [], 'sdk_sha256': identity(ROOT / 'sdk'),
              'firmware_sha256': digest(args.firmware), 'firmware_debug_sha256': digest(args.firmware_debug),
              'qemu_sha256': digest(ROOT / 'build/qemu-prime-g2/qemu-system-arm'),
              'app_elf_sha256': digest(project / 'build/app.elf'),
              'app_debug_sha256': digest(project / 'build/app-debug.elf'),
              'package_sha256': hashlib.sha256(signed).hexdigest(),
              'seed_overlay_sha256': digest(dest / 'nand.overlay'),
              'physical': 'not_tested', 'model': 'guest volatile-state loss between completed NAND operations',
              'sources': {name: digest(ROOT / name) for name in (
                  'vm/test-sdk-doom-reset.py', 'vm/test-sdk-doom-interruption.py', 'vm/sdk_doom_probe.py',
                  'sdk/tools/runner.py', 'sdk/ports/doom/assets.json',
                  'ports/lefony-prime-g2/ion/src/prime_g2/app_document_store.cpp',
                  'ports/lefony-prime-g2/ion/src/prime_g2/app_file_store.cpp', 'vm/qemu/prime_g2_peripherals.c')}}
    for name in report['sources']:
        target = out / 'sources' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    write_json(out / 'report.json', report)
    pending = None
    retry_pose = None
    phases = [(case, mode) for case in args.cases for mode in ('cut', 'recover-retry')] + [('final', 'cold')]
    for case, mode in phases:
        label = case + '-' + mode
        print('START:', label, flush=True)
        folder = out / label
        folder.mkdir()
        records = {}

        def snapshot(client, label):
            files = FileClient(client, timeout=180)
            files.export_file('doom-proof', SAVE, folder / (label + '.dsg'))
            files.export_file('doom-proof', 'default.cfg', folder / (label + '.cfg'))
            return files.info('doom-proof')

        def prepare(client):
            records['before'] = snapshot(client, 'before')
            assert not records['before']['pending_upgrade']
            if mode == 'recover-retry':
                assert (folder / 'before.cfg').read_bytes() == pending['config']
                current = (folder / 'before.dsg').read_bytes()
                if case == 'after-rename':
                    assert current != pending['save'] and current.startswith(b'456\0')
                    assert records['before']['generation'] > pending['generation']
                else:
                    assert current == pending['save']
                    assert records['before']['generation'] == pending['generation']
            elif mode == 'cold':
                assert (folder / 'before.dsg').read_bytes() == pending['retry_save']
                assert (folder / 'before.cfg').read_bytes() == pending['config']
                print('CHECK: final public WAD export', flush=True)
                FileClient(client, timeout=180).export_file('doom-proof', 'freedoom1.wad', folder / 'freedoom1.wad')
                expected = json.loads((ROOT / 'sdk/ports/doom/assets.json').read_text(encoding='utf-8'))['files']['freedoom1.wad']
                records['wad'] = {'bytes': (folder / 'freedoom1.wad').stat().st_size,
                                  'sha256': digest(folder / 'freedoom1.wad')}
                assert records['wad'] == {key: expected[key] for key in ('bytes', 'sha256')}

        def controls(channel):
            nonlocal pending, retry_pose
            normal = Controls(channel, folder)
            probe = DoomProbe(normal, project / 'build/app-debug.elf', folder,
                              symbols=(args.firmware_debug,), fields=FIELDS)
            try:
                probe.until('ready', lambda state: state['state'] == 0 and state['health'] > 0 and state['tics'] > 2)
                normal.key('symb')
                probe.until('load-menu', lambda state: state['menu'] == 1)
                restored = prior.at_breakpoint(normal, probe, args.firmware_debug, folder,
                                               'restored', 'P_ReadSaveGameEOF', {**POSE_FIELDS, 'tics': 'gametic'})
                loaded_pose = {key: restored[key] for key in POSE_FIELDS}
                records['loaded_pose'] = loaded_pose
                if mode == 'recover-retry':
                    assert loaded_pose == pending['expected_pose'], records
                elif retry_pose is not None:
                    assert loaded_pose == retry_pose, records
                # gameaction is cleared before loading finishes. Require a new
                # engine tick after the EOF witness before sending more input.
                probe.until('loaded', lambda state: not state['menu'] and state['action'] == 0 and
                            not state['save_error'] and state['tics'] > restored['tics'])
                probe.until('load-frame', lambda state: state['tics'] >= restored['tics'] + 3)
                probe.capture('loaded')
                if mode != 'cold':
                    # Turning gives a distinct serialized state independently
                    # of map collision. Wait for observed input consumption.
                    try:
                        normal.keys(['right'])
                        probe.until('turned', lambda state: state['angle'] != loaded_pose['angle'])
                    finally:
                        normal.keys([])
                    probe.save(name=('four', 'five', 'six') if mode == 'cut' else ('seven', 'eight', 'nine'), confirm=False)
                    if mode == 'cut':
                        stopped = stop_at_save(normal, probe, args.firmware_debug, folder, case, (folder / 'before.dsg').stat().st_size)
                        records['cut'] = stopped
                        pending = {'save': (folder / 'before.dsg').read_bytes(),
                                   'config': (folder / 'before.cfg').read_bytes(),
                                   'generation': records['before']['generation'],
                                   'expected_pose': stopped['serialized_pose'] if case == 'after-rename' else loaded_pose}
                        raise AbruptStop()
                    retry_pose = prior.at_breakpoint(normal, probe, args.firmware_debug, folder,
                                                      'retry-serialized', 'P_WriteSaveGameEOF', POSE_FIELDS)
                    records['retry_pose'] = retry_pose
                    saved = probe.until('saved', lambda state: not state['menu'] and not state['save_entry'] and
                                        not state['save_request'] and state['action'] == 0 and not state['writer'])
                    assert not saved['save_error'], saved
                    probe.capture('retry')
                normal.key('home')
                channel.app_client.wait()
                records['after'] = snapshot(channel.app_client, 'after')
                assert (folder / 'before.cfg').read_bytes() == (folder / 'after.cfg').read_bytes()
                after = (folder / 'after.dsg').read_bytes()
                if mode == 'recover-retry':
                    assert after.startswith(b'789\0') and after != (folder / 'before.dsg').read_bytes()
                    pending['retry_save'] = after
                else:
                    assert after == (folder / 'before.dsg').read_bytes()
                    assert records['after']['generation'] == records['before']['generation']
            finally:
                records['observations'] = probe.records
                write_json(folder / 'observations.json', records)
                if channel.owned_process.poll() is None:
                    normal.close()
                else:
                    normal.qtest.close()
                    normal.qmp.close()

        try:
            with opened(project, 'game') as (workspace, _), existing_install(records):
                try:
                    result = runner.exercise(app, ROOT / 'build/qemu-prime-g2/qemu-system-arm', args.firmware,
                                             workspace=workspace, prepare_workspace=prepare, controls=controls,
                                             measure_resources=True)
                except AbruptStop:
                    assert mode == 'cut' and records['cut']['process_returncode'] == -signal.SIGKILL
                    result = {'abrupt_stop': True, 'graceful_cleanup': False}
                else:
                    assert mode != 'cut' and result['result'] == 1 and result['os_responsive'], result
        except BaseException as error:
            report.update(status='failed', failed_phase=label,
                          error={'type': type(error).__name__, 'message': str(error)[:4096]})
            write_json(out / 'report.json', report)
            raise
        records['overlay_sha256'] = digest(dest / 'nand.overlay')
        report['cases'].append({'phase': label, 'records': records, 'runtime': result})
        write_json(out / 'report.json', report)
        print('PASS:', label, flush=True)
    report['status'] = 'passed'
    write_json(out / 'report.json', report)


if __name__ == '__main__':
    main()
