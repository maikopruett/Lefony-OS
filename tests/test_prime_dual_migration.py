# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline executor preflight and physical journal/page semantics, no HP inputs."""
from pathlib import Path
import struct
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vm'))
import prime_dual_migration as m
from prime_nand_image import checksum,encode_fcb


def fcb():
    # Well-formed legacy BCH2 ROM geometry must not pass the new BCH4 barrier.
    data=bytearray(1024)
    for offset,value in {4:0x20424346,8:0x01000000,0x14:2048,0x18:2112,0x1c:64,
        0x2c:1,0x30:512,0x34:512,0x38:1,0x3c:10,0x40:3,
        0x68:240*64,0x6c:248*64,0x70:1,0x74:1,0x78:256,
        0x7c:2028,0x80:2,0x84:2048}.items():struct.pack_into('<I',data,offset,value)
    struct.pack_into('<I',data,0,checksum(data))
    return encode_fcb(data)+b'\xff'*(63*2112)


def test_rom_route_barrier_checks_ecc_geometry(tmp_path,monkeypatch):
    image=tmp_path/'uboot.imx';image.write_bytes(bytes.fromhex('d1002040'))
    monkeypatch.setattr(m,'read_block',lambda *args:fcb())
    with m.NativeBCH() as native,pytest.raises(ValueError,match='BCH geometry'):
        m.verify_routes(tmp_path/'unused',image,set(),native)


def test_candidate_cannot_rewrite_dbbt_or_other_rom_controls(tmp_path,monkeypatch):
    digest=bytes(range(32));backup=tmp_path/'backup';candidate=tmp_path/'candidate'
    monkeypatch.setattr(m,'file_hash',lambda p:digest)
    monkeypatch.setattr(m,'bad_inventory',lambda p:set())
    def block(path,index):
        if index>=240:return m.ERASED
        raw=fcb()
        if path==candidate:
            decoded=bytearray(m.decode_fcb(raw[:2112])[0])
            struct.pack_into('<I',decoded,0x78,512)
            struct.pack_into('<I',decoded,0,checksum(decoded))
            raw=encode_fcb(decoded)+b'\xff'*(63*2112)
        return raw
    monkeypatch.setattr(m,'read_block',block)
    with pytest.raises(ValueError,match='DBBT search'):
        m.build_plan(backup,candidate,None,None,None,None,digest)


def test_file_media_uses_ecc_journals_and_refuses_zero_to_one(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'private_output',lambda p:p.resolve())
    target=tmp_path/'nand.raw';backup=tmp_path/'backup.raw'
    for path in (target,backup):
        with path.open('wb') as f:f.truncate(4096*m.RAW_BLOCK)
    media=m.FileMedia(target,backup,{300},tmp_path/'uboot')
    try:
        page=bytes((i*13)&255 for i in range(2048))
        media.write_journal(0,page)
        assert media.read_journal(0)==page
        assert media.read_block(258)[:2112]!=page+b'\xff'*64
        media.erase_block(260)
        media.program_raw_page(260*64,b'\xaa'*2112)
        old=media.read_block(260)
        with pytest.raises(ValueError,match='zero-to-one'):
            media.program_raw_page(260*64,b'\xff'*2112)
        assert media.read_block(260)==old
        with pytest.raises(ValueError,match='bad block'):media.erase_block(300)
    finally:media.close()
