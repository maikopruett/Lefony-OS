# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
from pathlib import Path
import struct
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from device import BACKUP_BYTES, DeviceError
from keys_device import Client, KeyUSB, InstallUSB, RecoveryUSB, decode_status, decode_key, decode_recovery, decode_damage
from signing import public_der, SPKI_PREFIX, SPKI_SUFFIX


class Transport:
    def __init__(self):
        self.flags=256;self.state=0;self.sequence=0;self.serial=0;self.operation=0;self.error=0
        self.nonce=bytes(16);self.identity=bytes(32);self.label=bytes(32);self.package_hash=bytes(32);self.records=[];self.writes=[];self.failure=None;self.corrupt=None
    def read(self,request,value=0,index=0,length=64):
        if request==0x60:return struct.pack('<16I',0x3141464c,2,2,0,0,0,2,0,1,BACKUP_BYTES,0,1,0,0,0,self.flags)
        if request==0x83:return self.records[value]
        assert request==0x80 and length==160
        raw=bytearray(struct.pack('<12I',0x534b464c,160,1,self.state,self.operation,self.error,self.sequence,
                                 2 if self.serial else 1,self.serial,len(self.records),8,0)+self.nonce+self.identity+self.label+self.package_hash)
        if self.corrupt:struct.pack_into('<I',raw,*self.corrupt)
        return bytes(raw)
    def write(self,request,data=b'',value=0,index=0):
        assert request in (0x81,0x82) and not value and not index
        self.writes.append((request,data));failure,self.failure=self.failure,None
        if failure=='before':raise TimeoutError('before acceptance')
        if request==0x81:
            assert len(data)==384
            self.sequence+=1;self.operation=struct.unpack_from('<I',data,8)[0];self.nonce=data[16:32]
            self.identity=data[32:64];self.label=data[320:352];self.package_hash=data[352:];self.state=3
            assert bool(any(self.package_hash))==(self.operation in (3,5,7))
        else:
            assert len(data)==32 and data[16:]==self.nonce
            self.state=6
        if failure=='after':raise TimeoutError('after acceptance')


def test_enrollment_uses_only_public_key_and_exact_binding():
    t=Transport();c=Client(t);messages=[];public=ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'
    result=c.begin('enroll',public_key=public,label='Development',notify=messages.append)
    der=public_der(public);packet=t.writes[0][1]
    assert result['state']=='awaiting_approval' and len(messages)==1
    assert result['fingerprint']==hashlib.sha256(der).hexdigest()
    assert packet[64:320]==der[len(SPKI_PREFIX):-len(SPKI_SUFFIX)] and packet[:16]==struct.pack('<4I',384,1,1,0)
    assert 'PRIVATE' not in packet.decode('ascii','ignore')
    with pytest.raises(DeviceError,match='previous'):c.begin('revoke',fingerprint=result['fingerprint'])
    t.state=5;assert c.wait()['state']=='complete'
    assert len(t.writes)==1


@pytest.mark.parametrize('failure',['before','after'])
def test_lost_ack_is_reported_without_retry_or_implicit_cancellation(failure):
    t=Transport();t.failure=failure;c=Client(t)
    with pytest.raises(DeviceError,match='outcome is unknown'):c.begin('revoke',fingerprint='12'*32)
    assert c.pending and len(t.writes)==1
    if failure=='after':assert c.bound_status()['nonce']==c.pending['nonce']
    else:
        with pytest.raises(DeviceError,match='changed'):c.bound_status()
    assert len(t.writes)==1


@pytest.mark.parametrize('field,value',[('sequence',7),('nonce',b'X'*16),('identity',b'X'*32),('operation',1)])
def test_changed_request_never_becomes_confirmation(field,value):
    t=Transport();c=Client(t);c.begin('revoke',fingerprint='12'*32);setattr(t,field,value)
    with pytest.raises(DeviceError,match='changed'):c.wait()
    assert len(t.writes)==1


def test_cancel_is_bound_and_does_not_claim_a_completed_rollback():
    t=Transport();c=Client(t);status=c.begin('revoke',fingerprint='12'*32)
    with pytest.raises(DeviceError,match='changed'):c.cancel(status['sequence']+1,status['nonce'])
    assert len(t.writes)==1
    assert c.cancel(status['sequence'],status['nonce'])['state']=='cancelled'
    assert [r for r,_ in t.writes]==[0x81,0x82]


def test_older_firmware_and_invalid_inputs_make_no_key_write():
    t=Transport();t.flags=0;c=Client(t)
    with pytest.raises(DeviceError,match='unavailable'):c.begin('revoke',fingerprint='12'*32)
    assert not t.writes
    t.flags=256
    for label in ('',' padded','padded ','bad\n','x'*32):
        with pytest.raises(ValueError):c.begin('enroll',public_key='missing',label=label)
    for fingerprint in ('','gg'*32,'0'*64):
        with pytest.raises(ValueError):c.begin('revoke',fingerprint=fingerprint)
    assert not t.writes


@pytest.mark.parametrize('offset,value',[(0,0),(4,159),(8,2),(12,10),(16,6),(20,15),(28,5),(32,1),(36,9),(40,9),(44,513),(128,1)])
def test_malformed_status_is_not_accepted(offset,value):
    t=Transport();t.corrupt=(offset,value)
    with pytest.raises(DeviceError):decode_status(t.read(0x80,length=160))


def test_listing_checks_public_identity_generation_and_duplicates():
    der=public_der(ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem')
    raw=struct.pack('<8I',0x494b464c,352,1,0,1,2,0,0)+hashlib.sha256(der).digest()+der[len(SPKI_PREFIX):-len(SPKI_SUFFIX)]+b'Revoked'.ljust(32,b'\0')
    t=Transport();t.serial=1;t.records=[raw];c=Client(t)
    assert c.keys()['keys'][0]['state']=='revoked'
    changed=bytearray(raw);changed[64]^=1
    with pytest.raises(DeviceError,match='fingerprint'):decode_key(changed)
    changed=bytearray(raw);struct.pack_into('<I',changed,16,2);t.records=[changed]
    with pytest.raises(DeviceError,match='changed'):c.keys()
    assert not t.writes


def test_usb_transports_exclude_firmware_and_raw_storage_commands():
    assert KeyUSB.READ_REQUESTS==(0x60,0x80,0x83,0x85,0x86,0x87,0x88) and KeyUSB.WRITE_REQUESTS==(0x81,0x82)
    assert set(InstallUSB.WRITE_REQUESTS)=={0x63,0x64,0x65,0x67,0x6a}
    assert not set(range(0x10,0x60))&set(KeyUSB.WRITE_REQUESTS+InstallUSB.WRITE_REQUESTS)
    assert set(RecoveryUSB.WRITE_REQUESTS)=={0x63,0x64,0x67,0x6a,0x81,0x82}
    assert 0x65 not in RecoveryUSB.WRITE_REQUESTS


def test_recovery_binds_exact_package_and_discovers_before_upload():
    t=Transport();c=Client(t)
    with pytest.raises(DeviceError,match='no package was uploaded'):c.recover_install(b'bad',[])
    assert not t.writes
    t.flags|=512
    result=c.begin('recover',fingerprint='12'*32,package_hash='34'*32)
    assert result['operation']=='recover' and result['package_hash']=='34'*32
    assert t.writes[0][1][64:352]==bytes(288)
    t.package_hash=b'X'*32
    with pytest.raises(DeviceError,match='changed'):c.wait()
    assert len(t.writes)==1


def test_recovery_information_checks_identity_and_padding():
    raw=struct.pack('<8I',0x524b464c,192,1,1,4,8,0,0)+b'private-counter'.ljust(64,b'\0')+b'1.2.0'.ljust(32,b'\0')+b'A'*32+b'B'*32
    assert decode_recovery(raw)['app_id']=='private-counter'
    for offset in (0,4,8,12,16,20):
        bad=bytearray(raw);struct.pack_into('<I',bad,offset,0)
        with pytest.raises(DeviceError):decode_recovery(bad)
    for offset in (24,28,95,127):
        bad=bytearray(raw);bad[offset]=1
        with pytest.raises(DeviceError):decode_recovery(bad)
    bad=bytearray(raw);bad[96:128]=b'1.02.0'.ljust(32,b'\0')
    assert decode_recovery(bad)['version']=='1.02.0' # Preserve the package manifest contract.
    bad[96:128]=b'1.1000000.0'.ljust(32,b'\0')
    with pytest.raises(DeviceError):decode_recovery(bad)


class DamagedTransport(Transport):
    def __init__(self):
        super().__init__();self.flags|=2048;self.raw=b'damaged public registry'+bytes(2730);self.is_damaged=True
        self.changed=False;self.short=False
    def read(self,request,value=0,index=0,length=64):
        if request==0x85:
            assert length==64 and self.is_damaged
            return struct.pack('<8I',0x444b464c,64,1,len(self.raw),0,0,0,0)+hashlib.sha256(self.raw).digest()
        if request==0x86:
            result=self.raw[value:value+length]
            if self.changed:self.raw=b'X'+self.raw[1:]
            return result[:-1] if self.short else result
        result=super().read(request,value,index,length)
        if request==0x80 and self.is_damaged:
            result=bytearray(result);struct.pack_into('<I',result,28,3);return bytes(result)
        return result


def test_empty_version_two_registry_retains_serial_and_accepts_listing():
    t=Transport();t.serial=3;c=Client(t)
    assert c.keys()=={'registry':'ready','serial':3,'keys':[]}
    t.flags|=2048;value=c.begin('remove',fingerprint='12'*32)
    assert value['operation']=='remove' and struct.unpack_from('<I',t.writes[0][1],12)[0]==3
    assert not any(t.writes[0][1][64:])


def test_maintenance_discovery_refuses_old_firmware_before_writes():
    t=Transport();c=Client(t)
    with pytest.raises(DeviceError,match='maintenance is unavailable'):c.begin('remove',fingerprint='12'*32)
    with pytest.raises(DeviceError,match='maintenance is unavailable'):c.damage_info()
    assert not t.writes and c.pending is None


@pytest.mark.parametrize('size',[0,1,2752,65536])
def test_damaged_backup_checks_complete_content_and_never_mutates_device(tmp_path,size):
    t=DamagedTransport();t.raw=b'X'*size;c=Client(t);path=tmp_path/'original.keys'
    result=c.backup_damaged(path)
    assert path.read_bytes()==t.raw and result['bytes']==size and result['sha256']==hashlib.sha256(t.raw).hexdigest()
    assert not t.writes and not list(tmp_path.glob('*.partial'))
    with pytest.raises(DeviceError,match='exists'):c.backup_damaged(path)


@pytest.mark.parametrize('failure',['changed','short','oversized','publish'])
def test_failed_damaged_backup_cannot_start_registry_repair(tmp_path,monkeypatch,failure):
    import keys_device
    t=DamagedTransport();c=Client(t);path=tmp_path/'original.keys'
    if failure=='changed':t.changed=True
    elif failure=='short':t.short=True
    elif failure=='oversized':t.raw=b'X'*65537
    else:
        def reject(*args,**kwargs):raise OSError('cannot publish backup')
        monkeypatch.setattr(keys_device,'publish_backup',reject)
    with pytest.raises((DeviceError,OSError)):
        c.repair(ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem','Recovery',path)
    assert not path.exists() and not t.writes and c.pending is None


def test_repair_binds_verified_host_backup_and_preserves_it_on_lost_ack(tmp_path):
    t=DamagedTransport();t.failure='after';c=Client(t);path=tmp_path/'original.keys';messages=[]
    with pytest.raises(DeviceError,match='outcome is unknown'):
        c.repair(ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem','Recovery',path,notify=messages.append)
    assert path.read_bytes()==t.raw and len(t.writes)==1
    packet=t.writes[0][1];assert struct.unpack_from('<4I',packet)==(384,1,5,0)
    assert packet[352:]==hashlib.sha256(path.read_bytes()).digest()
    status=c.bound_status();assert status['registry_hash']==hashlib.sha256(t.raw).hexdigest() and status['package_hash']=='0'*64
    t.package_hash=b'Y'*32
    with pytest.raises(DeviceError,match='changed'):c.bound_status()
    assert any('Other keys require explicit re-enrollment' in message for message in messages)


def test_repair_requires_valid_local_identity_and_corrupt_registry(tmp_path):
    t=DamagedTransport();c=Client(t)
    with pytest.raises(ValueError):c.repair('missing',' bad',tmp_path/'unused')
    assert not t.writes
    public=ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'
    with pytest.raises(ValueError,match='exported damaged'):c.begin('repair',public_key=public,label='Recovery')
    t.is_damaged=False
    with pytest.raises(DeviceError,match='readable damaged'):c.begin('repair',public_key=public,label='Recovery',registry_hash='12'*32)
    assert c.pending is None and not t.writes


@pytest.mark.parametrize('offset,value',[(0,0),(4,63),(8,2),(12,65537),(16,1),(28,1)])
def test_damaged_registry_information_rejects_bad_metadata(offset,value):
    t=DamagedTransport();raw=bytearray(t.read(0x85,length=64));struct.pack_into('<I',raw,offset,value)
    with pytest.raises(DeviceError):decode_damage(raw)
