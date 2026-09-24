# SPDX-License-Identifier: GPL-3.0-or-later
"""Controlled localhost TLS service and deterministic bytes for ARM fixtures."""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import time

BODY=bytes((i*13+7)&255 for i in range(131073))


@contextmanager
def service(*,response=None):
    with tempfile.TemporaryDirectory(prefix='sdk-local-tls-') as temp:
        root=Path(temp);key=root/'key.pem';cert=root/'cert.pem';requests=[]
        subprocess.run([shutil.which('openssl'),'req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost',
            '-addext','subjectAltName=DNS:localhost','-keyout',str(key),'-out',str(cert)],check=True,capture_output=True,timeout=15)
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*unused):pass
            def handle(self):
                try:super().handle()
                except (ConnectionResetError,BrokenPipeError,ssl.SSLError):pass
            def do_GET(self):
                requests.append({'method':'GET','path':self.path})
                status,body=(200,BODY) if response is None else response(self.path)
                if self.path=='/slow':time.sleep(5)
                try:
                    self.send_response(status);self.send_header('Content-Type','application/octet-stream')
                    if self.path=='/chunked':self.send_header('Transfer-Encoding','chunked')
                    else:self.send_header('Content-Length',str(len(body)))
                    self.send_header('Connection','close');self.end_headers()
                    if self.path=='/chunked':
                        for offset in range(0,len(body),1024):
                            data=body[offset:offset+1024];self.wfile.write(f'{len(data):x}\r\n'.encode()+data+b'\r\n')
                        self.wfile.write(b'0\r\n\r\n')
                    else:self.wfile.write(body[:100] if self.path=='/truncated' else body)
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
                        block=self.rfile.read(size);data.extend(block)
                        if len(block)!=size:break
                        self.rfile.read(2)
                else:data.extend(self.rfile.read(int(self.headers.get('Content-Length','0'))))
                requests.append({'method':'POST','path':self.path,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
                try:
                    self.send_response(201);self.send_header('Content-Type','application/octet-stream')
                    self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
                except OSError:pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
        server.socket=context.wrap_socket(server.socket,server_side=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:yield f'https://localhost:{server.server_port}',cert,requests
        finally:server.shutdown();server.server_close();thread.join(2)
