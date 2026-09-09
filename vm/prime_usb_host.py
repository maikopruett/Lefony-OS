#!/usr/bin/env python3
"""Deterministic USB host for the Prime G2 ChipIdea device-mode model."""

from __future__ import annotations

import socket
import struct
import time
from pathlib import Path


class USBError(RuntimeError):
    pass


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
        deadline = time.monotonic() + timeout
        while True:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                self.socket.connect(str(path))
                break
            except OSError:
                self.socket.close()
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)
        self.stream = self.socket.makefile("rb")
        if self.command("HELLO") != "USBHOST 1":
            raise USBError("unsupported Prime USB host protocol")

    def close(self) -> None:
        self.stream.close()
        self.socket.close()

    def __enter__(self) -> "PrimeUSBHost":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def command(self, command: str, retry_nak: bool = False,
                timeout: float = 5.0, retry_interval: float = 0.005) -> str:
        if retry_interval < 0:
            raise ValueError("retry interval must not be negative")
        deadline = time.monotonic() + timeout
        while True:
            self.socket.sendall((command + "\n").encode())
            response = self.stream.readline()
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
        if not 0 <= maximum <= 512:
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
        if len(payload) > 512:
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

    def stage_capsule(self, capsule: bytes, crc32: int) -> None:
        if not 0x30 <= len(capsule) <= 8 * 1024 * 1024:
            raise ValueError("capsule length outside native recovery bounds")
        length = len(capsule)
        self.control_out(0x40, 0x44, length & 0xFFFF, length >> 16)
        for offset in range(0, length, 512):
            chunk = capsule[offset:offset + 512]
            self.control_out(0x40, 0x45, offset & 0xFFFF, offset >> 16,
                             chunk)
        self.control_out(0x40, 0x46, crc32 & 0xFFFF, crc32 >> 16)

    def update_status(self) -> tuple[int, ...]:
        payload = self.control_in(0xC0, 0x48, length=64)
        if len(payload) != 64:
            raise USBError(f"short A/B updater status: {len(payload)} bytes")
        values = struct.unpack("<16I", payload)
        if values[0] != 0x31554241:
            raise USBError(f"invalid A/B updater magic: 0x{values[0]:08x}")
        return values

    def install_signed_capsule(self, package: bytes) -> tuple[int, ...]:
        if len(package) < 512 + 0x30 or package[:4] != b"LFU1":
            raise ValueError("invalid signed update container")
        manifest = package[:320]
        payload = package[512:]
        self.control_out(0x40, 0x48, payload=manifest)
        status = self.update_status()
        if status[2] != 1:
            raise USBError(f"manifest rejected: {status}")
        self.stage_capsule(payload, ion_crc32(payload))
        status = self.update_status()
        if status[2] != 2:
            raise USBError(f"payload rejected: {status}")
        self.control_out(0x40, 0x49)
        return self.update_status()
