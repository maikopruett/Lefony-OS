# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit app/signer/origin grant; narrow USB channel and one HTTPS bridge."""
import json
import signal
import threading
import time
from channel_device import Client,ChannelError,ChannelEnded
from emulator_usb import USBError as EmulatorUSBError
from https_bridge import Bridge
from https_worker import HTTPSError,Policy
from usb_files import LibUSB,USBError


class ChannelUSB(LibUSB):
    READ_REQUESTS=(0x78,0x7b)
    WRITE_REQUESTS=(0x79,0x7a,0x7c,0x7d,0x7e)


class ChannelEmulator:
    """Exclusive, already-enumerated QEMU USB endpoint; channel requests only.

    This opens a named local model socket, never discovers a physical device and
    never resets/enumerates the bus or grants installer/diagnostic authority.
    App identity, pairing and HTTPS policy are enforced by the ordinary client.
    """
    def __init__(self,path):
        from emulator_usb import PrimeUSBHost
        self.host=PrimeUSBHost(path,timeout=3)

    def read(self,request,value=0,index=0,length=64):
        if (request not in ChannelUSB.READ_REQUESTS or type(length) is not int or not 0<=length<=512
                or type(value) is not int or not 0<=value<=65535 or type(index) is not int or not 0<=index<=65535):
            raise USBError('Unsupported emulator app-channel read request')
        return self.host.control_in(0xc0,request,value,index,length)

    def write(self,request,data=b'',value=0,index=0):
        if (request not in ChannelUSB.WRITE_REQUESTS or not isinstance(data,bytes) or len(data)>512
                or type(value) is not int or not 0<=value<=65535 or type(index) is not int or not 0<=index<=65535):
            raise USBError('Unsupported emulator app-channel write request')
        self.host.control_out(0x40,request,value,index,data)

    def __enter__(self):return self
    def __exit__(self,*unused):self.host.close()


def console(message):
    # Consent and progress must be visible while a piped/GUI-launched companion
    # is still running; do not wait for the stdout buffer to fill or exit.
    print(message,flush=True)


def run_cli(args):
    """Finish the current bounded USB transaction before orderly Ctrl-C cleanup.

    Raising KeyboardInterrupt inside a model socket read can leave a partial
    control transfer, making the subsequent channel-close request ambiguous.
    The CLI records cancellation and observes it at transaction boundaries.
    """
    cancelled=threading.Event()
    previous=signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT,lambda *_:cancelled.set())
    try:return run(args,stopped=cancelled.is_set)
    finally:signal.signal(signal.SIGINT,previous)


def digest_argument(value):
    if len(value)!=64:raise ValueError('Expected a 64-digit SHA-256 identity')
    try:result=bytes.fromhex(value)
    except ValueError as exc:raise ValueError('Expected a hexadecimal SHA-256 identity') from exc
    if len(result)!=32:raise ValueError('Expected a 32-byte SHA-256 identity')
    return result


def run(args,*,transport_factory=None,emit=console,stopped=lambda:False):
    # Validate configuration before looking for a calculator. Nothing here uses
    # installer/device management APIs or accepts a file/firmware operation.
    signer=digest_argument(args.signer)
    payload=digest_argument(args.package_hash) if args.package_hash else None
    Client(None,args.app_id,signer,package_hash=payload)
    if not isinstance(args.label,str) or not 1<=len(args.label)<=31 or not all(32<=ord(c)<=126 for c in args.label):
        raise HTTPSError('Host label must be 1–31 printable ASCII characters')
    policy=Policy(tuple(args.allow_origin),tuple(args.method),args.upload_limit,args.response_limit,
                  args.timeout_ms,str(args.ca_file.resolve()) if args.ca_file else None)
    # Use every configured origin/method in validation, even for an idle app.
    for origin in policy.origins:
        for method in policy.methods:policy.validate(origin,method,(),0,0,policy.timeout_ms)
    if not policy.origins or not policy.methods:raise HTTPSError('Grant at least one origin and method')
    if transport_factory is None:
        path=getattr(args,'emulator_usb',None)
        transport_factory=(lambda:ChannelEmulator(path)) if path is not None else ChannelUSB
    if stopped():return 0
    with transport_factory() as transport:
        client=Client(transport,args.app_id,signer,package_hash=payload);bridge=None
        emit(f'Allowed app: {args.app_id}; signer: {args.signer}')
        emit('Allowed HTTPS origins: '+', '.join(policy.origins)+'; methods: '+', '.join(policy.methods))
        try:
            deadline=time.monotonic()+30
            if stopped():return 0
            emit('Open the app connection screen on the calculator. Ctrl-C stops this companion.')
            while client.status()['state']!=1:
                if stopped():return 0
                if time.monotonic()>=deadline:raise ChannelError('No app opened a channel within 30 seconds')
                time.sleep(.02)
            if stopped():return 0
            code=client.attach(args.label)
            if stopped():return 0
            emit(f'Compare code {code:06d}, then press OK on the calculator to allow this session.')
            while not client.paired():
                if stopped():return 0
                if time.monotonic()>=deadline:raise ChannelError('Calculator confirmation timed out')
                time.sleep(.02)
            if stopped():return 0
            def progress(event):
                # Only request IDs, phases, categories and counts; no URL query,
                # headers, bodies or device information enters the progress log.
                if event['phase']!='upload':emit(json.dumps(event,sort_keys=True))
            bridge=Bridge(client,policy,progress=progress);emit('Connected. The app may use the granted HTTPS origins until this session ends.')
            while not stopped():
                try:bridge.step()
                except (ChannelError,USBError,EmulatorUSBError,OSError) as error:
                    # The app can leave between a bound status read and a USB
                    # keepalive. Confirm that this exact peer closed normally;
                    # never replay the failed operation or infer closure from
                    # a transport error, changed identity or malformed status.
                    ended=isinstance(error,ChannelEnded) and error.normal
                    if bridge.id is None and not isinstance(error,ChannelError):
                        try:ended=client.ended()
                        except (ChannelError,USBError,EmulatorUSBError,OSError):pass
                    if bridge.id is None and ended:
                        emit('The app connection ended. Open a new session to reconnect.');return 0
                    raise
                time.sleep(.002)
            return 0
        except KeyboardInterrupt:return 0
        finally:
            if bridge is not None:bridge.close()
            try:client.close()
            except (ChannelError,RuntimeError,OSError):pass
