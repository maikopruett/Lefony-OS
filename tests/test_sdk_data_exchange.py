# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import os
import struct
import pytest
from test_sdk_file_exchange import Host
from data_device import DataClient, encode_backup, decode_backup, publish_backup, MAGIC, MAXIMUM
from device import DeviceError
from files_device import DATA_INFO, DATA_EXPORT, DATA_IMPORT, ROLLBACK


@pytest.mark.parametrize('payload',[b'',b'\0\xffsaved data',bytes(range(256))*256])
def test_backup_roundtrip_binds_exact_bytes_identity_and_schema(payload):
    raw=encode_backup('notes','12.3.4',5,payload);m,data=decode_backup(raw)
    assert data==payload and m['app']=='notes' and m['data_schema']==5
    assert m['sha256']==hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize('kind',['magic','length','hash','trailing','duplicate','identity','version','boolean','oversized','deep'])
def test_malformed_backup_is_rejected_before_usb(tmp_path,kind):
    raw=encode_backup('notes','1.0.0',0,b'data');size=struct.unpack_from('<I',raw,8)[0]
    header=raw[12:12+size];payload=raw[12+size:];m=json.loads(header)
    if kind=='magic':raw=b'WRONG123'+raw[8:]
    elif kind=='length':raw=raw[:8]+struct.pack('<I',4097)+raw[12:]
    elif kind=='hash':raw=raw[:-1]+b'x'
    elif kind=='trailing':raw+=b'x'
    elif kind=='oversized':raw=b'x'*(12+4096+MAXIMUM+1)
    else:
        if kind=='duplicate':header=header.replace(b'"schema":1',b'"schema":1,"schema":1')
        elif kind=='deep':header=('['*1500+'0'+']'*1500).encode()
        else:
            if kind=='identity':m['app']='../notes'
            if kind=='version':m['version']='1.0'
            if kind=='boolean':m['data_schema']=True
            header=json.dumps(m).encode()
        raw=MAGIC+struct.pack('<I',len(header))+header+payload
    path=tmp_path/'backup';path.write_bytes(raw);host=Host()
    with pytest.raises(DeviceError):DataClient(host).restore('notes',path)
    assert not host.reads and not host.writes


def test_old_firmware_receives_no_data_recovery_requests():
    host=Host(32)
    with pytest.raises(DeviceError,match='data recovery extension'):DataClient(host).info('notes')
    assert not host.reads and not host.writes


@pytest.mark.skipif(not hasattr(os,'mkfifo'),reason='no FIFO fixture on host')
def test_fifo_backup_is_refused_without_blocking(tmp_path):
    path=tmp_path/'pipe';os.mkfifo(path);host=Host()
    with pytest.raises(DeviceError,match='regular'):DataClient(host).restore('notes',path)
    assert not host.reads and not host.writes


@pytest.mark.parametrize('mismatch',['app','schema','pending'])
def test_restore_checks_scope_before_starting_transfer(tmp_path,mismatch):
    backup=tmp_path/'backup';backup.write_bytes(encode_backup('other' if mismatch=='app' else 'notes','1.0.0',0,b'data'))
    host=Host();client=DataClient(host)
    client.info=lambda _: {'data_schema':int(mismatch=='schema'),'app_schema':0,'pending_upgrade':mismatch=='pending'}
    with pytest.raises(DeviceError):client.restore('notes',backup)
    assert not host.writes


@pytest.mark.parametrize('operation',[DATA_INFO,DATA_EXPORT])
def test_oversized_device_reply_is_refused_before_allocating_or_reading(operation,tmp_path):
    host=Host();client=DataClient(host);cancelled=[];client._cancel=cancelled.append
    client._begin=lambda *a,**k:{'length':64*1024*1024,'sequence':7}
    if operation==DATA_EXPORT:
        client.info=lambda _: {'private_bytes':4}
        with pytest.raises(DeviceError,match='length'):client.export('notes',tmp_path/'backup')
    else:
        with pytest.raises(DeviceError,match='length'):client.info('notes')
    assert cancelled==[7] and not host.reads and not list(tmp_path.iterdir())


def test_backup_destination_race_does_not_replace_other_file(tmp_path,monkeypatch):
    target=tmp_path/'backup';original=os.link
    def raced(source,destination):
        target.write_bytes(b'other writer');original(source,destination)
    monkeypatch.setattr(os,'link',raced)
    with pytest.raises(FileExistsError):publish_backup(target,b'backup',False)
    assert target.read_bytes()==b'other writer' and len(list(tmp_path.iterdir()))==1


def test_private_restore_uses_same_transfer_and_never_retries_lost_commit(tmp_path):
    path=tmp_path/'backup';path.write_bytes(encode_backup('notes','1.0.0',0,b''))
    host=Host();client=DataClient(host)
    client.info=lambda _: {'generation':9,'data_schema':0,'app_schema':0,'pending_upgrade':False}
    calls=[]
    def begin(*args,**kwargs):
        calls.append((args,kwargs));return {'sequence':4,'state':3,'offset':0}
    client._begin=begin
    def lost(request,*args,**kwargs):host.writes.append(request);raise DeviceError('lost commit status')
    host.write=lost;client._cancel=lambda _:pytest.fail('ambiguous commit must not be cancelled')
    with pytest.raises(DeviceError,match='lost commit'):client.restore('notes',path)
    assert calls[0][0]==('notes',DATA_IMPORT,'') and host.writes==[0x74]


def test_rollback_target_is_inspected_and_commit_is_never_retried():
    host=Host();client=DataClient(host)
    identity={'rollback_available':True,'previous_package':2,'generation':9,'data_schema':1}
    client.info=lambda _:identity;begins=[]
    def begin(*args,**kwargs):begins.append((args,kwargs));return {'sequence':10,'state':3,'offset':0,'length':0}
    client._begin=begin
    def lost(request,*args,**kwargs):host.writes.append(request);raise DeviceError('disconnected')
    host.write=lost;client._cancel=lambda _:pytest.fail('ambiguous rollback must not be cancelled')
    with pytest.raises(DeviceError,match='disconnected'):client.rollback('notes')
    assert begins[0][0]==('notes',ROLLBACK) and begins[0][1]['cursor']==2 and host.writes==[0x74]
