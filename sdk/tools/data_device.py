# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit private-data backups and retained-pair rollback over app USB."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import tempfile
from device import DeviceError
from files_device import FileClient, DATA_INFO, DATA_EXPORT, DATA_IMPORT, ROLLBACK, WRITABLE, COMPLETE

MAGIC = b'LFDATA1\0'
MAXIMUM = 65536
HEADER_LIMIT = 4096
DATA_INFO_WIRE = struct.Struct('<20I32s32s32s')


def encode_backup(app_id, version, schema, payload):
    metadata = {'schema':1, 'app':app_id, 'version':version, 'data_schema':schema,
                'bytes':len(payload), 'sha256':hashlib.sha256(payload).hexdigest()}
    header = json.dumps(metadata, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    result = MAGIC + struct.pack('<I', len(header)) + header + payload
    decode_backup(result)  # Apply the same strict format boundary to exports.
    return result


def decode_backup(data):
    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result: raise ValueError('Duplicate backup field')
            result[key] = value
        return result
    try:
        if len(data)<12 or len(data)>12+HEADER_LIMIT+MAXIMUM or data[:8]!=MAGIC:
            raise ValueError('Invalid private-data backup header')
        size = struct.unpack_from('<I', data, 8)[0]
        if not 0<size<=HEADER_LIMIT or 12+size>len(data): raise ValueError('Invalid backup metadata length')
        m = json.loads(data[12:12+size].decode('utf-8'), object_pairs_hook=unique)
        if not isinstance(m,dict) or set(m)!={'schema','app','version','data_schema','bytes','sha256'}:
            raise ValueError('Invalid backup metadata fields')
        if type(m['schema']) is not int or m['schema']!=1: raise ValueError('Unsupported backup schema')
        if not isinstance(m['app'],str) or not re.fullmatch('[a-z][a-z0-9-]{0,47}',m['app']):
            raise ValueError('Invalid backup app identity')
        if not isinstance(m['version'],str) or not re.fullmatch(r'(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})',m['version']):
            raise ValueError('Invalid backup app version')
        if type(m['data_schema']) is not int or not 0<=m['data_schema']<=0xffffffff:
            raise ValueError('Invalid backup data schema')
        payload = data[12+size:]
        if type(m['bytes']) is not int or not 0<=m['bytes']<=MAXIMUM or len(payload)!=m['bytes']:
            raise ValueError('Invalid backup payload length')
        if m['sha256']!=hashlib.sha256(payload).hexdigest(): raise ValueError('Backup SHA-256 mismatch')
        return m,payload
    except (ValueError,TypeError,UnicodeError,struct.error,RecursionError) as error:
        raise DeviceError(str(error)) from error


def read_backup(path):
    fd = os.open(path,os.O_RDONLY|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_BINARY',0))
    with os.fdopen(fd,'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or not 12<=info.st_size<=12+HEADER_LIMIT+MAXIMUM:
            raise DeviceError('Choose a regular private-data backup within the format limit')
        data = stream.read(info.st_size+1)
        if len(data)!=info.st_size: raise DeviceError('Backup file length changed while reading')
    return decode_backup(data)


def publish_backup(path, data, replace):
    path = Path(path)
    if path.exists() and not replace: raise DeviceError('Backup destination exists; explicitly choose --replace')
    fd,temp = tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.partial',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            if stream.write(data)!=len(data): raise DeviceError('Short local backup write')
            stream.flush();os.fsync(stream.fileno())
        if replace: os.replace(temp,path)
        else: os.link(temp,path);os.unlink(temp)
        if os.name!='nt':
            folder = os.open(path.parent,os.O_RDONLY)
            try: os.fsync(folder)
            finally: os.close(folder)
    finally:
        if os.path.exists(temp): os.unlink(temp)


class DataClient(FileClient):
    def info(self, app_id):
        output = io.BytesIO()
        state = self._begin(app_id,DATA_INFO)
        if state['length']!=DATA_INFO_WIRE.size:
            self._cancel(state['sequence']); raise DeviceError('Invalid data recovery information length')
        result = self._download(state,output)
        data = output.getvalue()
        if len(data)!=DATA_INFO_WIRE.size: raise DeviceError('Invalid data recovery information length')
        w = DATA_INFO_WIRE.unpack(data)
        if (w[:2]!=(176,1) or not w[2] or w[2]!=result['generation'] or w[8]!=result['data_schema'] or
                w[3]&~3 or w[19] or w[9]>MAXIMUM or w[14]>MAXIMUM or
                any(v>999999 for v in (*w[4:7],*w[10:13],*w[15:18])) or
                w[3]&2 and (not w[3]&1 or not w[18])):
            raise DeviceError('Invalid data recovery information schema')
        return {'app':app_id,'generation':w[2],'pending_upgrade':bool(w[3]&1),'rollback_available':bool(w[3]&2),
            'version':'.'.join(map(str,w[4:7])),'app_schema':w[7],'data_schema':w[8],'private_bytes':w[9],
            'previous_version':'.'.join(map(str,w[10:13])) if w[3]&2 else None,
            'previous_schema':w[13],'previous_private_bytes':w[14],'high_version':'.'.join(map(str,w[15:18])),
            'previous_package':w[18],'package_sha256':w[20].hex(),'previous_package_sha256':w[21].hex(),
            'private_sha256':w[22].hex()}

    def export(self, app_id, destination, *, replace=False, cancelled=lambda:False, progress=lambda done,total:None):
        if Path(destination).exists() and not replace: raise DeviceError('Backup destination exists; explicitly choose --replace')
        identity = self.info(app_id); output = io.BytesIO()
        state = self._begin(app_id,DATA_EXPORT,identity=identity)
        if state['length']!=identity['private_bytes']:
            self._cancel(state['sequence']); raise DeviceError('Private-data export length differs from the inspected snapshot')
        result = self._download(state,output,cancelled=cancelled,progress=progress)
        if result['bytes']!=identity['private_bytes'] or result['sha256']!=identity['private_sha256']:
            raise DeviceError('Private-data export differs from the inspected snapshot')
        publish_backup(destination,encode_backup(app_id,identity['version'],identity['data_schema'],output.getvalue()),replace)
        return {'app':app_id,**result,'backup':'lefony-private-data-1'}

    def restore(self, app_id, source, *, cancelled=lambda:False, progress=lambda done,total:None):
        return self._restore(app_id,read_backup(source),cancelled=cancelled,progress=progress)

    def _restore(self, app_id, prepared, *, cancelled=lambda:False, progress=lambda done,total:None):
        # The CLI reads and validates the complete bounded backup before opening
        # USB, then keeps those exact bytes. Source callers use restore() above.
        metadata,payload = prepared
        if metadata['app']!=app_id: raise DeviceError('Backup belongs to a different app; no data was written')
        if cancelled(): raise DeviceError('Private-data restore cancelled before transfer')
        identity = self.info(app_id)
        if identity['pending_upgrade'] or metadata['data_schema']!=identity['data_schema'] or identity['app_schema']!=identity['data_schema']:
            raise DeviceError('Backup schema is incompatible or an upgrade is pending; no data was written')
        result = self._upload(app_id,'',io.BytesIO(payload),len(payload),hashlib.sha256(payload).digest(),identity,
            operation=DATA_IMPORT,cancelled=cancelled,progress=progress)
        result.pop('path'); return result

    def rollback(self, app_id, *, cancelled=lambda:False):
        identity = self.info(app_id)
        if not identity['rollback_available']: raise DeviceError('No verified compatible recovery pair is available')
        if cancelled(): raise DeviceError('Rollback cancelled before preparation')
        state = self._begin(app_id,ROLLBACK,identity=identity,cursor=identity['previous_package'])
        token = state['sequence']
        try:
            if state['state']!=WRITABLE or state['offset'] or state['length']:
                raise DeviceError('Rollback was not prepared')
            if cancelled(): raise DeviceError('Rollback cancelled before commit')
        except BaseException:
            self._cancel(token); raise
        # No automatic cancellation or retry after this explicit commit request.
        self.client.write(0x74,argument=token)
        state = self._wait(sequence=token,operation=ROLLBACK)
        if state['state']!=COMPLETE or state['flags']!=1 or state['data_schema']!=identity['previous_schema']:
            raise DeviceError('Rollback outcome requires inspection; no write was retried')
        try:
            after = self.info(app_id)
            if (after['generation']!=state['generation'] or after['pending_upgrade'] or
                    after['package_sha256']!=identity['previous_package_sha256'] or
                    after['data_schema']!=identity['previous_schema'] or after['high_version']!=identity['high_version']):
                raise DeviceError('Retained package/data identity did not match after rollback')
        except Exception as error:
            raise DeviceError('Rollback committed but final inspection failed; do not retry automatically: '+str(error)) from error
        return {'app':app_id,'committed':True,'version':after['version'],'data_schema':after['data_schema'],
            'generation':after['generation'],'high_version':after['high_version']}
