#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualified C subset on ARM, public stdio/files and synthetic descriptor boundaries.

The boundary cases seed only the emulator's handle serial and the fixture gate
with GDB. They do not simulate 32768 real opens or qualify physical endurance.
All allocation, file operations, commits and exports use the normal SDK/OS.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, identity, write_json
from files_device import FileClient
from replay import Controls
from runner import exercise
from workspace import opened

STREAM_LIFECYCLES = ('stdio-update', 'stdio-append', 'stdio-snapshots', 'stdio-position')
MODES = ('memory', 'strings', 'numbers', 'math', 'stdio', 'descriptors', *STREAM_LIFECYCLES,
         'file-errors', 'unsupported', 'exit', 'immediate-exit',
         'implicit-exit', 'implicit-error', 'immediate-unclosed', 'flush-all')
UNCLOSED = ('implicit-exit', 'implicit-error', 'immediate-unclosed', 'flush-all')
BOUNDARIES = {'handles-32767': 32766, 'handles-65535': 65534,
              'handles-int-max': 2147483630}


def gdb(normal, folder, name, commands):
    endpoint = Path(normal.channel.socket.getpeername()).parent / 'c-profile-gdb'
    normal.execute('human-monitor-command', {'command-line':
        'gdbserver unix:' + str(endpoint) + ',server=on,wait=off'})
    script = folder / (name + '.gdb')
    script.write_text('set pagination off\nset confirm off\ntarget remote ' + str(endpoint) +
                      '\n' + '\n'.join(commands) + '\ndetach\nquit\n')
    result = subprocess.run([shutil.which('arm-none-eabi-gdb'), '-q', '-nx', '-batch', '-x', str(script)],
                            capture_output=True, text=True, timeout=30)
    (folder / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def expected_files(mode):
    if mode == 'stdio-update':
        content = bytearray(((i * 131 + (i >> 8)) ^ 0x5d) & 255 for i in range(262175))
        content[130940:130977] = b'A' * 37
        content[261880:261897] = b'B' * 17
        return {'multi-update': bytes(content)}
    if mode == 'stdio-append':
        return {'append-existing': b'seedfirstnextlast', 'append-new': b'one'}
    if mode == 'stdio-snapshots': return {'snapshot-moved': b'replacement'}
    if mode == 'stdio-position': return {'seek-gap': b'head' + bytes(262151 - 4) + b'tail'}
    pattern = bytes(((i * 131 + (i >> 8)) ^ 0x5d) & 255 for i in range(65549))
    return {'stdio': {'large': pattern, 'text': b'42 1.25\nhello\nZ'},
            'descriptors': {'descriptor-output': pattern[:2048] + bytes(2048) + b'ZA'},
            'file-errors': {'present': b'safe'}, 'high-handles': {'high-handle': b'safe'},
            'exit': {'exit-order': b'MBA'}, 'immediate-exit': {'exit-order': b'M'},
            'implicit-exit': {'automatic': b'after'}, 'implicit-error': {'automatic': b'after'},
            'immediate-unclosed': {'automatic': b'before'}, 'flush-all': {'automatic': b'onetwothree'}}.get(mode, {})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--firmware-debug', type=Path, help='Matching symbols for synthetic boundary cases')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sdk', type=Path, default=ROOT / 'sdk', help='SDK source from the checkout or a relocated kit')
    parser.add_argument('--profile', choices=('debug', 'release'), default='debug')
    parser.add_argument('--comparison-picolibc', type=Path, help='Isolated comparison sysroot; not an SDK runtime selection')
    parser.add_argument('--keep-going', action='store_true', help='Record independent failed cases and continue; failures still exit nonzero')
    parser.add_argument('--cases', nargs='+', choices=(*MODES, *BOUNDARIES))
    args = parser.parse_args()
    sdk = args.sdk.resolve()
    cases = args.cases or [*MODES, *BOUNDARIES]
    firmware = args.firmware.resolve()
    symbols = (args.firmware_debug or firmware.with_name(firmware.stem + '-debug.elf')).resolve()
    if any(c in BOUNDARIES for c in cases) and not symbols.is_file():
        parser.error('Boundary cases require matching firmware debug ELF')
    output = args.output.resolve(); output.mkdir(parents=True)
    qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    sources = ['vm/test-sdk-c-profile.py', 'tests/native/sdk_c_profile.c', 'scripts/build_sdk_newlib.py']
    if args.comparison_picolibc:
        import sdk_picolibc_probe
        runtime_identity = sdk_picolibc_probe.resolve(args.comparison_picolibc)['identity']
        sources += ['vm/sdk_picolibc_probe.py', 'scripts/build_sdk_picolibc_comparison.py']
    else:
        runtime_identity = json.loads(subprocess.check_output([sys.executable, '-c',
            'import json,sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]+"/tools"); '
            'from runtime import resolve; print(json.dumps(resolve(Path(sys.argv[1]))["identity"]))', str(sdk)], text=True, timeout=30))
    report = {'schema': 1, 'status': 'running', 'physical': 'not_tested', 'profile': args.profile,
        'sdk_sha256': identity(sdk), 'library': runtime_identity, 'failures': [],
        'firmware_sha256': digest(firmware), 'qemu_sha256': digest(qemu), 'cases': [],
        'sources': {name: digest(ROOT / name) for name in sources}}
    if any(c in BOUNDARIES for c in cases): report['firmware_debug_sha256'] = digest(symbols)
    write_json(output / 'report.json', report)
    try:
        with tempfile.TemporaryDirectory(prefix='lefony-c-profile-') as temp:
            def run_case(case):
                mode = 'high-handles' if case in BOUNDARIES else case
                project = Path(temp) / case; (project / 'src').mkdir(parents=True)
                shutil.copyfile(ROOT / 'tests/native/sdk_c_profile.c', project / 'src/main.c')
                metadata = json.loads((ROOT / 'sdk/examples/c-main/app.json').read_text())
                metadata.update(id='c-profile', name='C Profile', minimum_api=12, required_capabilities=8280)
                write_json(project / 'app.json', metadata)
                write_json(project / 'project.json', {'schema': 2,
                    'runtime': 'picolibc-comparison-1' if args.comparison_picolibc else 'foreground-newlib-1',
                    'sources': ['src/main.c'], 'arguments': [mode]})
                if args.comparison_picolibc:
                    artifact = sdk_picolibc_probe.package(project, sdk, args.comparison_picolibc, args.profile)
                else:
                    subprocess.run([sys.executable, str(sdk / 'tools/cli.py'), '--project', str(project),
                                    'package', '--profile', args.profile], check=True, timeout=120)
                    artifact = project / 'build' / (metadata['id'] + '-' + metadata['version'] + '.lfapp')
                retained = output / case; retained.mkdir()
                for name in ('app-debug.elf', 'app.elf', 'app.map', 'build.json', artifact.name):
                    shutil.copyfile(project / 'build' / name, retained / name)
                for name in ('app.json', 'project.json', 'sdk.lock.json'):
                    shutil.copyfile(project / name, retained / name)
                shutil.copyfile(project / 'src/main.c', retained / 'main.c')
                if args.comparison_picolibc:
                    shutil.copytree(project / 'build/picolibc-adapter', retained / 'picolibc-adapter')
                for phase in ('initial', 'cold') if mode in ('stdio', 'descriptors', *UNCLOSED, *STREAM_LIFECYCLES) else ('initial',):
                    folder = retained / phase; folder.mkdir(); measured = {}
                    expected = expected_files(mode)
                    def setup(client):
                        if phase == 'initial' and mode in UNCLOSED:
                            before = folder / 'import-before'; before.write_bytes(b'before')
                            FileClient(client).import_file('c-profile', 'automatic', before)
                        if phase == 'cold':
                            for path, content in expected.items():
                                FileClient(client).export_file('c-profile', path, folder / ('before-' + path))
                                assert (folder / ('before-' + path)).read_bytes() == content
                    def controls(channel):
                        normal = Controls(channel, folder)
                        try:
                            if case in BOUNDARIES:
                                seed = BOUNDARIES[case]
                                owner = "'PrimeG2::AppManagement::(anonymous namespace)::sFiles'.m_handleSerial"
                                text = gdb(normal, folder, 'seed', [
                                    'file ' + json.dumps(str(symbols)), 'set variable ' + owner + '=' + str(seed),
                                    'print ' + owner, 'symbol-file ' + json.dumps(str(retained / 'app-debug.elf')),
                                    'set variable profile_gate=1', 'print profile_gate'])
                                assert re.search(r'\$1 = ' + str(seed) + r'\b', text) and '$2 = 1' in text
                                measured['synthetic_handle_serial_seed'] = seed
                            started = time.monotonic()
                            while channel.command('APP DIAG 15') == 'VALUE 0':
                                fault = channel.command('APP DIAG 9')
                                if fault != 'VALUE 0':
                                    pc = int(channel.command('APP DIAG 10').split()[1])
                                    location = subprocess.check_output(['arm-none-eabi-addr2line', '-if',
                                        '-e', str(retained / 'app-debug.elf'), hex(pc)], text=True)
                                    raise AssertionError((case, phase, fault, location))
                                assert time.monotonic() - started < 180, 'C profile completion deadline'
                                time.sleep(.025)
                            assert channel.command('APP DIAG 9') == 'VALUE 0'
                            status = int(channel.command('APP DIAG 21').split()[1])
                            measured.update(exit_status=status, program_wall_seconds=time.monotonic() - started)
                            expected_status = 7 if mode in ('exit', 'immediate-exit', 'implicit-error', 'immediate-unclosed') else 0
                            if status != expected_status:
                                lines = (retained / 'main.c').read_text().splitlines()
                                line = lines[status - 1] if 0 < status <= len(lines) else 'unknown'
                                raise AssertionError(f'{case}/{phase}: CHECK line {status}: {line}')
                            if case in BOUNDARIES:
                                text = gdb(normal, folder, 'handles', [
                                    'file ' + json.dumps(str(retained / 'app-debug.elf')), 'print profile_handles'])
                                handles = [int(n) for n in re.search(r'\$1 = \{([^}]+)\}', text)[1].split(',')]
                                assert handles == list(range(BOUNDARIES[case] + 1, BOUNDARIES[case] + 9)), handles
                                measured['handles'] = handles
                            normal.key('home'); channel.wait_for_storage()
                            files = FileClient(channel.app_client)
                            exports = {}
                            for path, content in expected.items():
                                exports[path] = files.export_file('c-profile', path, folder / path)
                                assert (folder / path).read_bytes() == content, path
                            paths = set(expected)
                            if expected_status == 0 and mode not in UNCLOSED:
                                exports['profile-result'] = files.export_file('c-profile', 'profile-result', folder / 'profile-result')
                                label, count = (folder / 'profile-result').read_text().split()
                                assert label == mode and int(count) > 0
                                measured['checks_before_report'] = int(count); paths.add('profile-result')
                            assert {e['path'] for e in files.list('c-profile')['entries']} == paths
                            measured['exports'] = exports
                        finally: normal.close()
                    with opened(project, 'profile') as (workspace, _):
                        result = exercise(artifact, qemu, firmware, workspace=workspace,
                                          prepare_workspace=setup, controls=controls)
                    assert result['result'] == 1 and result['os_responsive'], result
                    report['cases'].append({'case': case, 'phase': phase, 'runtime': result, **measured})
                    write_json(output / 'report.json', report); print('PASS:', case, phase, flush=True)
            for case in cases:
                try: run_case(case)
                except Exception as exc:
                    if not args.keep_going: raise
                    report['failures'].append({'case': case, 'error': str(exc)})
                    write_json(output / 'report.json', report); print('FAIL:', case, str(exc), flush=True)
        assert report['sources'] == {name: digest(ROOT / name) for name in sources}, 'Inputs changed during validation'
        assert report['sdk_sha256'] == identity(sdk), 'SDK changed during validation'
        report['status'] = 'failed' if report['failures'] else 'passed'; write_json(output / 'report.json', report)
        return 1 if report['failures'] else 0
    except BaseException as exc:
        report.update(status='failed', error=str(exc)); write_json(output / 'report.json', report); raise


if __name__ == '__main__': sys.exit(main())
