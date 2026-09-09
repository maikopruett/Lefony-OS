#!/usr/bin/env python3
"""Enumerate the native guest and exercise EP0 recovery over modeled USB."""

from __future__ import annotations

import argparse
import struct
import sys
import tempfile
from pathlib import Path
from prime_usb_host import PrimeUSBHost, USBError, ion_crc32

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import prime_g2_update_capsule as update_capsule


def make_capsule(length: int = 0x180) -> bytes:
    image = bytearray((i * 37 + 11) & 0xFF for i in range(length))
    struct.pack_into("<I", image, 0x24, 0x016F2818)
    struct.pack_into("<I", image, 0x2C, length)
    return bytes(image)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    args = parser.parse_args()
    with PrimeUSBHost(args.socket) as host:
        device, configuration = host.connect_and_enumerate()
        assert device == bytes.fromhex(
            "1201000200000040feca5250000101020301")
        assert configuration == bytes.fromhex(
            "0902120001010080190904000000ff4d4700")

        # Standard requests, suspend/resume, and malformed bus traffic.
        assert host.control_in(0x80, 8, length=1) == b"\x01"
        assert host.command("SUSPEND") == "OK"
        assert "suspended=1" in host.command("STATUS")
        assert host.command("RESUME") == "OK"
        assert host.command("SETUP 00") == "ERR setup"
        assert host.command("OUT deadbeef") == "NAK"

        capsule = make_capsule()
        crc = ion_crc32(capsule)
        host.stage_capsule(capsule, crc)
        recovery = host.control_in(0xC0, 0x43, length=32)
        magic, version, state, capacity, declared, received, actual_crc, chunk = \
            struct.unpack("<8I", recovery)
        assert (magic, version, state) == (0x4D475243, 1, 2)
        assert capacity == 8 * 1024 * 1024
        assert (declared, received, actual_crc, chunk) == \
            (len(capsule), len(capsule), crc, 512)

        # The signed path authenticates a model/version/digest manifest, writes
        # the capsule to inactive slot B through modeled GPMI/BCH, reads it back,
        # and atomically commits pending metadata.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "lefony.zImage"
            package = root / "lefony.lfu"
            payload.write_bytes(make_capsule(4096))
            update_capsule.build(
                payload, package, (1, 0, 1, 0),
                REPO / "tests/fixtures/prime_g2_emulator_update_private.pem",
            )
            signed = package.read_bytes()
            forged = bytearray(signed[:320])
            forged[64] ^= 1
            host.control_out(0x40, 0x48, payload=bytes(forged))
            rejected = host.update_status()
            assert (rejected[2], rejected[3]) == (6, 5), rejected
            update = host.install_signed_capsule(signed)
        assert update[2] == 4, update
        assert update[4:8] == (0, 1, 0, 3), update
        # The current runtime advertises direct-install capability in bit 8
        # in addition to the authenticated/verified/pending status bits.
        assert update[12:16] == (4096, 4096, 1, 7 | (1 << 8)), update
        # A disconnect must revoke configured state, and reconnect must repeat
        # address-zero enumeration rather than inheriting stale endpoint state.
        assert host.command("DISCONNECT") == "OK"
        assert "connected=0" in host.command("STATUS")
        device2, configuration2 = host.connect_and_enumerate(address=7)
        assert (device2, configuration2) == (device, configuration)
        assert "address=7" in host.command("STATUS")
    print("PASS: native USB enumeration, signed inactive-slot NAND install/readback/pending commit, reconnect, and recovery staging")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except USBError as error:
        raise SystemExit(f"FAIL: {error}")
