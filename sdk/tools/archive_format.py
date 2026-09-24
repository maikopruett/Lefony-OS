# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable app snapshots with bounded parsing and independently checked content.

Archives carry signed packages and mutable data, never device trust or internal
NAND/object identifiers. Validation precedes device access. An optional trusted
public-key list authenticates packages; structural validation alone does not.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
import struct
import subprocess

from signing import MAX_PACKAGE, envelope, verify

HEADER=struct.Struct('<8s14I64s')
PAIR=struct.Struct('<16I32s32s')
ENTRY=struct.Struct('<96s4I')
MAX_DATA=64*1024*1024
MAX_ARCHIVE=HEADER.size+2*(PAIR.size+MAX_PACKAGE+MAX_DATA+127*(ENTRY.size+32))
EMPTY_HASH=hashlib.sha256(b'').digest()


class ArchiveError(ValueError):
    pass


@dataclass(frozen=True)
class Span:
    offset: int
    size: int
    sha256: str


@dataclass(frozen=True)
class EntryInfo:
    path: str
    directory: bool
    content: Span


@dataclass(frozen=True)
class Snapshot:
    metadata: dict
    data_schema: int
    package: Span
    private: Span
    entries: tuple


@dataclass(frozen=True)
class Archive:
    app_id: str
    size: int
    sha256: str
    high_version: tuple
    snapshots: tuple
    signatures_checked: bool


def _require(condition,message):
    if not condition:raise ArchiveError(message)


def _text(raw):
    n=raw.find(b'\0')
    _require(n>0 and not any(raw[n:]),'Noncanonical archive text')
    try:return raw[:n].decode('ascii')
    except UnicodeDecodeError:raise ArchiveError('Non-ASCII archive text') from None


def _path(value):
    return (0<len(value)<=95 and all(re.fullmatch(r'[A-Za-z0-9._ -]{1,48}',part) and part not in ('.','..') for part in value.split('/')))


def _version(metadata):
    return tuple(int(part) for part in metadata['version'].split('.'))


def validate(source,public_keys=None,*,cancelled=lambda:False):
    """Read one open regular file, verifying all bytes in bounded chunks.

The caller retains the same descriptor for transfer. Firmware must still verify
the complete transfer digest and its own enrolled/compiled signing authority.
"""
    info=os.fstat(source.fileno())
    _require(stat.S_ISREG(info.st_mode),'Select a regular app archive file')
    _require(HEADER.size<=info.st_size<=MAX_ARCHIVE,'Invalid app archive size')
    source.seek(0);whole=hashlib.sha256();offset=0
    def read(size):
        nonlocal offset
        _require(not cancelled(),'Archive validation cancelled')
        _require(0<=size<=1024*1024 and size<=info.st_size-offset,'Truncated app archive')
        data=source.read(size);_require(len(data)==size,'Truncated app archive')
        whole.update(data);offset+=size;return data
    def content(size,expected,*,retain=False):
        start=offset;hasher=hashlib.sha256();parts=[]
        remaining=size
        while remaining:
            data=read(min(remaining,1024*1024));hasher.update(data);remaining-=len(data)
            if retain:parts.append(data)
        _require(expected is None or hasher.digest()==expected,'Archive content hash mismatch')
        return Span(start,size,hasher.hexdigest()),b''.join(parts) if retain else None
    h=HEADER.unpack(read(HEADER.size))
    _require(h[0]==b'LFARCH1\0' and h[1:3]==(1,HEADER.size),'Unsupported app archive format')
    _require(h[3]==info.st_size and h[4] in (1,2) and h[5]==int(h[4]==2) and not h[6] and not any(h[10:15]),'Invalid app archive header')
    app_id=_text(h[15]);high=tuple(h[7:10])
    _require(bool(re.fullmatch(r'[a-z][a-z0-9-]{0,47}',app_id)) and max(high)<=999999,'Invalid archived app identity')
    snapshots=[]
    for pair_number in range(h[4]):
        p=PAIR.unpack(read(PAIR.size))
        _require(p[:2]==(PAIR.size,1) and 468<=p[2]<=MAX_PACKAGE and p[4]<=65536 and p[5]<=127 and max(p[6:9])<=999999 and not any(p[9:16]),'Invalid archive snapshot header')
        package,blob=content(p[2],p[16],retain=True)
        try:
            metadata=(verify(blob,public_keys)[0] if public_keys is not None else envelope(blob)[2])
        except (ValueError,OSError,subprocess.SubprocessError) as exc:raise ArchiveError('Invalid signed package in archive: '+str(exc)) from exc
        _require(metadata['abi']==1 and metadata['id']==app_id and _version(metadata)==tuple(p[6:9]) and _version(metadata)<=high,'Archived package identity does not match its snapshot')
        app_schema=metadata.get('data_schema',0)
        _require((h[4]==2 and pair_number==0) or p[3]==app_schema,'Archived data schema is incompatible with its package')
        private,_=content(p[4],p[17]);entries=[];names={};used=p[4]
        for _ in range(p[5]):
            e=ENTRY.unpack(read(ENTRY.size));name=_text(e[0])
            _require(_path(name) and name not in names and e[1] in (1,2) and not e[3] and not e[4] and e[2]<=MAX_DATA,'Invalid archive file entry')
            directory=e[1]==2
            _require(not directory or not e[2],'Invalid archive directory')
            _require(used+e[2]<=MAX_DATA,'Archived snapshot exceeds the storage format limit')
            span,_=content(e[2],None)
            if not directory:_require(bytes.fromhex(span.sha256)==read(32),'Archive file hash mismatch')
            names[name]=directory;entries.append(EntryInfo(name,directory,span));used+=e[2]
            _require(used<=MAX_DATA,'Archived snapshot exceeds the storage format limit')
        for name in names:
            if '/' in name:_require(names.get(name.rsplit('/',1)[0]) is True,'Archived file has no directory parent')
        # The runtime reserves one index entry for private bytes and permits at
        # most 512 extents. Nonempty files and the private store are chunked
        # independently; empty files consume an entry but no extent.
        chunk_bytes=128*1024-128
        extents=(p[4]+chunk_bytes-1)//chunk_bytes+sum((entry.content.size+chunk_bytes-1)//chunk_bytes for entry in entries)
        _require(extents<=512,'Archived snapshot exceeds the file-index limit')
        snapshots.append(Snapshot(metadata,p[3],package,private,tuple(entries)))
    _require(offset==info.st_size and source.read(1)==b'','App archive has trailing bytes')
    if len(snapshots)==2:
        _require(_version(snapshots[1].metadata)<_version(snapshots[0].metadata),'Invalid retained upgrade version')
    return Archive(app_id,offset,whole.hexdigest(),high,tuple(snapshots),public_keys is not None)


def inspect(path,public_keys=None):
    # Opening a FIFO must not block before fstat can reject it. Keep and validate
    # the opened descriptor so a path replacement cannot change the selected file.
    descriptor=os.open(Path(path),os.O_RDONLY|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(descriptor,'rb') as source:return validate(source,public_keys)
