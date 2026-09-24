# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit app-private file exchange; no firmware, backup or raw NAND requests."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import stat
import struct
import tempfile
from device import Client, DeviceError

REQUEST = struct.Struct('<8I64s96s32s')
STATUS = struct.Struct('<16I32s')
INFO, EXPORT, IMPORT, LIST = 1, 2, 3, 4
DATA_INFO, DATA_EXPORT, DATA_IMPORT, ROLLBACK = 5, 6, 7, 8
WORKING, READABLE, WRITABLE, COMPLETE, FAILED, CANCELLED = 1, 2, 3, 4, 5, 6
ERRORS = {1:'invalid request',2:'invalid handle',3:'file or app not found',4:'destination already exists',
    5:'destination is a directory',6:'shared storage full',7:'file or index limit exceeded',8:'storage I/O failed',
    9:'storage is busy',10:'handle limit exceeded',11:'app data schema or upgrade is not ready for import',
    12:'access denied',13:'directory is not empty',14:'not a directory',15:'app data changed; inspect again',
    16:'app data quota exceeded',17:'import hash mismatch; replacement discarded',18:'transfer cancelled',19:'idle transfer expired'}


def file_path(value, *, directory=False):
    if not isinstance(value,str) or (not value and not directory) or len(value)>95:
        raise DeviceError('Choose an app-relative file path of at most 95 ASCII characters')
    if value and any(not re.fullmatch(r'[A-Za-z0-9._ -]{1,48}',p) or p in ('.','..') for p in value.split('/')):
        raise DeviceError('Invalid app-relative path; absolute paths and parent traversal are not allowed')
    return value.encode('ascii')


class FileClient:
    def __init__(self, client: Client, *, timeout=120):
        self.client=client;self.timeout=timeout;self._supported=False

    def status(self):
        if not self._supported:
            status=self.client.status()
            if status['protocol']!=2 or not status['reserved']&32:
                raise DeviceError('Update Lefony OS: this firmware has no app file exchange protocol')
            self._supported=True
        words=STATUS.unpack(self.client.read(0x70,STATUS.size))
        if (words[:3]!=(0x5841464c,96,1) or words[3]>6 or words[4]>8 or words[12]!=512 or
            words[14:16]!=(0,0) or words[13]&~3 or words[7]>words[8] or words[8]>64*1024*1024 or words[9]>512):
            raise DeviceError('Invalid file exchange status')
        result=dict(zip(('magic','size','schema','state','operation','error','sequence','offset','length',
                         'available','generation','data_schema','chunk_bytes','flags','reserved','reserved2','digest'),words))
        return result

    def _wait(self, *, sequence=None, operation=None, cancelled=lambda:False):
        deadline=self.client.clock()+self.timeout
        while self.client.clock()<deadline:
            if cancelled():raise DeviceError('File exchange cancelled')
            s=self.status()
            if sequence is not None and s['sequence']!=sequence:
                raise DeviceError('File exchange session changed; no write was retried')
            if operation is not None and s['operation']!=operation:
                raise DeviceError('File exchange operation changed; no write was retried')
            if s['state'] in (FAILED,CANCELLED):
                uncertainty=(' The import committed; final inspection failed.' if s['flags']&1 else
                    ' Commit outcome requires inspection.' if s['flags']&2 else '')
                raise DeviceError('File exchange: '+ERRORS.get(s['error'],f"error {s['error']}")+uncertainty)
            if s['state']!=WORKING:return s
            self.client.sleep(.01)
        raise DeviceError('File exchange timed out; no write was retried. Inspect the saved file before another import.')

    def _begin(self, app_id, operation, path='', *, identity=None, length=0, digest=bytes(32), replace=False, cursor=0):
        if not isinstance(app_id,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,47}',app_id):raise DeviceError('Choose an installed app ID')
        encoded=file_path(path,directory=operation in (INFO,LIST,DATA_INFO,DATA_EXPORT,DATA_IMPORT,ROLLBACK))
        if len(digest)!=32 or not 0<=length<=64*1024*1024:raise DeviceError('Invalid import size or hash')
        status=self.client.status()
        if status['protocol']!=2 or not status['reserved']&32:
            raise DeviceError('Update Lefony OS: this firmware has no app file exchange protocol')
        if operation>=DATA_INFO and not status['reserved']&128:
            raise DeviceError('Update Lefony OS: this firmware has no app data recovery extension')
        self._supported=True
        if status['state'] not in (2,6) or status['pending'] or status['reserved']&64:
            raise DeviceError('Close the app and finish or cancel the current operation before exchanging files')
        generation=identity['generation'] if identity else 0
        schema=identity['data_schema'] if identity else 0
        frame=REQUEST.pack(224,1,operation,int(replace),generation,schema,length,cursor,app_id.encode(),encoded,digest)
        self.client.write(0x71,frame)
        return self._wait(operation=operation)

    def _cancel(self, sequence):
        # Before COMMIT this is safe even after an ambiguous data-frame write.
        # Never retry that frame, and never cancel after the commit boundary.
        deadline=self.client.clock()+self.timeout
        try:
            while self.client.clock()<deadline:
                s=self.status()
                if s['sequence']!=sequence or s['state'] in (0,COMPLETE,FAILED,CANCELLED):return
                # A successful USB status phase acknowledges the command;
                # firmware may still need to consume it before accepting CANCEL.
                if s['state']!=WORKING:break
                self.client.sleep(.01)
            else:return
            self.client.write(0x75,argument=sequence)
        except Exception:
            return  # Disconnected device expires its uncommitted idle writer.
        while self.client.clock()<deadline:
            try:s=self.status()
            except Exception:return
            if s['sequence']!=sequence or s['state']!=WORKING:return
            self.client.sleep(.01)

    def _download(self, state, output, *, cancelled=lambda:False, progress=lambda done,total:None):
        token=state['sequence'];operation=state['operation'];digest=hashlib.sha256();offset=0;total=state['length']
        try:
            from bulk_transfer import try_download
            if operation==EXPORT and 0<total<=32*1024*1024:
                data=try_download(getattr(self.client,"transport",None),4,total,sequence=token,progress=progress,cancelled=cancelled)
                if data is not None:
                    if output.write(data)!=len(data):raise DeviceError('Short local export write')
                    digest.update(data);offset=len(data);state=self._wait(sequence=token,operation=operation,cancelled=cancelled)
            while state['state']!=COMPLETE:
                if cancelled():raise DeviceError('File export cancelled')
                if state['state']!=READABLE or state['offset']!=offset or not 0<state['available']<=min(512,total-offset):
                    raise DeviceError('Invalid file export offset or length')
                block=self.client.read(0x72,state['available'],token)
                if output.write(block)!=len(block):raise DeviceError('Short local export write')
                digest.update(block);offset+=len(block)
                self.client.write(0x73,struct.pack('<2I',token,offset))
                progress(offset,total);state=self._wait(sequence=token,operation=operation,cancelled=cancelled)
            if cancelled():raise DeviceError('File export cancelled before publishing')
            if offset!=total or state['offset']!=total or digest.digest()!=state['digest']:
                raise DeviceError('File export size or SHA-256 verification failed')
            return {'generation':state['generation'],'data_schema':state['data_schema'],'bytes':total,'sha256':digest.hexdigest()}
        except BaseException:
            self._cancel(token);raise

    def info(self, app_id):
        import io
        out=io.BytesIO();state=self._begin(app_id,INFO)
        self._download(state,out);data=out.getvalue()
        if len(data)!=144:raise DeviceError('Invalid app file information length')
        h=struct.unpack_from('<8I',data);space=struct.unpack_from('<16I',data,32);quota=struct.unpack_from('<12I',data,96)
        if h[:2]!=(144,1) or space[:2]!=(64,1) or quota[:2]!=(48,1) or quota[9:]!=(0,0,0):
            raise DeviceError('Invalid app file information schema')
        if space[3]!=quota[3] or space[3]!=state['generation'] or h[5]!=state['data_schema']:
            raise DeviceError('Inconsistent app file generation/schema')
        return {'app':app_id,'version':'.'.join(map(str,h[2:5])),'data_schema':h[5],'app_schema':h[6],
                'pending_upgrade':bool(h[7]),'generation':space[3],
                'private_bytes':space[5],'file_bytes':space[6],'files':space[7],'directories':space[8],
                'shared_available_bytes':space[12],'quota_bytes':quota[4],'quota_committed_bytes':quota[5],
                'quota_remaining_bytes':quota[8]}

    def list(self, app_id, directory=''):
        import io
        file_path(directory,directory=True);identity=self.info(app_id);cursor=0;entries=[]
        while True:
            out=io.BytesIO();state=self._begin(app_id,LIST,directory,identity=identity,cursor=cursor)
            self._download(state,out);data=out.getvalue()
            if len(data)!=1688:raise DeviceError('Invalid directory page size')
            size,schema,generation,next_cursor,count,reserved=struct.unpack_from('<6I',data)
            if (size!=1688 or schema!=1 or generation!=identity['generation'] or count>16 or reserved or
                next_cursor and next_cursor<=cursor):raise DeviceError('Invalid or changed directory page')
            for i in range(count):
                raw,kind,length=struct.unpack_from('<96sII',data,24+i*104)
                name=raw.split(b'\0',1)[0].decode('ascii');file_path(name)
                if kind not in (1,2):raise DeviceError('Invalid directory entry kind')
                entries.append({'path':name,'kind':'directory' if kind==2 else 'file','bytes':length})
            if not next_cursor:return {'app':app_id,'generation':generation,'directory':directory,'entries':entries}
            cursor=next_cursor

    def export_file(self, app_id, path, destination, *, replace=False, cancelled=lambda:False, progress=lambda done,total:None):
        file_path(path);destination=Path(destination)
        if destination.exists() and not replace:raise DeviceError('Export destination exists; choose another path or explicitly replace it')
        identity=self.info(app_id)
        descriptor,temp=tempfile.mkstemp(prefix='.'+destination.name+'.',suffix='.partial',dir=destination.parent)
        try:
            with os.fdopen(descriptor,'wb') as out:
                result=self._download(self._begin(app_id,EXPORT,path,identity=identity),out,cancelled=cancelled,progress=progress)
                out.flush();os.fsync(out.fileno())
            if replace:os.replace(temp,destination)
            else:os.link(temp,destination);os.unlink(temp)
            if os.name!='nt':
                fd=os.open(destination.parent,os.O_RDONLY)
                try:os.fsync(fd)
                finally:os.close(fd)
            return {'app':app_id,'path':path,**result}
        finally:
            if os.path.exists(temp):os.unlink(temp)

    def import_file(self, app_id, path, source, *, replace=False, cancelled=lambda:False, progress=lambda done,total:None):
        file_path(path);source=Path(source)
        descriptor=os.open(source,os.O_RDONLY|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_BINARY',0))
        with os.fdopen(descriptor,'rb') as stream:
            initial=os.fstat(stream.fileno());length=initial.st_size
            if not stat.S_ISREG(initial.st_mode):raise DeviceError('Import source must be a regular file')
            if not 0<=length<=64*1024*1024:raise DeviceError('Import source exceeds the file format limit')
            hashed=hashlib.sha256();remaining=length
            while remaining:
                if cancelled():raise DeviceError('File import cancelled before transfer')
                block=stream.read(min(1024*1024,remaining))
                if not block:raise DeviceError('Import source became shorter during hashing')
                hashed.update(block);remaining-=len(block)
            if stream.read(1):raise DeviceError('Import source grew during hashing')
            digest=hashed.digest();stream.seek(0)
            identity=self.info(app_id)
            return self._upload(app_id,path,stream,length,digest,identity,replace=replace,cancelled=cancelled,progress=progress)

    def _upload(self,app_id,path,stream,length,digest,identity,*,operation=IMPORT,replace=False,cancelled=lambda:False,progress=lambda done,total:None):
        if cancelled():raise DeviceError('File import cancelled before transfer')
        state=self._begin(app_id,operation,path,identity=identity,length=length,digest=digest,replace=replace)
        token=state['sequence'];offset=0;committing=False
        try:
            from bulk_transfer import try_upload
            if operation==IMPORT and 0<length<=32*1024*1024 and hasattr(getattr(self.client,'transport',None),'bulk_upload'):
                data=stream.read(length+1)
                if len(data)!=length:raise DeviceError('Import source length changed')
                if try_upload(self.client.transport,3,data,sequence=token,progress=progress,cancelled=cancelled):
                    offset=length;state=self._wait(sequence=token,operation=operation,cancelled=cancelled)
                else:
                    import io
                    stream=io.BytesIO(data)
            while offset<length:
                if cancelled():raise DeviceError('File import cancelled before commit')
                if state['state']!=WRITABLE or state['offset']!=offset:
                    raise DeviceError(f"Invalid file import offset: expected {offset}, received {state['offset']} "
                        f"(state {state['state']}, sequence {token}); no write was retried")
                block=stream.read(min(504,length-offset))
                if not block:raise DeviceError('Import source became shorter; replacement discarded')
                self.client.write(0x72,struct.pack('<2I',token,offset)+block)
                offset+=len(block);state=self._wait(sequence=token,operation=operation,cancelled=cancelled);progress(offset,length)
            if cancelled():raise DeviceError('File import cancelled before commit')
            if state['state']!=WRITABLE or state['offset']!=length or stream.read(1):raise DeviceError('Import source length changed')
            committing=True
            self.client.write(0x74,argument=token)
            state=self._wait(sequence=token,operation=operation)
            if state['state']!=COMPLETE or state['flags']!=1 or state['digest']!=digest or state['offset']!=length:
                raise DeviceError('Import commit could not be verified; inspect the saved file before another import')
            return {'app':app_id,'path':path,'generation':state['generation'],'data_schema':state['data_schema'],
                    'bytes':length,'sha256':digest.hex(),'committed':True}
        except BaseException:
            if not committing:self._cancel(token)
            raise
