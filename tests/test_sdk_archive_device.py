# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import os
import struct
import sys
import pytest
from test_sdk_archive import ROOT,PUBLIC,signed,snapshot,encoded
import archive_device as a
import archive_format
from device import Client as DeviceClient,DeviceError,BACKUP_BYTES


@pytest.fixture(scope='module')
def payload():return encoded(snapshot(signed(),b'private',(('notes',b'hello'*1700),('folder',None))))


class Transport:
    """Host peer fixture: records writes and injects ambiguous USB outcomes."""
    def __init__(self,payload):
        self.payload=payload;self.present=False;self.generation=0;self.sequence=0;self.nonce=bytes(16)
        self.operation=a.INSPECT;self.state=a.IDLE;self.error=0;self.offset=0;self.length=0
        self.digest=bytes(32);self.flags=0;self.supported=True;self.active_app=False;self.writes=[];self.reads=[]
        self.transfer=b'';self.upload=bytearray();self.failure=None;self.bad_digest=False;self.status_mutation=None;self.now=0
    def sleep(self,n):self.now+=n
    def client(self):return a.Client(DeviceClient(self,sleep=self.sleep,clock=lambda:self.now),timeout=.1)
    def info(self):
        # The archive fixture contains one schema-0 package at version 2.0.0.
        p=archive_format.PAIR.unpack_from(self.payload,128);present=self.present
        return a.INFO.pack(192,1,3 if present else 0,self.generation,*((2,0,0) if present else (0,0,0)),0,0,
            *((2,0,0) if present else (0,0,0)),p[4] if present else 0,8500 if present else 0,32*1024*1024,p[2] if present else 0,
            p[16] if present else bytes(32),self.payload[280:312] if present else bytes(32),b'document')
    def read(self,request,value=0,index=0,length=64):
        self.reads.append(request)
        if request==0x60:return struct.pack('<16I',0x3141464c,2,2,0,0,0,2,int(self.present),1,BACKUP_BYTES,0,1,0,0,0,
            (1024 if self.supported else 0)|(64 if self.active_app else 0))
        if request==0x92:
            assert value+(index<<16)==self.sequence and length==min(512,self.length-self.offset)
            return self.transfer[self.offset:self.offset+length]
        assert request==0x90 and length==112
        available=min(512,self.length-self.offset) if self.state==a.READABLE else 0
        fields=[0x5241464c,112,1,self.state,self.operation,self.error,self.sequence,self.offset,self.length,available,
                self.generation,self.flags,488,0,0,0,self.digest,self.nonce]
        if self.status_mutation:self.status_mutation(fields)
        return a.STATUS.pack(*fields)
    def write(self,request,data=b'',value=0,index=0):
        self.writes.append((request,data,value+(index<<16)))
        failure=self.failure if self.failure and self.failure[0]==request else None
        if failure:self.failure=None
        if failure and failure[1]=='before':raise DeviceError('disconnected before acceptance')
        if request==0x91:
            r=a.REQUEST.unpack(data);assert r[:2]==(144,1) and r[8].rstrip(b'\0')==b'document'
            self.operation=r[2];self.sequence+=1;self.nonce=r[10];self.offset=0;self.error=self.flags=0
            self.upload=bytearray();self.digest=r[9]
            if self.operation==a.RESTORE:self.state=a.WRITABLE;self.length=r[5]
            else:
                self.transfer=self.info() if self.operation==a.INSPECT else self.payload
                self.length=len(self.transfer);self.digest=hashlib.sha256(self.transfer).digest();self.state=a.READABLE
                if self.bad_digest and self.operation==a.EXPORT:self.digest=bytes(32)
        elif request==0x92:
            seq,offset,nonce=struct.unpack_from('<2I16s',data)
            assert (seq,offset,nonce)==(self.sequence,self.offset,self.nonce) and len(data)<=512
            self.upload.extend(data[24:]);self.offset+=len(data)-24
            if self.offset==self.length:self.state=a.READY
        elif request==0x93:
            seq,offset,nonce=struct.unpack('<2I16s',data)
            assert seq==self.sequence and nonce==self.nonce and offset==min(self.offset+512,self.length)
            self.offset=offset
            if offset==self.length:self.state=a.COMPLETE
        elif request in (0x94,0x95):
            if value+(index<<16)!=self.sequence or data!=self.nonce:return
            if request==0x94:
                assert self.state==a.READY and bytes(self.upload)==self.payload
                self.committed=bytes(self.upload)
                self.state=a.COMPLETE;self.flags=1;self.present=True;self.generation+=1
            else:self.state=a.CANCELLED;self.error=11
        else:raise AssertionError(request)
        if failure and failure[1]=='after':raise DeviceError('disconnected after acceptance')


@pytest.mark.parametrize('flags,protection',[(0,'single'),(192,'payload-only'),(320,'metadata-only'),(448,'both')])
def test_negotiated_root_health_preserves_legacy_inspection(payload,flags,protection):
    class HealthTransport(Transport):
        requested=False
        def read(self,request,*args,**kwargs):
            raw=super().read(request,*args,**kwargs)
            if request==0x60:
                values=list(struct.unpack('<16I',raw));values[15]|=32768;raw=struct.pack('<16I',*values)
            return raw
        def write(self,request,data=b'',*args,**kwargs):
            if request==0x91:self.requested=bool(a.REQUEST.unpack(data)[3]&8)
            return super().write(request,data,*args,**kwargs)
        def info(self):
            values=list(a.INFO.unpack(super().info()))
            if self.requested:values[2]|=flags
            return a.INFO.pack(*values)
    transport=HealthTransport(payload);transport.present=True;transport.generation=7;client=transport.client()
    assert client.info('document')['root_protection']==protection
    requests=[a.REQUEST.unpack(data) for command,data,_ in transport.writes if command==0x91]
    assert requests[0][2:4]==(a.INSPECT,8)
    # An old SDK does not request new flags and receives the original layout.
    state=client._begin('document',a.INSPECT);output=a.io.BytesIO();client._download(state,output)
    assert a.decode_info(output.getvalue(),'document')['root_protection'] is None
    assert not a.INFO.unpack(output.getvalue())[2]&448
    old=Transport(payload);old.present=True;old.generation=7
    assert old.client().info('document')['root_protection'] is None
    assert all(not a.REQUEST.unpack(data)[3]&8 for cmd,data,_ in old.writes if cmd==0x91)


@pytest.mark.parametrize('flags',[64,128,256,384,512])
def test_inconsistent_or_unknown_root_health_is_rejected(payload,flags):
    transport=Transport(payload);transport.present=True;transport.generation=1
    values=list(a.INFO.unpack(transport.info()));values[2]|=flags
    with pytest.raises(DeviceError):a.decode_info(a.INFO.pack(*values),'document',root_health=True)
    # Unnegotiated extensions remain invalid even for a coherent protected root.
    values[2]=3|448
    with pytest.raises(DeviceError):a.decode_info(a.INFO.pack(*values),'document')


def test_wait_backs_off_for_storage_without_repeating_writes(payload,monkeypatch):
    transport=Transport(payload);client=transport.client();delays=[]
    binding={'sequence':1,'operation':a.RESTORE,'nonce':b'x'*16}
    status={**binding,'state':a.WORKING}
    monkeypatch.setattr(client,'status',lambda:status)
    def sleep(delay):
        delays.append(delay);transport.sleep(delay)
        if len(delays)==6:status['state']=a.WRITABLE
    monkeypatch.setattr(client.client,'sleep',sleep)
    assert client._wait(binding)['state']==a.WRITABLE
    assert delays==[.001,.002,.004,.008,.01,.01] and not transport.writes
    # A new block starts with the short wait again, rather than inheriting a
    # long metadata/commit delay from the previous block.
    status['state']=a.WORKING;delays.clear()
    assert client._wait(binding)['state']==a.WRITABLE and delays[0]==.001


def test_wait_backoff_preserves_timeout_and_session_ownership(payload,monkeypatch):
    transport=Transport(payload);client=transport.client()
    binding={'sequence':1,'operation':a.RESTORE,'nonce':b'x'*16}
    status={**binding,'state':a.WORKING}
    monkeypatch.setattr(client,'status',lambda:status)
    with pytest.raises(DeviceError,match='timed out'):client._wait(binding)
    assert .1<=transport.now<.11 and not transport.writes
    status['nonce']=b'y'*16
    with pytest.raises(DeviceError,match='session changed'):client._wait(binding)
    assert not transport.writes


def test_complete_restore_export_and_independent_signature_check(tmp_path,payload):
    path=tmp_path/'input';path.write_bytes(payload);t=Transport(payload);client=t.client()
    report=client.restore(path,[PUBLIC]);assert report['committed'] and report['generation']==1
    assert len([w for w in t.writes if w[0]==0x94])==1
    target=tmp_path/'output';report=client.export('document',target,[PUBLIC])
    assert report['signatures_checked'] and target.read_bytes()==payload
    assert archive_format.inspect(target,[PUBLIC]).sha256==report['sha256']
    assert not list(tmp_path.glob('*.partial'))


@pytest.mark.parametrize('operation',['info','restore','export','status'])
def test_old_firmware_receives_no_archive_requests(tmp_path,payload,operation):
    t=Transport(payload);t.supported=False;c=t.client();path=tmp_path/'archive';path.write_bytes(payload)
    call={'info':lambda:c.info('document'),'restore':lambda:c.restore(path,[PUBLIC]),
          'export':lambda:c.export('document',tmp_path/'out',[PUBLIC]),'status':c.status}[operation]
    with pytest.raises(DeviceError,match='no whole-app archive'):call()
    assert not t.writes and set(t.reads)=={0x60}


@pytest.mark.parametrize('operation',['restore','export'])
def test_active_app_is_rejected_before_begin(tmp_path,payload,operation):
    t=Transport(payload);t.active_app=True;c=t.client();path=tmp_path/'archive';path.write_bytes(payload)
    with pytest.raises(DeviceError,match='Close the app'):
        c.restore(path,[PUBLIC]) if operation=='restore' else c.export('document',tmp_path/'out',[PUBLIC])
    assert not t.writes


@pytest.mark.parametrize('command,stage',[(0x91,'before'),(0x91,'after'),(0x92,'before'),(0x92,'after'),(0x94,'before'),(0x94,'after')])
def test_lost_write_ack_never_retries_and_commit_is_not_cancelled(tmp_path,payload,command,stage):
    path=tmp_path/'archive';path.write_bytes(payload);t=Transport(payload);c=t.client()
    original=c.info
    def inspected(app_id):
        info=original(app_id);t.failure=(command,stage);return info
    c.info=inspected
    with pytest.raises(DeviceError,match='outcome is unknown' if command==0x94 else 'disconnected'):c.restore(path,[PUBLIC])
    writes=[w[0] for w in t.writes]
    assert writes.count(command)==(2 if command==0x91 else 1)
    assert writes[-1]==(0x94 if command==0x94 else 0x91 if command==0x91 and stage=='before' else 0x95)


@pytest.mark.parametrize('state,error',[(a.COMPLETE,0),(a.FAILED,9),(a.CANCELLED,11)])
def test_cleanup_does_not_cancel_a_drained_session(payload,state,error):
    t=Transport(payload);c=t.client();binding=c._begin('document',a.RESTORE)
    t.state=state;t.error=error
    before=list(t.writes)
    c._cancel(binding)
    assert t.writes==before and t.state==state and t.error==error


@pytest.mark.parametrize('field,value',[('sequence',99),('nonce',b'x'*16),('operation',a.EXPORT)])
def test_cleanup_does_not_write_to_a_replacement_session(payload,field,value):
    t=Transport(payload);c=t.client();binding=c._begin('document',a.RESTORE)
    setattr(t,field,value)
    # A replacement export is actively readable, and therefore needs a
    # valid export status instead of the original restore's writable state.
    if field=='operation':t.state=a.READABLE;t.length=1
    before=list(t.writes)
    c._cancel(binding)
    assert t.writes==before


def test_cleanup_still_cancels_an_active_owned_session(payload):
    t=Transport(payload);c=t.client();binding=c._begin('document',a.RESTORE)
    c._cancel(binding)
    assert t.writes[-1]==(0x95,binding['nonce'],binding['sequence'])
    assert t.state==a.CANCELLED


def test_source_path_swap_uses_the_open_verified_descriptor(tmp_path,payload):
    path=tmp_path/'archive';path.write_bytes(payload);t=Transport(payload)
    with a.prepare(path,[PUBLIC]) as source:
        path.rename(tmp_path/'saved');path.write_bytes(b'replacement')
        assert t.client().restore_prepared(source)['committed']
    assert t.committed==payload


def test_same_descriptor_content_change_cancels_before_commit(tmp_path,payload):
    path=tmp_path/'archive';path.write_bytes(payload);t=Transport(payload)
    with a.prepare(path,[PUBLIC]) as source:
        changed=bytearray(payload);changed[-1]^=1;path.write_bytes(changed)
        with pytest.raises(DeviceError,match='source changed'):t.client().restore_prepared(source)
    assert 0x94 not in [w[0] for w in t.writes] and t.state==a.CANCELLED


@pytest.mark.parametrize('failure',['hash','cancel','race'])
def test_failed_export_preserves_destination_and_removes_partial(tmp_path,payload,monkeypatch,failure):
    t=Transport(payload);t.present=True;t.generation=1;c=t.client();dest=tmp_path/'out'
    if failure=='hash':t.bad_digest=True;dest.write_bytes(b'original')
    if failure=='race':
        original=os.link
        def race(source,target):dest.write_bytes(b'concurrent writer');return original(source,target)
        monkeypatch.setattr(os,'link',race)
    with pytest.raises((DeviceError,FileExistsError)):
        c.export('document',dest,[PUBLIC],replace=failure=='hash',cancelled=lambda:failure=='cancel')
    assert list(tmp_path.iterdir())==([] if failure=='cancel' else [dest])
    if failure!='cancel':assert dest.read_bytes()==(b'original' if failure=='hash' else b'concurrent writer')


def test_cli_authenticates_restore_before_usb_enumeration(tmp_path,payload,monkeypatch,capsys):
    import cli
    path=tmp_path/'archive';path.write_bytes(payload[:-1]+bytes([payload[-1]^1]))
    monkeypatch.setattr(a,'ArchiveUSB',lambda:pytest.fail('invalid archive reached USB'))
    monkeypatch.setattr(sys,'argv',['lefony-sdk','archive','restore',str(path),'--public-key',str(PUBLIC)])
    assert cli.main()==1 and 'archive' in capsys.readouterr().err


def test_cli_rejects_structurally_valid_archive_with_invalid_signature_before_usb(tmp_path,monkeypatch,capsys):
    import cli
    package=bytearray(signed());package[96]^=1
    path=tmp_path/'archive';path.write_bytes(encoded(snapshot(package)))
    monkeypatch.setattr(a,'ArchiveUSB',lambda:pytest.fail('unauthenticated archive reached USB'))
    monkeypatch.setattr(sys,'argv',['lefony-sdk','archive','restore',str(path),'--public-key',str(PUBLIC)])
    assert cli.main()==1 and 'signature' in capsys.readouterr().err


def test_cli_complete_restore_and_status_nonce_are_json(tmp_path,payload,monkeypatch,capsys):
    import cli,json
    from contextlib import nullcontext
    path=tmp_path/'archive';path.write_bytes(payload);t=Transport(payload)
    monkeypatch.setattr(a,'ArchiveUSB',lambda:nullcontext(t))
    monkeypatch.setattr(sys,'argv',['lefony-sdk','archive','restore',str(path),'--public-key',str(PUBLIC)])
    assert cli.main()==0 and json.loads(capsys.readouterr().out)['committed']
    monkeypatch.setattr(sys,'argv',['lefony-sdk','archive','status'])
    assert cli.main()==0 and len(json.loads(capsys.readouterr().out)['nonce'])==32


@pytest.mark.parametrize('field,value',[(0,0),(1,111),(2,2),(3,9),(4,0),(5,17),(7,1),(9,1),(11,4),(12,489),(13,1)])
def test_invalid_status_is_refused(payload,field,value):
    t=Transport(payload);t.status_mutation=lambda fields:fields.__setitem__(field,value)
    with pytest.raises(DeviceError):t.client().status()
    assert not t.writes


def test_cancellation_requires_current_nonce_and_sequence(payload):
    t=Transport(payload);c=t.client();s=c._begin('document',a.INSPECT)
    for sequence,nonce in [(s['sequence']+1,s['nonce'].hex()),(s['sequence'],'aa'*16)]:
        with pytest.raises(DeviceError,match='changed'):c.cancel(sequence,nonce)
    assert len(t.writes)==1
    assert c.cancel(s['sequence'],s['nonce'].hex())['state']==a.CANCELLED


@pytest.fixture(scope='module')
def pending_payload():
    return encoded(snapshot(signed(),b'private',(('notes',b'hello'*1700),('folder',None))),
                   snapshot(signed('1.0.0'),b'previous'))


class ApprovalTransport(Transport):
    """Host protocol fixture only; real firmware consent is tested separately."""
    def __init__(self,payload,archive):
        super().__init__(payload);self.archive=archive;self.consent_supported=True
        self.approval_mutation=None;self.decision='approve';self.force_approval=False
    def info(self):
        values=list(a.INFO.unpack(super().info()))
        if self.present:values[2]|=4
        return a.INFO.pack(*values)
    def read(self,request,value=0,index=0,length=64):
        if request==0x60:
            values=list(struct.unpack('<16I',super().read(request,value,index,length)))
            if self.consent_supported:values[15]|=4096
            return struct.pack('<16I',*values)
        if request==0x96:
            assert value+(index<<16)==self.sequence and length==216
            snapshots=self.archive.snapshots
            fields=[216,1,self.sequence,0,2,0,0,1,0,0,b'document'.ljust(64,b'\0'),
                *(self.payload[p.package.offset+24:p.package.offset+56] for p in snapshots),self.digest,self.nonce]
            if self.approval_mutation:self.approval_mutation(fields)
            return a.APPROVAL.pack(*fields)
        return super().read(request,value,index,length)
    def write(self,request,data=b'',value=0,index=0):
        super().write(request,data,value,index)
        if request==0x92 and self.state==a.READY:
            self.flags|=4
            self.state=a.READY if self.decision=='early' else a.AWAIT_USER
        if request==0x94:self.flags|=4
    def sleep(self,n):
        super().sleep(n)
        if self.state==a.AWAIT_USER:
            if self.decision=='approve':self.state=a.READY
            elif self.decision=='deny':self.state=a.FAILED;self.error=16
            elif self.decision=='cancel':self.state=a.CANCELLED;self.error=11


def approval_peer(tmp_path,payload):
    path=tmp_path/'pending';path.write_bytes(payload)
    return path,ApprovalTransport(payload,archive_format.inspect(path,[PUBLIC]))


def test_host_consent_binds_the_full_archive_and_both_identities(tmp_path,pending_payload):
    path,t=approval_peer(tmp_path,pending_payload);notices=[]
    report=t.client().restore(path,[PUBLIC],allow_recovery_pair=True,notify=notices.append)
    assert report['committed'] and report['snapshots']==2 and len(notices)==1
    note=notices[0];assert note['archive_sha256']==hashlib.sha256(pending_payload).hexdigest()
    assert note['current_version']=='2.0.0' and note['rollback_version']=='1.0.0'
    assert note['current_signer']==note['rollback_signer']==pending_payload[280:312].hex()
    begins=[a.REQUEST.unpack(w[1]) for w in t.writes if w[0]==0x91]
    assert next(r for r in begins if r[2]==a.RESTORE)[3]==2
    assert len([w for w in t.writes if w[0]==0x94])==1


@pytest.mark.parametrize('field',[0,1,2,3,4,7,10,11,12,13,14])
def test_changed_approval_record_never_commits(tmp_path,pending_payload,field):
    path,t=approval_peer(tmp_path,pending_payload)
    t.approval_mutation=lambda fields:fields.__setitem__(field,fields[field]+1 if field<10 else bytes(len(fields[field])))
    with pytest.raises(DeviceError,match='identities changed'):
        t.client().restore(path,[PUBLIC],allow_recovery_pair=True)
    assert not any(w[0]==0x94 for w in t.writes) and t.state==a.CANCELLED


@pytest.mark.parametrize('decision',['deny','cancel','wait'])
def test_denied_cancelled_or_expired_approval_never_commits(tmp_path,pending_payload,decision):
    path,t=approval_peer(tmp_path,pending_payload);t.decision=decision
    with pytest.raises(DeviceError,match='denied|cancelled|timed out'):
        t.client().restore(path,[PUBLIC],allow_recovery_pair=True)
    assert not any(w[0]==0x94 for w in t.writes)


def test_new_consent_feature_is_discovered_before_any_archive_request(tmp_path,pending_payload):
    path,t=approval_peer(tmp_path,pending_payload);t.consent_supported=False
    with pytest.raises(DeviceError,match='no archive recovery-pair consent'):
        t.client().restore(path,[PUBLIC],allow_recovery_pair=True)
    assert not t.writes and t.reads==[0x60]


def test_existing_app_cannot_use_fresh_archive_approval(tmp_path,pending_payload):
    path,t=approval_peer(tmp_path,pending_payload);t.present=True;t.generation=4
    with pytest.raises(DeviceError,match='absent app'):
        t.client().restore(path,[PUBLIC],replace=True,allow_recovery_pair=True)
    assert not any(w[0]==0x91 and a.REQUEST.unpack(w[1])[2]==a.RESTORE for w in t.writes)


def test_unrequested_approval_is_cancelled_without_commit(tmp_path,pending_payload):
    path,t=approval_peer(tmp_path,pending_payload)
    with pytest.raises(DeviceError,match='Unexpected archive approval'):
        t.client().restore(path,[PUBLIC])
    assert not any(w[0]==0x94 for w in t.writes) and t.state==a.CANCELLED


def test_user_cancellation_after_prompt_does_not_commit(tmp_path,pending_payload):
    path,t=approval_peer(tmp_path,pending_payload);notices=[]
    with pytest.raises(DeviceError,match='cancelled during approval'):
        t.client().restore(path,[PUBLIC],allow_recovery_pair=True,notify=notices.append,cancelled=lambda:bool(notices))
    assert notices and not any(w[0]==0x94 for w in t.writes) and t.state==a.CANCELLED


def test_approval_before_the_first_host_poll_still_checks_and_reports_identities(tmp_path,pending_payload):
    path,t=approval_peer(tmp_path,pending_payload);t.decision='early';notices=[]
    result=t.client().restore(path,[PUBLIC],allow_recovery_pair=True,notify=notices.append)
    assert result['committed'] and len(notices)==1 and notices[0]['archive_sha256']==t.archive.sha256
    assert len([w for w in t.writes if w[0]==0x94])==1


def test_early_approval_cannot_skip_mismatched_identity_rejection(tmp_path,pending_payload):
    path,t=approval_peer(tmp_path,pending_payload);t.decision='early'
    t.approval_mutation=lambda fields:fields.__setitem__(13,bytes(32))
    with pytest.raises(DeviceError,match='identities changed'):
        t.client().restore(path,[PUBLIC],allow_recovery_pair=True)
    assert not any(w[0]==0x94 for w in t.writes)


class RepairTransport(Transport):
    def __init__(self,payload,*,legacy=False,prefix=True):
        super().__init__(payload);self.present=True;self.generation=7;self.damaged=True
        self.legacy=legacy;self.prefix=prefix;self.repair_supported=True;self.request_flags=0
        self.proof_mutation=None;self.drop_repair_flag=False
    def info(self):
        raw=super().info()
        if not self.request_flags&4:return raw
        values=list(a.INFO.unpack(raw));values[:2]=[256,2];extra=bytes(64)
        if self.damaged:
            values[2]|=8;values[4:8]=[0]*4;values[17]=bytes(32)
            if self.legacy:
                values[2]|=16;values[8:12]=[0]*4;values[16]=bytes(32)
                p=archive_format.PAIR.unpack_from(self.payload,128)
                combined=hashlib.sha256(self.payload[256:256+p[2]+p[4]]).digest()
                prefix=hashlib.sha256(self.payload[256:608]).digest() if self.prefix else bytes(32)
                if self.prefix:values[2]|=32
                extra=combined+prefix
        if self.proof_mutation:extra=self.proof_mutation(values,extra)
        return a.INFO.pack(*values)+extra
    def read(self,request,value=0,index=0,length=64):
        raw=super().read(request,value,index,length)
        if request==0x60 and self.repair_supported:
            values=list(struct.unpack('<16I',raw));values[15]|=8192;raw=struct.pack('<16I',*values)
        return raw
    def write(self,request,data=b'',value=0,index=0):
        if request==0x91:self.request_flags=a.REQUEST.unpack(data)[3]
        super().write(request,data,value,index)
        if self.operation==a.RESTORE and self.request_flags&4:
            if not self.drop_repair_flag:self.flags|=8
            if request==0x94:self.damaged=False


@pytest.mark.parametrize('legacy,prefix',[(False,False),(True,False),(True,True)])
def test_code_repair_authenticates_identity_and_checks_receipt(tmp_path,payload,legacy,prefix):
    t=RepairTransport(payload,legacy=legacy,prefix=prefix);c=t.client();path=tmp_path/'backup';path.write_bytes(payload)
    info=c.info('document',include_unreadable=True)
    assert info['code_unavailable'] and info['version'] is None and info['signer'] is None and info['app_schema'] is None
    if legacy:assert info['package_sha256'] is None and info['high_version'] is None and info['data_schema'] is None
    result=c.restore(path,[PUBLIC],repair_code=True)
    assert result['committed'] and result['code_repaired'] and t.committed==payload
    requests=[a.REQUEST.unpack(w[1]) for w in t.writes if w[0]==0x91]
    assert [r[3] for r in requests if r[2]==a.RESTORE]==[5]
    assert t.client().info('document')['code_unavailable'] is False


@pytest.mark.parametrize('operation',['info','restore'])
def test_old_firmware_receives_no_repair_requests(tmp_path,payload,operation):
    t=RepairTransport(payload);t.repair_supported=False;c=t.client();path=tmp_path/'backup';path.write_bytes(payload)
    with pytest.raises(DeviceError,match='no unreadable-code recovery'):
        c.info('document',include_unreadable=True) if operation=='info' else c.restore(path,[PUBLIC],repair_code=True)
    assert not t.writes


@pytest.mark.parametrize('kind',['healthy','absent','package','prefix','combined','private_size','repair_flag'])
def test_repair_rejects_inadequate_proof_and_never_commits(tmp_path,payload,kind):
    legacy=kind in ('prefix','combined','private_size')
    t=RepairTransport(payload,legacy=legacy,prefix=False);c=t.client();path=tmp_path/'backup';path.write_bytes(payload)
    if kind=='healthy':t.damaged=False
    if kind=='absent':t.present=False;t.damaged=False;t.generation=0
    if kind=='repair_flag':t.drop_repair_flag=True
    def mutate(v,extra):
        if kind=='package':v[16]=bytes(32)
        if kind in ('combined','prefix'):extra=bytes(32)+extra[32:]
        if kind=='prefix':v[2]|=32;extra=extra[:32]+bytes([1])*32
        if kind=='private_size':v[12]+=1
        return extra
    t.proof_mutation=mutate
    with pytest.raises(DeviceError):c.restore(path,[PUBLIC],repair_code=True)
    assert not any(w[0]==0x94 for w in t.writes)
    if kind!='repair_flag':assert not any(w[0]==0x91 and a.REQUEST.unpack(w[1])[2]==a.RESTORE for w in t.writes)


def test_legacy_prefix_proof_allows_an_independent_private_snapshot(tmp_path,payload):
    t=RepairTransport(payload,legacy=True);c=t.client();path=tmp_path/'backup';path.write_bytes(payload)
    t.proof_mutation=lambda v,extra:bytes(32)+extra[32:]
    assert c.restore(path,[PUBLIC],repair_code=True)['code_repaired']


@pytest.mark.parametrize('field,value',[(0,192),(1,1),(2,8),(2,1|8|32),(4,1),(7,1),(17,b'identity')])
def test_repair_information_does_not_invent_authenticated_metadata(payload,field,value):
    t=RepairTransport(payload);t.request_flags=4;raw=t.info();values=list(a.INFO.unpack(raw[:192]));values[field]=value
    with pytest.raises(DeviceError):a.decode_info(a.INFO.pack(*values)+raw[192:],'document',repair=True)


def test_cli_repair_and_extended_inspection(tmp_path,payload,monkeypatch,capsys):
    import cli,json
    from contextlib import nullcontext
    t=RepairTransport(payload);path=tmp_path/'backup';path.write_bytes(payload)
    monkeypatch.setattr(a,'ArchiveUSB',lambda:nullcontext(t))
    monkeypatch.setattr(sys,'argv',['lefony-sdk','archive','info','document','--include-unreadable'])
    assert cli.main()==0 and json.loads(capsys.readouterr().out)['version'] is None
    monkeypatch.setattr(sys,'argv',['lefony-sdk','archive','restore',str(path),'--public-key',str(PUBLIC),'--repair-code'])
    assert cli.main()==0 and json.loads(capsys.readouterr().out)['code_repaired']
