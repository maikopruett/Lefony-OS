# SPDX-License-Identifier: GPL-3.0-or-later
from collections import deque
from pathlib import Path
import struct
import subprocess
import sys
import time
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sdk/tools'))
from https_bridge import Bridge,ProtocolError,BEGIN,URL,HEADERS,UPLOAD,CANCEL,RESPONSE,HEADER,DATA,DONE,ERROR,CREDIT,words
from https_worker import Policy
from companion import ChannelUSB,run
from usb_files import USBError
from test_sdk_https_worker import tls_server, BODY


class Channel:
    def __init__(self):self.incoming=deque();self.outgoing=deque();self.alive=True;self.pings=0
    def paired(self):return self.alive
    def keepalive(self):
        if not self.alive:raise USBError('Synthetic disconnect')
        self.pings+=1
    def receive(self):
        if not self.alive:raise USBError('Synthetic disconnect')
        return self.incoming[0] if self.incoming else None
    def acknowledge(self):self.incoming.popleft()
    def send(self,kind,data):
        if len(self.outgoing)==4:return False
        self.outgoing.append((kind,data));return True
    def app(self,kind,data):self.incoming.append({'kind':kind,'data':data})


def begin(channel,url,*,id=1,method=1,size=0,limit=200000,timeout=10000,headers=b''):
    encoded=url.encode();channel.app(BEGIN,words(1,id,method,size,limit,timeout,len(encoded),len(headers)))
    for kind,raw in ((URL,encoded),(HEADERS,headers)):
        for offset in range(0,len(raw),440):channel.app(kind,words(id,offset)+raw[offset:offset+440])


def pump(bridge,channel,body=b'',*,id=1,cancel=False):
    result=bytearray();headers=bytearray();status=None;events=[];deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        bridge.step()
        while channel.outgoing:
            kind,data=channel.outgoing.popleft();events.append((kind,data))
            if kind==CREDIT:
                request,offset,maximum=struct.unpack('<3I',data);assert request==id and maximum<=436
                chunk=body[offset:offset+maximum];final=offset+len(chunk)==len(body)
                channel.app(UPLOAD,words(id,offset,int(final))+chunk)
            elif kind==RESPONSE:
                values=struct.unpack('<8I',data);assert values[0:2]==(1,id);status=values[2]
            elif kind==HEADER:
                request,offset=struct.unpack_from('<2I',data);assert request==id and offset==len(headers);headers.extend(data[8:])
            elif kind==DATA:
                request,offset=struct.unpack_from('<2I',data);assert request==id and offset==len(result);result.extend(data[8:])
                if cancel:channel.app(CANCEL,words(id));cancel=False
            elif kind in (DONE,ERROR):return kind,data,status,bytes(headers),bytes(result),events
        time.sleep(.001)
    raise AssertionError('Bridge did not finish')


def test_real_tls_to_bounded_channel_and_sequential_request_ids(tls_server):
    origin,cert,_=tls_server;channel=Channel();bridge=Bridge(channel,Policy((origin,),ca_file=cert))
    try:
        for id,path in ((1,'/fixed'),(2,'/chunked')):
            begin(channel,origin+path,id=id);kind,data,status,headers,body,_=pump(bridge,channel,id=id)
            assert kind==DONE and struct.unpack('<4I',data)==(id,0,len(BODY),0)
            assert status==200 and body==BODY and b'Server:' in headers and bridge.id is None
        assert channel.pings>=1
    finally:bridge.close()


@pytest.mark.parametrize('unknown',[False,True])
def test_upload_credits_and_exact_echo(tls_server,unknown):
    origin,cert,requests=tls_server;channel=Channel();bridge=Bridge(channel,Policy((origin,),methods=('POST',),ca_file=cert));body=BODY[:70017]
    try:
        begin(channel,origin+'/echo',method=3,size=0xffffffff if unknown else len(body),headers=b'Content-Type: application/octet-stream\n')
        kind,data,status,_,received,events=pump(bridge,channel,body)
        assert kind==DONE and status==201 and received==body and requests[-1][3]==body
        assert struct.unpack('<4I',data)==(1,len(body),len(body),0)
        assert sum(kind==CREDIT for kind,_ in events)>100
    finally:bridge.close()


def test_policy_refusal_and_corrected_request_without_network_attempt(tls_server):
    origin,cert,requests=tls_server;channel=Channel();bridge=Bridge(channel,Policy((origin,),ca_file=cert));count=len(requests)
    try:
        begin(channel,'https://not-granted.invalid/private')
        result=pump(bridge,channel);assert result[0]==ERROR and struct.unpack('<6I',result[1])==(1,1,0,0,0,0)
        assert len(requests)==count
        begin(channel,origin+'/fixed',id=2);assert pump(bridge,channel,id=2)[0]==DONE
    finally:bridge.close()


def test_cancel_response_and_disconnect_stop_worker(tls_server):
    origin,cert,_=tls_server;channel=Channel();bridge=Bridge(channel,Policy((origin,),ca_file=cert))
    try:
        begin(channel,origin+'/fixed');kind,data,_,_,body,_=pump(bridge,channel,cancel=True)
        assert kind==ERROR and struct.unpack('<6I',data)[1:3]==(6,0) and 0<len(body)<len(BODY)
        begin(channel,origin+'/slow',id=2)
        deadline=time.monotonic()+5
        while bridge.exchange is None:bridge.step();assert time.monotonic()<deadline
        worker=bridge.exchange.process;channel.alive=False
        with pytest.raises(USBError):bridge.step()
        assert bridge.closed and not worker.is_alive()
    finally:bridge.close()


def test_full_usb_queue_stops_response_reads_and_deadline_still_applies(tls_server):
    origin,cert,_=tls_server;channel=Channel();bridge=Bridge(channel,Policy((origin,),ca_file=cert))
    try:
        begin(channel,origin+'/fixed',timeout=600);deadline=time.monotonic()+3
        while time.monotonic()<deadline and not bridge.finishing:
            bridge.step();time.sleep(.002)
        assert bridge.finishing and len(channel.outgoing)==4 and len(bridge.out)==1
        assert bridge.exchange.terminal['code']=='timeout' and not bridge.exchange.process.is_alive()
        assert bridge.downloaded<=440*4
        channel.outgoing.clear();bridge.step();assert channel.outgoing[0][0]==ERROR
    finally:bridge.close()


def test_metadata_timeout_never_starts_network(tls_server):
    origin,cert,requests=tls_server;channel=Channel();bridge=Bridge(channel,Policy((origin,),ca_file=cert));before=len(requests)
    try:
        channel.app(BEGIN,words(1,1,1,0,1000,100,20,0));result=pump(bridge,channel)
        assert result[0]==ERROR and struct.unpack('<6I',result[1])[1:3]==(5,0) and len(requests)==before
    finally:bridge.close()


def test_channel_usb_never_accepts_file_installer_or_diagnostics_commands():
    transport=ChannelUSB.__new__(ChannelUSB)
    for request in (0x40,0x48,0x60,0x68,0x70,0x71,0x72,0x73,0x74,0x75):
        with pytest.raises(USBError):transport.read(request)
        with pytest.raises(USBError):transport.write(request)


def test_companion_help_does_not_open_usb():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,str(root/'sdk/tools/lefony-sdk'),'companion','--help'],capture_output=True,text=True,timeout=10)
    assert result.returncode==0 and '--allow-origin' in result.stdout and '--signer' in result.stdout


@pytest.mark.parametrize('terminal',['done','error'])
def test_trailing_request_fragments_preserve_session_and_next_request(tls_server,terminal):
    origin,cert,requests=tls_server;channel=Channel();bridge=Bridge(channel,Policy((origin,),ca_file=cert))
    before=len(requests)
    try:
        # An error at BEGIN can be delivered before already queued metadata.
        # Cancellation can also arrive after the terminal frame was enqueued,
        # but before the app has read it. Neither operation creates a new job.
        begin(channel,origin+'/fixed',method=99 if terminal=='error' else 1)
        result=pump(bridge,channel)
        assert result[0]==(ERROR if terminal=='error' else DONE) and bridge.id is None
        channel.app(CANCEL,words(1));channel.app(CANCEL,words(1))
        while channel.incoming:bridge.step()
        assert not bridge.closed and bridge.exchange is None and not channel.outgoing
        assert len(requests)==before+(terminal=='done')
        begin(channel,origin+'/fixed',id=2)
        result=pump(bridge,channel,id=2)
        assert result[0]==DONE and result[4]==BODY and not bridge.closed
        assert len(requests)==before+1+(terminal=='done')
    finally:bridge.close()


@pytest.mark.parametrize('kind,payload',[
    (CANCEL,words(1)),(URL,words(1,0)+b'https://localhost/image'),
    (HEADERS,words(1,0)+b'Accept: image/test\n'),(UPLOAD,words(1,0,1)+b'abc'),
])
def test_retired_fragments_are_acknowledged_without_new_network_work(tls_server,kind,payload):
    origin,cert,requests=tls_server;channel=Channel();bridge=Bridge(channel,Policy((origin,),ca_file=cert))
    before=len(requests)
    try:
        channel.app(BEGIN,words(1,1,99,3,1000,10000,100,100))
        assert pump(bridge,channel)[0]==ERROR and bridge.id is None
        channel.app(kind,payload);bridge.step()
        assert not channel.incoming and not channel.outgoing and bridge.exchange is None and not bridge.closed
        assert len(requests)==before
    finally:bridge.close()


@pytest.mark.parametrize('kind,payload',[
    (CANCEL,words(0)),(CANCEL,words(2)),(CANCEL,words(1,0)),(CANCEL,b''),
    (URL,words(1,0)),(HEADERS,words(1,0)),(UPLOAD,words(1,0)),
    (UPLOAD,words(1,0,2)+b'a'),(UPLOAD,words(1,0,0)),
    (URL,words(1,0)+bytes(441)),(0x900,words(1)),
    (BEGIN,words(1,1,1,0,1000,10000,10,0)),
])
def test_invalid_or_foreign_retired_fragments_still_close_session(tls_server,kind,payload):
    origin,cert,requests=tls_server;channel=Channel();bridge=Bridge(channel,Policy((origin,),ca_file=cert))
    before=len(requests)
    try:
        channel.app(BEGIN,words(1,1,99,0,1000,10000,100,0));assert pump(bridge,channel)[0]==ERROR
        channel.app(kind,payload)
        with pytest.raises(ProtocolError):bridge.step()
        assert bridge.closed and bridge.exchange is None and len(requests)==before
    finally:bridge.close()


def test_old_fragment_is_protocol_error_for_new_active_request(tls_server):
    origin,cert,requests=tls_server;channel=Channel();bridge=Bridge(channel,Policy((origin,),ca_file=cert))
    before=len(requests)
    try:
        channel.app(BEGIN,words(1,1,99,0,1000,10000,100,0));assert pump(bridge,channel)[0]==ERROR
        channel.app(BEGIN,words(1,2,1,0,1000,10000,100,0));bridge.step();assert bridge.id==2
        channel.app(CANCEL,words(1));result=pump(bridge,channel,id=2)
        assert result[0]==ERROR and struct.unpack('<6I',result[1])[:3]==(2,2,0)
        assert len(requests)==before
    finally:bridge.close()
