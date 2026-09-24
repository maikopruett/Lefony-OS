# SPDX-License-Identifier: GPL-3.0-or-later
"""OS-approved developer public keys. Never sends firmware or raw-storage commands."""
import hashlib
import secrets
import re
import struct
import time
from pathlib import Path
from data_device import publish_backup

from device import Client as AppClient, DeviceError
from signing import SPKI_PREFIX, SPKI_SUFFIX, public_der
from usb_files import LibUSB
import key_snapshot

STATES=('idle','awaiting_usb_ack','preparing','awaiting_approval','working','complete','cancelled','denied','expired','failed')
ERRORS=('none','invalid','stale_registry','key_limit','registry_unavailable','busy','protected_key','key_not_found','storage_error','outcome_unknown','serial_exhausted','invalid_recovery_package','signer_ownership','key_required_by_installed_or_unreadable_apps','revoke_key_before_removal','registry_fully_readable')


class KeyUSB(LibUSB):
    READ_REQUESTS=(0x60,0x80,0x83,0x85,0x86,0x87,0x88)
    WRITE_REQUESTS=(0x81,0x82)


class InstallUSB(LibUSB):
    READ_REQUESTS=(0x60,0x68,0x6a,0x6e)
    WRITE_REQUESTS=(0x63,0x64,0x65,0x67,0x6a)


class RecoveryUSB(LibUSB):
    READ_REQUESTS=(0x60,0x68,0x6a,0x6e,0x80,0x83,0x84)
    WRITE_REQUESTS=(0x63,0x64,0x67,0x6a,0x81,0x82)


def _text(raw,empty=False):
    n=raw.find(b'\0')
    if n<0 or (not n and not empty) or any(raw[n:]) or any(b<32 or b>126 for b in raw[:n]):
        raise DeviceError('Invalid developer-key label')
    value=raw[:n].decode('ascii')
    if value.strip()!=value:raise DeviceError('Invalid developer-key label padding')
    return value


def decode_status(raw):
    if len(raw)!=160:raise DeviceError('Invalid developer-key status length')
    v=struct.unpack_from('<12I',raw)
    if (v[:3]!=(0x534b464c,160,1) or v[3]>=len(STATES) or v[4]>7 or v[5]>=len(ERRORS) or
            v[7]>4 or v[9]>8 or v[10]!=8 or v[11]>512 or (bool(any(raw[128:]))!=(v[4] in (3,5,7)))):
        raise DeviceError('Unsupported developer-key status')
    if (v[7]==2 and (not v[8] or v[8]<v[9])) or (v[7]!=2 and (v[8] or v[9])):
        raise DeviceError('Invalid developer-key registry state')
    label=_text(raw[96:128],True)
    if v[6]:
        if not v[4] or not any(raw[48:64]) or bool(any(raw[64:96]))!=(v[4]!=6):raise DeviceError('Invalid developer-key request binding')
        if v[4]==6 and label:raise DeviceError('Unexpected identity in partial registry backup')
    elif v[3] or v[4] or v[5] or any(raw[48:128]):raise DeviceError('Invalid initial developer-key status')
    return {'state':STATES[v[3]],'operation':('none','enroll','revoke','recover','remove','repair','backup-unreadable','repair-unreadable')[v[4]],'error':ERRORS[v[5]],
            'sequence':v[6],'registry':('uninitialized','empty','ready','corrupt','unreadable')[v[7]],
            'serial':v[8],'count':v[9],'maximum':v[10],'unavailable_apps':v[11],
            'nonce':raw[48:64].hex(),'fingerprint':raw[64:96].hex(),'label':label,
            'package_hash':raw[128:].hex() if v[4]==3 else '0'*64,'registry_hash':raw[128:].hex() if v[4] in (5,7) else '0'*64}


def decode_damage(raw):
    if len(raw)!=64:raise DeviceError('Invalid damaged-registry information length')
    v=struct.unpack_from('<8I',raw)
    if v[:3]!=(0x444b464c,64,1) or v[3]>65536 or any(v[4:]) or not any(raw[32:]):
        raise DeviceError('Unsupported damaged-registry information')
    return {'bytes':v[3],'sha256':raw[32:].hex()}


def decode_unreadable(raw):
    if len(raw)!=96:raise DeviceError('Invalid partial-registry information length')
    v=struct.unpack_from('<8I',raw)
    if (v[:3]!=(0x554b464c,96,1) or not v[3] or not 0<v[4]<=key_snapshot.MAX_SOURCE or
            not 0<v[7]<=(v[4]+511)//512 or not 0<=v[6]<v[4] or
            not (v[7]-1)*512<v[4]-v[6]<=v[7]*512 or
            v[5]!=32+((v[4]+511)//512)*16+v[6] or not any(raw[32:48]) or
            not any(raw[48:80]) or any(raw[80:])):
        raise DeviceError('Unsupported partial-registry information')
    return {'sequence':v[3],'original_bytes':v[4],'bytes':v[5],'readable_bytes':v[6],
            'unreadable_chunks':v[7],'nonce':raw[32:48].hex(),'sha256':raw[48:80].hex()}


def enrollment(public_key,label):
    if not isinstance(label,str) or not 1<=len(label)<=31 or label.strip()!=label or any(not 32<=ord(c)<=126 for c in label):
        raise ValueError('Key label must be 1–31 printable ASCII characters without outer spaces')
    der=public_der(public_key)
    return hashlib.sha256(der).digest(),der[len(SPKI_PREFIX):-len(SPKI_SUFFIX)],label.encode().ljust(32,b'\0')


def decode_recovery(raw):
    if len(raw)!=192:raise DeviceError('Invalid app recovery information length')
    v=struct.unpack_from('<8I',raw)
    if v[:3]!=(0x524b464c,192,1) or not all(v[3:6]) or any(v[6:]) or not any(raw[128:160]) or not any(raw[160:]):
        raise DeviceError('Invalid app recovery information')
    app_id,version=_text(raw[32:96]),_text(raw[96:128])
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}',app_id) or not re.fullmatch(r'[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}',version):
        raise DeviceError('Invalid app recovery identity')
    return {'sequence':v[3],'serial':v[4],'generation':v[5],'app_id':app_id,'version':version,
            'old_fingerprint':raw[128:160].hex(),'package_hash':raw[160:].hex()}


def decode_key(raw):
    if len(raw)!=352:raise DeviceError('Invalid developer public-key length')
    v=struct.unpack_from('<8I',raw)
    if v[:3]!=(0x494b464c,352,1) or v[3]>=8 or not v[4] or v[5] not in (1,2) or any(v[6:]):
        raise DeviceError('Unsupported developer-key record')
    identity,modulus=raw[32:64],raw[64:320]
    if not modulus[0]&128 or not modulus[-1]&1 or hashlib.sha256(SPKI_PREFIX+modulus+SPKI_SUFFIX).digest()!=identity:
        raise DeviceError('Developer public-key fingerprint mismatch')
    return {'index':v[3],'serial':v[4],'state':'active' if v[5]==1 else 'revoked',
            'fingerprint':identity.hex(),'modulus':modulus.hex(),'label':_text(raw[320:352])}


class Client:
    def __init__(self,transport,*,clock=time.monotonic,sleep=time.sleep):
        self.transport=transport;self.app=AppClient(transport,clock=clock,sleep=sleep)
        self.clock=clock;self.sleep=sleep;self.pending=None

    def status(self):
        if not self.app.status()['reserved']&256:
            raise DeviceError('Update Lefony OS: developer-key management is unavailable; no key request was sent')
        return decode_status(self.app.read(0x80,160))

    def keys(self):
        before=self.status();records=[]
        if before['registry'] not in ('empty','ready'):raise DeviceError('Developer registry is unavailable; no reset was attempted')
        for index in range(before['count']):
            item=decode_key(self.app.read(0x83,352,index))
            if item['index']!=index or item['serial']!=before['serial']:raise DeviceError('Developer registry changed during listing')
            records.append(item)
        after=self.status()
        if any(before[k]!=after[k] for k in ('registry','serial','count')):raise DeviceError('Developer registry changed during listing')
        if len({item['fingerprint'] for item in records})!=len(records):raise DeviceError('Duplicate developer-key identities')
        return {'registry':before['registry'],'serial':before['serial'],'keys':records}

    def begin(self,operation,*,public_key=None,label=None,fingerprint=None,package_hash=None,registry_hash=None,notify=lambda message:None):
        if self.pending is not None:raise DeviceError('Inspect the previous developer-key request before starting another')
        if operation in ('enroll','repair','repair-unreadable'):
            identity,modulus,encoded_label=enrollment(public_key,label)
        elif operation in ('revoke','recover','remove'):
            if not isinstance(fingerprint,str) or len(fingerprint)!=64:raise ValueError('Use the full 64-digit public-key fingerprint')
            try:identity=bytes.fromhex(fingerprint)
            except ValueError:raise ValueError('Invalid public-key fingerprint') from None
            if len(identity)!=32 or not any(identity):raise ValueError('Invalid public-key fingerprint')
            modulus=bytes(256);encoded_label=bytes(32)
        elif operation=='backup-unreadable':
            if any(v is not None for v in (public_key,label,fingerprint)):raise ValueError('A partial backup does not enroll an identity')
            identity=bytes(32);modulus=bytes(256);encoded_label=bytes(32)
        else:raise ValueError('Unknown key operation')
        extra=bytes(32)
        if operation=='recover':
            if not isinstance(package_hash,str) or not re.fullmatch('[0-9a-fA-F]{64}',package_hash) or not any(bytes.fromhex(package_hash)):
                raise ValueError('Recovery requires the exact signed package SHA-256')
            extra=bytes.fromhex(package_hash)
            if not self.app.status()['reserved']&512:raise DeviceError('Update Lefony OS: app signer recovery is unavailable')
        elif package_hash is not None:raise ValueError('Package hash is only valid for app signer recovery')
        if operation in ('repair','repair-unreadable'):
            if not isinstance(registry_hash,str) or not re.fullmatch('[0-9a-fA-F]{64}',registry_hash) or not any(bytes.fromhex(registry_hash)):
                raise ValueError('Repair requires the SHA-256 of the exported damaged registry')
            extra=bytes.fromhex(registry_hash)
        elif registry_hash is not None:raise ValueError('Registry hash is only valid for registry repair')
        if operation in ('remove','repair') and not self.app.status()['reserved']&2048:
            raise DeviceError('Update Lefony OS: developer-key maintenance is unavailable; no key request was sent')
        if operation in ('backup-unreadable','repair-unreadable') and not self.app.status()['reserved']&16384:
            raise DeviceError('Update Lefony OS: unreadable-registry recovery is unavailable; no key request was sent')
        before=self.status()
        if operation=='repair':
            if before['registry']!='corrupt':raise DeviceError('Repair requires a readable damaged registry; no reset was attempted')
        elif operation=='repair-unreadable':
            if before['registry'] not in ('corrupt','unreadable'):raise DeviceError('Repair requires an unreadable registry; no reset was attempted')
        elif operation!='backup-unreadable' and before['registry'] not in ('empty','ready'):raise DeviceError('Developer registry is unavailable; no reset was attempted')
        if before['state'] in STATES[1:5]:raise DeviceError('A developer-key request is already pending')
        if before['sequence']==0xffffffff:raise DeviceError('Developer-key session counter is exhausted; restart the calculator')
        nonce=secrets.token_bytes(16)
        if not any(nonce):raise DeviceError('Nonce generation failed')
        serial=0 if operation in ('backup-unreadable','repair-unreadable') else before['serial']
        packet=struct.pack('<4I',384,1,{'enroll':1,'revoke':2,'recover':3,'remove':4,'repair':5,'backup-unreadable':6,'repair-unreadable':7}[operation],serial)+nonce+identity+modulus+encoded_label+extra
        self.pending={'operation':operation,'fingerprint':identity.hex(),'nonce':nonce.hex(),'sequence':before['sequence']+1,'packet':packet,
            'package_hash':extra.hex() if operation=='recover' else '0'*64,'registry_hash':extra.hex() if operation in ('repair','repair-unreadable') else '0'*64}
        if operation!='backup-unreadable':
            notify(f'Return the calculator to Home. Compare this public-key fingerprint, then approve on the calculator:\n{identity.hex()}\nRequest nonce: {nonce.hex()}')
        try:self.app.write(0x81,packet)
        except Exception as exc:
            raise DeviceError(f'Key request outcome is unknown. Run keys status and keys list; request nonce {nonce.hex()}. No write was retried.') from exc
        return self.bound_status()

    def bound_status(self):
        if self.pending is None:raise DeviceError('No developer-key request is being followed')
        status=self.status()
        if any(status[k]!=self.pending[k] for k in ('operation','fingerprint','nonce','sequence','package_hash','registry_hash')):
            raise DeviceError('Developer-key request changed or calculator restarted; inspect keys list before any new request')
        return status

    def damage_info(self):
        if not self.app.status()['reserved']&2048:raise DeviceError('Update Lefony OS: developer-key maintenance is unavailable')
        before=self.status()
        if before['registry']!='corrupt' or before['state'] in STATES[1:5]:
            raise DeviceError('Readable damaged registry is not available; no reset was attempted')
        return decode_damage(self.app.read(0x85,64))

    def backup_damaged(self,destination,*,replace=False):
        destination=Path(destination)
        if destination.exists() and not replace:raise DeviceError('Backup destination exists; choose a new path or explicitly use --replace')
        before=self.damage_info();raw=bytearray()
        while len(raw)<before['bytes']:
            n=min(512,before['bytes']-len(raw));block=self.app.read(0x86,n,len(raw))
            if len(block)!=n:raise DeviceError('Short damaged-registry export; no backup was published')
            raw.extend(block)
        if self.damage_info()!=before or hashlib.sha256(raw).hexdigest()!=before['sha256']:
            raise DeviceError('Damaged registry changed during export; no backup was published')
        publish_backup(destination,raw,replace)
        return {**before,'backup':str(destination),'status':'backed_up'}

    def repair(self,public_key,label,backup,*,notify=lambda message:None):
        enrollment(public_key,label) # Validate local inputs before device access.
        saved=self.backup_damaged(backup)
        notify(f"Saved damaged registry backup: {saved['backup']}\nDamaged registry SHA-256: {saved['sha256']}\n"
               'Repair rebuilds trust with the selected key. Other keys require explicit re-enrollment; installed app/data bytes remain unchanged.')
        self.begin('repair',public_key=public_key,label=label,registry_hash=saved['sha256'],notify=notify)
        return {**self.wait(),'backup':saved}

    def unreadable_info(self):
        before=self.bound_status()
        if before['operation']!='backup-unreadable' or before['state']!='complete':
            raise DeviceError('Partial registry backup is not ready')
        info=decode_unreadable(self.app.read(0x87,96));after=self.bound_status()
        if any(info[k]!=before[k] or info[k]!=after[k] for k in ('sequence','nonce')):
            raise DeviceError('Partial registry snapshot changed')
        return info

    def backup_unreadable(self,destination,*,replace=False):
        destination=Path(destination)
        if destination.exists() and not replace:raise DeviceError('Backup destination exists; choose a new path or explicitly use --replace')
        self.begin('backup-unreadable');status=self.wait()
        if status['state']!='complete':raise DeviceError('Partial registry backup failed: '+status['error'])
        before=self.unreadable_info();raw=bytearray()
        while len(raw)<before['bytes']:
            n=min(512,before['bytes']-len(raw));block=self.app.read(0x88,n,len(raw))
            if len(block)!=n:raise DeviceError('Short partial-registry export; no backup was published')
            raw.extend(block)
        parsed=key_snapshot.inspect(raw)
        if self.unreadable_info()!=before or any(parsed[k]!=before[k] for k in parsed):
            raise DeviceError('Partial registry changed during export; no backup was published')
        publish_backup(destination,raw,replace)
        return {**before,'backup':str(destination),'status':'partially_backed_up'}

    def repair_unreadable(self,public_key,label,backup,*,notify=lambda message:None):
        enrollment(public_key,label)
        saved=Client(self.transport,clock=self.clock,sleep=self.sleep).backup_unreadable(backup)
        notify(f"Saved partial registry backup: {saved['backup']}\nPartial backup SHA-256: {saved['sha256']}\n"
               f"Preserved {saved['readable_bytes']} of {saved['original_bytes']} bytes; {saved['unreadable_chunks']} regions were unreadable.\n"
               'Missing bytes cannot be recovered from this backup. Repair trusts only the selected key; other keys need explicit re-enrollment. Installed apps/data remain unchanged.')
        self.begin('repair-unreadable',public_key=public_key,label=label,registry_hash=saved['sha256'],notify=notify)
        return {**self.wait(),'backup':saved}

    def recovery_info(self):
        before=self.bound_status()
        if before['operation']!='recover' or before['state'] not in ('awaiting_approval','working','complete'):
            raise DeviceError('App signer recovery is not prepared')
        info=decode_recovery(self.app.read(0x84,192))
        after=self.bound_status()
        if any(info[k]!=before[k] or info[k]!=after[k] for k in ('sequence','serial','package_hash')):
            raise DeviceError('App recovery information changed')
        return info

    def recover_install(self,package,public_keys,*,notify=lambda message:None):
        # Discover before uploading, so older firmware is left untouched.
        if not self.app.status()['reserved']&512:raise DeviceError('Update Lefony OS: app signer recovery is unavailable; no package was uploaded')
        expected_hash=hashlib.sha256(package).hexdigest()
        def commit(metadata):
            notify(f"Recover app {metadata['id']} to version {metadata['version']}. Saved data will be retained.\nPackage SHA-256: {expected_hash}")
            self.begin('recover',fingerprint=package[24:56].hex(),package_hash=expected_hash,notify=notify)
            deadline=self.clock()+125;reviewed=False
            while self.clock()<deadline:
                status=self.bound_status()
                if status['state'] in ('awaiting_approval','working','complete') and not reviewed:
                    info=self.recovery_info()
                    if info['app_id']!=metadata['id'] or info['version']!=metadata['version']:
                        raise DeviceError('Recovery app identity does not match the uploaded package')
                    notify(f"Retained revoked key: {info['old_fingerprint']}\nSaved-data generation: {info['generation']}");reviewed=True
                if status['state'] not in STATES[1:5]:
                    if status['state']!='complete':raise DeviceError(f"App signer recovery {status['state']}: {status['error']}; inspect keys status and the app catalog")
                    return
                self.sleep(.1)
            raise DeviceError('App signer recovery timed out; inspect keys status and the app catalog. No write was retried')
        return self.app.install(package,public_keys,commit=commit)

    def wait(self,timeout=125):
        if not 0<timeout<=180:raise ValueError('Key wait must be between 0 and 180 seconds')
        deadline=self.clock()+timeout
        while self.clock()<deadline:
            status=self.bound_status()
            if status['state'] not in STATES[1:5]:return status
            self.sleep(.1)
        raise DeviceError('Key request timed out. Inspect keys status and keys list; no cancellation or write was retried')

    def cancel(self,sequence,nonce):
        if not isinstance(sequence,int) or not 0<sequence<=0xffffffff or not isinstance(nonce,str) or len(nonce)!=32:
            raise ValueError('Cancellation requires the exact sequence and nonce from keys status')
        try:identity=bytes.fromhex(nonce)
        except ValueError:raise ValueError('Invalid request nonce') from None
        if len(identity)!=16 or not any(identity):raise ValueError('Invalid request nonce')
        status=self.status()
        if status['sequence']!=sequence or status['nonce']!=nonce.lower():raise DeviceError('Key request changed; cancellation was not sent')
        self.app.write(0x82,struct.pack('<4I',32,1,sequence,0)+identity)
        return self.status() # Committing may continue; cancellation never claims rollback.
