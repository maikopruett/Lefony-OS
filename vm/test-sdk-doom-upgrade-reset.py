#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Interrupt signed Doom updates, cold-inspect, roll back and retry through USB.

Uses only copied synthetic workspaces and the owned QEMU processes. Fixture
versions change the package manifest, not the checked-in Doom release. Hardware
breakpoints observe storage work; no guest functions or variables are injected.
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
from data_device import DataClient
from device import Client, DeviceError
from files_device import FileClient, REQUEST, INFO, EXPORT, LIST, DATA_INFO, DATA_EXPORT, ROLLBACK
from replay import Controls
import runner
from signing import sign
from workspace import opened
from sdk_doom_probe import DoomProbe

spec = importlib.util.spec_from_file_location('doom_reset', Path(__file__).with_name('test-sdk-doom-reset.py'))
reset = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset)
prior = reset.prior
APP, SAVE = 'doom-proof', reset.SAVE
PUBLIC = ROOT / 'tests/fixtures/prime_g2_emulator_update_public.pem'
PRIVATE = ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem'
REAL_INSTALL, REAL_WRITE = Client.install, Client.write
CASES = ('upload', 'package-write', 'before-rename', 'after-rename')
NAMESPACE = 'PrimeG2::AppManagement::(anonymous namespace)::'
VOLUME = prior.VOLUME
DOCUMENT = VOLUME + '.m_documents'
PENDING = 'PrimeG2::AppDocumentRoot::PendingUpgrade'
FIELDS = {
    'state': "'" + NAMESPACE + "sState'",
    'received': "'" + NAMESPACE + "sReceived'",
    'length': "'" + NAMESPACE + "sLength'",
    'document_operation': VOLUME + '.m_documentOperation',
    'phase': '(int)' + DOCUMENT + '.m_phase',
    'cursor': DOCUMENT + '.m_cursor',
    'package_writes': DOCUMENT + '.m_packageWrites',
    'open': DOCUMENT + '.m_open',
    'writing_package': DOCUMENT + '.m_phase == PrimeG2::AppDocumentStore::Store::Phase::Package',
    'committing_root': DOCUMENT + '.m_phase == PrimeG2::AppDocumentStore::Store::Phase::Commit',
    'pending_after': '(' + DOCUMENT + '.m_after.flags & ' + PENDING + ') != 0',
    'before_generation': DOCUMENT + '.m_before.serial',
    'after_generation': DOCUMENT + '.m_after.serial',
}


class ExpectedRejection(BaseException):
    """End the inspected rejected-upload session before normal runner cleanup."""


@contextmanager
def access(records):
    permission = {'kind': None}

    def guarded_write(client, request, data=b'', argument=0):
        kind = permission['kind']
        allowed = {0x6a, 0x71, 0x73, 0x75}
        if kind == 'install':
            allowed |= {0x63, 0x64, 0x65, 0x67}
        elif kind == 'rollback':
            allowed.add(0x74)
        assert request in allowed, (kind, 'unexpected USB mutation', request)
        operation = None
        if request == 0x71:
            operation = REQUEST.unpack(data)[2]
            operations = {INFO, EXPORT, LIST, DATA_INFO, DATA_EXPORT}
            if kind == 'rollback':
                operations.add(ROLLBACK)
            assert operation in operations, (kind, 'unexpected file mutation', operation)
        key = f'{kind or "read"}:{request:#x}' + (f':{operation}' if operation is not None else '')
        counts = records.setdefault('host_requests', {})
        counts[key] = counts.get(key, 0) + 1
        return REAL_WRITE(client, request, data, argument)

    @contextmanager
    def mutation(kind):
        assert permission['kind'] is None and kind in ('install', 'rollback')
        permission['kind'] = kind
        try:
            yield
        finally:
            permission['kind'] = None

    # The runner's startup always verifies/readbacks the existing installation.
    # Mutations occur only in the explicit host actions below, after inspection.
    with reset.existing_install(records), patch.object(Client, 'write', guarded_write):
        yield mutation


def cut_install(normal, probe, firmware_debug, folder, case, trigger=None):
    session = normal.channel.session_directory
    assert not any(c.isspace() for c in str(session))
    armed, hit = session / 'upgrade-armed', session / 'upgrade-hit'
    counter = "'" + NAMESPACE + "sCount'"
    # dump's range parser splits at spaces, including those inside a quoted
    # anonymous-namespace symbol. Resolve it in GDB first; this convenience
    # variable is debugger state and does not write guest memory.
    dump = lambda path: f'dump binary memory {path} $upgrade_marker $upgrade_marker+1'
    commands = ['set pagination off', 'set confirm off', 'set language c++',
                'target remote ' + str(probe.endpoint), 'set $upgrade_marker = &' + counter]
    if case == 'upload':
        normal.execute('stop')
    else:
        if case == 'package-write':
            target = "'PrimeG2::AppDocumentStore::Store::writeObject'"
            condition = FIELDS['writing_package'] + ' && ' + FIELDS['open'] + ' && ' + FIELDS['package_writes'] + ' >= 2048'
        else:
            target = '*lfs_rename'
            condition = FIELDS['committing_root']
        condition = '(' + condition + ') && ' + FIELDS['document_operation'] + ' && ' + FIELDS['pending_after']
        commands += ['thbreak ' + target, 'condition $bpnum ' + condition, dump(armed), 'continue',
                     reset.printf_fields('BOUNDARY', FIELDS)]
        if case == 'after-rename':
            commands += ['thbreak *($lr & ~1)', 'continue', 'printf "RENAME_RETURN %d\\n", $r0']
    commands += [reset.printf_fields('WITNESS', FIELDS), 'bt 5', dump(hit)]
    script = folder / 'upgrade-reset.gdb'
    script.write_text('\n'.join(commands) + '\n', encoding='utf-8', newline='\n')
    log = folder / 'upgrade-breakpoint.log'
    process = normal.channel.owned_process
    assert process.poll() is None
    trigger_error = None
    with log.open('w', encoding='utf-8') as stream:
        gdb = subprocess.Popen([shutil.which('arm-none-eabi-gdb'), '-q', '-nx', str(firmware_debug.resolve()), '-x', str(script)],
                               stdin=subprocess.PIPE, stdout=stream, stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8')

        def wait_marker(path, timeout):
            deadline = time.monotonic() + timeout
            while not path.exists():
                text = log.read_text(encoding='utf-8')
                assert gdb.poll() is None and process.poll() is None and time.monotonic() < deadline and '\n(gdb)' not in text, text
                time.sleep(.02)

        try:
            if trigger is not None:
                wait_marker(armed, 30)
                try:
                    trigger()
                except Exception as error:
                    # A paused CPU can prevent a final USB acknowledgement.
                    # Keep the one attempted command; require the witnessed cut.
                    trigger_error = {'type': type(error).__name__, 'message': str(error)}
            wait_marker(hit, 180)
            text = log.read_text(encoding='utf-8')
            witness = reset.read_fields(text, 'WITNESS', FIELDS)
            if case == 'upload':
                assert witness['state'] == 4 and 0 < witness['received'] < witness['length'], witness
            else:
                assert witness['state'] == 5 and witness['received'] == witness['length'], witness
                assert witness['document_operation'] and witness['pending_after'], witness
                assert witness['after_generation'] == witness['before_generation'] + 1, witness
                if case == 'package-write':
                    assert witness['writing_package'] and witness['open'] and 2048 <= witness['package_writes'] < witness['length'], witness
                else:
                    assert witness['committing_root'] and witness['package_writes'] == witness['length'], witness
                if case == 'after-rename':
                    assert re.search(r'^RENAME_RETURN 0$', text, re.M) and 'PrimeG2::AppDocumentStore::Store::step' in text, text
            process.kill()
            assert process.wait(timeout=10) == -signal.SIGKILL
            (folder / 'qemu-stderr.log').write_bytes(process.stderr.read())
            gdb.communicate('quit\n', timeout=15)
            return {'witness': witness, 'trigger_error': trigger_error, 'process_returncode': process.returncode,
                    'gdb_returncode': gdb.returncode, 'cleanup': 'no guest cancellation, Home, quit or storage drain',
                    'pause': 'QMP stop after upload acknowledgement' if case == 'upload' else 'hardware breakpoint'}
        finally:
            if gdb.poll() is None:
                gdb.send_signal(signal.SIGINT)
                try:
                    gdb.communicate('detach\nquit\n', timeout=10)
                except subprocess.TimeoutExpired:
                    gdb.kill()
                    gdb.communicate(timeout=5)
            if process.poll() is None and case == 'upload':
                normal.execute('cont')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('seed-project', 'output', 'firmware', 'firmware-debug'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--cases', nargs='+', choices=CASES, default=list(CASES))
    args = parser.parse_args()
    assert len(set(args.cases)) == len(args.cases)
    out = args.output.resolve()
    out.mkdir(parents=True)
    assert prior.load_segments(args.firmware) == prior.load_segments(args.firmware_debug)
    old_metadata = json.loads((args.seed_project / 'app.json').read_text(encoding='utf-8'))
    assert old_metadata['id'] == APP and old_metadata['data_schema'] == 0
    version = list(map(int, old_metadata['version'].split('.')))
    assert version[2] < 999998
    projects, packages, signed, versions = {}, {}, {}, {}
    for index, name in enumerate(('old', 'new', 'retry')):
        project = out / name
        shutil.copytree(args.seed_project, project,
                        ignore=shutil.ignore_patterns('build', '.lefony', 'sdk.lock.json', 'compile_commands.json'))
        metadata = dict(old_metadata)
        metadata['version'] = '.'.join(map(str, (*version[:2], version[2] + index)))
        write_json(project / 'app.json', metadata)
        projects[name], versions[name] = project, metadata['version']
        packages[name] = package(project)
        signed[name] = sign(packages[name].read_bytes(), PRIVATE)
        assert prior.load_segments(project / 'build/app.elf') == prior.load_segments(project / 'build/app-debug.elf')
    source_names = ('vm/test-sdk-doom-upgrade-reset.py', 'vm/test-sdk-doom-reset.py',
                    'vm/test-sdk-doom-interruption.py', 'vm/sdk_doom_probe.py', 'sdk/tools/device.py',
                    'sdk/tools/data_device.py', 'sdk/tools/runner.py', 'sdk/ports/doom/assets.json',
                    'ports/lefony-prime-g2/ion/src/prime_g2/app_management.cpp',
                    'ports/lefony-prime-g2/ion/src/prime_g2/app_document_store.cpp',
                    'ports/lefony-prime-g2/ion/src/prime_g2/app_storage.cpp')
    report = {'status': 'running', 'cases': [], 'versions': versions,
              'version_scope': 'manifest-only local update fixtures; not a Doom release',
              'sdk_sha256': identity(ROOT / 'sdk'), 'firmware_sha256': digest(args.firmware),
              'firmware_debug_sha256': digest(args.firmware_debug),
              'qemu_sha256': digest(ROOT / 'build/qemu-prime-g2/qemu-system-arm'),
              'artifacts': {name: {'raw_sha256': digest(packages[name]),
                                  'signed_sha256': hashlib.sha256(signed[name]).hexdigest(),
                                  'elf_sha256': digest(projects[name] / 'build/app.elf'),
                                  'debug_sha256': digest(projects[name] / 'build/app-debug.elf')} for name in projects},
              'sources': {name: digest(ROOT / name) for name in source_names},
              'physical': 'not_tested', 'model': 'guest state loss between completed modeled NAND operations'}
    for name in source_names:
        destination = out / 'sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    with opened(args.seed_project.resolve(), 'game') as (seed, _):
        assert json.loads((seed / 'workspace.json').read_text(encoding='utf-8'))['package_sha256'] == report['artifacts']['old']['signed_sha256']
        report['seed_overlay_sha256'] = digest(seed / 'nand.overlay')
        for case in args.cases:
            dest = projects['old'] / '.lefony/workspaces' / case
            dest.mkdir(parents=True)
            for filename in ('workspace.json', 'nand.overlay'):
                shutil.copyfile(seed / filename, dest / filename)
    write_json(out / 'report.json', report)
    baseline = None
    for case in args.cases:
        start_generation = rolled_generation = None
        phases = ('cut', 'rollback-deny', 'retry', 'accept', 'cold') if case == 'after-rename' else ('cut', 'retry', 'accept', 'cold')
        accepted = 'retry' if case == 'after-rename' else 'new'
        for mode in phases:
            active = 'new' if mode == 'rollback-deny' else accepted if mode in ('accept', 'cold') else 'old'
            label = case + '-' + mode
            folder = out / label
            folder.mkdir()
            records = {}
            print('START:', label, flush=True)

            def snapshot(client, name):
                files = FileClient(client, timeout=180)
                files.export_file(APP, SAVE, folder / (name + '.dsg'))
                files.export_file(APP, 'default.cfg', folder / (name + '.cfg'))
                files.export_file(APP, 'doomgenericdoom.cfg', folder / (name + '-extra.cfg'))
                value = DataClient(client, timeout=180).info(APP)
                records[name + '_files'] = files.list(APP)
                records[name + '_saves'] = files.list(APP, '.savegame')
                assert value['package_sha256'] == report['artifacts'][next(key for key in versions if versions[key] == value['version'])]['signed_sha256']
                if baseline is not None:
                    assert (folder / (name + '.dsg')).read_bytes() == baseline['save']
                    assert (folder / (name + '.cfg')).read_bytes() == baseline['config']
                    assert (folder / (name + '-extra.cfg')).read_bytes() == baseline['extra_config']
                    assert value['private_sha256'] == baseline['info']['private_sha256']
                    assert records[name + '_files']['entries'] == baseline['files']
                    assert records[name + '_saves']['entries'] == baseline['saves']
                return value

            def prepare(client):
                nonlocal start_generation
                records['before'] = snapshot(client, 'before')
                value = records['before']
                assert value['version'] == versions[active]
                pending = mode in ('accept', 'rollback-deny')
                assert value['pending_upgrade'] == pending and value['rollback_available'] == pending, value
                expected_high = versions['new'] if case == 'after-rename' and mode in ('retry', 'rollback-deny') else versions[active]
                assert value['high_version'] == expected_high, value
                if mode == 'cut':
                    start_generation = value['generation']
                elif mode == 'rollback-deny':
                    assert value['generation'] == start_generation + 1, value
                elif mode == 'retry':
                    assert value['generation'] == (rolled_generation if case == 'after-rename' else start_generation), value
                if pending:
                    assert value['previous_version'] == versions['old']
                    assert value['previous_package_sha256'] == report['artifacts']['old']['signed_sha256']

            def controls(channel):
                nonlocal baseline, rolled_generation
                normal = Controls(channel, folder)
                probe = DoomProbe(normal, projects[active] / 'build/app-debug.elf', folder)
                try:
                    probe.until('ready', lambda state: state['state'] == 0 and state['health'] > 0 and state['tics'] > 2)
                    normal.key('symb')
                    probe.until('load-menu', lambda state: state['menu'] == 1)
                    restored = prior.at_breakpoint(normal, probe, args.firmware_debug, folder,
                        'restored', 'P_ReadSaveGameEOF', {**prior.POSE_FIELDS, 'tics': 'gametic'})
                    pose = {key: restored[key] for key in prior.POSE_FIELDS}
                    records['restored_pose'] = pose
                    if baseline is None:
                        baseline = {'pose': pose, 'save': (folder / 'before.dsg').read_bytes(),
                                    'config': (folder / 'before.cfg').read_bytes(),
                                    'extra_config': (folder / 'before-extra.cfg').read_bytes(),
                                    'files': records['before_files']['entries'],
                                    'saves': records['before_saves']['entries'], 'info': records['before']}
                    else:
                        assert pose == baseline['pose'], (pose, baseline['pose'])
                    probe.until('loaded', lambda state: not state['menu'] and state['action'] == 0 and
                                not state['save_error'] and state['tics'] > restored['tics'])
                    if mode == 'accept':
                        probe.quit()
                        # Home unloads the app and clears the live exit flag.
                        # Retain its observed ordinary exit before that action.
                        records['clean_exit'] = probe.records[-1]
                        assert records['clean_exit']['exited'] and records['clean_exit']['exit_status'] == 0
                    normal.key('home')
                    channel.app_client.wait()
                    records['closed'] = snapshot(channel.app_client, 'closed')
                    if mode == 'accept':
                        assert not records['closed']['pending_upgrade'] and not records['closed']['rollback_available']
                        assert records['closed']['high_version'] == versions[accepted]
                    else:
                        assert records['closed']['generation'] == records['before']['generation'], records
                    if mode == 'cut':
                        def progress(done, total):
                            if case == 'upload' and done >= total // 2:
                                records['cut'] = cut_install(normal, probe, args.firmware_debug, folder, case)
                                raise reset.AbruptStop()

                        def commit(_):
                            records['cut'] = cut_install(normal, probe, args.firmware_debug, folder, case,
                                                         trigger=lambda: channel.app_client.write(0x65))
                            raise reset.AbruptStop()

                        with mutation('install'):
                            REAL_INSTALL(channel.app_client, signed['new'], [PUBLIC], progress=progress,
                                         commit=commit if case != 'upload' else None)
                        raise AssertionError('Installation completed instead of reaching its cut')
                    if mode == 'rollback-deny':
                        with mutation('rollback'):
                            records['rollback'] = DataClient(channel.app_client, timeout=180).rollback(APP)
                        records['rolled_back'] = snapshot(channel.app_client, 'rolled-back')
                        rolled_generation = records['rolled_back']['generation']
                        assert records['rolled_back']['version'] == versions['old']
                        assert records['rolled_back']['high_version'] == versions['new']
                        try:
                            with mutation('install'):
                                REAL_INSTALL(channel.app_client, signed['new'], [PUBLIC])
                        except DeviceError as error:
                            state = channel.app_client.status()
                            assert state['state'] == 7 and state['error'] == 8, (str(error), state)
                            assert channel.command('PING') == 'PONG'
                            records['rejection'] = {'message': str(error), 'status': state, 'os_responsive': True}
                            raise ExpectedRejection()
                        raise AssertionError('Rollback permitted reusing the retired update version')
                    if mode == 'retry':
                        with mutation('install'):
                            records['installed'] = REAL_INSTALL(channel.app_client, signed[accepted], [PUBLIC])
                        records['updated'] = snapshot(channel.app_client, 'updated')
                        assert records['updated']['version'] == versions[accepted]
                        assert records['updated']['pending_upgrade'] and records['updated']['rollback_available']
                        assert records['updated']['previous_package_sha256'] == report['artifacts']['old']['signed_sha256']
                    if mode == 'cold':
                        print('CHECK: final public WAD export', flush=True)
                        wad = folder / 'freedoom1.wad'
                        FileClient(channel.app_client, timeout=180).export_file(APP, 'freedoom1.wad', wad)
                        expected = json.loads((ROOT / 'sdk/ports/doom/assets.json').read_text(encoding='utf-8'))['files']['freedoom1.wad']
                        records['wad'] = {'bytes': wad.stat().st_size, 'sha256': digest(wad)}
                        assert records['wad'] == {key: expected[key] for key in ('bytes', 'sha256')}
                finally:
                    records['observations'] = probe.records
                    write_json(folder / 'observations.json', records)
                    if channel.owned_process.poll() is None:
                        normal.close()
                    else:
                        normal.qtest.close()
                        normal.qmp.close()

            try:
                with opened(projects['old'], case) as (workspace, _), access(records) as mutation:
                    try:
                        runtime = runner.exercise(packages[active], ROOT / 'build/qemu-prime-g2/qemu-system-arm', args.firmware,
                                                  workspace=workspace, prepare_workspace=prepare, controls=controls,
                                                  measure_resources=True)
                    except reset.AbruptStop:
                        assert mode == 'cut' and records['cut']['process_returncode'] == -signal.SIGKILL
                        runtime = {'abrupt_stop': True, 'graceful_cleanup': False}
                        records['cut_overlay_bytes'] = (workspace / 'nand.overlay').stat().st_size
                    except ExpectedRejection:
                        assert mode == 'rollback-deny' and records['rejection']['status']['error'] == 8
                        runtime = {'expected_install_rejection': True, 'os_responsive': True}
                    else:
                        assert mode not in ('cut', 'rollback-deny') and runtime['result'] == 1 and runtime['os_responsive'], runtime
                        if mode == 'accept':
                            assert records['clean_exit']['exited'] and records['clean_exit']['exit_status'] == 0, records
                    records['overlay_sha256'] = digest(workspace / 'nand.overlay')
                report['cases'].append({'phase': label, 'records': records, 'runtime': runtime})
                write_json(out / 'report.json', report)
                print('PASS:', label, flush=True)
            except BaseException as error:
                report.update(status='failed', failed_phase=label,
                              error={'type': type(error).__name__, 'message': str(error)[:4096]})
                write_json(out / 'report.json', report)
                raise
    report['status'] = 'passed'
    write_json(out / 'report.json', report)


if __name__ == '__main__':
    main()
