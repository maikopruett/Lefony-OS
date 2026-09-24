# SPDX-License-Identifier: GPL-3.0-or-later
"""Saved preview snapshots, composed only with the public emulator fixture key.

Source edits can replace a preview's code at the same version. Each composed
snapshot is restored into fresh synthetic media using normal signed USB APIs;
no installed namespace or firmware update policy is bypassed.
"""
from contextlib import ExitStack,contextmanager
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile

import archive_format as wire
from sdk_environment import SDK
from signing import sign,verify

PUBLIC=SDK.parent/'tests/fixtures/prime_g2_emulator_update_public.pem'
PRIVATE=SDK.parent/'tests/fixtures/prime_g2_emulator_update_private.pem'
QUOTA=32*1024*1024


@contextmanager
def regular(path):
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0))
    with os.fdopen(fd,'rb') as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):raise ValueError('Preview data must be a regular file')
        yield source


def fixtures(directory):
    directory=Path(directory)
    if directory.is_symlink() or not directory.is_dir():raise ValueError('Preview fixture directory must be a real directory')
    directory=directory.resolve();result=[];total=0
    def visit(folder):
        nonlocal total
        for path in sorted(folder.iterdir()):
            name=path.relative_to(directory).as_posix()
            if not wire._path(name):raise ValueError('Preview fixture path exceeds the app file contract')
            mode=path.lstat().st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):raise ValueError('Preview fixtures reject symlinks and special files')
            result.append((name,path))
            if len(result)>127:raise ValueError('Preview fixtures exceed 127 named entries including directories')
            if stat.S_ISREG(mode):
                total+=path.stat().st_size
                if total>QUOTA:raise ValueError('Preview fixtures exceed 32 MiB')
            else:visit(path)
    visit(directory);return result


def fixture_identity(directory):
    if directory is None:return None
    values=[]
    for name,path in fixtures(directory):
        if path.is_dir():values.append((name,'directory'))
        else:
            with regular(path) as source:values.append((name,hashlib.file_digest(source,'sha256').hexdigest()))
    return hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest()


@dataclass
class Part:
    source:object
    offset:int
    size:int
    sha256:str|None
    def write(self,out):
        self.source.seek(self.offset);remaining=self.size;digest=hashlib.sha256()
        while remaining:
            block=self.source.read(min(65536,remaining))
            if not block:raise ValueError('Preview snapshot source was truncated')
            if out.write(block)!=len(block):raise OSError('Short preview snapshot write')
            remaining-=len(block);digest.update(block)
        value=digest.hexdigest()
        if self.sha256 is not None and value!=self.sha256:raise ValueError('Preview snapshot source changed')
        return bytes.fromhex(value)


def memory(data):return Part(io.BytesIO(data),0,len(data),hashlib.sha256(data).hexdigest())
def span(source,value):return Part(source,value.offset,value.size,value.sha256)


@dataclass
class Pair:
    metadata:dict
    package:Part
    schema:int
    private:Part
    entries:list
    @property
    def version(self):return tuple(map(int,self.metadata['version'].split('.')))
    @property
    def size(self):return 128+self.package.size+self.private.size+sum(112+part.size+(0 if directory else 32) for _,directory,part in self.entries)
    def write(self,out):
        out.write(wire.PAIR.pack(128,1,self.package.size,self.schema,self.private.size,len(self.entries),*self.version,*([0]*7),
            bytes.fromhex(self.package.sha256),bytes.fromhex(self.private.sha256)))
        self.package.write(out);self.private.write(out)
        for name,directory,part in self.entries:
            out.write(wire.ENTRY.pack(name.encode(),2 if directory else 1,part.size,0,0))
            digest=part.write(out)
            if not directory:out.write(digest)


def pair(source,snapshot):
    return Pair(snapshot.metadata,span(source,snapshot.package),snapshot.data_schema,span(source,snapshot.private),
        [(entry.path,entry.directory,span(source,entry.content)) for entry in snapshot.entries])


def compose(unsigned,destination,*,saved=None,saved_hash=None,fixture_dir=None):
    """Create a verified preview seed; never modifies the prior snapshot."""
    package=sign(unsigned.read_bytes(),PRIVATE);metadata,_=verify(package,[PUBLIC])
    if metadata['abi']!=1:raise ValueError('Saved preview data requires ABI 1; use --fresh-data for older experiments')
    with ExitStack() as stack:
        seed=Pair(metadata,memory(package),metadata.get('data_schema',0),memory(b''),[])
        high=seed.version;pairs=[seed]
        if saved is not None:
            source=stack.enter_context(regular(saved));archive=wire.validate(source,[PUBLIC])
            if archive.sha256!=saved_hash:raise ValueError('Saved preview archive changed; existing data was preserved')
            if archive.app_id!=metadata['id']:raise ValueError('Saved preview belongs to another app; use --reset-data to start fresh')
            old=pair(source,archive.snapshots[0]);old_schema=old.metadata.get('data_schema',0)
            if seed.version<old.version:raise ValueError('Saved preview has a newer app version; use --reset-data to start fresh')
            if seed.schema!=old_schema and seed.version==old.version:
                raise ValueError('Changing the preview data schema requires a newer app version and a migration')
            seed.private=old.private;seed.entries=old.entries;seed.schema=old.schema
            if seed.version>old.version:
                if len(archive.snapshots)==2:raise ValueError('Accept or roll back the pending app upgrade before another version; --reset-data starts fresh')
                if seed.version<=archive.high_version:raise ValueError('New preview version must exceed its retained version high-water mark')
                pairs.append(old)
            elif len(archive.snapshots)==2:pairs.append(pair(source,archive.snapshots[1]))
            high=max(archive.high_version,seed.version)
        elif fixture_dir is not None:
            used=0
            for name,path in fixtures(fixture_dir):
                directory=path.is_dir()
                if directory:part=memory(b'')
                else:
                    source=stack.enter_context(regular(path));size=os.fstat(source.fileno()).st_size;used+=size
                    if used>QUOTA:raise ValueError('Preview fixtures grew beyond 32 MiB')
                    part=Part(source,0,size,None)
                seed.entries.append((name,directory,part))
        total=128+sum(p.size for p in pairs)
        if total>wire.MAX_ARCHIVE:raise ValueError('Preview snapshot exceeds archive bounds')
        with Path(destination).open('x+b') as out:
            out.write(wire.HEADER.pack(b'LFARCH1\0',1,128,total,len(pairs),int(len(pairs)==2),0,*high,*([0]*5),metadata['id'].encode()))
            for p in pairs:p.write(out)
            out.flush();os.fsync(out.fileno());result=wire.validate(out,[PUBLIC])
        return package,result


def _sync(directory):
    if os.name=='nt':return
    fd=os.open(directory,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


class Checkpoints:
    """An atomic receipt selects immutable archive blobs; retain one prior blob.

The caller holds the project preview lock throughout reading, running and
publication. App data lives outside build/ and is excluded from source upload.
"""
    def __init__(self,project):
        self.directory=Path(project)/'.lefony/preview'
        for path in (self.directory.parent,self.directory):
            if path.is_symlink():raise ValueError('Preview data directories must not be symlinks')
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.receipt=self.directory/'state.json'
    @staticmethod
    def validate(value):
        keys={'schema','archive','fixture_sha256','previous'}
        if (not isinstance(value,dict) or set(value)!=keys or type(value['schema']) is not int or value['schema']!=1 or
            not isinstance(value['archive'],str) or not re.fullmatch('[0-9a-f]{64}',value['archive']) or
            any(v is not None and (not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v)) for v in (value['fixture_sha256'],value['previous']))):
            raise ValueError('Invalid saved preview receipt; use --reset-data to start fresh')
        return value
    def read(self):
        try:
            with regular(self.receipt) as source:
                raw=source.read(2049)
                if len(raw)>2048:raise ValueError('Saved preview receipt is oversized')
        except FileNotFoundError:return None
        try:return self.validate(json.loads(raw))
        except (ValueError,TypeError) as exc:raise ValueError('Invalid saved preview receipt; use --reset-data to start fresh') from exc
    def path(self,receipt):return self.directory/(self.validate(receipt)['archive']+'.lfarchive')
    def commit(self,archive,fixture_hash,previous):
        with regular(archive) as source:
            value=wire.validate(source,[PUBLIC]);source.seek(0)
            name=value.sha256;target=self.directory/(name+'.lfarchive')
            if target.exists():
                with regular(target) as existing:
                    if hashlib.file_digest(existing,'sha256').hexdigest()!=name:raise ValueError('Existing preview blob is damaged')
            else:
                fd,temp=tempfile.mkstemp(prefix='.snapshot-',dir=self.directory)
                try:
                    with os.fdopen(fd,'wb') as out:
                        remaining=value.size
                        while remaining:
                            block=source.read(min(65536,remaining))
                            if not block:raise ValueError('Preview export was truncated during publication')
                            out.write(block);remaining-=len(block)
                        if source.read(1):raise ValueError('Preview export grew during publication')
                        out.flush();os.fsync(out.fileno())
                    with regular(temp) as check:
                        if hashlib.file_digest(check,'sha256').hexdigest()!=name:raise ValueError('Preview export changed during publication')
                    os.link(temp,target);_sync(self.directory)
                finally:os.unlink(temp)
        receipt=self.validate({'schema':1,'archive':name,'fixture_sha256':fixture_hash,'previous':previous['archive'] if previous else None})
        fd,temp=tempfile.mkstemp(prefix='.receipt-',dir=self.directory)
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as out:
                json.dump(receipt,out,sort_keys=True);out.write('\n');out.flush();os.fsync(out.fileno())
            os.replace(temp,self.receipt);_sync(self.directory)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        keep={name,receipt['previous']}
        for path in self.directory.glob('*.lfarchive'):
            if re.fullmatch('[0-9a-f]{64}',path.stem) and path.stem not in keep and not path.is_symlink():
                try:path.unlink()
                except OSError:pass  # Publication succeeded; stale blobs can be reclaimed next time.
        return receipt
