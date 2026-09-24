# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual child exits, full stderr pipes and stale startup-report handling."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest
from test_native_app_package import META, image

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'sdk/tools'))
import runner
from emulator_failure import Capture, LIMIT, record, tail
from lfapp import pack


@pytest.fixture
def failing_emulator(tmp_path, monkeypatch):
    package=tmp_path/'sample.lfapp';package.write_bytes(pack(META,image()))
    firmware=tmp_path/'firmware.elf';firmware.write_bytes(b'fixture firmware')
    qemu=tmp_path/'qemu.py'
    qemu.write_text('''import os,socket,sys,time
from pathlib import Path
mode=sys.argv[1];args=sys.argv[2:]
os.write(2,b'x'*262144+b'known host failure\\n')
if mode=='boot':os._exit(17)
uart=Path(next(a[5:] for a in args if a.startswith('file:')))
path=next(a.split('path=',1)[1].split(',',1)[0] for a in args if a.startswith('socket,id=appcontrol,'))
with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
 server.bind(path);server.listen(1)
 uart.write_text('entering calculator runtime\\n')
 with server.accept()[0] as connection:
  assert connection.recv(128)==b'PING\\n'
  connection.sendall(b'PO')
  if mode=='partial':os._exit(19)
  connection.shutdown(socket.SHUT_WR)
  time.sleep(60)
''')
    original=subprocess.Popen;children=[]
    def use(mode):
        def launch(arguments,**options):
            assert arguments[0]==str(qemu)
            child=original([sys.executable,str(qemu),mode,*arguments[1:]],**options);children.append(child)
            return child
        monkeypatch.setattr(runner.subprocess,'Popen',launch)
        return package,qemu,firmware,children
    yield use
    for child in children:
        if child.poll() is None:child.kill();child.wait(timeout=5)


@pytest.mark.parametrize('mode,phase,code',[('boot','boot',17),('partial','control-handshake',19),('alive','control-handshake',None)])
def test_actual_child_failure_records_bounded_logs_and_original_outcome(failing_emulator,tmp_path,mode,phase,code):
    if mode!='boot' and not hasattr(__import__('socket'),'AF_UNIX'):pytest.skip('Host Python AF_UNIX fixture required')
    package,qemu,firmware,children=failing_emulator(mode)
    output=tmp_path/'diagnostics';started=time.monotonic()
    with pytest.raises(RuntimeError) as caught:
        runner.exercise(package,qemu,firmware,diagnostics_dir=output)
    assert time.monotonic()-started<5
    report=caught.value.emulator_failure
    assert report['phase']==phase
    assert report['command']==(None if mode=='boot' else 'PING')
    assert report['process']['stderr_complete'] and report['process']['stderr_truncated']
    assert report['process']['stderr_retained_bytes']==LIMIT
    assert report['process']['stderr_bytes']==262144+len(b'known host failure\n')
    if code is not None:assert report['process']['exit_after_cleanup']==code
    else:
        assert report['process']['exit_at_failure'] is None
        assert report['process']['cleanup_action']=='terminated-for-cleanup'
    assert all(child.poll() is not None for child in children)
    folder=output/report['directory'];saved=json.loads((folder/'failure.json').read_text())
    assert saved==report and str(tmp_path) not in json.dumps(saved)
    assert (folder/'stderr.log').stat().st_size==LIMIT
    assert (folder/'stderr.log').read_bytes().endswith(b'known host failure\n')
    assert report['identities']['package_sha256']==hashlib.sha256(package.read_bytes()).hexdigest()
    assert report['identities']['qemu_sha256']==hashlib.sha256(qemu.read_bytes()).hexdigest()
    assert not any(t.name=='lefony-qemu-stderr' for t in threading.enumerate())


def test_failed_startup_replaces_previous_success_report(failing_emulator,tmp_path):
    package,qemu,firmware,_=failing_emulator('boot')
    path=tmp_path/'run.json';path.write_text('{"status":"passed","result":1,"os_responsive":true}')
    with pytest.raises(RuntimeError):runner.run(package,qemu,firmware,True,True)
    report=json.loads(path.read_text())
    assert report['status']=='failed' and report['result'] is None and not report['os_responsive']
    assert report['emulator_failure']['process']['exit_after_cleanup']==17
    assert len(list((tmp_path/'emulator').glob('failure-*/failure.json')))==1


def test_replay_preserves_failure_summary_without_embedding_raw_logs(failing_emulator,tmp_path):
    from replay import test_project
    package,qemu,firmware,_=failing_emulator('boot')
    assert test_project(tmp_path,package,qemu,firmware)==1
    report=json.loads((tmp_path/'build/run.json').read_text());case=report['cases'][-1]
    assert report['status']=='failed' and case['emulator_failure']['process']['exit_after_cleanup']==17
    assert 'known host failure' not in json.dumps(report) and len(json.dumps(report))<10000
    assert len(list((tmp_path/'build/tests/platform-startup/emulator').glob('failure-*/stderr.log')))==1


def test_control_close_error_does_not_hide_primary_failure_or_leave_child(failing_emulator,tmp_path,monkeypatch):
    if not hasattr(__import__('socket'),'AF_UNIX'):pytest.skip('Host Python AF_UNIX fixture required')
    package,qemu,firmware,children=failing_emulator('alive');original=runner.Channel.close
    def failed_close(self):original(self);raise OSError('fixture close failure')
    monkeypatch.setattr(runner.Channel,'close',failed_close)
    with pytest.raises(RuntimeError,match='control response was incomplete') as caught:
        runner.exercise(package,qemu,firmware,diagnostics_dir=tmp_path/'diagnostics')
    assert caught.value.emulator_failure['cleanup_errors']==[{'resource':'control','error':'OSError'}]
    assert all(child.poll() is not None for child in children)


def test_control_close_error_preserves_cancellation_and_stops_actual_child(failing_emulator,tmp_path,monkeypatch):
    if not hasattr(__import__('socket'),'AF_UNIX'):pytest.skip('Host Python AF_UNIX fixture required')
    package,qemu,firmware,children=failing_emulator('alive');original=runner.Channel.close
    def cancelled(*args):raise KeyboardInterrupt('cancelled control handshake')
    def failed_close(self):original(self);raise OSError('fixture close failure')
    monkeypatch.setattr(runner.Channel,'command',cancelled)
    monkeypatch.setattr(runner.Channel,'close',failed_close)
    with pytest.raises(KeyboardInterrupt,match='cancelled control handshake'):
        runner.run(package,qemu,firmware,True,True)
    report=json.loads((tmp_path/'run.json').read_text())
    assert report['status']=='cancelled' and all(child.poll() is not None for child in children)
    assert not any(t.name=='lefony-qemu-stderr' for t in threading.enumerate())


def test_preview_links_retained_failure_and_keeps_previous_frame(tmp_path):
    from preview import render
    from PIL import Image
    folder=tmp_path/'emulator/failure-example';folder.mkdir(parents=True)
    (folder/'failure.json').write_text('{}');Image.new('RGB',(320,240),'green').save(tmp_path/'frame.png')
    render(tmp_path,{'status':'failed','error':'emulator stopped','emulator_failure':{'directory':'failure-example'}})
    text=(tmp_path/'index.html').read_text()
    assert 'STALE' in text and 'Last successful frame' in text
    assert 'href="emulator/failure-example/failure.json"' in text
    render(tmp_path,{'status':'failed','emulator_failure':{'directory':'../escape'}})
    assert 'href=' not in (tmp_path/'index.html').read_text()


def test_cancelled_startup_cannot_leave_a_previous_pass(tmp_path,monkeypatch):
    package=tmp_path/'sample.lfapp';package.write_bytes(b'fixture')
    path=tmp_path/'run.json';path.write_text('{"status":"passed"}')
    def cancelled(*a,**kw):raise KeyboardInterrupt
    monkeypatch.setattr(runner,'exercise',cancelled)
    with pytest.raises(KeyboardInterrupt):runner.run(package,package,package,True,True)
    report=json.loads(path.read_text());assert report['status']=='cancelled' and report['result'] is None


def test_new_preview_validation_failure_clears_previous_emulator_diagnostics(tmp_path):
    from preview import once
    from PIL import Image
    output=tmp_path/'build/preview';output.mkdir(parents=True)
    folder=output/'emulator/failure-previous';folder.mkdir(parents=True)
    (folder/'failure.json').write_text('{}')
    (output/'status.json').write_text(json.dumps({'status':'failed','error':'old emulator failure',
        'emulator_failure':{'directory':'failure-previous'}}))
    Image.new('RGB',(320,240),'green').save(output/'frame.png')
    before=(output/'frame.png').read_bytes()
    result=once(tmp_path,tmp_path/'qemu',tmp_path/'firmware',reset_data=True,fresh_data=True)
    assert result['status']=='failed' and 'Choose either' in result['error']
    assert 'emulator_failure' not in result
    page=(output/'index.html').read_text()
    assert 'STALE' in page and 'emulator/failure-previous' not in page
    assert (output/'frame.png').read_bytes()==before and (folder/'failure.json').is_file()


def test_diagnostic_write_failure_does_not_replace_original_error(tmp_path):
    destination=tmp_path/'unusable';destination.write_bytes(b'existing file')
    error=RuntimeError('original failure')
    report,*_=record(error,{},b'host',tmp_path/'missing',identities={},command='PING',phase='boot',directory=destination)
    assert error.emulator_failure==report and report['save_error']['type']=='FileExistsError'
    assert str(error)=='original failure' and destination.read_bytes()==b'existing file'


def test_uart_tail_is_bounded_and_reports_original_length(tmp_path):
    path=tmp_path/'uart';path.write_bytes(b'A'*(LIMIT*4)+b'end')
    retained,total=tail(path)
    assert len(retained)==LIMIT and total==LIMIT*4+3 and retained.endswith(b'end')
