# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded RAM entry and erase-budget checks; no USB enumeration."""
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prime_phase6_transport as t
import prime_phase6_recovery_entry as entry


@pytest.mark.parametrize('remaining,accepted',[(5400000,True),(300001,True),(300000,False),(0,False),(5400001,False)])
def test_recovery_budget_is_checked_before_each_erase(monkeypatch,remaining,accepted):
    calls=[];d=t.Phase6SDP.__new__(t.Phase6SDP)
    d.run=lambda cmd:calls.append(cmd)
    d.read=lambda addr,length:struct.pack('<4I',0x36445242,1,remaining,5400000)
    monkeypatch.setattr(t.PrimeSDP,'erase',lambda *a,**kw:calls.append('erase'))
    if accepted:d.erase(258)
    else:
        with pytest.raises(TimeoutError):d.erase(258)
    assert calls==['hprecoverybudget']+(['erase'] if accepted else [])


def test_rom_launch_verifies_complete_ram_without_depending_on_snvs(monkeypatch,tmp_path):
    start=0x877ff400;offset=0xc00;code=b'bounded test code'
    image=bytearray(offset+len(code))
    struct.pack_into('<8I',image,0,0x402000d1,0x87800000,0,start+44,start+32,start,0,0)
    image[44:48]=bytes.fromhex('d201e840');image[offset:]=code
    binary=tmp_path/'ram.bin';binary.write_bytes(code)
    imx=tmp_path/'ram.imx';imx.write_bytes(image)
    calls=[];ram={};jumped=False
    class HID:
        def open_path(self,path):calls.append('open-rom')
        def close(self):calls.append('close-rom')
        def write(self,*a):raise AssertionError('ROM register write is not required')
    def enumerate(vid,pid):
        if vid==0x15a2 and not jumped:return [{'usage_page':0xff00,'usage':1,'path':b'test'}]
        if vid==0xcafe and jumped:return [{'path':b'recovery'}]
        return []
    monkeypatch.setitem(sys.modules,'hid',SimpleNamespace(enumerate=enumerate,device=HID))
    def command(self,cmd,address,data=b''):
        nonlocal jumped
        calls.append(cmd)
        if cmd==0x0404:ram[address]=data
        if cmd==0x0b0b:jumped=True
    monkeypatch.setattr(entry.PrimeSDP,'_command',command)
    ack=iter((0x128a8a12,0x900dd009))
    monkeypatch.setattr(entry.PrimeSDP,'_ack',lambda *a:next(ack))
    monkeypatch.setattr(entry.PrimeSDP,'read',lambda self,addr,n:ram[start][addr-start:addr-start+n])
    monkeypatch.setattr(entry,'Phase6SDP',lambda:SimpleNamespace(verify_protocol=lambda:calls.append('verified-recovery'),close=lambda:None))
    entry.enter(binary,imx,tmp_path)
    assert calls==['open-rom',0x0a0a,0x0c0c,0x0404,0x0b0b,'close-rom','verified-recovery']
