# SPDX-License-Identifier: GPL-3.0-or-later
"""Native app USB protocols 1 (legacy banks) and 2 (shared filesystem). Never sends firmware or recovery write requests."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import struct
import time
from signing import verify
from lfapp import compatible, PackageError

PROFILE=1
FIRST_BLOCK=3456
BLOCKS=512
PAGE_BYTES=2048
RAW_PAGE_BYTES=2112
BACKUP_BYTES=BLOCKS*64*RAW_PAGE_BYTES
SLOTS=8

class DeviceError(RuntimeError):
    pass

class Client:
    def __init__(self,transport,*,sleep=time.sleep,clock=time.monotonic):
        self.transport=transport
        self.sleep=sleep
        self.clock=clock

    def write(self,request,data=b'',argument=0):
        self.transport.write(request,data,value=argument&65535,index=argument>>16)

    def read(self,request,size,argument=0):
        data=self.transport.read(request,value=argument&65535,index=argument>>16,length=size)
        if len(data)!=size:
            raise DeviceError('Short USB response; no command was retried. Reconnect to inspect status.')
        return data

    def status(self):
        values=struct.unpack('<16I',self.read(0x60,64))
        if values[0]!=0x3141464c or values[1] not in (1,2) or values[8:10]!=(1,BACKUP_BYTES) or (values[1]==1 and values[6:8]!=(PROFILE,SLOTS)) or (values[1]==2 and (values[6]!=2 or values[7]>BLOCKS)):
            raise DeviceError('Unsupported app installation protocol or storage geometry')
        return dict(zip(('magic','protocol','state','error','received','length','profile','entries','abi','backup_bytes','backup_received','storage_state','progress','target','pending','reserved'),values))

    def capabilities(self, status=None):
        status = self.status() if status is None else status
        if not status['reserved'] & 16:
            return None  # Old firmware: no speculative request or write.
        values = struct.unpack('<12I', self.read(0x6e, 48))
        if (values[:5] != (0x4341464c, 48, 1, 0, 1) or not values[5] or
                not values[7] & 1 or values[8] != status['profile'] or
                values[9:12] != (2101664, 65536, 0)):
            raise DeviceError('Invalid app capability response; no upload was started')
        return dict(zip(('magic', 'size', 'version', 'reserved', 'abi', 'api', 'features',
                         'package_schemas', 'storage_profile', 'maximum_package', 'private_data_bytes', 'reserved2'), values))

    def require_compatible(self, metadata, status=None):
        if not metadata.get('schema', 0):
            return  # Original ABI 1 contract remains unchanged.
        info = self.capabilities(status)
        if info is None:
            raise DeviceError('Update Lefony OS: this app requires package schema 1 capability negotiation')
        try:
            compatible(metadata, api=info['api'], features=info['features'],
                       schemas=tuple(i for i in range(32) if info['package_schemas'] & (1 << i)))
        except PackageError as exc:
            raise DeviceError(str(exc)) from exc

    def wait(self,timeout=120):
        deadline=self.clock()+timeout
        while self.clock()<deadline:
            status=self.status()
            if status['state']==7:
                raise DeviceError(f"Calculator rejected the app operation (error {status['error']}). Previous committed apps remain recoverable.")
            if status['state']!=5 and not status['pending']:
                return status
            self.sleep(.1)
        raise DeviceError('App operation timed out. Do not retry a write; reconnect and inspect the installed catalog.')

    def connect(self):
        status=self.status()
        if status['state'] in (3,4,5) or status['pending']:
            raise DeviceError('Calculator has an unfinished operation. Inspect status or explicitly cancel an upload before reconnecting.')
        if status['protocol']==1:
            self.write(0x60)
            return self.wait()
        return status

    def cancel_upload(self):
        if self.status()["state"] not in (3,4):
            raise DeviceError("Only an unfinished backup or upload may be cancelled")
        self.write(0x67)

    def catalog(self):
        result=[]
        for slot in range(self.status()['entries']):
            data=self.read(0x68,168,slot)
            size,generation,abi=struct.unpack_from('<III',data)
            if not size:
                continue
            def string(start,end):
                raw=data[start:end]
                if b'\0' not in raw:
                    raise DeviceError('Invalid catalog text')
                return raw.split(b'\0',1)[0].decode('ascii')
            result.append({'slot':slot,'bytes':size,'generation':generation,'abi':abi,
                           'id':string(12,61),'name':string(61,142),'version':string(142,166)})
        return result

    def read_package(self,slot,size):
        self.write(0x6a,argument=slot)
        if self.wait()['state']!=6:
            raise DeviceError('Package readback was not prepared')
        from bulk_transfer import try_download
        fast=try_download(self.transport,5,size)
        if fast is not None:return fast
        return b''.join(self.read(0x6a,min(512,size-offset),offset) for offset in range(0,size,512))

    def install(self,package,public_keys,*,progress=lambda done,total:None,cancelled=lambda:False,commit=None):
        metadata,_=verify(package,public_keys)
        if metadata['abi']!=1:
            raise DeviceError('Physical installation requires an ABI 1 app')
        status = self.status()
        if status['state'] not in (2,6):
            raise DeviceError('App storage must be provisioned before installing')
        self.require_compatible(metadata, status)
        self.write(0x63,argument=len(package))
        from bulk_transfer import try_upload
        sent=try_upload(self.transport,2,package,progress=progress,cancelled=cancelled)
        for offset in range(0 if not sent else len(package),len(package),512):
            if cancelled():
                self.write(0x67)
                raise DeviceError('Upload cancelled before installation')
            self.write(0x64,package[offset:offset+512],offset)
            progress(min(offset+512,len(package)),len(package))
        # No retry/automatic abort after this boundary: a lost status may follow
        # a successful commit. Resolve that ambiguity by reading the catalog.
        if commit is None:self.write(0x65)
        else:commit(metadata)
        status=self.wait()
        if status['state']!=6:
            raise DeviceError('Installation did not commit')
        entries=self.catalog()
        matches=[entry for entry in entries if entry['id']==metadata['id']]
        if len(matches)!=1 or matches[0]['version']!=metadata['version'] or matches[0]['bytes']!=len(package):
            raise DeviceError('Installed app identity does not match the package')
        returned=self.read_package(matches[0]['slot'],len(package))
        if hashlib.sha256(returned).digest()!=hashlib.sha256(package).digest():
            raise DeviceError('Installed package readback does not match')
        return matches[0]

    def remove(self,app_id):
        entries=[entry for entry in self.catalog() if entry['id']==app_id]
        if len(entries)!=1:
            raise DeviceError('Select an installed app ID')
        self.write(0x66,argument=entries[0]['slot'])
        if self.wait()['state']!=6 or any(entry['id']==app_id for entry in self.catalog()):
            raise DeviceError('App removal was not confirmed')

    def backup_and_migrate(self,directory:Path,*,retire_stock_filesystem=False,progress=lambda done,total:None,cancelled=lambda:False):
        if not retire_stock_filesystem:
            raise DeviceError('Migration requires explicit consent to retire the stock HP filesystem')
        if self.status()['state']!=1:
            raise DeviceError('Only an unprovisioned app region may be migrated')
        directory=Path(directory)
        directory.mkdir(parents=True,exist_ok=False,mode=0o700)
        path=directory/'app-region.raw'
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        digest=hashlib.sha256()
        self.write(0x61)
        with os.fdopen(descriptor,'wb') as output:
            offset=0
            while offset<BACKUP_BYTES:
                if cancelled():
                    self.write(0x67)
                    raise DeviceError('Backup cancelled; migration was not started')
                size=min(512,RAW_PAGE_BYTES-offset%RAW_PAGE_BYTES)
                block=self.read(0x61,size,offset)
                output.write(block);digest.update(block);offset+=size
                progress(offset,BACKUP_BYTES)
            output.flush();os.fsync(output.fileno())
        receipt=self.read(0x62,32)
        with path.open('rb') as source:
            disk_digest=hashlib.file_digest(source,'sha256').digest()
        if path.stat().st_size!=BACKUP_BYTES or disk_digest!=digest.digest() or receipt!=disk_digest:
            raise DeviceError('Backup receipt or disk verification failed; migration was not started')
        record={'schema':1,'profile':PROFILE,'offset':FIRST_BLOCK*64*PAGE_BYTES,
                'payload_bytes':BLOCKS*64*PAGE_BYTES,'raw_page_bytes':RAW_PAGE_BYTES,
                'raw_bytes':BACKUP_BYTES,'sha256':digest.hexdigest(),
                'stock_filesystem_retired':True,'migration_committed':False}
        record_path=directory/'backup.json'
        with os.fdopen(os.open(record_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8',newline='\n') as output:
            json.dump(record,output,indent=2);output.write('\n');output.flush();os.fsync(output.fileno())
        directory_fd=os.open(directory,os.O_RDONLY)
        try: os.fsync(directory_fd)
        finally: os.close(directory_fd)
        self.write(0x62,receipt)
        if self.wait()['state']!=2:
            raise DeviceError('Migration outcome unknown; preserve this backup and inspect the calculator')
        record['migration_committed']=True
        # Backup and pre-migration record are durable before any device erase.
        complete=directory/'migration-complete.json'
        with os.fdopen(os.open(complete,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8',newline='\n') as output:
            json.dump(record,output,indent=2);output.write('\n');output.flush();os.fsync(output.fileno())
        return record
