# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded public input tests through KPP/Goodix and normal OS dispatch."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from build import contract, digest, identity, write_json
from runner import Channel, exercise
from sdk_environment import SDK

KEYS = json.loads((SDK / 'contracts/keys.json').read_text(encoding='utf-8'))
NAME = re.compile(r'[a-zA-Z][a-zA-Z0-9_-]{0,47}')


def bounded_integer(value, lower, upper):
    return type(value) is int and lower <= value <= upper


def validate(value):
    if not isinstance(value, dict) or set(value) != {'schema', 'name', 'steps'} or type(value['schema']) is not int or value['schema'] != 1:
        raise ValueError('replay requires schema 1, name and steps')
    if not isinstance(value['name'], str) or not NAME.fullmatch(value['name']):
        raise ValueError('invalid replay name')
    if not isinstance(value['steps'], list) or not 1 <= len(value['steps']) <= 256:
        raise ValueError('replay requires 1–256 steps')
    snapshots, elapsed = set(), 0
    for step in value['steps']:
        if not isinstance(step, dict) or len(step) != 1:
            raise ValueError('each step must contain exactly one action')
        action, data = next(iter(step.items()))
        if action == 'key':
            if not isinstance(data, str) or data not in KEYS:
                raise ValueError('unknown Prime key')
            elapsed += 1000
        elif action == 'keys':
            if (not isinstance(data, list) or len(data)>len(KEYS) or
                not all(isinstance(name,str) and name in KEYS for name in data) or len(set(data))!=len(data)):
                raise ValueError('keys requires unique Prime key names; [] releases all held keys')
        elif action == 'touch':
            if not isinstance(data, list) or len(data) > 2:
                raise ValueError('touch requires zero, one or two contacts')
            ids = set()
            for contact in data:
                if (not isinstance(contact, list) or len(contact) != 3 or
                    not bounded_integer(contact[0], 0, 15) or
                    not bounded_integer(contact[1], 0, 319) or not bounded_integer(contact[2], 0, 239) or contact[0] in ids):
                    raise ValueError('touch contacts require unique id, x, y in display bounds')
                ids.add(contact[0])
            elapsed += 300
        elif action == 'wait_ms':
            if not bounded_integer(data, 0, 5000):
                raise ValueError('wait_ms must be 0–5000')
            elapsed += data
        elif action == 'program_exit':
            if not bounded_integer(data, -2147483648, 2147483647):
                raise ValueError('program_exit requires a signed 32-bit status')
            elapsed += 20000
        elif action == 'capture':
            if not isinstance(data, str) or not NAME.fullmatch(data) or data in snapshots:
                raise ValueError('capture name must be unique and safe')
            snapshots.add(data)
            elapsed += 300
        elif action in ('same', 'different'):
            if not isinstance(data, list) or len(data) != 2 or not all(isinstance(x, str) and x in snapshots for x in data):
                raise ValueError('image assertion must refer to two earlier captures')
        elif action == 'pixel':
            if (not isinstance(data, list) or len(data) != 4 or not isinstance(data[0], str) or data[0] not in snapshots or
                not bounded_integer(data[1], 0, 319) or not bounded_integer(data[2], 0, 239) or
                not isinstance(data[3], list) or len(data[3]) != 3 or not all(bounded_integer(c, 0, 255) for c in data[3])):
                raise ValueError('pixel requires capture, x, y, [red, green, blue]')
        elif action == 'relaunch':
            if data is not True:
                raise ValueError('relaunch requires true')
            elapsed += 11300  # Home/release, bounded storage drain, launch.
        else:
            raise ValueError(f'unsupported replay action: {action}')
    # Large bundled-data apps verify their on-device root before first play.
    # Keep a finite bound while allowing that real storage work to finish.
    if elapsed > 180000:
        raise ValueError('replay exceeds 180 seconds of requested interaction')
    return value


def load(path):
    if path.is_symlink() or path.stat().st_size > 65536:
        raise ValueError('replay must be a regular JSON file of at most 64 KiB')
    return validate(json.loads(path.read_text(encoding='utf-8')))


@contextmanager
def control_session(device):
    failure = None
    try:
        yield device
    except (Exception, KeyboardInterrupt) as error:
        failure = error
        raise
    finally:
        try:
            device.close()
        except Exception as error:
            if failure is None:
                raise
            device.cleanup_errors = [*getattr(device, 'cleanup_errors', []), type(error).__name__]


class Controls:
    def __init__(self, channel, output):
        self.channel, self.output = channel, output
        folder = channel.session_directory
        self.qtest = Channel(folder / 'qtest', None)
        self.qmp = Channel(folder / 'qmp', None)
        json.loads(self.qmp.file.readline())
        self.execute('qmp_capabilities')
        self.frames = {}
        self.assertions = 0
        self.held_keys = set()
        self.cleanup_errors = []

    def execute(self, command, arguments=None):
        self.qmp.file.write((json.dumps({'execute': command, 'arguments': arguments or {}}) + '\n').encode())
        while True:
            line = self.qmp.file.readline(65536)
            if not line:
                raise RuntimeError('emulator monitor closed')
            response = json.loads(line)
            if 'event' in response:
                continue
            if 'error' in response:
                raise RuntimeError(str(response['error']))
            return response

    def key_edge(self, name, down):
        row, col = KEYS[name]
        self.qtest.file.write(f'writew 0x020b8008 {(row << 8) | col | (0x8000 if down else 0):#x}\n'.encode())
        while True:
            reply = self.qtest.file.readline(4096)
            if reply.startswith(b'IRQ'):
                continue
            if not reply.startswith(b'OK'):
                raise RuntimeError('key injection failed')
            break

    def keys(self, names):
        wanted = set(names)
        for name in sorted(self.held_keys-wanted):
            self.key_edge(name, False)
            self.held_keys.remove(name)
        for name in sorted(wanted-self.held_keys):
            self.key_edge(name, True)
            self.held_keys.add(name)

    def key(self, name):
        if name in self.held_keys:
            raise ValueError('key is already held; use keys to release it before pressing again')
        state = self.channel.command('STATE').split(' home_row=')[0]
        sequence = self.channel.command('APP DIAG 7')
        normal_app_key = (state == getattr(self.channel, 'native_state', None)
                          and name not in ('back', 'home', 'apps', 'shift', 'alpha'))
        failure = None
        try:
            self.key_edge(name,True)
            if normal_app_key and sequence.startswith('VALUE '):
                deadline = time.monotonic() + 5
                while self.channel.command('APP DIAG 7') == sequence:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('normal OS dispatch did not deliver the key')
                    time.sleep(.01)
                # Logical dispatch can precede the stream's stable down edge.
                time.sleep(.05)
            else:
                time.sleep(.25)
        except (Exception, KeyboardInterrupt) as error:
            failure = error
            raise
        finally:
            try:
                self.key_edge(name,False)
                # Leave enough time for release to traverse normal debouncing.
                time.sleep(.75)
            except Exception as error:
                if failure is None:
                    raise
                self.cleanup_errors.append(type(error).__name__)

    def run(self, replay, records):
        from PIL import Image
        for index, step in enumerate(replay['steps']):
            action, value = next(iter(step.items()))
            record = {'step': index, 'action': action, 'status': 'running'}
            records.append(record)
            try:
                if action == 'key':
                    self.key(value)
                elif action == 'keys':
                    self.keys(value)
                elif action == 'touch':
                    command = 'TOUCH FRAME ' + str(len(value)) + ''.join(' ' + ' '.join(map(str, p)) for p in value)
                    if self.channel.command(command) != 'OK':
                        raise RuntimeError('Goodix injection failed')
                    time.sleep(.3)
                elif action == 'wait_ms':
                    time.sleep(value / 1000)
                elif action == 'program_exit':
                    deadline = time.monotonic() + 20
                    while int(self.channel.command('APP DIAG 15').split()[1]) == 0:
                        fault = int(self.channel.command('APP DIAG 9').split()[1])
                        if fault:
                            if fault >= 2**31: fault -= 2**32
                            pc = int(self.channel.command('APP DIAG 10').split()[1])
                            record.update(fault_code=fault, fault_pc=pc)
                            raise AssertionError(f'program faulted before exit: {fault} at {pc:#x}')
                        if time.monotonic() >= deadline:
                            raise AssertionError('program did not exit within 20 seconds')
                        time.sleep(.025)
                    status = int(self.channel.command('APP DIAG 21').split()[1])
                    if status >= 2**31: status -= 2**32
                    if status != value:
                        raise AssertionError(f'program exited with {status}, expected {value}')
                    record['exit_status'] = status
                    self.assertions += 1
                elif action == 'capture':
                    time.sleep(.3)
                    path = self.output / (value + '.ppm')
                    self.execute('screendump', {'filename': str(path.resolve())})
                    self.frames[value] = path
                    record['sha256'] = digest(path)
                elif action in ('same', 'different'):
                    with Image.open(self.frames[value[0]]) as a, Image.open(self.frames[value[1]]) as b:
                        same = a.size == b.size and a.convert('RGB').tobytes() == b.convert('RGB').tobytes()
                    if same != (action == 'same'):
                        raise AssertionError(f'{value[0]} and {value[1]} expected {action}')
                    self.assertions += 1
                elif action == 'pixel':
                    with Image.open(self.frames[value[0]]) as img:
                        if img.convert('RGB').getpixel((value[1], value[2])) != tuple(value[3]):
                            raise AssertionError(f'pixel assertion failed in {value[0]}')
                    self.assertions += 1
                elif action == 'relaunch':
                    # A main return leaves its last frame in the native app
                    # container. Leave through normal input before reopening;
                    # opening that same active container is not a new launch.
                    self.key('home')
                    if hasattr(self.channel, 'wait_for_storage'):
                        self.channel.wait_for_storage(timeout=10)
                    if hasattr(self.channel, 'preview_size'):
                        if self.channel.command(f'APP LOAD {self.channel.preview_size}') != 'OK':
                            raise RuntimeError('app preview reload failed')
                    command = f'APP OPEN {self.channel.installed_slot}' if hasattr(self.channel, 'installed_slot') else 'APP LAUNCH'
                    if self.channel.command(command) != 'OK':
                        raise RuntimeError('app relaunch failed')
                    time.sleep(.3)
                crash = self.channel.command('APP DIAG 9')
                if crash.startswith('VALUE '):
                    code = int(crash.split()[1])
                    if code >= 2**31:
                        code -= 2**32
                    if code < 0:
                        raise RuntimeError(f'app fault during replay: {code}')
                record['status'] = 'passed'
            except KeyboardInterrupt:
                record.update(status='cancelled', error='Replay interrupted')
                raise
            except Exception as exc:
                record.update(status='failed', error=str(exc))
                raise

    def close(self):
        # Release every held contact even when an assertion fails.
        try:
            self.keys([])
            self.channel.command('TOUCH FRAME 0')
        finally:
            try:
                self.qtest.close()
            finally:
                self.qmp.close()


def _save_report(project, report):
    states = ('passed', 'failed', 'skipped') + tuple(state for state in ('not_run', 'running', 'cancelled')
        if any(case['status'] == state for case in report['cases']))
    report['summary'] = {state: sum(case['status'] == state for case in report['cases']) for state in states}
    write_json(project / 'build/run.json', report)


def _run_replays(project, package, qemu, firmware, suite, workspace, measure_resources, report):
    if suite != 'all' and (Path(suite).is_absolute() or '..' in Path(suite).parts):
        raise ValueError('Suite must be a project-relative replay JSON path')
    files = sorted((project / 'tests').rglob('*.json')) if suite == 'all' else [project / suite]
    if len(files) > 32:
        raise ValueError('at most 32 replay files per suite')
    cases = [(path, load(path)) for path in files]
    if len({replay['name'] for _, replay in cases}) != len(cases):
        raise ValueError('replay names must be unique within a suite')
    output = project / 'build/tests'
    output.mkdir(parents=True, exist_ok=True)
    if not cases:
        report['cases'].append({'name': 'author-interactions', 'status': 'skipped', 'reason': 'no tests/*.json'})
        cases = [(None, {'name': 'platform-startup', 'steps': []})]
    pending = []
    for path, replay in cases:
        item = {'name': replay['name'], 'status': 'not_run', 'steps': [], 'assertions': 0}
        if path:
            item['test_sha256'] = digest(path)
        report['cases'].append(item)
        pending.append((replay, item))
    report['phase'] = 'execution'
    for replay, item in pending:
        item['status'] = 'running'
        _save_report(project, report)
        destination = output / replay['name']
        destination.mkdir(exist_ok=True)
        def controls(channel):
            device = Controls(channel, destination)
            try:
                with control_session(device):
                    device.run(replay, item['steps'])
            finally:
                item['assertions'] = device.assertions
                if getattr(device, 'cleanup_errors', None):
                    item['cleanup_errors'] = device.cleanup_errors
        try:
            from bundled_data import prepare as prepare_data, install as install_data
            data_spec, data_parts = prepare_data(project)
            prepare_files = None
            if data_spec:
                from lfapp import unpack
                app_id = unpack(package.read_bytes())[0]['id']
                prepare_files = lambda client: install_data(client, app_id, data_spec, [data for _, data in data_parts])
            result = exercise(package, qemu, firmware, controls=controls, workspace=workspace, prepare_workspace=prepare_files, measure_resources=measure_resources,diagnostics_dir=destination/'emulator')
            item['runtime'] = result
            report['persistence'] = result['persistence']
            if result['result'] != 1 or not result['os_responsive']:
                raise RuntimeError(f"callback failed: {result['result']}")
            status = (result.get('program') or {}).get('exit_status')
            if status not in (None, 0) and not any(step.get('program_exit') == status for step in replay['steps']):
                raise RuntimeError(f'program exited with status {status}')
            item['status'] = 'passed'
        except (OSError, ValueError, RuntimeError, AssertionError) as exc:
            item.update(status='failed', error=str(exc))
            if hasattr(exc,'emulator_failure'):item['emulator_failure']=exc.emulator_failure
        _save_report(project, report)
    report['status'] = 'failed' if any(c['status'] == 'failed' for c in report['cases']) else 'passed'
    report['phase'] = 'complete'
    _save_report(project, report)
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'passed' else 1


def test_project(project, package, qemu, firmware, suite='all', workspace=None, measure_resources=False):
    report = {'schema': 1, 'validation': 'developer-local', 'independently_verified': False,
              'status': 'running', 'phase': 'validation', 'target': 'prime_g2_vm', 'layer': 'arm-interaction',
              'persistence': 'installed-workspace' if workspace else 'not_tested', 'physical': 'not_tested', 'cases': []}
    (project / 'build').mkdir(parents=True, exist_ok=True)
    # Invalidate the earlier pass before inspecting or running this suite. A
    # hard-killed process leaves an explicit incomplete report, never that pass.
    _save_report(project, report)
    try:
        report.update(sdk=contract(SDK)['sdk'], sdk_sha256=identity(SDK), package_sha256=digest(package),
                      firmware_sha256=digest(firmware), qemu_sha256=digest(qemu))
        return _run_replays(project, package, qemu, firmware, suite, workspace, measure_resources, report)
    except (Exception, KeyboardInterrupt) as error:
        status = 'cancelled' if isinstance(error, KeyboardInterrupt) else 'failed'
        message = 'Replay interrupted' if status == 'cancelled' else str(error)
        report.update(status=status, error=message)
        for case in report['cases']:
            if case['status'] == 'running':
                case.update(status=status, error=message)
                for step in case['steps']:
                    if step['status'] == 'running':
                        step.update(status=status, error=message)
        try:
            _save_report(project, report)
        except OSError as save_error:
            print('Could not save incomplete replay report: ' + str(save_error), file=sys.stderr)
        raise
