#!/usr/bin/env python3
"""Private-emulator probe for HP Prime G2's stock update HID stream.

This module contains only the transport framing reconstructed from HP's
Connectivity Kit.  It never contains, downloads, or modifies HP firmware.
The command-line probe accepts only the emulator's Unix-domain USB socket, so
it cannot write to a physical calculator by accident.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path
from typing import Iterator

from prime_usb_host import PrimeUSBHost


REPORT_BYTES = 64
REPORT_HEADER_BYTES = 6
REPORT_PAYLOAD_BYTES = REPORT_BYTES - REPORT_HEADER_BYTES
CRC_INITIAL = 0x1234
CRC_POLYNOMIAL = 0x1021


def stock_crc16(payload: bytes, initial: int = CRC_INITIAL) -> int:
    """Return the MSB-first CRC-16 used by the stock update reports."""
    crc = initial
    for byte in payload:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ CRC_POLYNOMIAL) & 0xFFFF \
                if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def stock_update_report(offset: int, payload: bytes,
                        report_bytes: int = REPORT_BYTES) -> bytes:
    """Build report ID 0: little-endian offset, CRC, data, and zero padding."""
    if not 0 <= offset <= 0xFFFFFFFF:
        raise ValueError("stock update offset is outside uint32 range")
    if report_bytes < REPORT_HEADER_BYTES:
        raise ValueError("stock update report is too short")
    if len(payload) > report_bytes - REPORT_HEADER_BYTES:
        raise ValueError("stock update payload exceeds one HID report")

    report = bytearray(report_bytes)
    struct.pack_into("<I", report, 0, offset)
    report[REPORT_HEADER_BYTES:REPORT_HEADER_BYTES + len(payload)] = payload
    struct.pack_into("<H", report, 4, stock_crc16(report))
    return bytes(report)


def iter_stock_update_reports(image: bytes) -> Iterator[tuple[int, bytes]]:
    """Yield every fixed-size report in the first stock upload phase."""
    for offset in range(0, len(image), REPORT_PAYLOAD_BYTES):
        yield offset, stock_update_report(
            offset, image[offset:offset + REPORT_PAYLOAD_BYTES]
        )


def stock_next_offset(response: bytes) -> int:
    """Decode the optional four-byte resynchronization response."""
    if len(response) < 4:
        raise ValueError("stock update response has no next-offset word")
    return struct.unpack_from("<I", response)[0]


def flip_package_byte(package: bytes, offset: int) -> bytes:
    """Return an in-memory one-bit mutation for emulator rejection tests."""
    if not 0 <= offset < len(package):
        raise ValueError("stock update mutation offset is outside the package")
    mutated = bytearray(package)
    mutated[offset] ^= 1
    return bytes(mutated)


def probe(socket_path: Path, package_path: Path, report_count: int,
          pause_before_final: bool = False,
          flip_byte: int | None = None) -> None:
    if report_count < 1:
        raise ValueError("report count must be positive")
    package = package_path.read_bytes()
    if not package:
        raise ValueError("stock update package is empty")
    if flip_byte is not None:
        package = flip_package_byte(package, flip_byte)
        print(f"research_mutation=flip-bit offset={flip_byte}")

    with PrimeUSBHost(socket_path) as host:
        # HP's maintenance image performs display, storage, and RTOS startup
        # before its native ChipIdea device task runs.  That authentic path is
        # intentionally slower than Lefony's minimal runtime USB service.
        device, configuration = host.connect_and_enumerate(
            controller_timeout=30.0
        )
        report_descriptor = host.control_in(0x81, 6, 0x2200, 0, 35)
        host.control_out(0x21, 10, 0, 0)  # HID SET_IDLE
        print(f"device={device.hex()}")
        print(f"configuration={configuration.hex()}")
        print(f"hid_report={report_descriptor.hex()}")

        total_reports = (len(package) + REPORT_PAYLOAD_BYTES - 1) // REPORT_PAYLOAD_BYTES
        send_limit = min(report_count, total_reports)
        sent = 0
        for offset, report in iter_stock_update_reports(package):
            if pause_before_final and sent + 1 == total_reports:
                input(
                    "paused before final report; enable the desired VM trace "
                    "and press Enter to continue: "
                )
            host.endpoint_out(2, report)
            sent += 1
            if send_limit <= 16 or sent == send_limit or sent % 4096 == 0:
                print(
                    f"sent report={sent}/{send_limit} offset={offset} "
                    f"crc=0x{report[5]:02x}{report[4]:02x}"
                )
            if sent >= send_limit:
                break

        # A valid report is copied into the package buffer without an endpoint
        # 1 response. The updater sends a four-byte resynchronization value on
        # an error and a completion response only after the whole declared
        # container has arrived. Waiting after every OUT report therefore
        # deadlocks a valid stream after its first packet.
        if sent == total_reports:
            response = host.endpoint_in(1, REPORT_BYTES)
            print(f"response={response.hex()}")
            if len(response) >= 4:
                print(f"next_offset={stock_next_offset(response)}")
        else:
            print(
                f"partial_stream={sent}/{total_reports}; "
                "no completion response expected"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe stock HP update framing inside the private VM"
    )
    parser.add_argument("--socket", required=True, type=Path,
                        help="prime-g2-usbotg Unix socket from a VM run")
    parser.add_argument("--package", "--image", dest="package", required=True,
                        type=Path,
                        help="locally supplied authentic HP update container")
    parser.add_argument("--reports", type=int, default=1,
                        help="number of 64-byte reports to send (default: 1)")
    parser.add_argument(
        "--pause-before-final", action="store_true",
        help="keep the emulator connection open before sending the last report",
    )
    parser.add_argument(
        "--flip-byte", type=lambda value: int(value, 0),
        help=("flip one bit at a package offset in memory to test device-side "
              "rejection; emulator socket only"),
    )
    args = parser.parse_args()
    probe(args.socket, args.package, args.reports, args.pause_before_final,
          args.flip_byte)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
