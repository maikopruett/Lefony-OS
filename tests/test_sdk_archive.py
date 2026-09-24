# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import io
import os
import struct
import sys
from pathlib import Path
import pytest
from test_native_app_package import META,image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
import archive_format as archive
import signing
from lfapp import pack

PRIVATE=ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem'
PUBLIC=ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'


def signed(version='2.0.0',app_id='document',schema=0):
    metadata={**META,'abi':1,'id':app_id,'version':version}
    if schema:metadata.update(schema=1,data_schema=schema,minimum_api=1,required_capabilities=0,optional_capabilities=0)
    return signing.sign(pack(metadata,image()),PRIVATE)


def snapshot(package,private=b'saved',entries=(),schema=0):
    metadata=signing.envelope(package)[2]
    result=archive.PAIR.pack(128,1,len(package),schema,len(private),len(entries),
        *map(int,metadata['version'].split('.')),*([0]*7),hashlib.sha256(package).digest(),hashlib.sha256(private).digest())
    result+=package+private
    for name,data in entries:
        result+=archive.ENTRY.pack(name.encode().ljust(96,b'\0'),2 if data is None else 1,0 if data is None else len(data),0,0)
        if data is not None:result+=data+hashlib.sha256(data).digest()
    return result


def encoded(*pairs,app_id='document',high=(2,0,0)):
    body=b''.join(pairs)
    return archive.HEADER.pack(b'LFARCH1\0',1,128,128+len(body),len(pairs),int(len(pairs)==2),0,*high,*([0]*5),app_id.encode().ljust(64,b'\0'))+body


@pytest.fixture(scope='module')
def packages():return signed(),signed('1.0.0'),signed('2.0.0',schema=3)


def inspect_bytes(tmp_path,data,keys=None):
    path=tmp_path/'snapshot.lfarchive';path.write_bytes(data)
    return archive.inspect(path,keys)


def test_current_and_pending_snapshots_keep_exact_offsets_hashes_and_signatures(tmp_path,packages):
    current,previous,upgraded=packages
    files=(('docs/note.bin',bytes(range(256))*1100),('docs',None),('empty',b''))
    data=encoded(snapshot(upgraded,b'old schema',files,schema=0),snapshot(previous,b'recovery',files))
    result=inspect_bytes(tmp_path,data,[PUBLIC])
    assert result.signatures_checked and result.high_version==(2,0,0)
    assert result.sha256==hashlib.sha256(data).hexdigest() and result.size==len(data)
    assert [p.metadata['version'] for p in result.snapshots]==['2.0.0','1.0.0']
    assert result.snapshots[0].data_schema==0 and result.snapshots[0].metadata['data_schema']==3
    for p in result.snapshots:
        for span in (p.package,p.private,*(e.content for e in p.entries)):
            assert hashlib.sha256(data[span.offset:span.offset+span.size]).hexdigest()==span.sha256
    assert not inspect_bytes(tmp_path,data).signatures_checked
    assert inspect_bytes(tmp_path,encoded(snapshot(current,b'',(('zero',b''),))),[PUBLIC]).snapshots[0].private.size==0


@pytest.mark.parametrize('offset,value',[(0,0),(8,2),(12,127),(16,1),(20,0),(24,1),(28,1),(32,1000000),(44,1),
    (128,127),(132,2),(136,467),(144,65537),(148,128),(152,1000000),(164,1)])
def test_invalid_headers_fail(tmp_path,packages,offset,value):
    raw=bytearray(encoded(snapshot(packages[0])));struct.pack_into('<I',raw,offset,value)
    with pytest.raises(archive.ArchiveError):inspect_bytes(tmp_path,raw)


@pytest.mark.parametrize('name',['../escape','/root','a//b','a/..','a/./b','a\\b','a'*49,'x/','é','a\0hidden'])
def test_invalid_paths_fail(tmp_path,packages,name):
    with pytest.raises(archive.ArchiveError):inspect_bytes(tmp_path,encoded(snapshot(packages[0],entries=((name,b'x'),))))


@pytest.mark.parametrize('entries',[(('missing/file',b'x'),),(('file',b'x'),('file/child',b'y')),(('same',None),('same',b'x'))])
def test_directory_tree_is_validated_as_a_whole(tmp_path,packages,entries):
    with pytest.raises(archive.ArchiveError):inspect_bytes(tmp_path,encoded(snapshot(packages[0],entries=entries)))


def test_integrity_is_not_signature_authority(tmp_path,packages):
    package=bytearray(packages[0]);package[96]^=1
    raw=encoded(snapshot(package))
    assert not inspect_bytes(tmp_path,raw).signatures_checked
    with pytest.raises(archive.ArchiveError,match='signature'):inspect_bytes(tmp_path,raw,[PUBLIC])
    with pytest.raises(archive.ArchiveError,match='key'):inspect_bytes(tmp_path,encoded(snapshot(packages[0])),[])


@pytest.mark.parametrize('kind',['package','private','file','trailer','padding','directory_size','directory_reserved','trailing','truncated','wrong_identity','wrong_version','schema','previous_schema','previous_version'])
def test_snapshot_mismatches_fail(tmp_path,packages,kind):
    current,previous,upgraded=packages
    raw=bytearray(encoded(snapshot(current,b'data',(('file',b'contents'),('dir',None)))))
    entry=256+len(current)+4
    if kind=='package':raw[256+len(current)-1]^=1
    elif kind=='private':raw[256+len(current)]^=1
    elif kind=='file':raw[entry+112]^=1
    elif kind=='trailer':raw[entry+112+8]^=1
    elif kind=='padding':raw[entry+5]=1
    elif kind=='directory_size':struct.pack_into('<I',raw,entry+112+8+32+100,1)
    elif kind=='directory_reserved':struct.pack_into('<I',raw,entry+112+8+32+104,1)
    elif kind=='trailing':raw+=b'x';struct.pack_into('<I',raw,16,len(raw))
    elif kind=='truncated':raw=raw[:-1];struct.pack_into('<I',raw,16,len(raw))
    elif kind=='wrong_identity':raw=encoded(snapshot(current),app_id='other')
    elif kind=='wrong_version':struct.pack_into('<I',raw,152,1)
    elif kind=='schema':raw=encoded(snapshot(upgraded,schema=0))
    elif kind=='previous_schema':raw=encoded(snapshot(current),snapshot(previous,schema=1))
    elif kind=='previous_version':raw=encoded(snapshot(current),snapshot(current))
    with pytest.raises(archive.ArchiveError):inspect_bytes(tmp_path,raw)


def test_bounded_reads_and_cancellation(tmp_path,packages):
    raw=encoded(snapshot(packages[0],entries=(('large',b'x'*(2*1024*1024+13)),)))
    path=tmp_path/'snapshot';path.write_bytes(raw)
    class Bounded:
        def __init__(self,source):self.source=source;self.sizes=[]
        def fileno(self):return self.source.fileno()
        def seek(self,*args):return self.source.seek(*args)
        def read(self,size):
            assert 0<=size<=1024*1024
            self.sizes.append(size);return self.source.read(size)
    with path.open('rb') as source:
        bounded=Bounded(source);archive.validate(bounded)
        assert max(bounded.sizes)==1024*1024
        with pytest.raises(archive.ArchiveError,match='cancelled'):archive.validate(bounded,cancelled=lambda:True)


@pytest.mark.skipif(not hasattr(os,'mkfifo'),reason='FIFO unavailable on host')
def test_fifo_is_rejected_before_blocking(tmp_path):
    path=tmp_path/'fifo';os.mkfifo(path)
    with pytest.raises(archive.ArchiveError,match='regular'):archive.inspect(path)
