# SPDX-License-Identifier: GPL-3.0-or-later
"""Logical history and independently encoded tag/ECC corruption cases."""
from pathlib import Path
import hashlib
import json
import struct
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vm'))
import prime_hp_logical_archive as a
from prime_bch_native import NativeBCH
from prime_gpmi_bch import Layout


def header(kind,parent,name,size=0,shrink=0,shadow=0):
    data=bytearray(2048)
    struct.pack_into('>2I',data,0,kind,parent)
    data[10:10+len(name)]=name
    struct.pack_into('>I',data,292,size)
    struct.pack_into('>2I',data,504,shadow,shrink)
    return bytes(data)


def source(tmp_path,pages):
    path=tmp_path/'source.raw'
    with path.open('wb') as f:
        f.truncate(4096*64*2112)
        f.seek(392*64*2112);f.write(b'\xff'*(64*2112))
        f.seek(4094*64*2112);f.write(b'\xff'*(128*2112))
        with NativeBCH() as native:
            for index,(obj,chunk,length,data) in enumerate(pages):
                tags=struct.pack('>4I',0x1000,obj,chunk,length)
                raw=a.encode(data.ljust(2048,b'\0'),tags,native)
                f.seek((392*64+index)*2112);f.write(raw)
    return path


def test_shrink_then_extend_does_not_resurrect_old_tail(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'private_output',lambda p:p)
    pages=[(257,0,0xffff,header(1,1,b'file',4096)),
           (257,1,2048,b'A'*2048),(257,2,2048,b'B'*2048),
           (257,0,0xffff,header(1,1,b'file',100,1)),
           (257,0,0xffff,header(1,1,b'file',4096)),
           (258,0,0xffff,header(3,4,b'deleted-directory',0,1))]
    report=a.export(source(tmp_path,pages),tmp_path/'archive',end=393)
    assert report['end_block']==393
    assert [o['id'] for o in report['objects']]==[257]
    assert (tmp_path/'archive/257.data').read_bytes()==b'A'*100+bytes(3996)
    recreated=a.recreate(tmp_path/'archive',tmp_path/'recreated')
    assert recreated['used_pages']==3
    with NativeBCH() as native:
        raw=(tmp_path/'recreated/392.raw').read_bytes()
        restored,_=a.decode(raw[:2112],native)
        assert struct.unpack_from('>2I',restored,504)==(0,0)
        restored,_=a.decode(raw[2112:4224],native)
        assert restored==b'A'*100+bytes(1948)


def test_shadowed_rename_and_post_header_write(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'private_output',lambda p:p)
    pages=[(257,0,0xffff,header(1,1,b'file',3)),(257,1,3,b'old'),
           (258,0,0xffff,header(1,1,b'file',0,shadow=257)),(258,1,3,b'new')]
    report=a.export(source(tmp_path,pages),tmp_path/'archive',end=393)
    assert [(o['id'],o['size']) for o in report['objects']]==[(258,3)]
    assert (tmp_path/'archive/258.data').read_bytes()==b'new'
    (tmp_path/'archive/258.data').write_bytes(b'bad')
    with pytest.raises(ValueError,match='backup mismatch'):a.verify(tmp_path/'archive')


@pytest.mark.parametrize('fault',['duplicate','cycle','link'])
def test_incomplete_or_ambiguous_tree_fails_before_archive(tmp_path,monkeypatch,fault):
    monkeypatch.setattr(a,'private_output',lambda p:p)
    if fault=='duplicate':pages=[(257,0,0xffff,header(1,1,b'a')),(258,0,0xffff,header(1,1,b'a'))]
    elif fault=='cycle':pages=[(257,0,0xffff,header(3,258,b'a')),(258,0,0xffff,header(3,257,b'b'))]
    else:pages=[(257,0,0xffff,header(2,1,b'link'))]
    with pytest.raises(ValueError):a.export(source(tmp_path,pages),tmp_path/'archive',end=393)
    assert not (tmp_path/'archive').exists()


def test_tag_parity_known_vector_and_unused_padding():
    # Packed tags: sequence 4096, object 257, header 0, byte count 65535.
    tags=bytes.fromhex('0000100000000101000000000000ffff')
    # Three odd bytes (indices 2, 6, 7) give row 3, complement ~3;
    # the paired bit-zero contributions cancel, leaving bit four's 0x25.
    assert a.tag_ecc(tags).hex()=='2500000003000000fcffffff'


@pytest.mark.parametrize('registers',[(0x03241080,0x08401080),(0x030a0880,0x08400880),(0x0720a020,0x0840a020)])
def test_accelerated_bch_decode_matches_reference(registers):
    geometry=Layout(*registers)
    data=bytes((i*7+19)&255 for i in range(geometry.payload_bytes))
    metadata=bytes((i*11+3)&255 for i in range(geometry.metadata_bytes))
    with NativeBCH() as native:
        raw=geometry.encode(data,metadata,native)
        for bit in (None,7,331):
            damaged=bytearray(raw)
            if bit is not None:damaged[bit//8]^=1<<(bit%8)
            assert geometry.decode(bytes(damaged),decoder=native)==geometry.decode(bytes(damaged))
