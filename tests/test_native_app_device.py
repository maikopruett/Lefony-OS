# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import hashlib
import json
import struct
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
import device
from signing import sign, openssl
from lfapp import pack
from test_native_app_package import image

META={'abi':1,'id':'sample','name':'Sample','license':'CC-BY-NC-SA-4.0','version':'1.0.0'}

@pytest.fixture
def signed(tmp_path):
    private=tmp_path/'private.pem';public=tmp_path/'public.pem'
    private.write_bytes(openssl('genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048'))
    public.write_bytes(openssl('pkey','-in',private,'-pubout'))
    return sign(pack(META,image()),private),[public]

class Transport:
    def __init__(self,state=2):
        self.state=state;self.calls=[];self.upload=bytearray();self.package=b'';self.expected=0;self.backup=bytes(range(256))*17;self.offset=0;self.corrupt=False;self.ambiguous=False
    def write(self,request,data=b'',value=0,index=0):
        argument=value|(index<<16);self.calls.append(request)
        assert 0x60<=request<=0x6a
        if request==0x60:pass
        elif request==0x61:self.state=3;self.offset=0
        elif request==0x62:assert data==hashlib.sha256(self.backup[:device.BACKUP_BYTES]).digest();self.state=2
        elif request==0x63:self.expected=argument;self.upload=bytearray();self.state=4
        elif request==0x64:assert argument==len(self.upload);self.upload.extend(data)
        elif request==0x65:
            assert len(self.upload)==self.expected
            self.package=bytes(self.upload);self.state=6
            if self.ambiguous:raise OSError('lost commit acknowledgement')
        elif request==0x66:self.package=b'';self.state=6
        elif request==0x67:self.state=0
        elif request==0x6a:self.state=6
    def read(self,request,value=0,index=0,length=0):
        offset=value|(index<<16)
        if request==0x60:return struct.pack('<16I',0x3141464c,1,self.state,0,len(self.upload),self.expected,1,8,1,device.BACKUP_BYTES,self.offset,1,0,0,0,0)
        if request==0x61:assert offset==self.offset;self.offset+=length;return self.backup[offset:offset+length]
        if request==0x62:return hashlib.sha256(self.backup[:device.BACKUP_BYTES]).digest()
        if request==0x68:
            row=bytearray(168)
            if self.package and offset==0:
                struct.pack_into('<III',row,0,len(self.package),1,1)
                for start,key in [(12,'id'),(61,'name'),(142,'version')]:row[start:start+len(META[key])]=META[key].encode()
            return bytes(row)
        if request==0x6a:
            result=bytearray(self.package[offset:offset+length])
            if self.corrupt:result[0]^=1
            return bytes(result)
        raise AssertionError(request)

def test_signed_install_readback_and_remove(signed):
    package,keys=signed;t=Transport();c=device.Client(t)
    assert c.connect()['state']==2
    assert c.install(package,keys)['id']=='sample'
    c.remove('sample');assert c.catalog()==[]

def test_invalid_signature_never_uploads(signed):
    package,keys=signed;t=Transport();value=bytearray(package);value[100]^=1
    with pytest.raises(ValueError):device.Client(t).install(value,keys)
    assert not t.calls

def test_unknown_commit_outcome_is_never_retried(signed):
    package,keys=signed;t=Transport();t.ambiguous=True
    with pytest.raises(OSError):device.Client(t).install(package,keys)
    assert t.calls.count(0x65)==1 and 0x67 not in t.calls

def test_readback_mismatch_is_not_success(signed):
    package,keys=signed;t=Transport();t.corrupt=True
    with pytest.raises(device.DeviceError,match='readback'):device.Client(t).install(package,keys)

def test_cancel_is_before_commit(signed):
    package,keys=signed;t=Transport()
    with pytest.raises(device.DeviceError,match='cancelled'):device.Client(t).install(package,keys,cancelled=lambda:True)
    assert 0x65 not in t.calls and t.calls[-1]==0x67

def test_backup_is_durable_and_verified_before_migration(tmp_path,monkeypatch):
    monkeypatch.setattr(device,'BACKUP_BYTES',4224)
    t=Transport(1);c=device.Client(t);directory=tmp_path/'backup'
    with pytest.raises(device.DeviceError,match='consent'):c.backup_and_migrate(directory)
    assert not t.calls and not directory.exists()
    record=c.backup_and_migrate(directory,retire_stock_filesystem=True)
    assert record['migration_committed']
    assert (directory/'app-region.raw').read_bytes()==t.backup[:4224]
    assert (directory/'app-region.raw').stat().st_mode&0o777==0o600
    assert not json.loads((directory/'backup.json').read_text())['migration_committed']
    assert t.calls==[0x61,0x62]

def test_bad_backup_receipt_prevents_migration(tmp_path,monkeypatch):
    monkeypatch.setattr(device,'BACKUP_BYTES',4224)
    t=Transport(1);read=t.read
    t.read=lambda request,**kwargs:bytes(32) if request==0x62 else read(request,**kwargs)
    with pytest.raises(device.DeviceError,match='verification'):device.Client(t).backup_and_migrate(tmp_path/'backup',retire_stock_filesystem=True)
    assert 0x62 not in t.calls
