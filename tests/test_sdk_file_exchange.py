# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import io
import os
from pathlib import Path
import struct
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from device import DeviceError
from files_device import FileClient,STATUS,EXPORT,READABLE,COMPLETE,file_path
from usb_files import LibUSB,USBError

class Host:
    def __init__(self,flags=32):self.flags=flags;self.reads=[];self.writes=[];self.t=0
    def status(self):return {'protocol':2,'reserved':self.flags,'state':2,'pending':0}
    def clock(self):self.t+=1;return self.t
    def sleep(self,_):pass
    def read(self,*args):self.reads.append(args);raise AssertionError('unexpected USB read')
    def write(self,*args,**kwargs):self.writes.append((args,kwargs));raise AssertionError('unexpected USB write')


def test_older_firmware_never_receives_speculative_file_request():
    host=Host(16);files=FileClient(host)
    with pytest.raises(DeviceError,match='Update Lefony'):files.status()
    with pytest.raises(DeviceError,match='Update Lefony'):files.info('notes')
    assert not host.reads and not host.writes


def test_foreground_app_is_rejected_before_starting_exchange():
    host=Host(32|64)
    with pytest.raises(DeviceError,match='Close the app'):FileClient(host).info('notes')
    assert not host.reads and not host.writes


@pytest.mark.parametrize('path',['/absolute','../escape','a/../b','a//b','a/','a\\b','a\0b','é','x'*49])
def test_bad_paths_cannot_reach_usb(path):
    host=Host()
    with pytest.raises(DeviceError):FileClient(host).export_file('notes',path,Path('/unused'))
    assert not host.reads and not host.writes


def test_protocol_shapes_and_malformed_status_are_rejected():
    assert STATUS.size==96
    for change in [(0,0),(1,64),(2,2),(3,7),(4,9),(8,67108865),(9,513),(12,4096),(13,4),(14,1),(7,1)]:
        fields=[0x5841464c,96,1,0,0,0,0,0,0,0,0,0,512,0,0,0,bytes(32)]
        fields[change[0]]=change[1];host=Host();host.read=lambda *args:STATUS.pack(*fields)
        with pytest.raises(DeviceError,match='Invalid file exchange status'):FileClient(host).status()


def test_failed_download_preserves_existing_destination_and_removes_partial(tmp_path):
    host=Host();files=FileClient(host);target=tmp_path/'saved';target.write_bytes(b'previous')
    files.info=lambda _: {'generation':1,'data_schema':0}
    files._begin=lambda *args,**kwargs: {}
    def fail(state,out,**kwargs):out.write(b'partial');raise DeviceError('bad remote hash')
    files._download=fail
    with pytest.raises(DeviceError,match='hash'):files.export_file('notes','saved',target,replace=True)
    assert target.read_bytes()==b'previous' and sorted(p.name for p in tmp_path.iterdir())==['saved']


def test_export_publish_refuses_new_destination_race(tmp_path):
    files=FileClient(Host());target=tmp_path/'saved';files.info=lambda _: {'generation':1,'data_schema':0}
    files._begin=lambda *args,**kwargs: {}
    def raced(state,out,**kwargs):out.write(b'export');target.write_bytes(b'other writer');return {}
    files._download=raced
    with pytest.raises(FileExistsError):files.export_file('notes','saved',target)
    assert target.read_bytes()==b'other writer' and len(list(tmp_path.iterdir()))==1


def test_bad_export_hash_cancels_without_publishing():
    host=Host();files=FileClient(host);host.read=lambda *args:b'data';host.write=lambda *args,**kwargs:host.writes.append((args,kwargs))
    start={'sequence':7,'operation':EXPORT,'state':READABLE,'offset':0,'length':4,'available':4}
    files._wait=lambda **kwargs: {'sequence':7,'operation':EXPORT,'state':COMPLETE,'offset':4,'length':4,'digest':bytes(32)}
    cancellations=[];files._cancel=cancellations.append
    with pytest.raises(DeviceError,match='SHA-256'):files._download(start,io.BytesIO())
    assert cancellations==[7]


def test_ambiguous_import_commit_is_never_retried_or_cancelled(tmp_path):
    source=tmp_path/'source';source.write_bytes(b'')
    host=Host();files=FileClient(host);files.info=lambda _: {'generation':1,'data_schema':0}
    files._begin=lambda *args,**kwargs: {'sequence':9,'state':3,'offset':0}
    def lost(request,*args,**kwargs):
        host.writes.append(request);raise DeviceError('lost status after commit')
    host.write=lost
    files._cancel=lambda _:pytest.fail('must not cancel an ambiguous commit')
    with pytest.raises(DeviceError,match='lost status'):files.import_file('notes','saved',source)
    assert host.writes==[0x74]


def test_file_transport_cannot_issue_firmware_or_raw_nand_commands():
    transport=LibUSB.__new__(LibUSB)
    for command in (0x44,0x45,0x48,0x50,0x51,0x53,0x60,0x61,0x62,0x65,0x66):
        with pytest.raises(USBError,match='Unsupported SDK'):transport.write(command)
    for command in (0x40,0x41,0x48,0x50,0x51,0x53,0x61,0x62):
        with pytest.raises(USBError,match='Unsupported SDK'):transport.read(command)


@pytest.mark.parametrize('flags,message',[(1,'import committed'),(2,'outcome requires inspection')])
def test_failure_after_commit_does_not_claim_the_old_file_survived(flags,message):
    files=FileClient(Host());files.status=lambda: {'state':5,'flags':flags,'error':8,'operation':3,'sequence':1}
    with pytest.raises(DeviceError,match=message):files._wait(sequence=1,operation=3)


@pytest.mark.skipif(not hasattr(os,'mkfifo'),reason='host has no FIFO fixture')
def test_nonregular_import_source_is_rejected_without_blocking_or_usb(tmp_path):
    pipe=tmp_path/'pipe';os.mkfifo(pipe);host=Host()
    with pytest.raises(DeviceError,match='regular file'):FileClient(host).import_file('notes','saved',pipe)
    assert not host.reads and not host.writes


def test_hashing_cancellation_happens_before_any_device_request(tmp_path):
    source=tmp_path/'source';source.write_bytes(b'x'*2048);host=Host()
    with pytest.raises(DeviceError,match='cancelled'):FileClient(host).import_file('notes','saved',source,cancelled=lambda:True)
    assert not host.reads and not host.writes
