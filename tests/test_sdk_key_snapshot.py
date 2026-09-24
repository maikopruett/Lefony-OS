# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import struct
import sys
import pytest
from test_sdk_keys_device import ROOT, Transport
import key_snapshot
import keys_device
from keys_device import Client, DeviceError, decode_unreadable

PUBLIC = ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'


def capsule(size=2752, missing=(0,)):
    source = bytes((i*17+3)%256 for i in range(size))
    raw = bytearray(b'LFKREAD1'+struct.pack('<6I',1,size,512,(size+511)//512,0,0))
    for index, offset in enumerate(range(0,size,512)):
        data = source[offset:offset+512]
        raw += struct.pack('<4I',offset,len(data),int(index in missing),0)
        if index not in missing:raw += data
    return bytes(raw), source


class PartialTransport(Transport):
    def __init__(self):
        super().__init__();self.flags |= 16384
        self.raw,_ = capsule();self.info = key_snapshot.inspect(self.raw)
        self.fault = None;self.repair_failure = None;self.info_reads = 0
    def read(self,request,value=0,index=0,length=64):
        if request==0x87:
            assert self.operation==6 and self.state==5 and length==96
            self.info_reads += 1
            i=self.info
            raw=bytearray(struct.pack('<8I',0x554b464c,96,1,self.sequence,i['original_bytes'],i['bytes'],i['readable_bytes'],i['unreadable_chunks'])+
                          self.nonce+bytes.fromhex(i['sha256'])+bytes(16))
            if self.fault=='binding':raw[32]^=1
            if self.fault=='changed_info' and self.info_reads>1:raw[48]^=1
            return bytes(raw)
        if request==0x88:
            result=self.raw[(index<<16)+value:(index<<16)+value+length]
            if self.fault=='short':return result[:-1]
            if self.fault=='changed_payload':return bytes([result[0]^1])+result[1:]
            if self.fault=='changed_session':self.nonce=b'X'*16
            return result
        raw=super().read(request,value,index,length)
        if request==0x80:
            raw=bytearray(raw);struct.pack_into('<I',raw,28,4);return bytes(raw)
        return raw
    def write(self,request,data=b'',value=0,index=0):
        if request==0x81 and struct.unpack_from('<I',data,8)[0]==7:self.failure=self.repair_failure
        super().write(request,data,value,index)
        if self.operation==6:
            self.state=9 if self.fault=='readable' else 5
            self.error=15 if self.fault=='readable' else 0


@pytest.mark.parametrize('size,missing',[(1,(0,)),(512,(0,)),(513,(1,)),(2752,(0,3,5)),(65536,(127,))])
def test_partial_container_bounds_and_usb_export(tmp_path,size,missing):
    t=PartialTransport();t.raw,source=capsule(size,missing);t.info=key_snapshot.inspect(t.raw)
    assert t.info['readable_bytes']==size-sum(len(source[i*512:(i+1)*512]) for i in missing)
    c=Client(t);path=tmp_path/'partial.keys';result=c.backup_unreadable(path)
    assert path.read_bytes()==t.raw and result['status']=='partially_backed_up'
    assert len(t.writes)==1 and struct.unpack_from('<4I',t.writes[0][1])==(384,1,6,0)
    assert not any(t.writes[0][1][32:]) and result['sha256']==hashlib.sha256(t.raw).hexdigest()


@pytest.mark.parametrize('offset,value',[(0,0),(8,2),(12,0),(12,65537),(16,256),(20,5),(24,1),(28,1),(32,1),(36,511),(40,2),(44,1)])
def test_partial_container_rejects_malformed_header_or_records(offset,value):
    raw=bytearray(capsule()[0]);struct.pack_into('<I',raw,offset,value)
    with pytest.raises(ValueError):key_snapshot.inspect(raw)


@pytest.mark.parametrize('raw',[b'',b'LFKREAD1',capsule()[0][:-1],capsule()[0]+b'X',capsule(missing=())[0]])
def test_partial_container_rejects_incomplete_or_falsely_complete_backups(raw):
    with pytest.raises(ValueError):key_snapshot.inspect(raw)


@pytest.mark.parametrize('fault',['binding','changed_info','short','changed_payload','changed_session','readable','publish'])
def test_failed_partial_backup_never_requests_repair(tmp_path,monkeypatch,fault):
    t=PartialTransport();t.fault=fault;c=Client(t);path=tmp_path/'partial.keys'
    if fault=='publish':
        def reject(*args,**kwargs):raise OSError('cannot publish backup')
        monkeypatch.setattr(keys_device,'publish_backup',reject)
    with pytest.raises((DeviceError,ValueError,OSError)):c.repair_unreadable(PUBLIC,'Recovered',path)
    assert not path.exists() and c.pending is None
    assert len(t.writes)==1 and struct.unpack_from('<I',t.writes[0][1],8)[0]==6


@pytest.mark.parametrize('failure',['before','after'])
def test_partial_backup_survives_unknown_repair_outcome_and_is_exactly_bound(tmp_path,failure):
    t=PartialTransport();t.repair_failure=failure;c=Client(t);path=tmp_path/'partial.keys';messages=[]
    with pytest.raises(DeviceError,match='outcome is unknown'):
        c.repair_unreadable(PUBLIC,'Recovered',path,notify=messages.append)
    assert path.read_bytes()==t.raw and len(t.writes)==2
    packet=t.writes[1][1]
    assert struct.unpack_from('<4I',packet)==(384,1,7,0)
    assert packet[352:]==hashlib.sha256(t.raw).digest() and packet[16:32]!=t.writes[0][1][16:32]
    assert any('Missing bytes cannot be recovered' in message for message in messages)
    if failure=='after':
        assert c.bound_status()['registry_hash']==hashlib.sha256(t.raw).hexdigest()
        t.package_hash=b'X'*32
    with pytest.raises(DeviceError,match='changed'):c.bound_status()
    assert len(t.writes)==2


def test_partial_repair_waits_for_selected_request_and_keeps_backup(tmp_path):
    t=PartialTransport();c=Client(t,sleep=lambda _:setattr(t,'state',5));path=tmp_path/'partial.keys'
    result=c.repair_unreadable(PUBLIC,'Recovered',path)
    assert result['state']=='complete' and result['operation']=='repair-unreadable'
    assert result['backup']['sha256']==hashlib.sha256(path.read_bytes()).hexdigest() and len(t.writes)==2


def test_partial_operations_validate_inputs_destinations_and_discovery_before_requests(tmp_path):
    t=PartialTransport();c=Client(t);path=tmp_path/'partial.keys';path.write_bytes(b'keep')
    with pytest.raises(DeviceError,match='exists'):c.backup_unreadable(path)
    with pytest.raises(DeviceError,match='exists'):c.repair_unreadable(PUBLIC,'Recovery',path)
    with pytest.raises(ValueError):c.repair_unreadable('missing',' bad',tmp_path/'new.keys')
    t.flags &= ~16384
    with pytest.raises(DeviceError,match='unavailable'):c.backup_unreadable(tmp_path/'new.keys')
    with pytest.raises(DeviceError,match='unavailable'):c.begin('repair-unreadable',public_key=PUBLIC,label='Recovery',registry_hash='12'*32)
    assert not t.writes and path.read_bytes()==b'keep' and not (tmp_path/'new.keys').exists()


@pytest.mark.parametrize('offset,value',[(0,0),(4,95),(8,2),(12,0),(16,0),(16,65537),(20,0),(24,2752),(28,0),(28,7),(80,1)])
def test_partial_snapshot_information_rejects_bad_metadata(offset,value):
    t=PartialTransport();c=Client(t);c.begin('backup-unreadable')
    raw=bytearray(t.read(0x87,length=96));struct.pack_into('<I',raw,offset,value)
    with pytest.raises(DeviceError):decode_unreadable(raw)


@pytest.mark.parametrize('operation',['backup-unreadable','repair-unreadable'])
def test_partial_cli_dispatch_uses_verified_backup_workflow(tmp_path,monkeypatch,capsys,operation):
    import cli
    t=PartialTransport()
    class USB:
        def __enter__(self):return t
        def __exit__(self,*args):pass
    monkeypatch.setattr(keys_device,'KeyUSB',USB)
    original=keys_device.Client
    monkeypatch.setattr(keys_device,'Client',lambda transport,**kwargs:original(transport,sleep=lambda _:setattr(t,'state',5)))
    path=tmp_path/'backup.keys'
    args=['sdk','keys',operation]
    args += [str(path)] if operation=='backup-unreadable' else ['--backup',str(path),'--public-key',str(PUBLIC),'--label','Recovered']
    monkeypatch.setattr(sys,'argv',args)
    assert cli.main()==0 and path.read_bytes()==t.raw
    assert len(t.writes)==(1 if operation=='backup-unreadable' else 2)
    output=capsys.readouterr()
    assert 'approve on the calculator' in output.err if operation=='repair-unreadable' else not output.err
