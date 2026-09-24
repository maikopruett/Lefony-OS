# SPDX-License-Identifier: GPL-3.0-or-later
"""One bounded HTTPS exchange in a disposable process; no USB or store authority.

The companion pumps poll()/acknowledge() without blocking its USB lease. Upload
credits and response acknowledgements bound both IPC directions to one chunk.
Cancellation terminates DNS/socket waits as well as a stalled streaming peer.
"""
from dataclasses import dataclass
import http.client
import multiprocessing
import re
import ssl
import time
from urllib.parse import urlsplit
from tls_context import client_context, TrustError

CHUNK=440
METHODS=frozenset(('GET','HEAD','POST','PUT','PATCH','DELETE'))
MUTATIONS=frozenset(('POST','PUT','PATCH','DELETE'))
FORBIDDEN=frozenset(('host','content-length','transfer-encoding','connection','keep-alive',
    'proxy-authorization','proxy-authenticate','te','trailer','upgrade','expect'))


class HTTPSError(ValueError):pass


def _url(url):
    if not isinstance(url,str) or not 1<=len(url)<=2048 or any(ord(c)<33 or ord(c)>126 for c in url) or '\\' in url:
        raise HTTPSError('URL must be bounded, percent-encoded ASCII')
    try:
        parsed=urlsplit(url);port=443 if parsed.port is None else parsed.port
        host=parsed.hostname
        if parsed.scheme!='https' or not host or parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise ValueError()
        if not 1<=port<=65535:raise ValueError()
    except ValueError as exc:raise HTTPSError('Only HTTPS URLs without credentials or fragments are supported') from exc
    authority=('['+host+']' if ':' in host else host)+(f':{port}' if port!=443 else '')
    return parsed,host,port,'https://'+authority


@dataclass(frozen=True)
class Policy:
    # The companion binds this explicit grant to an authenticated app/signer.
    origins:tuple
    methods:tuple=('GET','HEAD')
    upload_limit:int=8*1024*1024
    response_limit:int=8*1024*1024
    timeout_ms:int=120000
    ca_file:str|None=None

    def validate(self,url,method,headers,upload_bytes,response_limit,timeout_ms):
        parsed,host,port,origin=_url(url)
        allowed=set()
        for item in self.origins:
            p,_,_,o=_url(item)
            if p.path not in ('','/') or p.query:raise HTTPSError('Policy grants exact origins, without paths or queries')
            allowed.add(o)
        if not allowed or origin not in allowed:raise HTTPSError('HTTPS origin is not granted for this app')
        if not isinstance(method,str) or method not in METHODS or method not in self.methods:raise HTTPSError('HTTP method is not granted for this app')
        for value in (self.upload_limit,self.response_limit):
            if type(value) is not int or not 0<=value<=32*1024*1024:raise HTTPSError('Invalid host byte limit')
        if type(self.timeout_ms) is not int or not 100<=self.timeout_ms<=120000:raise HTTPSError('Invalid host deadline')
        if upload_bytes is not None and (type(upload_bytes) is not int or not 0<=upload_bytes<=self.upload_limit):
            raise HTTPSError('Upload exceeds host grant')
        if method in ('GET','HEAD') and upload_bytes!=0:raise HTTPSError('GET and HEAD do not accept a body in this profile')
        if type(response_limit) is not int or not 0<=response_limit<=self.response_limit:raise HTTPSError('Response exceeds host grant')
        if type(timeout_ms) is not int or not 100<=timeout_ms<=self.timeout_ms:raise HTTPSError('Deadline exceeds host grant')
        if not isinstance(headers,(list,tuple)) or len(headers)>16:raise HTTPSError('At most sixteen request headers are supported')
        result={};size=0
        for pair in headers:
            if not isinstance(pair,(list,tuple)) or len(pair)!=2:raise HTTPSError('Invalid request header pair')
            name,value=pair
            if not isinstance(name,str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]{1,64}",name):raise HTTPSError('Invalid header name')
            name=name.lower()
            if name in FORBIDDEN or name in result:raise HTTPSError('Reserved or duplicate request header')
            if not isinstance(value,str) or len(value)>1024 or any(ord(c)<32 or ord(c)>126 for c in value):raise HTTPSError('Invalid header value')
            size+=len(name)+len(value)+4;result[name]=value
        if size>4096:raise HTTPSError('Request headers exceed limit')
        target=(parsed.path or '/')+('?' + parsed.query if parsed.query else '')
        return {'host':host,'port':port,'target':target,'method':method,'headers':result,'upload_bytes':upload_bytes,
                'upload_limit':self.upload_limit,'response_limit':response_limit,'timeout_ms':timeout_ms,'ca_file':self.ca_file}


def _worker(pipe,request):
    connection=None;sent=received=0;started=False;response_started=False
    def event(kind,**fields):
        pipe.send({'kind':kind,**fields})
        reply=pipe.recv()
        if not isinstance(reply,dict):raise HTTPSError('Invalid companion acknowledgement')
        return reply
    def acknowledged(kind,**fields):
        if event(kind,**fields)!={'kind':'ack'}:raise HTTPSError('Expected companion acknowledgement')
    try:
        context=client_context(request['ca_file'])
        connection=http.client.HTTPSConnection(request['host'],request['port'],
            timeout=min(10,request['timeout_ms']/1000),context=context)
        connection.connect()
        # The parent sees this before any HTTP request can reach the server.
        acknowledged('request');started=True
        connection.putrequest(request['method'],request['target'],skip_accept_encoding=True)
        for name,value in request['headers'].items():connection.putheader(name,value)
        if 'accept-encoding' not in request['headers']:connection.putheader('Accept-Encoding','identity')
        connection.putheader('Connection','close')
        chunked=request['upload_bytes'] is None
        if chunked:connection.putheader('Transfer-Encoding','chunked')
        else:connection.putheader('Content-Length',str(request['upload_bytes']))
        connection.endheaders()
        while request['upload_bytes']!=0:
            reply=event('upload',offset=sent,maximum=CHUNK)
            data=reply.get('data');final=reply.get('final')
            if reply.get('kind')!='upload' or not isinstance(data,bytes) or type(final) is not bool or len(data)>CHUNK:
                raise HTTPSError('Invalid upload chunk')
            if not data and not final:raise HTTPSError('Empty nonfinal upload')
            if sent+len(data)>request['upload_limit'] or (not chunked and sent+len(data)>request['upload_bytes']):
                raise HTTPSError('Upload exceeded declared limit')
            if data:
                connection.send((f'{len(data):x}\r\n'.encode()+data+b'\r\n') if chunked else data)
                sent+=len(data)
            if final:
                if not chunked and sent!=request['upload_bytes']:raise HTTPSError('Upload shorter than declared length')
                if chunked:connection.send(b'0\r\n\r\n')
                break
        response=connection.getresponse()
        if response.status<200:raise HTTPSError('Protocol upgrades are not supported')
        headers=response.getheaders()
        if len(headers)>32 or sum(len(k)+len(v)+4 for k,v in headers)>8192:raise HTTPSError('Response headers exceed limit')
        lengths=[v for k,v in headers if k.lower()=='content-length']
        transfers=[v for k,v in headers if k.lower()=='transfer-encoding']
        if len(lengths)>1 or len(transfers)>1 or (lengths and transfers):raise HTTPSError('Ambiguous response framing')
        if lengths and not re.fullmatch(r'[0-9]{1,10}',lengths[0]):raise HTTPSError('Invalid response length')
        if transfers and transfers[0].lower()!='chunked':raise HTTPSError('Unsupported response transfer encoding')
        no_body=request['method']=='HEAD' or response.status in (204,304)
        expected=0 if no_body else int(lengths[0]) if lengths else None
        if expected is not None and expected>request['response_limit']:raise HTTPSError('Response exceeds limit')
        # Redirects are returned to the app as ordinary responses. Following one
        # requires a new request and a fresh origin/method policy check.
        acknowledged('response',status=response.status,headers=headers,upload_bytes=sent,response_bytes=expected)
        response_started=True
        while not no_body:
            data=response.read(min(CHUNK,request['response_limit']-received+1))
            if not data:break
            if received+len(data)>request['response_limit']:raise HTTPSError('Response exceeds limit')
            acknowledged('data',offset=received,data=data);received+=len(data)
        if expected is not None and expected!=received:raise HTTPSError('Truncated response')
        pipe.send({'kind':'done','upload_bytes':sent,'response_bytes':received})
    except (OSError,ValueError,EOFError,http.client.HTTPException) as exc:
        # Never include URLs, request headers, certificate paths or peer text in
        # the app-facing error. In particular, no bearer secret enters logs.
        code=('tls' if isinstance(exc,(ssl.SSLError,TrustError)) else 'timeout' if isinstance(exc,TimeoutError)
              else 'protocol' if isinstance(exc,(HTTPSError,http.client.HTTPException)) else 'network')
        try:pipe.send({'kind':'error','code':code,'upload_bytes':sent,'response_bytes':received,
                       'outcome_unknown':started and not response_started and request['method'] in MUTATIONS})
        except (OSError,EOFError):pass
    finally:
        if connection is not None:connection.close()
        pipe.close()


class Exchange:
    def __init__(self,policy,url,*,method='GET',headers=(),upload_bytes=0,response_limit=1048576,timeout_ms=30000):
        request=policy.validate(url,method,headers,upload_bytes,response_limit,timeout_ms)
        self.method=method;self.deadline=time.monotonic()+timeout_ms/1000
        self.pending=None;self.terminal=None;self.started=False;self.response_started=False
        context=multiprocessing.get_context('spawn');self.pipe,child=context.Pipe()
        self.process=context.Process(target=_worker,args=(child,request),daemon=True)
        try:self.process.start()
        except BaseException:self.pipe.close();child.close();raise
        child.close()

    def poll(self):
        if self.terminal is not None:return self.terminal
        if time.monotonic()>=self.deadline:return self.cancel('timeout')
        if self.pending is not None:return self.pending
        if self.pipe.poll():
            try:event=self.pipe.recv()
            except (EOFError,OSError):return self.cancel('network')
            if event['kind']=='request':self.started=True
            if event['kind']=='response':self.response_started=True
            if event['kind'] in ('done','error'):
                self.terminal=event;self._stop();return event
            self.pending=event;return event
        if not self.process.is_alive():return self.cancel('network')
        return None

    def acknowledge(self):
        if self.pending is None or self.pending['kind']=='upload':raise HTTPSError('No response event to acknowledge')
        self.pipe.send({'kind':'ack'});self.pending=None

    def upload(self,data=b'',*,final=False):
        if self.pending is None or self.pending['kind']!='upload':raise HTTPSError('Wait for an upload credit')
        if not isinstance(data,bytes) or len(data)>CHUNK or type(final) is not bool or (not data and not final):
            raise HTTPSError('Invalid upload chunk')
        self.pipe.send({'kind':'upload','data':data,'final':final});self.pending=None

    def cancel(self,code='cancelled'):
        if self.terminal is None:
            self.terminal={'kind':'error','code':code,
                           'outcome_unknown':self.started and not self.response_started and self.method in MUTATIONS}
            self.pending=None;self._stop()
        return self.terminal

    def _stop(self):
        self.pipe.close()
        if self.process.is_alive():self.process.terminate()
        self.process.join(.2)
        if self.process.is_alive():self.process.kill();self.process.join(.5)

    def __enter__(self):return self
    def __exit__(self,*unused):self.cancel()
