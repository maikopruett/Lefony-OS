# SPDX-License-Identifier: GPL-3.0-or-later
"""Companion protocol 1: bounded app USB messages to one policy-scoped HTTPS job."""
from collections import deque
import re
import struct
import time
from https_worker import Exchange,HTTPSError

BEGIN,URL,HEADERS,UPLOAD,CANCEL=range(0x100,0x105)
RESPONSE,HEADER,DATA,DONE,ERROR,CREDIT,PROGRESS=range(0x180,0x187)
UNKNOWN=0xffffffff
METHODS={1:'GET',2:'HEAD',3:'POST',4:'PUT',5:'PATCH',6:'DELETE'}
ERRORS={'policy':1,'protocol':2,'tls':3,'network':4,'timeout':5,'cancelled':6}
MUTATIONS=frozenset(('POST','PUT','PATCH','DELETE'))


class ProtocolError(HTTPSError):pass


def words(*values):return struct.pack('<'+'I'*len(values),*values)


class Bridge:
    def __init__(self,client,policy,*,progress=lambda event:None):
        if not client.paired():raise ProtocolError('Calculator consent is required')
        self.client=client;self.policy=policy;self.progress=progress;self.closed=False
        self.last_id=0;self.id=None;self.exchange=None;self.out=deque();self.after=None
        self.finishing=False;self.credit=None;self.last_keepalive=0
        self.uploaded=self.downloaded=0;self.response_sent=False

    def _queue(self,kind,payload):
        if len(payload)>448:raise ProtocolError('Companion frame exceeds channel')
        self.out.append((kind,payload))

    def _finish(self):
        if self.exchange is not None:self.exchange.cancel()
        self.exchange=None;self.id=None;self.credit=None;self.finishing=False;self.after=None

    def _fail(self,code):
        unknown=False
        if self.exchange is not None:
            event=self.exchange.cancel(code)
            unknown=(self.exchange.started and not self.response_sent and self.method in MUTATIONS)
            self.uploaded=event.get('upload_bytes',self.uploaded)
        self.out.clear();self.after=self._finish;self.credit=None;self.finishing=True
        self._queue(ERROR,words(self.id,ERRORS.get(code,4),int(unknown),self.uploaded,self.downloaded,0))
        self.progress({'id':self.id,'phase':'error','code':code,'outcome_unknown':unknown,
                       'upload_bytes':self.uploaded,'response_bytes':self.downloaded})

    def _start(self):
        try:
            url=self.url.decode('ascii');raw=self.headers.decode('ascii')
            if (raw and not raw.endswith('\n')) or any(c!='\n' and not 32<=ord(c)<=126 for c in raw):
                raise HTTPSError('Headers require ASCII lines ending with LF')
            headers=[]
            for line in raw.splitlines():
                if ':' not in line:raise HTTPSError('Invalid header line')
                name,value=line.split(':',1);headers.append((name,value.lstrip(' ')))
            if '\r' in raw:raise HTTPSError('CR is not permitted in metadata')
            remaining=int((self.deadline-time.monotonic())*1000)
            if remaining<100:self._fail('timeout');return
            self.exchange=Exchange(self.policy,url,method=self.method,headers=headers,
                upload_bytes=None if self.upload_bytes==UNKNOWN else self.upload_bytes,
                response_limit=self.response_limit,timeout_ms=remaining)
        except (HTTPSError,UnicodeError):self._fail('policy');return
        except OSError:self._fail('network');return
        self._queue(PROGRESS,words(self.id,0,0,1))
        self.progress({'id':self.id,'phase':'connecting','upload_bytes':0,'response_bytes':0})

    @staticmethod
    def _discard_terminal_fragment(kind,data):
        # The app can have queued these before observing DONE/ERROR. Validate
        # their wire shape, then acknowledge without another result or job.
        # Offsets/content no longer affect a request after its terminal result.
        if kind==CANCEL and len(data)==4:return
        if kind in (URL,HEADERS) and 8<len(data)<=448:return
        if kind==UPLOAD and 12<=len(data)<=448:
            flags=struct.unpack_from('<I',data,8)[0]
            if flags in (0,1) and (len(data)>12 or flags):return
        raise ProtocolError('Malformed fragment after HTTPS completion')

    def _message(self,message):
        kind,data=message['kind'],message['data']
        if kind==BEGIN:
            if len(data)!=32:raise ProtocolError('Invalid HTTPS request header')
            schema,request,method,size,limit,timeout,url_bytes,header_bytes=struct.unpack('<8I',data)
            if self.id is not None or not request or request<=self.last_id:raise ProtocolError('Concurrent or reused HTTPS request ID')
            self.id=self.last_id=request;self.uploaded=self.downloaded=0;self.response_sent=False
            self.method=METHODS.get(method);self.upload_bytes=size;self.response_limit=limit
            self.url_bytes=url_bytes;self.header_bytes=header_bytes;self.url=bytearray();self.headers=bytearray()
            self.deadline=time.monotonic()+timeout/1000
            if schema!=1 or self.method is None or not 1<=url_bytes<=2048 or header_bytes>4096 or not 100<=timeout<=self.policy.timeout_ms or limit>self.policy.response_limit or (size!=UNKNOWN and size>self.policy.upload_limit):
                self._fail('policy')
            return
        if len(data)<4:raise ProtocolError('Truncated HTTPS message')
        request=struct.unpack_from('<I',data)[0]
        if self.id is None and self.last_id and request==self.last_id:
            # Sending the terminal over USB does not mean the app has read it.
            # Keep draining that last request until a newer BEGIN is accepted.
            self._discard_terminal_fragment(kind,data);return
        if self.id is None or request!=self.id:raise ProtocolError('HTTPS request ID changed')
        if self.finishing:self._discard_terminal_fragment(kind,data);return
        if kind==CANCEL:
            if len(data)!=4:raise ProtocolError('Invalid HTTPS cancellation')
            self._fail('cancelled');return
        if kind in (URL,HEADERS):
            if self.exchange is not None or len(data)<=8:raise ProtocolError('Unexpected HTTPS metadata')
            offset=struct.unpack_from('<I',data,4)[0]
            target=self.url if kind==URL else self.headers;maximum=self.url_bytes if kind==URL else self.header_bytes
            if offset!=len(target) or len(target)+len(data)-8>maximum:raise ProtocolError('Metadata offset/length mismatch')
            target.extend(data[8:])
            if len(self.url)==self.url_bytes and len(self.headers)==self.header_bytes:self._start()
            return
        if kind==UPLOAD:
            if self.exchange is None or self.credit is None or len(data)<12:raise ProtocolError('Upload requires a credit')
            offset,flags=struct.unpack_from('<2I',data,4);payload=data[12:]
            if flags not in (0,1) or offset!=self.credit['offset'] or len(payload)>self.credit['maximum'] or (not payload and not flags):
                raise ProtocolError('Invalid upload chunk')
            if flags and self.upload_bytes!=UNKNOWN and offset+len(payload)!=self.upload_bytes:
                raise ProtocolError('Final upload length differs from request')
            self.exchange.upload(payload,final=bool(flags));self.credit=None;return
        raise ProtocolError('Unknown HTTPS message kind')

    def _event(self,event):
        kind=event['kind']
        if kind=='request':
            self.exchange.acknowledge();self._queue(PROGRESS,words(self.id,self.uploaded,self.downloaded,2))
        elif kind=='upload':
            maximum=min(436,event['maximum'],self.policy.upload_limit-event['offset'])
            if self.upload_bytes!=UNKNOWN:maximum=min(maximum,self.upload_bytes-event['offset'])
            if maximum<0:raise ProtocolError('Worker upload exceeds grant')
            self.uploaded=event['offset'];credit={'offset':event['offset'],'maximum':maximum}
            self._queue(CREDIT,words(self.id,credit['offset'],maximum))
            self.after=lambda:setattr(self,'credit',credit)
            self.progress({'id':self.id,'phase':'upload','upload_bytes':self.uploaded,'response_bytes':self.downloaded})
        elif kind=='response':
            headers=[]
            for name,value in event['headers']:
                if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+",name) or '\r' in value or '\n' in value:
                    raise ProtocolError('Response contains an unsupported header')
                headers.append(name+': '+value+'\n')
            encoded=''.join(headers).encode('latin1')
            if len(encoded)>8192:raise ProtocolError('Response headers exceed limit')
            self.uploaded=event['upload_bytes']
            self._queue(RESPONSE,words(1,self.id,event['status'],len(encoded),self.uploaded,
                        UNKNOWN if event['response_bytes'] is None else event['response_bytes'],0,0))
            for offset in range(0,len(encoded),440):self._queue(HEADER,words(self.id,offset)+encoded[offset:offset+440])
            self.after=self.exchange.acknowledge
        elif kind=='data':
            if event['offset']!=self.downloaded or len(event['data'])>440:raise ProtocolError('Worker response offset changed')
            self._queue(DATA,words(self.id,self.downloaded)+event['data']);self.after=self.exchange.acknowledge
        elif kind=='done':
            if event['response_bytes']!=self.downloaded:raise ProtocolError('Worker response length changed')
            self.uploaded=event['upload_bytes'];self.finishing=True;self.after=self._finish
            self._queue(DONE,words(self.id,self.uploaded,self.downloaded,0))
            self.progress({'id':self.id,'phase':'complete','upload_bytes':self.uploaded,'response_bytes':self.downloaded})
        elif kind=='error':self._fail(event['code'])
        else:raise ProtocolError('Unknown worker event')

    def step(self):
        """Perform bounded work, then return to the companion/UI event loop."""
        if self.closed:raise ProtocolError('Bridge is closed')
        try:
            now=time.monotonic()
            if now-self.last_keepalive>=1:self.client.keepalive();self.last_keepalive=now
            if self.id is not None and not self.finishing and now>=self.deadline:self._fail('timeout')
            message=self.client.receive()
            if message is not None:
                try:self._message(message)
                except (ProtocolError,UnicodeError):
                    if self.id is None:raise
                    self._fail('protocol')
                self.client.acknowledge()
            if self.out:
                kind,data=self.out[0]
                if self.client.send(kind,data):
                    self.out.popleft()
                    if kind==RESPONSE:self.response_sent=True
                    if kind==DATA:self.downloaded+=len(data)-8
                    if not self.out and self.after is not None:
                        callback,self.after=self.after,None;callback()
            elif self.exchange is not None and self.credit is None and not self.finishing:
                event=self.exchange.poll()
                if event is not None:
                    try:self._event(event)
                    except (ProtocolError,UnicodeError):self._fail('protocol')
        except BaseException:
            self.close();raise

    def close(self):
        if self.exchange is not None:self.exchange.cancel()
        self.exchange=None;self.out.clear();self.after=None;self.credit=None;self.closed=True
