# SPDX-License-Identifier: GPL-3.0-or-later
"""Incomplete replays cannot leave a previous pass or lose completed cases."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
import replay


@pytest.fixture
def project(tmp_path):
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'build').mkdir()
    for number, name in enumerate(('first', 'second', 'third')):
        (tmp_path / 'tests' / f'{number}.json').write_text(json.dumps(
            {'schema': 1, 'name': name, 'steps': [{'wait_ms': 1}]}))
    (tmp_path / 'build/run.json').write_text('{"status":"passed","previous":true}')
    (tmp_path / 'artifact').write_bytes(b'dependency identity')
    return tmp_path


def run(project):
    artifact = project / 'artifact'
    return replay.test_project(project, artifact, artifact, artifact)


def state(project):
    return json.loads((project / 'build/run.json').read_text())


@pytest.mark.parametrize('failure,status', [(KeyboardInterrupt, 'cancelled'), (KeyError, 'failed')])
def test_incomplete_suite_keeps_prefix_and_marks_current_and_unstarted_cases(project, monkeypatch, failure, status):
    calls = []
    def exercise(*args, **options):
        current = state(project)
        assert current['status'] == 'running' and 'previous' not in current
        assert current['phase'] == 'execution'
        expected = ['running', 'not_run', 'not_run'] if not calls else ['passed', 'running', 'not_run']
        assert [case['status'] for case in current['cases']] == expected
        calls.append(options['diagnostics_dir'].parent.name)
        if len(calls) == 2:
            raise failure('interrupted fixture')
        return {'result': 1, 'os_responsive': True, 'persistence': 'not_tested'}
    monkeypatch.setattr(replay, 'exercise', exercise)
    with pytest.raises(failure):
        run(project)
    report = state(project)
    assert report['status'] == status and calls == ['first', 'second']
    assert [case['status'] for case in report['cases']] == ['passed', status, 'not_run']
    assert report['summary']['passed'] == 1 and report['summary']['not_run'] == 1
    assert report['summary'][status] == 1
    assert all(len(case['test_sha256']) == 64 for case in report['cases'])


@pytest.mark.parametrize('failure', ['invalid-json', 'duplicate-name', 'missing-input', 'absolute-suite', 'parent-suite'])
def test_validation_failure_invalidates_old_pass_before_any_emulator(project, monkeypatch, failure):
    monkeypatch.setattr(replay, 'exercise', lambda *a, **k: pytest.fail('emulator started after invalid input'))
    suite = 'all'
    if failure == 'invalid-json':
        (project / 'tests/0.json').write_text('{')
    elif failure == 'duplicate-name':
        (project / 'tests/1.json').write_bytes((project / 'tests/0.json').read_bytes())
    elif failure == 'missing-input':
        (project / 'artifact').unlink()
    else:
        suite = str(project / 'tests/0.json') if failure == 'absolute-suite' else '../test.json'
    with pytest.raises((ValueError, OSError)):
        replay.test_project(project, project / 'artifact', project / 'artifact', project / 'artifact', suite)
    report = state(project)
    assert report['status'] == 'failed' and report['phase'] == 'validation' and 'previous' not in report


def test_output_error_retains_completed_prefix_and_stops_later_tests(project, monkeypatch):
    (project / 'build/tests').mkdir()
    (project / 'build/tests/second').write_bytes(b'occupied destination')
    calls = []
    def exercise(*args, **options):
        calls.append(options['diagnostics_dir'].parent.name)
        return {'result': 1, 'os_responsive': True, 'persistence': 'not_tested'}
    monkeypatch.setattr(replay, 'exercise', exercise)
    with pytest.raises(FileExistsError):
        run(project)
    report = state(project)
    assert calls == ['first'] and report['status'] == 'failed'
    assert [case['status'] for case in report['cases']] == ['passed', 'failed', 'not_run']
    assert (project / 'build/tests/second').read_bytes() == b'occupied destination'


def test_cancellation_report_write_error_cannot_restore_previous_pass_or_hide_interrupt(project, monkeypatch):
    original = replay.write_json
    def write(path, value):
        if value['status'] == 'cancelled':
            raise OSError('fixture full disk')
        original(path, value)
    def cancel(*args, **options):
        raise KeyboardInterrupt('original interruption')
    monkeypatch.setattr(replay, 'write_json', write)
    monkeypatch.setattr(replay, 'exercise', cancel)
    with pytest.raises(KeyboardInterrupt, match='original interruption'):
        run(project)
    report = state(project)
    assert report['status'] == 'running' and 'previous' not in report


def test_unwritable_initial_report_prevents_any_replay(project, monkeypatch):
    def write(*args):
        raise PermissionError('read-only output')
    monkeypatch.setattr(replay, 'write_json', write)
    monkeypatch.setattr(replay, 'exercise', lambda *a, **k: pytest.fail('ran without invalidating previous pass'))
    with pytest.raises(PermissionError):
        run(project)
    assert state(project)['previous']  # No new run was allowed to begin.


def test_cleanup_failure_does_not_change_cancellation_into_test_failure(project, monkeypatch):
    class Controls:
        assertions = 2
        def __init__(self, *args): pass
        def run(self, value, records):
            records.extend([{'step': 0, 'status': 'passed'}, {'step': 1, 'status': 'running'}])
            raise KeyboardInterrupt
        def close(self):
            raise OSError('control disconnected during cancellation')
    monkeypatch.setattr(replay, 'Controls', Controls)
    monkeypatch.setattr(replay, 'exercise', lambda *a, **k: k['controls'](None))
    with pytest.raises(KeyboardInterrupt):
        run(project)
    report = state(project)
    first = report['cases'][0]
    assert report['status'] == first['status'] == 'cancelled'
    assert first['assertions'] == 2 and first['cleanup_errors'] == ['OSError']
    assert [step['status'] for step in first['steps']] == ['passed', 'cancelled']


def test_success_keeps_publication_compatible_summary(project, monkeypatch):
    monkeypatch.setattr(replay, 'exercise', lambda *a, **k:
        {'result': 1, 'os_responsive': True, 'persistence': 'not_tested'})
    assert run(project) == 0
    report = state(project)
    assert report['status'] == 'passed' and report['phase'] == 'complete'
    assert report['summary'] == {'passed': 3, 'failed': 0, 'skipped': 0}


def test_disconnected_key_release_cannot_mask_ctrl_c(monkeypatch):
    from types import SimpleNamespace
    device = replay.Controls.__new__(replay.Controls)
    device.held_keys = set()
    device.cleanup_errors = []
    device.channel = SimpleNamespace(command=lambda command: 'VALUE 0' if command.startswith('APP') else 'OS')
    edges = []
    def edge(name, down):
        edges.append((name, down))
        if not down:raise OSError('key release disconnected')
    def interrupt(*args):raise KeyboardInterrupt('user interrupted key hold')
    device.key_edge = edge
    monkeypatch.setattr(replay.time, 'sleep', interrupt)
    with pytest.raises(KeyboardInterrupt, match='user interrupted key hold'):
        device.key('shift')
    assert edges == [('shift', True), ('shift', False)]
    assert device.cleanup_errors == ['OSError']


@pytest.mark.parametrize('failure', [KeyboardInterrupt, RuntimeError])
def test_control_session_preserves_primary_error(failure):
    class Device:
        def close(self):raise OSError('closing disconnected input')
    device = Device()
    with pytest.raises(failure, match='primary'):
        with replay.control_session(device):raise failure('primary')
    assert device.cleanup_errors == ['OSError']


def test_control_session_reports_cleanup_error_without_a_primary_error():
    class Device:
        def close(self):raise OSError('closing disconnected input')
    with pytest.raises(OSError, match='closing disconnected'):
        with replay.control_session(Device()):pass
