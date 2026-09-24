# SPDX-License-Identifier: GPL-3.0-or-later
"""Restricted app-channel transport; never sends installer/diagnostic commands."""
import re
import secrets
import struct

PAYLOAD=448
ERRORS={3:'unsupported',4:'invalid',5:'denied',6:'not ready',7:'stale session',
        8:'disconnected',9:'timeout',10:'cancelled',11:'sequence exhausted',12:'buffer too small'}


class ChannelError(RuntimeError):pass


class ChannelEnded(ChannelError):
    """The exact bound peer reports a terminal channel state."""
    def __init__(self,error):
        self.error=error
        super().__init__('Channel ended: '+ERRORS.get(error,'closed'))

    @property
    def normal(self):
        return self.error in (0,8,10)


def _text(data,maximum,empty=False):
    zero=data.find(b'\0')
    if zero<0 or zero>maximum or (not zero and not empty) or any(data[zero:]) or any(b<32 or b>126 for b in data[:zero]):
        raise ChannelError('Invalid channel identity text')
    return data[:zero].decode('ascii')


def decode_info(data):
    if len(data)!=320:raise ChannelError('Update Lefony OS: app channel status is unavailable')
    values=struct.unpack_from('<16I',data)
    if values[:2]!=(320,1) or values[2]>4 or values[4] not in (0,*ERRORS) or values[7]>4 or values[8]>4 or values[9]>PAYLOAD or values[10:12]!=(PAYLOAD,4) or any(data[296:]):
        raise ChannelError('Invalid channel status')
    app=_text(data[64:116],48,True);name=_text(data[116:200],80,True);label=_text(data[264:296],31,True)
    if app and not re.fullmatch(r'[a-z][a-z0-9-]{0,47}',app):raise ChannelError('Invalid channel app ID')
    if values[2] in (1,2,3) and (not values[3] or not app or not name or not values[5] or not values[6]):
        raise ChannelError('Invalid active channel identity')
    if values[2] in (2,3) and (not any(values[12:16]) or not label):raise ChannelError('Invalid peer binding')
    return dict(zip(('size','schema','state','session','error','send_sequence','receive_sequence',
                     'send_queued','receive_queued','next_receive_bytes','maximum_payload','queue_capacity'),values[:12]),
                nonce=values[12:16],app=app,name=name,package_hash=data[200:232],signer=data[232:264],host_label=label)


class Client:
    def __init__(self,transport,app_id,signer,*,package_hash=None):
        if not isinstance(app_id,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,47}',app_id):raise ValueError('Invalid app ID')
        if not isinstance(signer,bytes) or len(signer)!=32:raise ValueError('Expected signing-key SHA-256 is required')
        if package_hash is not None and (not isinstance(package_hash,bytes) or len(package_hash)!=32):raise ValueError('Invalid package hash')
        self.transport,self.app_id,self.signer,self.package_hash=transport,app_id,signer,package_hash
        self.binding=None;self.pending=None;self.received=None;self.send_sequence=self.receive_sequence=1

    def status(self):
        return decode_info(bytes(self.transport.read(0x78,length=320)))

    def attach(self,label='Lefony SDK companion'):
        if self.binding is not None:raise ChannelError('Close this host session before attaching again')
        if not isinstance(label,str) or not 1<=len(label)<=31 or not all(32<=ord(c)<=126 for c in label):raise ValueError('Host label must be 1–31 printable ASCII characters')
        info=self.status()
        if info['state']!=1:raise ChannelError('The app must open a new channel before pairing')
        if info['app']!=self.app_id or info['signer']!=self.signer or (self.package_hash is not None and info['package_hash']!=self.package_hash):
            raise ChannelError('Channel app, signing key or package differs from the authorized identity')
        nonce=secrets.token_bytes(16)
        if not any(nonce):raise ChannelError('Random nonce generation failed')
        self.binding={**info,'nonce':struct.unpack('<4I',nonce)}
        self.send_sequence=self.receive_sequence=1;self.pending=self.received=None
        packet=struct.pack('<8I',64,1,info['session'],0,*self.binding['nonce'])+label.encode().ljust(32,b'\0')
        # Retain the exact attach after an uncertain USB completion. Retry only
        # this immutable packet; the firmware never restarts consent on replay.
        self.attach_packet=packet
        self.transport.write(0x79,data=packet)
        return self.binding['nonce'][0]%1000000

    def retry_attach(self):
        if self.binding is None:raise ChannelError('No attach is pending')
        info=self.status()
        if any(info[k]!=self.binding[k] for k in ('session','app','package_hash','signer')):raise ChannelError('Channel identity changed')
        self.transport.write(0x79,data=self.attach_packet)

    def _bound(self,states=(3,)):
        if self.binding is None:raise ChannelError('No host session')
        info=self.status()
        if any(info[k]!=self.binding[k] for k in ('session','nonce','app','package_hash','signer')):
            raise ChannelError('Channel disconnected or changed identity')
        if info['state']==4:raise ChannelEnded(info['error'])
        if info['state'] not in states:raise ChannelError('Channel is awaiting calculator confirmation')
        return info

    def paired(self):
        return self._bound((2,3))['state']==3

    def ended(self):
        """Confirm ordinary closure without accepting a different peer or retrying I/O."""
        try:self._bound()
        except ChannelEnded as error:return error.normal
        return False

    def _control(self,command,sequence=0):
        if command not in (0x7c,0x7d,0x7e):raise ValueError('Not an app-channel control')
        self.transport.write(command,data=struct.pack('<8I',32,1,self.binding['session'],sequence,*self.binding['nonce']))

    def keepalive(self):
        self._bound();self._control(0x7d)

    def send(self,kind,data):
        if type(kind) is not int or not 1<=kind<=65535 or not isinstance(data,bytes) or len(data)>PAYLOAD:raise ValueError('Invalid app message')
        if self.pending is not None:raise ChannelError('Resolve the pending send before sending another message')
        info=self._bound()
        if info['receive_sequence']!=self.send_sequence:raise ChannelError('Another sender changed the channel sequence')
        if info['receive_queued']==4:return False
        if self.send_sequence==0xffffffff:raise ChannelError('Channel sequence exhausted; reopen explicitly')
        self.pending=struct.pack('<16I',64+len(data),1,self.binding['session'],self.send_sequence,kind,len(data),
                                 *self.binding['nonce'],*([0]*6))+data
        return self.flush()

    def flush(self):
        if self.pending is None:return True
        info=self._bound()
        if info['receive_sequence']==self.send_sequence+1:
            # The identical pending frame already committed despite a lost USB
            # status. Never submit a new logical message in its place.
            self.pending=None;self.send_sequence+=1;return True
        if info['receive_sequence']!=self.send_sequence:raise ChannelError('Pending frame sequence changed')
        if info['receive_queued']==4:return False
        self.transport.write(0x7a,data=self.pending)
        self.pending=None;self.send_sequence+=1;return True

    def receive(self):
        info=self._bound()
        if self.received is not None:return self.received
        if not info['send_queued']:return None
        session=self.binding['session']
        data=bytes(self.transport.read(0x7b,value=session&65535,index=session>>16,length=512))
        if len(data)<64:raise ChannelError('Truncated app message')
        words=struct.unpack_from('<16I',data)
        if words[:4]!=(len(data),1,session,self.receive_sequence) or not 1<=words[4]<=65535 or words[5]>PAYLOAD or words[5]+64!=len(data) or words[6:10]!=self.binding['nonce'] or any(words[10:]):
            raise ChannelError('Malformed, replayed or foreign app message')
        self.received={'sequence':words[3],'kind':words[4],'data':data[64:]};return self.received

    def acknowledge(self):
        if self.received is None:raise ChannelError('No received message to acknowledge')
        self._bound();self._control(0x7c,self.received['sequence'])
        self.receive_sequence+=1;self.received=None

    def close(self):
        if self.binding is None:return
        self._bound((2,3));self._control(0x7e)
        self.binding=self.pending=self.received=None
