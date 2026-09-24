# SPDX-License-Identifier: GPL-3.0-or-later
"""The explicit model companion has the same narrow USB authority as physical."""
import argparse
from pathlib import Path
import socket
import signal
import struct
import sys
import threading

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sdk/tools'))
import companion
from companion import ChannelEmulator,ChannelUSB,run
from usb_files import USBError
from local_transport import session_directory
from emulator_usb import PrimeUSBHost


@pytest.fixture
def socket_folder():
    with session_directory() as directory:yield Path(directory)


def test_model_adapter_rejects_management_requests_and_oversized_payloads():
    transport=ChannelEmulator.__new__(ChannelEmulator)
    for request in range(256):
        if request not in ChannelUSB.READ_REQUESTS:
            with pytest.raises(USBError):transport.read(request)
        if request not in ChannelUSB.WRITE_REQUESTS:
            with pytest.raises(USBError):transport.write(request)
    for length in (-1,513,True):
        with pytest.raises(USBError):transport.read(0x78,length=length)
    for data in (b'x'*513,'text'):
        with pytest.raises(USBError):transport.write(0x79,data=data)
    for value in (-1,65536,True):
        with pytest.raises(USBError):transport.read(0x78,value=value)
        with pytest.raises(USBError):transport.write(0x79,index=value)


def test_model_endpoint_uses_usb_phases_without_bus_reset_or_device_discovery(socket_folder,monkeypatch):
    if sys.platform=='win32':pytest.skip('Native Windows AF_UNIX server fixture is separately qualified')
    path=socket_folder/'usb';received=[];errors=[]
    listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);listener.bind(str(path));listener.listen();listener.settimeout(5)
    expected=['HELLO','SETUP '+struct.pack('<BBHHH',0xc0,0x78,2,3,4).hex(),
              'IN 4','OUT -','SETUP '+struct.pack('<BBHHH',0x40,0x79,0,0,3).hex(),'OUT 616263','IN 0']
    responses=['USBHOST 1','OK','DATA 01020304','OK','OK','OK','DATA']
    def server():
        try:
            connection,_=listener.accept()
            with connection,connection.makefile('rwb',buffering=0) as stream:
                for response in responses:
                    received.append(stream.readline().decode().strip());stream.write((response+'\n').encode())
                assert stream.readline()==b''
        except BaseException as error:errors.append(error)
    thread=threading.Thread(target=server,daemon=True);thread.start()
    monkeypatch.setattr(companion,'ChannelUSB',type('NoDeviceDiscovery',(),{
        'READ_REQUESTS':ChannelUSB.READ_REQUESTS,'WRITE_REQUESTS':ChannelUSB.WRITE_REQUESTS,
        '__init__':lambda self:pytest.fail('Physical USB discovery in emulator adapter')}))
    try:
        with ChannelEmulator(path) as transport:
            assert transport.read(0x78,value=2,index=3,length=4)==b'\1\2\3\4'
            transport.write(0x79,data=b'abc')
        thread.join(5);assert not thread.is_alive() and not errors and received==expected
    finally:listener.close()


def options(**kwargs):
    return argparse.Namespace(**({'app_id':'fixture','signer':'12'*32,'package_hash':None,
        'label':'Test companion','allow_origin':['https://example.org'],'method':['GET'],
        'upload_limit':1024,'response_limit':1024,'timeout_ms':1000,'ca_file':None,
        'emulator_usb':Path('/missing-model-socket')}|kwargs))


def test_explicit_model_connection_never_falls_back_to_physical(monkeypatch):
    calls=[]
    def model(path):calls.append(path);raise RuntimeError('Model socket unavailable')
    monkeypatch.setattr(companion,'ChannelEmulator',model)
    monkeypatch.setattr(companion,'ChannelUSB',lambda:pytest.fail('Physical fallback'))
    with pytest.raises(RuntimeError,match='Model socket unavailable'):run(options())
    assert calls==[Path('/missing-model-socket')]


def test_lending_model_socket_restores_the_existing_host_object(socket_folder):
    if sys.platform=='win32':pytest.skip('Native Windows AF_UNIX server fixture is separately qualified')
    path=socket_folder/'usb';commands=[];errors=[]
    listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);listener.bind(str(path));listener.listen();listener.settimeout(5)
    def server():
        try:
            for count in (1,1,2):
                connection,_=listener.accept()
                with connection,connection.makefile('rwb',buffering=0) as stream:
                    for _ in range(count):
                        command=stream.readline();commands.append(command);stream.write(b'USBHOST 1\n')
                    assert stream.readline()==b''
        except BaseException as error:errors.append(error)
    thread=threading.Thread(target=server,daemon=True);thread.start()
    try:
        with PrimeUSBHost(path) as host:
            with host.lend_connection() as lent:
                with PrimeUSBHost(lent):pass
            assert host.command('HELLO')=='USBHOST 1'
        thread.join(5);assert not thread.is_alive() and not errors and commands==[b'HELLO\n']*4
    finally:listener.close()


def test_invalid_grant_is_rejected_before_opening_either_transport(monkeypatch):
    monkeypatch.setattr(companion,'ChannelEmulator',lambda path:pytest.fail('Model opened before validation'))
    monkeypatch.setattr(companion,'ChannelUSB',lambda:pytest.fail('Device opened before validation'))
    for origin in ('http://example.org','https://example.org/private'):
        with pytest.raises(ValueError):run(options(allow_origin=[origin]))


@pytest.mark.parametrize('phase',['status','attach','paired'])
def test_cli_interrupt_finishes_current_transaction_before_closing(monkeypatch,phase):
    events=[];previous=signal.getsignal(signal.SIGINT)
    def transaction(name):
        events.append(name+'-start')
        if phase==name:signal.raise_signal(signal.SIGINT)
        events.append(name+'-finished')
    class Transport:
        def __enter__(self):return self
        def __exit__(self,*unused):events.append('transport-closed')
    class Client:
        def __init__(self,*unused,**kwargs):pass
        def status(self):transaction('status');return {'state':1}
        def attach(self,label):transaction('attach');return 123456
        def paired(self):transaction('paired');return True
        def close(self):events.append('channel-closed')
    monkeypatch.setattr(companion,'Client',Client)
    monkeypatch.setattr(companion,'ChannelUSB',Transport)
    monkeypatch.setattr(companion,'Bridge',lambda *a,**k:pytest.fail('Bridge opened after cancellation'))
    assert companion.run_cli(options(emulator_usb=None))==0
    assert events[-3:]==[phase+'-finished','channel-closed','transport-closed']
    assert signal.getsignal(signal.SIGINT) is previous
