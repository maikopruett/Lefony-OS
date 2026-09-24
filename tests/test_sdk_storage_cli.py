# SPDX-License-Identifier: GPL-3.0-or-later
"""Packaged storage commands retain input and device-access boundaries."""
from contextlib import nullcontext
import hashlib
import os
from pathlib import Path
import signal
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'sdk/tools'))
import cli
import emulator_usb
from archive_device import ArchiveUSB
from data_device import DataClient, encode_backup
from files_device import FileClient
from usb_files import LibUSB


def test_transfer_interrupt_waits_for_checkpoint_and_restores_handler():
    from usb_files import transfer_interrupts
    previous = signal.getsignal(signal.SIGINT)
    with transfer_interrupts() as checkpoint:
        signal.raise_signal(signal.SIGINT)
        signal.raise_signal(signal.SIGINT)
        transaction_finished = True
        with pytest.raises(KeyboardInterrupt):checkpoint()
        # Cleanup is protected even when Ctrl-C is pressed again.
        signal.raise_signal(signal.SIGINT)
    assert transaction_finished and signal.getsignal(signal.SIGINT) == previous


@pytest.mark.parametrize('stage', ['upload', 'commit', 'export'])
def test_archive_cli_interrupt_finishes_transfer_and_preserves_commit(tmp_path, monkeypatch, capsys, stage):
    import archive_device as archive
    from test_sdk_archive import PUBLIC, signed, snapshot, encoded
    from test_sdk_archive_device import Transport
    payload = encoded(snapshot(signed(), b'private', (('notes', b'hello'*1700), ('folder', None))))
    class Interrupted(Transport):
        interrupted = False
        completed_transfer = False
        def interrupt(self):
            self.interrupted = True
            signal.raise_signal(signal.SIGINT)
            signal.raise_signal(signal.SIGINT)
            self.completed_transfer = True
        def read(self, request, *args, **kwargs):
            raw = super().read(request, *args, **kwargs)
            if not self.interrupted and ((stage=='upload' and request==0x90 and self.operation==archive.RESTORE and self.offset)
                    or (stage=='export' and request==0x92 and self.operation==archive.EXPORT)):
                self.interrupt()
            return raw
        def write(self, request, *args, **kwargs):
            result = super().write(request, *args, **kwargs)
            if stage=='commit' and request==0x94:self.interrupt()
            if request==0x95:signal.raise_signal(signal.SIGINT)
            return result
    transport = Interrupted(payload)
    path = tmp_path/'archive'
    if stage=='export':
        transport.present = True;transport.generation = 1;path.write_bytes(b'previous archive')
        arguments = ['export', 'document', str(path), '--replace']
    else:
        path.write_bytes(payload);arguments = ['restore', str(path)]
    monkeypatch.setattr(cli, 'management_transport', lambda *a: nullcontext(transport))
    monkeypatch.setattr(sys, 'argv', ['lefony-sdk', 'archive', *arguments, '--public-key', str(PUBLIC)])
    assert cli.main() == (0 if stage=='commit' else 130)
    assert transport.interrupted and transport.completed_transfer
    writes = [request for request, *_ in transport.writes]
    if stage=='commit':
        assert writes.count(0x94)==1 and 0x95 not in writes and transport.committed==payload
        assert '"committed": true' in capsys.readouterr().out
    else:
        assert writes.count(0x95)==1 and 0x94 not in writes and transport.state==archive.CANCELLED
    if stage=='export':assert path.read_bytes()==b'previous archive' and len(list(tmp_path.iterdir()))==1


@pytest.mark.parametrize('family', ['files', 'data'])
@pytest.mark.parametrize('stage', ['upload', 'commit'])
def test_file_and_data_cli_interrupts_do_not_cancel_committed_data(tmp_path, monkeypatch, capsys, family, stage):
    import files_device as files
    contents = b'chosen input';source = tmp_path/'input'
    source.write_bytes(contents if family=='files' else encode_backup('notes', '1.0.0', 0, contents))
    state = {'sequence':1,'state':files.WRITABLE,'offset':0,'operation':files.IMPORT if family=='files' else files.DATA_IMPORT,
             'generation':2,'data_schema':0,'flags':0,'digest':hashlib.sha256(contents).digest()}
    writes = [];finished = []
    class Transport:
        def write(self, request, data=b'', **unused):
            writes.append(request)
            if request==0x72:state['offset']+=len(data)-8
            elif request==0x74:state.update(state=files.COMPLETE,flags=1)
            else:raise AssertionError(request)
            if request==(0x72 if stage=='upload' else 0x74):signal.raise_signal(signal.SIGINT)
            finished.append(request)
    def cancel(self, sequence):
        assert sequence==1;writes.append(0x75);signal.raise_signal(signal.SIGINT)
    kind = FileClient if family=='files' else DataClient
    monkeypatch.setattr(kind, 'info', lambda *_: {'generation':1,'data_schema':0,'app_schema':0,'pending_upgrade':False})
    monkeypatch.setattr(kind, '_begin', lambda *a, **kw: dict(state))
    monkeypatch.setattr(kind, 'status', lambda *_: dict(state))
    monkeypatch.setattr(kind, '_cancel', cancel)
    monkeypatch.setattr(cli, 'management_transport', lambda *a: nullcontext(Transport()))
    arguments = ['files', 'import', 'notes', 'saved', str(source)] if family=='files' else ['data','restore','notes',str(source)]
    monkeypatch.setattr(sys, 'argv', ['lefony-sdk', *arguments])
    assert cli.main()==(130 if stage=='upload' else 0)
    assert finished==([0x72] if stage=='upload' else [0x72,0x74])
    assert writes==([0x72,0x75] if stage=='upload' else [0x72,0x74])
    if stage=='commit':assert '"committed": true' in capsys.readouterr().out


def test_rollback_ctrl_c_after_preparation_cancels_without_commit(monkeypatch):
    from test_sdk_file_exchange import Host
    from usb_files import transfer_interrupts
    host=Host();client=DataClient(host);cancellations=[]
    monkeypatch.setattr(client,'info',lambda *_: {'rollback_available':True,'previous_package':7})
    def prepared(*args, **kwargs):
        signal.raise_signal(signal.SIGINT)
        return {'sequence':3,'state':3,'offset':0,'length':0}
    monkeypatch.setattr(client,'_begin',prepared)
    monkeypatch.setattr(client,'_cancel',cancellations.append)
    with transfer_interrupts() as cancelled, pytest.raises(KeyboardInterrupt):
        client.rollback('notes',cancelled=cancelled)
    assert cancellations==[3] and not host.writes


@pytest.mark.parametrize('family', ['files', 'archive'])
@pytest.mark.parametrize('outcome', ['ready', 'complete', 'changed', 'timeout'])
def test_cleanup_waits_for_owned_pending_command_before_sending_cancel(monkeypatch, family, outcome):
    import archive_device as archive
    from test_sdk_file_exchange import Host
    host=Host();host.clock=lambda:host.t;host.sleep=lambda n:setattr(host,'t',host.t+n)
    client=FileClient(host,timeout=.025) if family=='files' else archive.Client(host,timeout=.025)
    binding={'sequence':7,'nonce':b'n'*16,'operation':3};reads=[];writes=[]
    working=1;ready=3;complete=4 if family=='files' else archive.COMPLETE
    cancelled=6 if family=='files' else archive.CANCELLED
    def status():
        reads.append(True)
        state=cancelled if writes else (working if len(reads)<=2 or outcome=='timeout' else complete if outcome=='complete' else ready)
        return {**binding,'sequence':8 if outcome=='changed' and len(reads)>2 else 7,'state':state}
    def write(request,*args,**kwargs):
        assert len(reads)>=3 and outcome=='ready'
        writes.append(request)
    monkeypatch.setattr(client,'status',status);host.write=write
    client._cancel(7 if family=='files' else binding)
    assert writes==([0x75 if family=='files' else 0x95] if outcome=='ready' else [])
    assert host.t<=.03


@pytest.mark.parametrize('kind', ['malformed', 'wrong-app', 'oversized', 'fifo'])
def test_data_restore_rejects_bad_backup_before_opening_usb(kind, tmp_path, monkeypatch):
    backup = tmp_path/'backup'
    if kind == 'fifo':
        if not hasattr(os, 'mkfifo'):pytest.skip('No FIFO fixture on this host')
        os.mkfifo(backup)
    else:
        payload = (b'invalid' if kind=='malformed' else b'X'*80000 if kind=='oversized'
                   else encode_backup('another-app', '1.0.0', 0, b'private bytes'))
        backup.write_bytes(payload)
    monkeypatch.setattr(cli, 'management_transport', lambda *a: pytest.fail('Invalid backup opened USB'))
    monkeypatch.setattr(sys, 'argv', ['lefony-sdk', 'data', 'restore', 'notes', str(backup)])
    assert cli.main() == 1


def test_data_restore_uses_bytes_validated_before_usb_even_if_path_changes(tmp_path, monkeypatch):
    backup = tmp_path/'backup';original = b'original chosen document bytes'
    backup.write_bytes(encode_backup('notes', '1.0.0', 0, original));uploads = []
    def open_transport(*args):
        backup.write_bytes(encode_backup('notes', '1.1.0', 0, b'changed after opening USB'))
        return nullcontext(object())
    def upload(self, app_id, path, stream, length, digest, identity, **options):
        uploads.append(stream.read());assert length==len(original) and digest==hashlib.sha256(original).digest()
        return {'app': app_id, 'path': path, 'committed': True}
    monkeypatch.setattr(cli, 'management_transport', open_transport)
    monkeypatch.setattr(DataClient, 'info', lambda *_: {'data_schema':0,'app_schema':0,'pending_upgrade':False})
    monkeypatch.setattr(DataClient, '_upload', upload)
    monkeypatch.setattr(sys, 'argv', ['lefony-sdk', 'data', 'restore', 'notes', str(backup)])
    assert cli.main() == 0 and uploads == [original]


def test_archive_preflight_still_precedes_either_transport(tmp_path, monkeypatch):
    archive = tmp_path/'invalid.lfarchive';archive.write_bytes(b'invalid archive')
    monkeypatch.setattr(cli, 'management_transport', lambda *a: pytest.fail('Invalid archive opened USB'))
    monkeypatch.setattr(sys, 'argv', ['lefony-sdk', 'archive', '--emulator-usb', '/missing', 'restore', str(archive)])
    assert cli.main() == 1


def test_successful_file_listing_returns_without_entering_build_dispatch(monkeypatch):
    monkeypatch.setattr(cli, 'management_transport', lambda *a: nullcontext(object()))
    monkeypatch.setattr(FileClient, 'list', lambda *a: {'app':'notes','entries':[]})
    monkeypatch.setattr(cli, 'package', lambda *a: pytest.fail('File command entered build dispatch'))
    monkeypatch.setattr(sys, 'argv', ['lefony-sdk', 'files', 'list', 'notes'])
    assert cli.main() == 0


@pytest.mark.parametrize('policy', [LibUSB, ArchiveUSB])
def test_storage_model_transport_keeps_physical_request_restrictions(policy, monkeypatch):
    calls = []
    class Host:
        def __init__(self, *a, **kw):pass
        def control_in(self, *args):calls.append(('read', args));return b'data'
        def control_out(self, *args):calls.append(('write', args))
        def close(self):pass
    monkeypatch.setattr(emulator_usb, 'PrimeUSBHost', Host)
    with emulator_usb.ManagementUSB('model', policy) as transport:
        for request in range(256):
            if request in policy.READ_REQUESTS:assert transport.read(request)==b'data'
            else:
                with pytest.raises(emulator_usb.USBError):transport.read(request)
            if request in policy.WRITE_REQUESTS:transport.write(request)
            else:
                with pytest.raises(emulator_usb.USBError):transport.write(request)
    assert len(calls)==len(policy.READ_REQUESTS)+len(policy.WRITE_REQUESTS)


@pytest.mark.parametrize('family, operation', [('files','status'), ('data','info'), ('archive','status')])
def test_explicit_storage_model_never_falls_back_to_physical(family, operation, monkeypatch):
    monkeypatch.setattr(LibUSB, '__init__', lambda *a: pytest.fail('Physical USB opened'))
    def missing(*a, **kw):raise OSError('Model connection unavailable')
    monkeypatch.setattr(emulator_usb, 'PrimeUSBHost', missing)
    arguments = ['lefony-sdk', family, '--emulator-usb', '/missing', operation]
    if family=='data':arguments.append('notes')
    monkeypatch.setattr(sys, 'argv', arguments)
    assert cli.main() == 1
