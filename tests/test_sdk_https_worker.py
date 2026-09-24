# SPDX-License-Identifier: GPL-3.0-or-later
"""Real local TLS and HTTP framing, with no external service or attached device."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import threading
import time
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sdk/tools'))
from https_worker import CHUNK,Exchange,HTTPSError,Policy

BODY=bytes((i*13+7)&255 for i in range(131073))


@pytest.fixture(scope='module')
def tls_server(tmp_path_factory):
    root=tmp_path_factory.mktemp('https-worker');key=root/'key.pem';cert=root/'cert.pem'
    openssl=shutil.which('openssl');assert openssl,'OpenSSL is required for local TLS fixtures'
    subprocess.run([openssl,'req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost',
        '-addext','subjectAltName=DNS:localhost','-keyout',str(key),'-out',str(cert)],check=True,capture_output=True,timeout=15)
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*args):pass
        def do_GET(self):
            requests.append((self.command,self.path,dict(self.headers),b''))
            try:
                if self.path=='/slow':time.sleep(1.5)
                if self.path=='/redirect':
                    self.send_response(302);self.send_header('Location','https://ungranted.invalid/private');self.send_header('Content-Length','0');self.end_headers();return
                self.send_response(200)
                if self.path=='/chunked':self.send_header('Transfer-Encoding','chunked')
                elif self.path=='/ambiguous':
                    self.send_header('Content-Length','3');self.send_header('Transfer-Encoding','chunked')
                elif self.path!='/unknown':self.send_header('Content-Length',str(len(BODY)))
                self.send_header('Connection','close');self.end_headers()
                if self.path=='/truncated':self.wfile.write(BODY[:100])
                elif self.path=='/chunked':
                    for offset in range(0,len(BODY),1024):
                        data=BODY[offset:offset+1024];self.wfile.write(f'{len(data):x}\r\n'.encode()+data+b'\r\n')
                    self.wfile.write(b'0\r\n\r\n')
                elif self.path!='/ambiguous':self.wfile.write(BODY)
            except OSError:pass
            self.close_connection=True
        def do_POST(self):
            data=bytearray()
            if self.headers.get('Transfer-Encoding')=='chunked':
                while True:
                    line=self.rfile.readline()
                    if not line:break
                    size=int(line.strip(),16)
                    if not size:self.rfile.readline();break
                    data.extend(self.rfile.read(size));self.rfile.read(2)
            else:data.extend(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((self.command,self.path,dict(self.headers),bytes(data)))
            if self.path=='/slow':time.sleep(1.5)
            try:
                self.send_response(201);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except OSError:pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
    server.socket=context.wrap_socket(server.socket,server_side=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'https://localhost:{server.server_port}',str(cert),requests
    finally:server.shutdown();server.server_close();thread.join(2)


def pump(exchange,body=b'',*,before_ack=lambda event:None):
    events=[];data=bytearray();offset=0;deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        event=exchange.poll()
        if event is None:time.sleep(.001);continue
        events.append(event);before_ack(event)
        if event['kind'] in ('done','error'):return events,bytes(data)
        if event['kind']=='upload':
            assert event['offset']==offset and event['maximum']==CHUNK
            chunk=body[offset:offset+CHUNK];offset+=len(chunk);exchange.upload(chunk,final=offset==len(body))
        else:
            if event['kind']=='data':
                assert event['offset']==len(data) and len(event['data'])<=CHUNK;data.extend(event['data'])
            exchange.acknowledge()
    raise AssertionError('HTTPS fixture did not finish')


@pytest.mark.parametrize('path',['/fixed','/chunked','/unknown'])
def test_streamed_tls_response_and_one_event_backpressure(tls_server,path):
    origin,cert,_=tls_server
    with Exchange(Policy((origin,),ca_file=cert),origin+path) as exchange:
        def held(event):
            if event['kind']=='data':assert exchange.poll() is event
        events,body=pump(exchange,before_ack=held)
        assert events[-1]=={'kind':'done','upload_bytes':0,'response_bytes':len(BODY)} and body==BODY
        assert any(e['kind']=='response' and e['status']==200 for e in events)
        assert not exchange.process.is_alive()


@pytest.mark.parametrize('known',[True,False])
def test_streamed_upload_and_response_exact_bytes(tls_server,known):
    origin,cert,requests=tls_server;body=BODY[:70017]
    with Exchange(Policy((origin,),methods=('POST',),ca_file=cert),origin+'/echo',method='POST',
                  headers=(('Authorization','Bearer app-owned-test-value'),),upload_bytes=len(body) if known else None) as exchange:
        events,result=pump(exchange,body)
        assert events[-1]['kind']=='done' and events[-1]['upload_bytes']==len(body) and result==body
    assert requests[-1][3]==body and {k.lower():v for k,v in requests[-1][2].items()}['authorization']=='Bearer app-owned-test-value'


def test_redirect_is_returned_without_following_or_forwarding_credentials(tls_server):
    origin,cert,requests=tls_server;count=len(requests)
    with Exchange(Policy((origin,),ca_file=cert),origin+'/redirect') as exchange:
        events,result=pump(exchange)
        assert events[-1]['kind']=='done' and not result
        assert any(e['kind']=='response' and e['status']==302 for e in events)
    assert len(requests)==count+1


@pytest.mark.parametrize('path,limit',[('/truncated',200000),('/fixed',1000),('/unknown',1000),('/ambiguous',200000)])
def test_bad_or_excessive_responses_fail_with_bounded_output(tls_server,path,limit):
    origin,cert,_=tls_server
    with Exchange(Policy((origin,),ca_file=cert),origin+path,response_limit=limit) as exchange:
        events,result=pump(exchange)
        assert events[-1]['kind']=='error' and len(result)<=limit and not exchange.process.is_alive()


def test_tls_trust_and_hostname_are_both_checked(tls_server):
    origin,cert,requests=tls_server;count=len(requests)
    for url,ca in ((origin,None),(origin.replace('localhost','127.0.0.1'),cert)):
        with Exchange(Policy((url,),ca_file=ca),url+'/fixed') as exchange:
            events,_=pump(exchange)
            assert events[-1]['kind']=='error' and events[-1]['code']=='tls' and not events[-1]['outcome_unknown']
    assert len(requests)==count


def test_cancel_and_deadline_terminate_blocked_mutation_without_retry(tls_server):
    origin,cert,requests=tls_server
    for cancel in (True,False):
        before=sum(r[0]=='POST' and r[1]=='/slow' for r in requests)
        with Exchange(Policy((origin,),methods=('POST',),ca_file=cert),origin+'/slow',method='POST',
                      upload_bytes=0,timeout_ms=700 if not cancel else 30000) as exchange:
            deadline=time.monotonic()+5
            while sum(r[0]=='POST' and r[1]=='/slow' for r in requests)==before:
                event=exchange.poll()
                if event:
                    if event['kind']=='upload':exchange.upload(final=True)
                    else:exchange.acknowledge()
                assert time.monotonic()<deadline;time.sleep(.002)
            start=time.monotonic()
            if cancel:event=exchange.cancel()
            else:
                while (event:=exchange.poll()) is None:time.sleep(.002)
            assert event['kind']=='error' and event['code']==('cancelled' if cancel else 'timeout') and event['outcome_unknown']
            assert time.monotonic()-start<1 and not exchange.process.is_alive()
        assert sum(r[0]=='POST' and r[1]=='/slow' for r in requests)==before+1


@pytest.mark.parametrize('change',[
    {'url':'http://example.test/a'},{'url':'https://elsewhere.test/a'},{'url':'https://user:secret@example.test/a'},
    {'url':'https://example.test/a#b'},{'url':'https://example.test/a\r\nb'}, {'method':'POST'},
    {'url':'https://example.test:0/a'},
    {'headers':(('Host','other.test'),)},{'headers':(('X-Test','bad\r\nheader'),)},
    {'headers':(('X-Test','one'),('x-test','two'))},{'upload_bytes':1},{'response_limit':33554433},{'timeout_ms':120001},
])
def test_request_policy_rejects_before_starting_network_process(change):
    arguments={'url':'https://example.test/a','method':'GET','headers':(),'upload_bytes':0,'response_limit':1000,'timeout_ms':1000,**change}
    with pytest.raises(HTTPSError):Policy(('https://example.test',)).validate(**arguments)
