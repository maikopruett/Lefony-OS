# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit, signed whole-app snapshots over the scoped archive USB protocol."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path
import re
import secrets
import struct
import tempfile

import archive_format
from device import Client as DeviceClient,DeviceError
from usb_files import LibUSB

REQUEST=struct.Struct('<8I64s32s16s')
STATUS=struct.Struct('<16I32s16s')
INFO=struct.Struct('<16I32s32s64s')
REPAIR_INFO_BYTES=256
APPROVAL=struct.Struct('<10I64s32s32s32s16s')
INSPECT,EXPORT,RESTORE=1,2,3
IDLE,WORKING,READABLE,WRITABLE,READY,COMPLETE,FAILED,CANCELLED,AWAIT_USER=range(9)
ERRORS={1:'invalid archive request',2:'storage is busy',3:'app is absent',4:'app or signing authority changed',
    5:'package signing authority rejected',6:'package version or exact-code ownership rejected',7:'app quota exceeded',
    8:'insufficient shared storage for an atomic restore',9:'archive or stored content integrity failed',10:'storage I/O failed',
    11:'archive operation cancelled',12:'idle archive session expired',13:'commit outcome is unknown',
    14:'app already exists; use --replace explicitly',15:'archive package/data schema mismatch',16:'OS denied archive approval; return to Home before retrying'}


class ArchiveUSB(LibUSB):
    READ_REQUESTS=(0x60,0x6e,0x90,0x92,0x96)
    WRITE_REQUESTS=(0x91,0x92,0x93,0x94,0x95)


class TransferFailure(DeviceError):
    def __init__(self,status):
        self.status=status
        message='Archive: '+ERRORS.get(status['error'],f"error {status['error']}")
        if status['flags']&2:message+='; inspect the app before another restore'
        super().__init__(message)


@dataclass
class Prepared:
    stream: object
    archive: archive_format.Archive


@contextmanager
def prepare(path,public_keys,*,cancelled=lambda:False):
    if not public_keys:raise DeviceError('Provide trusted --public-key files before restoring an archive')
    descriptor=os.open(Path(path),os.O_RDONLY|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_BINARY',0))
    with os.fdopen(descriptor,'rb') as stream:
        yield Prepared(stream,archive_format.validate(stream,public_keys,cancelled=cancelled))


def decode_status(raw):
    if len(raw)!=STATUS.size:raise DeviceError('Invalid archive status length')
    v=STATUS.unpack(raw)
    if (v[:3]!=(0x5241464c,112,1) or v[3]>8 or v[4] not in (1,2,3) or v[5]>16 or v[12]!=488 or
            any(v[13:16]) or v[7]>v[8] or v[8]>archive_format.MAX_ARCHIVE or v[9]>min(512,v[8]-v[7]) or v[11]&~15):
        raise DeviceError('Invalid archive status')
    state,operation,error,sequence=v[3:7]
    if (v[11]&12 and operation!=RESTORE or v[11]&12==12 or state==AWAIT_USER and not v[11]&4 or
            state not in (WORKING,FAILED,CANCELLED) and error or state==READABLE and (operation==RESTORE or not v[9]) or state!=READABLE and v[9] or
            state in (WRITABLE,READY,AWAIT_USER) and operation!=RESTORE or state in (READY,AWAIT_USER) and v[7]!=v[8] or
            state==COMPLETE and (error or v[7]!=v[8]) or state in (FAILED,CANCELLED) and not error or
            state!=IDLE and (not sequence or not any(v[17]))):
        raise DeviceError('Inconsistent archive status')
    return dict(zip(('magic','size','schema','state','operation','error','sequence','offset','length','available',
                     'generation','flags','chunk_bytes','reserved','reserved2','reserved3','digest','nonce'),v))


def decode_info(raw,app_id,*,repair=False,root_health=False):
    size=REPAIR_INFO_BYTES if repair else INFO.size
    if len(raw)!=size:raise DeviceError('Invalid archive app information length')
    v=INFO.unpack(raw[:INFO.size]);extra=raw[INFO.size:]
    try:name=archive_format._text(v[18])
    except ValueError as exc:raise DeviceError('Invalid archive app identity') from exc
    allowed=(63 if repair else 7)|(448 if root_health else 0)
    if (v[:2]!=(size,2 if repair else 1) or name!=app_id or v[2]&~allowed or bool(v[2]&1)!=bool(v[3]) or
            max((*v[4:7],*v[9:12]))>999999 or v[12]>65536 or v[13]>archive_format.MAX_DATA or
            not 32*1024*1024<=v[14]<=archive_format.MAX_DATA or
            v[2]&1 and not 468<=v[15]<=archive_format.MAX_PACKAGE or
            not v[2]&1 and (v[2] or any(v[3:14]) or v[15] or any(v[16]) or any(v[17]))):
        raise DeviceError('Invalid archive app information')
    unavailable,legacy,prefix=(bool(v[2]&bit) for bit in (8,16,32))
    replicated=bool(v[2]&64);copies=v[2]&384
    if replicated!=bool(copies) or replicated and (not v[2]&1 or legacy):
        raise DeviceError('Invalid archive root protection information')
    if (unavailable and (not v[2]&1 or any(v[4:8]) or any(v[17])) or
            legacy and (not unavailable or v[2]&4 or v[8] or any(v[9:12]) or any(v[16])) or
            prefix and not legacy or repair and (not legacy and any(extra[:32]) or not prefix and any(extra[32:]))):
        raise DeviceError('Invalid archive repair information')
    return {'app':name,'exists':bool(v[2]&1),'index_known':bool(v[2]&2),'pending_upgrade':bool(v[2]&4),
            'root_protection':({0:'single',128:'payload-only',256:'metadata-only',384:'both'}[copies]
                               if root_health and v[2]&1 else None),
            'code_unavailable':unavailable,'legacy':legacy,
            'generation':v[3],'version':None if unavailable else tuple(v[4:7]),'app_schema':None if unavailable else v[7],
            'data_schema':None if legacy else v[8],'high_version':None if legacy else tuple(v[9:12]),
            'private_bytes':v[12],'named_bytes':v[13],'quota_bytes':v[14],'package_bytes':v[15],
            'package_sha256':None if legacy else v[16].hex(),'signer':None if unavailable else v[17].hex(),
            'legacy_sha256':extra[:32].hex() if legacy else None,'prefix_sha256':extra[32:].hex() if prefix else None}


class Client:
    def __init__(self,client:DeviceClient,*,timeout=120):
        self.client=client;self.timeout=timeout;self.supported=False

    def status(self):
        if not self.supported:
            hello=self.client.status()
            if hello['protocol']!=2 or not hello['reserved']&1024:
                raise DeviceError('Update Lefony OS: this firmware has no whole-app archive protocol')
            self.supported=True
        return decode_status(self.client.read(0x90,STATUS.size))

    def _wait(self,binding,*,cancelled=lambda:False):
        deadline=self.client.clock()+self.timeout;delay=.001
        while self.client.clock()<deadline:
            if cancelled():raise DeviceError('Archive operation cancelled')
            status=self.status()
            if any(status[field]!=binding[field] for field in ('sequence','nonce','operation')):
                raise DeviceError('Archive session changed; no write was retried')
            if status['state'] in (FAILED,CANCELLED):raise TransferFailure(status)
            if status['state']!=WORKING:return status
            # Most streaming steps finish quickly. Back off for real storage
            # work instead of adding ten milliseconds to every ready block.
            # Only status reads repeat; the operation deadline is unchanged.
            self.client.sleep(delay);delay=min(.01,delay*2)
        raise DeviceError('Archive operation timed out; no write was retried')

    def _begin(self,app_id,operation,*,generation=0,length=0,digest=bytes(32),replace=False,allow_recovery_pair=False,repair_code=False,root_health=False):
        if not isinstance(app_id,str) or not re.fullmatch('[a-z][a-z0-9-]{0,47}',app_id):raise DeviceError('Choose a valid app ID')
        hello=self.client.status()
        if hello['protocol']!=2 or not hello['reserved']&1024:raise DeviceError('Update Lefony OS: this firmware has no whole-app archive protocol')
        if allow_recovery_pair and (operation!=RESTORE or not hello['reserved']&4096):
            raise DeviceError('Update Lefony OS: this firmware has no archive recovery-pair consent')
        if repair_code and (operation not in (INSPECT,RESTORE) or not hello['reserved']&8192):
            raise DeviceError('Update Lefony OS: this firmware has no unreadable-code recovery')
        if repair_code and (allow_recovery_pair or operation==RESTORE and not replace):
            raise DeviceError('Code repair requires replacement and cannot request recovery-pair consent')
        if root_health and (operation!=INSPECT or not hello['reserved']&32768):
            raise DeviceError('Update Lefony OS: this firmware has no root protection inspection')
        if hello['state'] not in (2,6,7) or hello['pending'] or hello['reserved']&64:
            raise DeviceError('Close the app and finish or cancel the current operation before archiving')
        self.supported=True;previous=self.status()
        if previous['sequence']==0xffffffff:raise DeviceError('Archive session counter exhausted; restart the calculator')
        binding={'sequence':previous['sequence']+1,'operation':operation,'nonce':secrets.token_bytes(16)}
        request=REQUEST.pack(144,1,operation,int(replace)|(2 if allow_recovery_pair else 0)|(4 if repair_code else 0)|(8 if root_health else 0),generation,length,0,0,app_id.encode(),digest,binding['nonce'])
        try:
            self.client.write(0x91,request)
            return self._wait(binding)
        except BaseException:
            self._cancel(binding);raise

    def _cancel(self,binding):
        try:
            deadline=self.client.clock()+self.timeout
            # Cleanup owns only this session. A failed/finished session has
            # already drained; sending CANCEL there is rejected by firmware
            # and can obscure the original error with a transport timeout.
            while self.client.clock()<deadline:
                state=self.status()
                if (any(state[field]!=binding[field] for field in ('sequence','nonce','operation')) or
                        state['state'] in (IDLE,COMPLETE,FAILED,CANCELLED)):
                    return
                # Do not race a command which was acknowledged over USB but
                # is still awaiting the firmware's storage poll.
                if state['state']!=WORKING:break
                self.client.sleep(.01)
            else:return
            self.client.write(0x95,binding['nonce'],argument=binding['sequence'])
            while self.client.clock()<deadline:
                state=self.status()
                if state['nonce']!=binding['nonce'] or state['sequence']!=binding['sequence'] or state['state']!=WORKING:return
                self.client.sleep(.01)
        except Exception:return

    def cancel(self,sequence,nonce):
        if not isinstance(sequence,int) or not 0<sequence<=0xffffffff:raise DeviceError('Choose the current archive sequence')
        try:nonce=bytes.fromhex(nonce)
        except (ValueError,TypeError):raise DeviceError('Use the current archive nonce') from None
        if len(nonce)!=16:raise DeviceError('Use the current 16-byte archive nonce')
        state=self.status()
        if state['sequence']!=sequence or state['nonce']!=nonce:raise DeviceError('Archive session changed')
        if state['state']==CANCELLED:return state
        state=self._wait(state)
        if state['state'] in (IDLE,COMPLETE):raise DeviceError('Archive session has already finished')
        self.client.write(0x95,nonce,argument=sequence)
        try:return self._wait(state)
        except TransferFailure as exc:
            if exc.status['state']==CANCELLED:return exc.status
            raise

    def _download(self,state,out,*,cancelled=lambda:False,progress=lambda done,total:None):
        binding=state;offset=0;total=state['length'];digest=hashlib.sha256()
        try:
            while state['state']!=COMPLETE:
                if cancelled():raise DeviceError('Archive export cancelled')
                if state['state']!=READABLE or state['offset']!=offset or state['length']!=total or not 0<state['available']<=min(512,total-offset):
                    raise DeviceError('Invalid archive export offset or length')
                block=self.client.read(0x92,state['available'],state['sequence'])
                if out.write(block)!=len(block):raise DeviceError('Short local archive write')
                offset+=len(block);digest.update(block)
                self.client.write(0x93,struct.pack('<2I16s',state['sequence'],offset,state['nonce']))
                progress(offset,total);state=self._wait(binding,cancelled=cancelled)
            if cancelled():raise DeviceError('Archive export cancelled before publishing')
            if state['length']!=total or offset!=total or state['offset']!=total or state['digest']!=digest.digest():
                raise DeviceError('Archive export size or complete hash mismatch')
            return {'generation':state['generation'],'bytes':total,'sha256':digest.hexdigest()}
        except BaseException:
            self._cancel(binding);raise

    def info(self,app_id,*,include_unreadable=False):
        root_health=bool(self.client.status()['reserved']&32768)
        state=self._begin(app_id,INSPECT,repair_code=include_unreadable,root_health=root_health);out=io.BytesIO()
        if state['length']!=(REPAIR_INFO_BYTES if include_unreadable else INFO.size):
            self._cancel(state);raise DeviceError('Invalid archive app information length')
        result=self._download(state,out);info=decode_info(out.getvalue(),app_id,repair=include_unreadable,root_health=root_health)
        if info['generation']!=result['generation']:raise DeviceError('Archive app information changed')
        return info

    def export(self,app_id,destination,public_keys,*,replace=False,cancelled=lambda:False,progress=lambda done,total:None):
        if not public_keys:raise DeviceError('Provide trusted --public-key files to verify the exported archive')
        destination=Path(destination)
        if destination.exists() and not replace:raise DeviceError('Archive destination exists; use --replace explicitly')
        info=self.info(app_id)
        if not info['exists']:raise DeviceError('App is absent')
        fd,temp=tempfile.mkstemp(prefix='.'+destination.name+'.',suffix='.partial',dir=destination.parent)
        try:
            with os.fdopen(fd,'w+b') as out:
                state=self._begin(app_id,EXPORT,generation=info['generation'])
                report=self._download(state,out,cancelled=cancelled,progress=progress)
                out.flush();os.fsync(out.fileno());archive=archive_format.validate(out,public_keys,cancelled=cancelled)
                if archive.app_id!=app_id or archive.sha256!=report['sha256']:raise DeviceError('Exported archive identity or hash changed')
            if replace:os.replace(temp,destination)
            else:os.link(temp,destination);os.unlink(temp)
            if os.name!='nt':
                folder=os.open(destination.parent,os.O_RDONLY)
                try:os.fsync(folder)
                finally:os.close(folder)
            return {'app':app_id,'snapshots':len(archive.snapshots),'signatures_checked':True,**report}
        finally:
            if os.path.exists(temp):os.unlink(temp)

    def restore(self,path,public_keys,**options):
        with prepare(path,public_keys,cancelled=options.get('cancelled',lambda:False)) as source:
            return self.restore_prepared(source,**options)

    def _approve_pair(self,source,binding,*,cancelled,notify):
        archive=source.archive
        if binding['offset']!=archive.size or binding['length']!=archive.size or binding['digest'].hex()!=archive.sha256:
            raise DeviceError('Archive approval does not match the verified upload')
        raw=self.client.read(0x96,APPROVAL.size,argument=binding['sequence'])
        if len(raw)!=APPROVAL.size:raise DeviceError('Invalid archive approval record length')
        v=APPROVAL.unpack(raw);signers=[]
        for snapshot in archive.snapshots:
            source.stream.seek(snapshot.package.offset+24);signers.append(source.stream.read(32))
        expected=(216,1,binding['sequence'],0,
            *map(int,archive.snapshots[0].metadata['version'].split('.')),
            *map(int,archive.snapshots[1].metadata['version'].split('.')),
            archive.app_id.encode().ljust(64,b'\0'),*signers,bytes.fromhex(archive.sha256),binding['nonce'])
        if v!=expected:raise DeviceError('Archive approval identities changed; no commit was sent')
        notify({'app':archive.app_id,'archive_sha256':archive.sha256,
            'current_version':archive.snapshots[0].metadata['version'],'current_signer':signers[0].hex(),
            'rollback_version':archive.snapshots[1].metadata['version'],'rollback_signer':signers[1].hex(),
            'instruction':'Compare these identities on the calculator. OK allows the retained signer after rollback; Back cancels.'})
        deadline=self.client.clock()+min(self.timeout,120)
        while self.client.clock()<deadline:
            if cancelled():raise DeviceError('Archive restore cancelled during approval')
            state=self._wait(binding,cancelled=cancelled)
            if state['flags']!=binding['flags']:raise DeviceError('Archive approval changed; no commit was sent')
            if state['state']!=AWAIT_USER:return state
            if state['digest']!=binding['digest'] or state['offset']!=archive.size or state['length']!=archive.size:
                raise DeviceError('Archive approval changed; no commit was sent')
            self.client.sleep(.05)
        raise DeviceError('Archive approval timed out; no commit was sent')

    def _repair_identity(self,source,before,*,cancelled):
        current=source.archive.snapshots[0]
        if not before['exists']:raise DeviceError('Code repair requires an existing app')
        if not before['code_unavailable']:raise DeviceError('Installed code is readable; use ordinary restore --replace')
        if current.package.size!=before['package_bytes']:raise DeviceError('Repair requires the exact original signed package')
        if not before['legacy']:
            if current.package.sha256!=before['package_sha256']:raise DeviceError('Repair requires the exact original signed package')
            return
        stream=source.stream;stream.seek(current.package.offset)
        prefix=stream.read(352)
        if before['prefix_sha256'] and len(prefix)==352 and hashlib.sha256(prefix).hexdigest()==before['prefix_sha256']:return
        # FILE2 has only a combined package/private digest. If the signed
        # envelope is damaged too, only the exact original snapshot proves it.
        if current.private.size==before['private_bytes']:
            combined=hashlib.sha256()
            for content in (current.package,current.private):
                stream.seek(content.offset);remaining=content.size
                while remaining:
                    if cancelled():raise DeviceError('Archive repair cancelled')
                    chunk=stream.read(min(65536,remaining))
                    if not chunk:raise DeviceError('Archive source changed during repair verification')
                    combined.update(chunk);remaining-=len(chunk)
            if combined.hexdigest()==before['legacy_sha256']:return
        raise DeviceError('Legacy repair needs the original signed envelope or an exact package/private-data backup')

    def restore_prepared(self,source,*,replace=False,allow_recovery_pair=False,repair_code=False,cancelled=lambda:False,progress=lambda done,total:None,notify=lambda info:None):
        archive=source.archive
        if not archive.signatures_checked:raise DeviceError('Archive signatures must be checked before device access')
        if repair_code and allow_recovery_pair:raise DeviceError('Code repair cannot request fresh recovery-pair consent')
        if repair_code:replace=True
        if allow_recovery_pair:
            if len(archive.snapshots)!=2:raise DeviceError('Recovery-pair approval requires an archive with two snapshots')
            hello=self.client.status()
            if hello['protocol']!=2 or not hello['reserved']&4096:
                raise DeviceError('Update Lefony OS: this firmware has no archive recovery-pair consent')
        current=archive.snapshots[0];self.client.require_compatible(current.metadata)
        before=self.info(archive.app_id,include_unreadable=True) if repair_code else self.info(archive.app_id)
        if repair_code:self._repair_identity(source,before,cancelled=cancelled)
        if before['exists'] and allow_recovery_pair:raise DeviceError('Recovery-pair approval requires an absent app; existing ownership is preserved')
        if before['exists'] and not replace:raise DeviceError('App already exists; use --replace explicitly')
        used=current.private.size+sum(entry.content.size for entry in current.entries)
        if used>before['quota_bytes']:raise DeviceError('Archive exceeds the current app quota')
        if before['exists'] and not repair_code:
            version=tuple(map(int,current.metadata['version'].split('.')))
            if ((version==before['version'] and current.package.sha256!=before['package_sha256']) or
                    version!=before['version'] and version<=before['high_version']):
                raise DeviceError('Archive code must match the installed version exactly or exceed its version high-water mark')
        if cancelled():raise DeviceError('Archive restore cancelled before upload')
        stream=source.stream;stream.seek(0)
        state=self._begin(archive.app_id,RESTORE,generation=before['generation'],length=archive.size,digest=bytes.fromhex(archive.sha256),replace=replace,allow_recovery_pair=allow_recovery_pair,repair_code=repair_code)
        binding=state;offset=0;committing=False;digest=hashlib.sha256()
        try:
            while offset<archive.size:
                if cancelled():raise DeviceError('Archive restore cancelled')
                if state['state']!=WRITABLE or state['offset']!=offset or state['length']!=archive.size:raise DeviceError('Invalid archive upload offset')
                block=stream.read(min(488,archive.size-offset))
                if not block:raise DeviceError('Archive source changed during upload')
                self.client.write(0x92,struct.pack('<2I16s',state['sequence'],offset,state['nonce'])+block)
                digest.update(block);offset+=len(block);progress(offset,archive.size);state=self._wait(binding,cancelled=cancelled)
            if stream.read(1) or digest.hexdigest()!=archive.sha256:raise DeviceError('Archive source changed during upload')
            consent_flag=state['flags']&4
            repair_flag=state['flags']&8
            if bool(repair_flag)!=repair_code:raise DeviceError('Archive code-repair receipt changed; no commit was sent')
            if consent_flag:
                if not allow_recovery_pair or state['state'] not in (AWAIT_USER,READY):raise DeviceError('Unexpected archive approval request')
                state=self._approve_pair(source,state,cancelled=cancelled,notify=notify)
            if state['state']!=READY or state['offset']!=archive.size or state['digest']!=digest.digest():raise DeviceError('Archive was not fully verified by the calculator')
            if cancelled():raise DeviceError('Archive restore cancelled before commit')
            committing=True
            self.client.write(0x94,state['nonce'],argument=state['sequence'])
            state=self._wait(binding)
            if state['state']!=COMPLETE or state['flags']!=(1|consent_flag|repair_flag) or state['digest']!=digest.digest():raise DeviceError('Archive commit receipt is incomplete')
        except BaseException as exc:
            if not committing:self._cancel(binding);raise
            if isinstance(exc,TransferFailure) and not exc.status['flags']&2 and exc.status['error']!=13:raise
            raise DeviceError('Archive commit outcome is unknown; inspect the app before another restore. No write was retried.') from exc
        try:
            after=self.info(archive.app_id)
            if (not after['exists'] or not after['index_known'] or after['generation']!=state['generation'] or
                    after['package_sha256']!=current.package.sha256 or after['data_schema']!=current.data_schema or
                    after['private_bytes']!=current.private.size or after['named_bytes']!=used-current.private.size or
                    after['pending_upgrade']!=(len(archive.snapshots)==2) or after['high_version']!=max(before['high_version'] or (0,0,0),archive.high_version)):
                raise DeviceError('Restored app metadata differs from the archive')
        except BaseException as exc:
            raise DeviceError('Archive restore committed, but final inspection failed. No rollback was attempted.') from exc
        return {'app':archive.app_id,'generation':after['generation'],'bytes':archive.size,'sha256':archive.sha256,
                'snapshots':len(archive.snapshots),'committed':True,'code_repaired':repair_code,'package_sha256':after['package_sha256']}
