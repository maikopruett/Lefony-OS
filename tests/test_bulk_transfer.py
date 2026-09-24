# SPDX-License-Identifier: GPL-3.0-or-later
import struct
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sdk/tools'))
from bulk_transfer import MAGIC,CAPACITY,available,upload,download,try_upload

class Device:
    def __init__(self,payload=b''):
        self.state=0;self.sequence=0;self.target=0;self.length=0;self.received=0;self.applied=0
        self.payload=payload;self.data=bytearray();self.commands=[];self.sends=[]
    def read(self,*args,**kwargs):
        return struct.pack('<16I',MAGIC,1,self.state,self.sequence,self.target,self.length,self.received,self.applied,0,CAPACITY,262144,1,1,1,0,0)
    def write(self,request,data=b'',value=0,index=0):
        self.commands.append(request)
        if request==0x59:
            _,_,self.target,self.length,_,_=struct.unpack('<6I',data);self.sequence+=1;self.state=1
        elif request==0x5a:self.applied=self.length;self.state=4
        elif request==0x5b:self.state=0
    def send(self,data):
        self.sends.append(len(data));self.data.extend(data);self.received+=len(data)
        if self.received==self.length:self.state=2
    def receive(self,length):
        result=self.payload[self.received:self.received+length];self.received+=len(result)
        if self.received==self.length:self.state=4;self.applied=self.length
        return result

def test_upload_has_separate_apply_and_never_commits():
    d=Device();data=bytes(range(256))*2049
    assert upload(d.read,d.write,d.send,3,data,sequence=91)
    assert bytes(d.data)==data and max(d.sends)==262144
    assert d.commands==[0x59,0x5a]

def test_ambiguous_payload_is_not_replayed_or_applied():
    d=Device()
    def fail(data):d.send(data);raise OSError('lost ACK')
    with pytest.raises(OSError):upload(d.read,d.write,fail,1,b'x'*524288)
    assert d.commands==[0x59,0x5b] and len(d.sends)==1

def test_cancel_before_apply_aborts_only():
    d=Device()
    with pytest.raises(RuntimeError,match='cancelled'):
        upload(d.read,d.write,d.send,3,b'x'*524288,cancelled=lambda:bool(d.received))
    assert d.commands==[0x59,0x5b]

def test_bulk_export_matches_exact_payload_without_commit():
    d=Device(bytes(range(256))*2051)
    assert download(d.read,d.write,d.receive,4,len(d.payload),sequence=17)==d.payload
    assert d.commands==[0x59]

def test_short_download_aborts():
    d=Device(b'abc')
    with pytest.raises(RuntimeError,match='Short bulk'):
        download(d.read,d.write,lambda size:d.receive(size-1),5,3)
    assert d.commands==[0x59,0x5b]

def test_legacy_detection_is_read_only():
    assert not available(bytes((9,2,18,0,1,1,0,128,25,9,4,0,0,0,255,77,71,0)))
    assert not try_upload(object(),1,b'data')

def test_invalid_status_rejected_before_writes():
    d=Device();d.length=CAPACITY+1
    with pytest.raises(RuntimeError):upload(d.read,d.write,d.send,2,b'abc')
    assert not d.commands

@pytest.mark.parametrize('mode', ['slow', 'stalled', 'endless'])
def test_physical_file_apply_has_progress_and_absolute_bounds(monkeypatch, mode):
    import bulk_transfer
    clock = [0]
    monkeypatch.setattr(bulk_transfer.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(bulk_transfer.time, 'sleep', lambda _: clock.__setitem__(0, clock[0]+30))
    class SlowDevice(Device):
        def write(self, request, *args, **kwargs):
            super().write(request, *args, **kwargs)
            if request == 0x5a:self.state=3;self.applied=0
        def read(self, *args, **kwargs):
            if self.state == 3 and mode != 'stalled':
                self.applied += 25 if mode == 'slow' else 1
                if self.applied == self.length:self.state=4
            return super().read(*args, **kwargs)
    d=SlowDevice()
    if mode == 'slow':
        assert upload(d.read,d.write,d.send,3,b'x'*1000)
        assert 600 < clock[0] < 1800 and d.commands == [0x59,0x5a]
    else:
        with pytest.raises(RuntimeError,match='stalled' if mode == 'stalled' else 'timed out'):
            upload(d.read,d.write,d.send,3,b'x'*1000)
        assert clock[0] <= (150 if mode == 'stalled' else 1800)
        assert d.commands == [0x59,0x5a,0x5b]
