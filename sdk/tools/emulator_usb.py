#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic QEMU USB transport. No physical USB discovery or firmware APIs."""

from __future__ import annotations

import struct
import time
from contextlib import contextmanager
from pathlib import Path
from local_transport import connect


class USBError(RuntimeError):
    pass


class ManagementUSB:
    """Exclusive model connection restricted to the selected app command family.

    The caller supplies its physical transport's request allowlist. There is no
    discovery, reset, enumeration, physical fallback or firmware-write path.
    """
    def __init__(self, path, policy):
        self.read_requests = tuple(policy.READ_REQUESTS)
        self.write_requests = tuple(policy.WRITE_REQUESTS)
        if any(not 0x60 <= request <= 0x96 for request in (*self.read_requests, *self.write_requests)):
            raise ValueError('Not an SDK app-management request family')
        self.host = PrimeUSBHost(path, timeout=3)

    def read(self, request, value=0, index=0, length=64):
        if (type(request) is not int or request not in self.read_requests or
                type(length) is not int or not 0 <= length <= 512 or
                type(value) is not int or not 0 <= value <= 65535 or
                type(index) is not int or not 0 <= index <= 65535):
            raise USBError('Unsupported emulator app-management read request')
        return self.host.control_in(0xc0, request, value, index, length)

    def write(self, request, data=b'', value=0, index=0):
        if (type(request) is not int or request not in self.write_requests or
                not isinstance(data, bytes) or len(data) > 512 or
                type(value) is not int or not 0 <= value <= 65535 or
                type(index) is not int or not 0 <= index <= 65535):
            raise USBError('Unsupported emulator app-management write request')
        self.host.control_out(0x40, request, value, index, data)

    def bulk_upload(self,target,data,**kwargs):
        from bulk_transfer import available, upload, download
        if (target==2 and 0x64 not in self.write_requests or
                target==3 and 0x72 not in self.write_requests or
                target==4 and 0x72 not in self.read_requests or target==5 and 0x6a not in self.read_requests or target not in (2,3,4,5)):
            raise USBError('Bulk target outside app transport policy')
        if not available(self.host.control_in(0x80,6,0x200,0,32)):return None if target>=4 else False
        def read(request,value=0,index=0,length=64):
            return self.host.control_in(0xc0,request,value,index,length)
        def write(request,data=b'',value=0,index=0):
            return self.host.control_out(0x40,request,value,index,data)
        def send(block):
            for offset in range(0,len(block),16384):
                self.host.endpoint_out(1,block[offset:offset+16384])
        def receive(length):
            return b''.join(self.host.endpoint_in(1,min(16384,length-offset)) for offset in range(0,length,16384))
        return download(read,write,receive,target,data,**kwargs) if target>=4 else upload(read,write,send,target,data,**kwargs)

    def bulk_download(self,target,length,**kwargs):
        if target not in (4,5):raise USBError('Unsupported bulk download target')
        return self.bulk_upload(target,length,**kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.host.close()


def ion_crc32(payload: bytes) -> int:
    """Match Ion::crc32Byte's MSB-first, reversed-word traversal."""
    crc = 0xFFFFFFFF
    complete = len(payload) // 4 * 4
    ordered = bytearray()
    for offset in range(0, complete, 4):
        ordered.extend(reversed(payload[offset:offset + 4]))
    ordered.extend(payload[complete:])
    for byte in ordered:
        crc ^= byte << 24
        for _ in range(8):
            crc = (((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF
                   if crc & 0x80000000 else (crc << 1) & 0xFFFFFFFF)
    return crc


class PrimeUSBHost:
    def __init__(self, path: str | Path, timeout: float = 10.0):
        path = Path(path)
        # Artifact directories can exceed macOS' AF_UNIX sockaddr limit. The
        # VM runner exposes a descriptive symlink to its short private socket.
        if path.is_symlink():
            path = path.resolve()
        self.path, self.timeout = path, timeout
        self.socket = connect(path, timeout=timeout, io_timeout=timeout)
        self.stream = self.socket.makefile("rb")
        try:
            if self.command("HELLO") != "USBHOST 1":
                raise USBError("unsupported Prime USB host protocol")
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        self.stream.close()
        self.socket.close()

    def __enter__(self) -> "PrimeUSBHost":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def lend_connection(self):
        """Lend the exclusive model socket, then restore this host connection.

        The borrower must close before returning. Neither handoff resets or
        enumerates USB. Existing clients referencing this object remain valid.
        This is only a local QEMU socket, never a physical-device operation.
        """
        self.close()
        try:
            yield self.path
        finally:
            replacement = PrimeUSBHost(self.path, timeout=self.timeout)
            self.socket, self.stream = replacement.socket, replacement.stream

    def command(self, command: str, retry_nak: bool = False,
                timeout: float = 5.0, retry_interval: float = 0.0001) -> str:
        # This is a local modeled endpoint, not physical USB. A 5 ms host
        # sleep misses the guest's short active-poll window on every EP0 phase.
        # Retry only explicit NAKs; deadlines and all terminal errors are intact.
        if retry_interval < 0:
            raise ValueError("retry interval must not be negative")
        deadline = time.monotonic() + timeout
        while True:
            self.socket.sendall((command + "\n").encode())
            response = self.stream.readline(65536)
            if response and not response.endswith(b"\n"):
                raise USBError("Oversized or incomplete USB model response")
            if not response:
                raise USBError("USB host socket closed")
            text = response.decode(errors="replace").strip()
            if text != "NAK" or not retry_nak:
                return text
            if time.monotonic() >= deadline:
                raise USBError(f"timed out waiting for {command}")
            time.sleep(retry_interval)

    @staticmethod
    def setup(request_type: int, request: int, value: int = 0,
              index: int = 0, length: int = 0) -> str:
        return struct.pack("<BBHHH", request_type, request, value,
                           index, length).hex()

    def setup_packet(self, request_type: int, request: int, value: int = 0,
                     index: int = 0, length: int = 0) -> None:
        packet = self.setup(request_type, request, value, index, length)
        response = self.command("SETUP " + packet)
        if response != "OK":
            raise USBError(f"setup {packet} rejected: {response}")

    def in_packet(self, maximum: int) -> bytes:
        response = self.command(f"IN {maximum}", retry_nak=True, timeout=30.0)
        if not response.startswith("DATA"):
            raise USBError(f"IN failed: {response}")
        payload = response[4:].strip()
        return bytes.fromhex(payload) if payload else b""

    def out_packet(self, payload: bytes) -> None:
        encoded = payload.hex() if payload else "-"
        # Full A/B capsules keep the bare-metal runtime busy with cache
        # maintenance and NAND-sized staging buffers. Give an individual EP0
        # packet enough time to drain under an instrumented QEMU build.
        response = self.command("OUT " + encoded, retry_nak=True, timeout=30.0)
        if response != "OK":
            raise USBError(f"OUT failed: {response}")

    def endpoint_in(self, endpoint: int, maximum: int = 64,
                    timeout: float = 30.0) -> bytes:
        if not 1 <= endpoint < 8:
            raise ValueError("data endpoint must be between 1 and 7")
        if not 0 <= maximum <= 16384:
            raise ValueError("endpoint transfer exceeds emulator limit")
        response = self.command(f"EPIN {endpoint} {maximum}",
                                retry_nak=True, timeout=timeout)
        if not response.startswith("DATA"):
            raise USBError(f"endpoint {endpoint} IN failed: {response}")
        payload = response[4:].strip()
        return bytes.fromhex(payload) if payload else b""

    def endpoint_out(self, endpoint: int, payload: bytes,
                     timeout: float = 30.0) -> None:
        if not 1 <= endpoint < 8:
            raise ValueError("data endpoint must be between 1 and 7")
        if len(payload) > 16384:
            raise ValueError("endpoint transfer exceeds emulator limit")
        encoded = payload.hex() if payload else "-"
        response = self.command(f"EPOUT {endpoint} {encoded}",
                                retry_nak=True, timeout=timeout,
                                retry_interval=0.0001)
        if response != "OK":
            raise USBError(f"endpoint {endpoint} OUT failed: {response}")

    def control_in(self, request_type: int, request: int, value: int = 0,
                   index: int = 0, length: int = 0) -> bytes:
        self.setup_packet(request_type, request, value, index, length)
        data = self.in_packet(length)
        self.out_packet(b"")
        return data

    def control_out(self, request_type: int, request: int, value: int = 0,
                    index: int = 0, payload: bytes = b"") -> None:
        self.setup_packet(request_type, request, value, index, len(payload))
        if payload:
            self.out_packet(payload)
        self.in_packet(0)

    def connect_and_enumerate(self, address: int = 5,
                              controller_timeout: float = 10.0
                              ) -> tuple[bytes, bytes]:
        if controller_timeout <= 0:
            raise ValueError("controller timeout must be positive")
        if self.command("CONNECT") != "OK":
            raise USBError("CONNECT failed")
        deadline = time.monotonic() + controller_timeout
        while "run=1" not in self.command("STATUS"):
            if time.monotonic() >= deadline:
                raise USBError("native USB controller did not start")
            time.sleep(0.01)
        if self.command("RESET") != "OK":
            raise USBError("RESET failed")
        # A real host waits for reset recovery. Here the status transition also
        # proves that the native driver's poll loop rebuilt its EP0 queue heads
        # before the first setup packet can race that initialization.
        deadline = time.monotonic() + 2.0
        while "sts=00000000" not in self.command("STATUS"):
            if time.monotonic() >= deadline:
                raise USBError("native USB reset recovery timed out")
            time.sleep(0.005)
        # USB 2.0 requires reset recovery before the first setup transaction.
        # The status bit can clear just before stock firmware has rebuilt its
        # EP0 queue heads, so preserve that small host-side recovery interval.
        time.sleep(0.020)
        device = self.control_in(0x80, 6, 1 << 8, length=18)
        self.control_out(0x00, 5, address)
        configuration = self.control_in(0x80, 6, 2 << 8, length=18)
        self.control_out(0x00, 9, 1)
        return device, configuration
