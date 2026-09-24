# SPDX-License-Identifier: GPL-3.0-or-later
"""Host boundary and uncertain-completion tests, without an attached calculator."""
from pathlib import Path
import struct
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sdk/tools'))
from channel_device import Client, ChannelError, ChannelEnded, decode_info


class Transport:
    def __init__(self):
        self.state=1;self.error=0;self.session=7;self.nonce=(0,0,0,0);self.label=b''
        self.app=b'channel-lab';self.signer=b'S'*32;self.hash=b'H'*32
        self.rx=1;self.rx_count=0;self.frames=[];self.writes=[];self.failure=None;self.raw=None

    def read(self,request,value=0,index=0,length=0):
        if request==0x78:
            if self.raw is not None:return self.raw
            return (struct.pack('<16I',320,1,self.state,self.session,self.error,1,self.rx,len(self.frames),self.rx_count,0,448,4,*self.nonce)
                    +self.app.ljust(52,b'\0')+b'Channel Lab'.ljust(84,b'\0')+self.hash+self.signer
                    +self.label.ljust(32,b'\0')+bytes(24))
        assert request==0x7b and value|(index<<16)==self.session and length==512
        return self.frames[0]

    def frame(self,sequence=1,kind=12,data=b'response'):
        return struct.pack('<16I',64+len(data),1,self.session,sequence,kind,len(data),*self.nonce,*([0]*6))+data

    def write(self,request,data=b'',value=0,index=0):
        assert request in (0x79,0x7a,0x7c,0x7d,0x7e) and not value and not index
        self.writes.append((request,data))
        failure,self.failure=self.failure,None
        if failure=='before':raise TimeoutError('before acceptance')
        if request==0x79:
            self.nonce=struct.unpack_from('<4I',data,16);self.label=data[32:].rstrip(b'\0');self.state=2
        elif request==0x7a:self.rx+=1;self.rx_count+=1
        elif request==0x7c:
            sequence=struct.unpack_from('<I',data,12)[0]
            if self.frames and struct.unpack_from('<I',self.frames[0],12)[0]==sequence:self.frames.pop(0)
        elif request==0x7e:self.state=4
        if failure=='after':raise TimeoutError('accepted, status lost')


def paired():
    transport=Transport();client=Client(transport,'channel-lab',b'S'*32,package_hash=b'H'*32)
    assert 0<=client.attach()<1000000
    assert not client.paired();transport.state=3;assert client.paired()
    return transport,client


@pytest.mark.parametrize('attribute,value',[('app',b'other'),('signer',b'X'*32),('hash',b'X'*32)])
def test_identity_mismatch_before_attach_writes(attribute,value):
    transport=Transport();setattr(transport,attribute,value)
    with pytest.raises(ChannelError,match='authorized identity'):
        Client(transport,'channel-lab',b'S'*32,package_hash=b'H'*32).attach()
    assert transport.writes==[]


@pytest.mark.parametrize('failure',['before','after'])
def test_attach_retry_retains_nonce_and_packet(failure):
    transport=Transport();client=Client(transport,'channel-lab',b'S'*32);transport.failure=failure
    with pytest.raises(TimeoutError):client.attach('Fixture')
    packet=client.attach_packet;client.retry_attach()
    assert transport.writes==[(0x79,packet),(0x79,packet)]
    assert not client.paired();client.close();assert transport.state==4 and client.binding is None


@pytest.mark.parametrize('failure',['before','after'])
def test_send_reconciles_lost_completion_without_duplicate_logical_packet(failure):
    transport,client=paired();transport.failure=failure
    with pytest.raises(TimeoutError):client.send(3,bytes(range(256)))
    packet=client.pending
    with pytest.raises(ChannelError,match='pending'):client.send(3,b'replacement')
    assert client.flush() and client.pending is None and client.send_sequence==2
    sent=[p for command,p in transport.writes if command==0x7a]
    assert sent==[packet]*(2 if failure=='before' else 1)
    assert transport.rx==2 and transport.rx_count==1


def test_queues_and_explicit_ack_with_uncertain_completion():
    transport,client=paired();transport.rx_count=4;count=len(transport.writes)
    assert not client.send(4,b'x') and client.pending is None and len(transport.writes)==count
    transport.rx_count=0;assert client.send(4,b'') and client.send(4,b'x'*448)
    transport.frames=[transport.frame(),transport.frame(2,data=b'next')]
    first=client.receive();assert first=={'sequence':1,'kind':12,'data':b'response'}
    assert client.receive()==first and len(transport.frames)==2
    transport.failure='after'
    with pytest.raises(TimeoutError):client.acknowledge()
    assert client.receive()==first and len(transport.frames)==1
    client.acknowledge();assert client.receive()['data']==b'next'
    client.acknowledge();assert client.receive() is None


@pytest.mark.parametrize('attribute,value',[('app',b'other'),('session',8),('nonce',(1,2,3,4)),('hash',b'X'*32),('signer',b'X'*32)])
def test_changed_session_never_writes_to_replacement_owner(attribute,value):
    transport,client=paired();setattr(transport,attribute,value);before=list(transport.writes)
    for operation in (lambda:client.send(1,b'x'),client.keepalive,client.receive,client.close):
        with pytest.raises(ChannelError,match='identity'):operation()
    assert transport.writes==before


@pytest.mark.parametrize('word,value',[(0,1),(1,2),(2,6),(7,5),(8,5),(9,449),(10,449),(11,8),(74,1)])
def test_invalid_status_is_rejected(word,value):
    transport=Transport();raw=bytearray(transport.read(0x78));struct.pack_into('<I',raw,word*4,value)
    with pytest.raises(ChannelError):decode_info(raw)


@pytest.mark.parametrize('word,value',[(0,65),(1,2),(2,8),(3,0),(4,0),(5,449),(6,0),(10,1)])
def test_malformed_frame_never_acknowledged(word,value):
    transport,client=paired();raw=bytearray(transport.frame());struct.pack_into('<I',raw,word*4,value)
    transport.frames=[raw];before=list(transport.writes)
    with pytest.raises(ChannelError):client.receive()
    assert transport.writes==before


@pytest.mark.parametrize('reason',[0,5,8,9,10,11])
def test_normal_end_requires_a_matching_terminal_status(reason):
    transport,client=paired()
    assert not client.ended()
    transport.state=4;transport.error=reason
    with pytest.raises(ChannelEnded) as result:client.receive()
    assert result.value.error==reason
    assert client.ended()==(reason in (0,8,10))
    transport.session+=1
    with pytest.raises(ChannelError,match='identity'):client.ended()


@pytest.mark.parametrize('pending',[False,True])
@pytest.mark.parametrize('outcome',['ended','cancelled','timeout','live','foreign','unreadable','protocol'])
@pytest.mark.parametrize('transport_kind',['model','physical'])
def test_companion_exit_race_never_replays_or_hides_unconfirmed_failure(monkeypatch,pending,outcome,transport_kind):
    import argparse
    import companion
    from https_bridge import Bridge,ProtocolError
    from emulator_usb import USBError as ModelError
    from usb_files import USBError as PhysicalError
    failure=(ProtocolError('bad peer frame') if outcome=='protocol' else
             (ModelError if transport_kind=='model' else PhysicalError)('status stalled'))
    class RacingTransport(Transport):
        failed=False
        def __enter__(self):return self
        def __exit__(self,*unused):pass
        def read(self,*args,**kwargs):
            if self.failed and outcome=='unreadable':raise OSError('disconnected socket')
            return super().read(*args,**kwargs)
        def write(self,request,**kwargs):
            if request==0x7d:
                self.writes.append((request,kwargs['data']));self.failed=True
                if outcome!='live':self.state=4
                self.error=9 if outcome=='timeout' else 10 if outcome=='cancelled' else 8
                if outcome=='foreign':self.hash=b'F'*32
                raise failure
            super().write(request,**kwargs)
            if request==0x79:self.state=3
    class RequestBridge(Bridge):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            if pending:self.id=1
    transport=RacingTransport();messages=[]
    monkeypatch.setattr(companion,'Bridge',RequestBridge)
    args=argparse.Namespace(app_id='channel-lab',signer=(b'S'*32).hex(),package_hash=(b'H'*32).hex(),
        label='Race fixture',allow_origin=['https://example.org'],method=['GET'],
        upload_limit=1024,response_limit=1024,timeout_ms=1000,ca_file=None)
    if not pending and outcome in ('ended','cancelled'):
        assert companion.run(args,transport_factory=lambda:transport,emit=messages.append)==0
        assert messages[-1].startswith('The app connection ended.')
    else:
        with pytest.raises(type(failure)) as caught:
            companion.run(args,transport_factory=lambda:transport,emit=messages.append)
        assert caught.value is failure
        assert not any(message.startswith('The app connection ended.') for message in messages)
    assert sum(request==0x7d for request,_ in transport.writes)==1
