#!/usr/bin/env python3
"""End-to-end signed A/B update, confirmation, and rollback in Prime G2 VM."""

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import tempfile
import time
from pathlib import Path

from prime_usb_host import PrimeUSBHost, USBError

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import prime_g2_update_capsule as update_capsule

NO_SLOT = 0xFFFFFFFF


def wait_for_text(path: Path, text: str, count: int = 1,
                  timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and path.read_text(errors="replace").count(text) >= count:
            return
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {text!r} x{count} in {path}")


def connect_ready(path: Path, timeout: float = 45.0) -> PrimeUSBHost:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        host: PrimeUSBHost | None = None
        try:
            host = PrimeUSBHost(path, timeout=2.0)
            host.connect_and_enumerate()
            return host
        except (OSError, USBError) as error:
            last_error = error
            if host is not None:
                host.close()
            time.sleep(0.2)
    raise AssertionError(f"USB did not return after reboot: {last_error}")


def qmp_reset(path: Path) -> None:
    if path.is_symlink():
        path = path.resolve()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(str(path))
        stream = connection.makefile("rwb", buffering=0)
        json.loads(stream.readline())
        stream.write(b'{"execute":"qmp_capabilities"}\n')
        while "return" not in json.loads(stream.readline()):
            pass
        stream.write(b'{"execute":"system_reset"}\n')
        while True:
            message = json.loads(stream.readline())
            if message.get("event") == "RESET" or "return" in message:
                return


def hanging_capsule(length: int = 4096) -> bytes:
    image = bytearray(length)
    struct.pack_into("<I", image, 0, 0xEAFFFFFE)  # ARM: b .
    struct.pack_into("<I", image, 0x24, 0x016F2818)
    struct.pack_into("<I", image, 0x2C, length)
    return bytes(image)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--qmp", type=Path, required=True)
    parser.add_argument("--uart", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    args = parser.parse_args()

    wait_for_text(args.uart, "Lefony A/B: factory slot A verified; booting")
    wait_for_text(args.uart, "Lefony OS: control ready")
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        success_package = temporary / "lefony-1.0.1.lfu"
        update_capsule.build(args.payload, success_package, (1, 0, 1, 0),
                             args.private_key)

        host = connect_ready(args.socket)
        initial = host.update_status()
        assert initial[4:8] == (0, NO_SLOT, 0, 3), initial
        assert initial[14] == 1, initial
        installed = host.install_signed_capsule(success_package.read_bytes())
        assert installed[2] == 4 and installed[4:8] == (0, 1, 0, 3), installed
        host.control_out(0x40, 0x4B)
        host.close()

        wait_for_text(args.uart, "Lefony A/B: pending slot B attempt 1/3")
        wait_for_text(args.uart, "Lefony OS: control ready", count=2)
        host = connect_ready(args.socket)
        confirmed = host.update_status()
        assert confirmed[4:8] == (1, NO_SLOT, 0, 3), confirmed
        assert confirmed[8:12] == (1, 0, 1, 0), confirmed
        assert confirmed[14] == 4, confirmed

        # Install a correctly signed and hashed capsule that passes U-Boot's
        # structural checks but never reaches runtime confirmation.
        hang_payload = temporary / "hang.zImage"
        hang_package = temporary / "hang-1.0.2.lfu"
        hang_payload.write_bytes(hanging_capsule())
        update_capsule.build(hang_payload, hang_package, (1, 0, 2, 0),
                             args.private_key)
        failed = host.install_signed_capsule(hang_package.read_bytes())
        assert failed[4:8] == (1, 0, 0, 3), failed
        host.close()
        # Model the first failed-start power cycle explicitly. The successful
        # path above already proves the device-requested software reboot.
        qmp_reset(args.qmp)

        wait_for_text(args.uart, "Lefony A/B: pending slot A attempt 1/3")
        qmp_reset(args.qmp)
        wait_for_text(args.uart, "Lefony A/B: pending slot A attempt 2/3")
        qmp_reset(args.qmp)
        wait_for_text(args.uart, "Lefony A/B: pending slot A attempt 3/3")
        qmp_reset(args.qmp)
        wait_for_text(args.uart,
                      "Lefony A/B: rolling back pending slot (boot limit reached)")
        wait_for_text(args.uart, "Lefony OS: control ready", count=3)

        host = connect_ready(args.socket)
        rolled_back = host.update_status()
        host.close()
        assert rolled_back[4:8] == (1, NO_SLOT, 0, 3), rolled_back
        assert rolled_back[8:12] == (1, 0, 1, 0), rolled_back
        assert rolled_back[14] == 9, rolled_back

    print("PASS: factory seed, full signed USB update, pending boot, runtime "
          "confirmation, failed-start boot limit, and automatic rollback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
