# SPDX-License-Identifier: GPL-3.0-or-later
"""Small synthetic media exercises capture integrity without USB."""
import hashlib
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prime_phase6_capture as c


@pytest.fixture
def device(monkeypatch):
    monkeypatch.setattr(c,'RAW_BLOCK',8)
    monkeypatch.setattr(c,'ERASED',b'\xff'*8)
    monkeypatch.setattr(c.model,'private_output',lambda p:p)
    class Device:
        calls=0
        reads=[]
        changed=False
        def verify_protocol(self):pass
        def inventory(self):return c.GEOMETRY,{7}
        def raw(self,b):return b.to_bytes(8,'little') if b<2 else c.ERASED
        def hash_blocks(self,first,count):
            self.calls+=1
            values=[hashlib.sha256(self.raw(b)).hexdigest() for b in range(first,first+count)]
            if self.changed and self.calls==129:values[0]='00'*32
            return values
        def read_block(self,b):self.reads.append(b);return self.raw(b)
    return Device()


def test_reference_reuse_requires_fresh_match_and_unknown_bytes_are_read(device,tmp_path):
    reference=tmp_path/'reference.raw'
    reference.write_bytes(bytes(8)+b'wrong!!!'+c.ERASED*4094)
    output=tmp_path/'capture.raw'
    report=c.capture(device,output,[reference],event=lambda _:None)
    assert device.reads==[1] and device.calls==256
    assert report['raw_reads']==1 and report['complete_matching_fingerprints']==2
    assert output.read_bytes()==b''.join(device.raw(b) for b in range(4096))
    assert output.stat().st_mode&0o777==0o600


def test_changed_second_fingerprint_cannot_finalize_capture(device,tmp_path):
    device.changed=True;output=tmp_path/'capture.raw'
    with pytest.raises(ValueError,match='changed between'):
        c.capture(device,output,[],event=lambda _:None)
    assert not output.exists() and not output.with_suffix('.json').exists()


def test_raw_read_must_match_independent_device_hash(device,tmp_path):
    device.read_block=lambda _:b'wrong!!!'
    with pytest.raises(ValueError,match='unstable raw'):
        c.capture(device,tmp_path/'capture.raw',[],event=lambda _:None)
