#!/usr/bin/env python3
"""Boot the physical candidate in QEMU and qualify RAM-only USB staging.

No update execution or NAND writes: this test does not qualify physical USB.
Set PRIME_G2_CURRENT_CAPSULE to the candidate to test.
"""
from pathlib import Path
import runpy
import struct
import subprocess
import tempfile
import time
import socket

from prime_usb_host import PrimeUSBHost, ion_crc32


def main():
    boot = runpy.run_path(str(Path(__file__).with_name("test-prime-g2-nand-rom-boot.py")))
    directory = Path(tempfile.mkdtemp(prefix="lfusb-", dir="/tmp"))
    overlay = boot["capsule_overlay"](directory)
    initial_overlay = overlay.read_bytes()
    uart = directory / "uart.log"
    usb = directory / "usb.sock"
    qmp_path = directory / "qmp.sock"
    process = subprocess.Popen(boot["command"](overlay, usb_path=usb,
                               serial=f"file:{uart}", qmp_path=qmp_path),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if uart.exists() and "entering calculator runtime" in uart.read_text(errors="replace"):
                break
            if process.poll() is not None:
                raise AssertionError("guest exited before runtime")
            time.sleep(0.05)
        else:
            raise AssertionError("guest did not reach runtime")
        with PrimeUSBHost(usb) as host:
            descriptor, config = host.connect_and_enumerate()
            assert descriptor[8:12] == bytes.fromhex("feca5250")
            assert config[5] == 1
            capabilities = struct.unpack("<4I", host.control_in(0xC0, 0x4E, length=16))
            assert capabilities == (0x3156444c, 1, 3, 8 << 20), capabilities
            host.control_out(0x40, 0x50, 0x4e50)
            nand_report = struct.unpack("<18I", host.control_in(0xC0, 0x50, length=72))
            assert nand_report[:2] == (0x31504e4c, 1), nand_report
            assert nand_report[2:4] == (0, 3), nand_report
            assert nand_report[4] & 0xff not in (0, 0xff), nand_report
            print("Physical NAND probe in emulator:", nand_report, flush=True)
            reference = boot["CURRENT_CAPSULE"].read_bytes()
            for index in range((len(reference) + 2047) // 2048):
                if index % 64 == 0:
                    print(f"ECC readback page {index}", flush=True)
                host.control_out(0x40, 0x51, 2048 + index)
                result = struct.unpack("<6I", host.control_in(0xC0, 0x51, length=24))
                assert result[0:3] == (0x3152504c, 2048 + index, 0), result
                assert result[5] == 1, result
                data = b"".join(host.control_in(0xC0, 0x52, offset, length=512)
                                for offset in range(0, 2048, 512))
                expected = reference[index * 2048:(index + 1) * 2048]
                assert data[:len(expected)] == expected, ("ECC read differs", index)
            print(f"ECC NAND readback matches all {len(reference)} capsule bytes", flush=True)
            # Withhold SET_ADDRESS's status IN token. The device must remain
            # at its old address until the host acknowledges that status.
            host.setup_packet(0x00, 5, 23, 0, 0)
            time.sleep(0.05)
            assert "address=5 " in host.command("STATUS")
            assert host.in_packet(0) == b""
            time.sleep(0.05)
            assert "address=23 " in host.command("STATUS")
            # A replacement SETUP cancels an unacknowledged pending address.
            host.setup_packet(0x00, 5, 42, 0, 0)
            time.sleep(0.05)
            host.setup_packet(0x80, 8, 0, 0, 1)
            # The socket model accepts SETUP before the guest polling loop
            # has flushed the deliberately outstanding old status descriptor.
            time.sleep(0.05)
            assert host.in_packet(1) == b"\x01"
            host.out_packet(b"")
            time.sleep(0.05)
            assert "address=23 " in host.command("STATUS")
            # Zero is a valid deferred address, not the "no pending" sentinel.
            host.control_out(0x00, 5, 0)
            time.sleep(0.05)
            assert "address=0 " in host.command("STATUS")
            host.control_out(0x00, 5, 5)
            time.sleep(0.05)
            time.sleep(0.05)
            trace = struct.unpack("<8I", host.control_in(0xC0, 0x4D, length=32))
            assert trace[:2] == (0x4c465554, 1), trace
            assert trace[3] == 5 and trace[4] > 0 and trace[5] > 0 and trace[6] > 0, trace
            time.sleep(0.05)
            # Reading diagnostics must not replace or advance the captured request.
            assert struct.unpack("<8I", host.control_in(0xC0, 0x4D, length=32)) == trace
            payload = bytearray((i * 37 + 11) & 255 for i in range(65536))
            struct.pack_into("<I", payload, 0x24, 0x016F2818)
            struct.pack_into("<I", payload, 0x2C, len(payload))
            crc = ion_crc32(payload)
            host.stage_capsule(payload, crc)
            status = struct.unpack("<8I", host.control_in(0xC0, 0x43, length=32))
            assert status[2] == 2 and status[4:7] == (len(payload), len(payload), crc), status
            # A development handoff must not reset before the host ACKs its
            # status stage. Cancel it with a replacement SETUP and verify USB
            # remains alive. Actual physical ROM entry is a separate gate.
            host.setup_packet(0x40, 0x4E, crc & 0xffff, crc >> 16, 0)
            time.sleep(0.05)
            host.setup_packet(0xC0, 0x4E, 0, 0, 16)
            time.sleep(0.05)
            assert struct.unpack("<4I", host.in_packet(16)) == capabilities
            host.out_packet(b"")
            host.control_out(0x40, 0x47)  # release staged RAM; no execution
            assert host.command("DISCONNECT") == "OK"
            descriptor2, config2 = host.connect_and_enumerate(address=7)
            assert (descriptor2, config2) == (descriptor, config)
            time.sleep(0.05)
            after = struct.unpack("<8I", host.control_in(0xC0, 0x4D, length=32))
            assert after[4] > trace[4] and after[5] > trace[5] and after[6] > trace[6], after
            # Exercise real APBH/BCH erase+encode+readback, not the synthetic
            # emulator NAND API. The device's NAND image is an ephemeral overlay.
            print("Staging full capsule for native installation", flush=True)
            crc = ion_crc32(reference)
            host.stage_capsule(reference, crc)
            host.control_out(0x40, 0x53, crc & 0xffff, crc >> 16)
            deadline = time.monotonic() + 180
            last = None
            while time.monotonic() < deadline:
                installed = struct.unpack("<8I", host.control_in(0xc0, 0x53, length=32))
                current = (installed[2], installed[3] * 100 // max(1, installed[4]))
                if current != last:
                    print("Native install:", current, flush=True)
                    last = current
                assert installed[2] != 9, installed
                if installed[2] == 8:
                    assert installed[3:5] == (len(reference), len(reference)), installed
                    assert installed[7] == crc, installed
                    break
                time.sleep(0.05)
            else:
                raise AssertionError("native writer did not finish")
            subprocess.run(["python3", str(Path(__file__).with_name("qmp-screendump.py")),
                            str(qmp_path), str(directory / "update-verified.ppm")], check=True)
            journal = overlay.read_bytes()
            assert journal.startswith(initial_overlay)
            offset = len(initial_overlay)
            while offset < len(journal):
                kind, index = struct.unpack_from("<B3xI", journal, offset)
                offset += 8
                assert kind in (1, 2)
                assert (2048 <= index < 6144) if kind == 1 else (32 <= index < 96)
                if kind == 1: offset += 2112
            assert offset == len(journal)
            host.control_out(0x40, 0x54)
            # -no-reboot converts a real guest reset request into QEMU exit.
            process.wait(timeout=10)
            assert process.returncode == 0, process.returncode
            boot["run_until"](b"Lefony OS: entering calculator runtime", overlay)
        print(f"PASS physical-target emulated USB: deferred address/status/cancellation/zero, enumerate, 64 KiB RAM transfer/CRC, abort, reconnect; {directory}")
    except Exception:
        qmp = runpy.run_path(str(Path(__file__).with_name("qmp-screendump.py")))
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(str(qmp_path))
            stream = client.makefile("rb")
            qmp["receive_message"](stream)
            qmp["execute"](client, stream, {"execute": "qmp_capabilities"})
            print(qmp["execute"](client, stream, {"execute": "human-monitor-command",
                "arguments": {"command-line": "info registers"}}), flush=True)
            qmp["execute"](client, stream, {"execute": "screendump",
                "arguments": {"filename": str(directory / "failure.ppm")}})
        print("Failure artifacts:", directory, flush=True)
        raise
    finally:
        boot["stop"](process)


if __name__ == "__main__":
    main()
