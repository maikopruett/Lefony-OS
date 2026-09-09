#!/usr/bin/env python3
"""Black-box proof of the i.MX6ULL software-to-ROM recovery transition."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time

from prime_usb_host import PrimeUSBHost


ROOT = Path(__file__).resolve().parents[1]
QEMU = Path(os.environ.get(
    "PRIME_G2_QEMU", ROOT / "build/qemu-prime-g2/qemu-system-arm"))
STOCK_FIXTURE = Path(os.environ.get(
    "HP_PRIME_STOCK_FIXTURE_DIR", ROOT / "build/hp-prime-stock"))
ROM_STUB = Path(os.environ.get(
    "PRIME_G2_ROM_RECOVERY_STUB",
    ROOT / "build/prime-g2-rom-recovery/rom-recovery.bin"))
ROM_STUB_ADDRESS = 0x80010000

SRC_GPR9 = 0x020D8040
SRC_SRSR = 0x020D8008
SRC_GPR10 = 0x020D8044
WDOG1_WCR = 0x020BC000
ROM_USB_BOOT_CFG = 0x20
SRC_GPR10_BMODE = 1 << 28

NAND_OVERLAY_PAGES = 0x01806160
NAND_PROGRAM_FAILURES = 0x01806164
NAND_ECC_WRITES = 0x01806170


def connect_socket(path: Path, timeout: float = 5.0) -> socket.socket:
    deadline = time.monotonic() + timeout
    while True:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect(str(path))
            return client
        except OSError:
            client.close()
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)


class QTest:
    def __init__(self, path: Path):
        self.socket = connect_socket(path)
        self.stream = self.socket.makefile("rb")

    def close(self) -> None:
        self.stream.close()
        self.socket.close()

    def command(self, command: str) -> str:
        self.socket.sendall((command + "\n").encode())
        response = self.stream.readline().decode(errors="replace").strip()
        if not response.startswith("OK"):
            raise RuntimeError(f"qtest rejected {command!r}: {response}")
        return response

    def writel(self, address: int, value: int) -> None:
        self.command(f"writel 0x{address:x} 0x{value:x}")

    def writew(self, address: int, value: int) -> None:
        self.command(f"writew 0x{address:x} 0x{value:x}")

    def readl(self, address: int) -> int:
        response = self.command(f"readl 0x{address:x}")
        return int(response.split()[1], 16)


class QMP:
    def __init__(self, path: Path):
        self.socket = connect_socket(path)
        self.stream = self.socket.makefile("rb")
        self._read_message()  # greeting
        self.execute("qmp_capabilities")

    def close(self) -> None:
        self.stream.close()
        self.socket.close()

    def _read_message(self) -> dict[str, object]:
        line = self.stream.readline()
        if not line:
            raise RuntimeError("QMP socket closed")
        return json.loads(line)

    def execute(self, command: str, arguments: dict | None = None) -> dict[str, object]:
        request = {"execute": command}
        if arguments is not None:
            request["arguments"] = arguments
        payload = json.dumps(request, separators=(",", ":"))
        self.socket.sendall((payload + "\n").encode())
        while True:
            response = self._read_message()
            if "return" in response:
                return response
            if "error" in response:
                raise RuntimeError(f"QMP rejected {command}: {response['error']}")


class RecoveryVM:
    def __init__(self, directory: Path, payload: Path | None = None):
        directory.mkdir(parents=True)
        self.usb_path = directory / "usb.sock"
        self.qtest_path = directory / "qtest.sock"
        self.qmp_path = directory / "qmp.sock"
        command = [
            str(QEMU),
            "-machine", "hp-prime-g2",
            "-display", "none",
            "-monitor", "none",
            "-serial", "none",
            "-chardev",
            f"socket,id=primeusb,path={self.usb_path},server=on,wait=off",
            "-global", "prime-g2-usbotg-device.chardev=primeusb",
            "-qtest", f"unix:{self.qtest_path},server=on,wait=off",
            "-qmp", f"unix:{self.qmp_path},server=on,wait=off",
            "-watchdog-action", "reset",
        ]
        if payload is not None:
            command += [
                # A RAM-only watchdog stub assumes prior DDR setup. Keep
                # that debugger fixture explicit, not the default ROM state.
                "-global", "prime-g2-mmdc.preinitialized=on",
                "-device",
                f"loader,file={payload},addr=0x{ROM_STUB_ADDRESS:x},force-raw=on",
                "-device",
                f"loader,addr=0x{ROM_STUB_ADDRESS:x},cpu-num=0",
            ]
        # Isolate SRC/watchdog transitions from the autonomous NAND ROM.
        # A malformed stock fixture legitimately enters SDP after a normal
        # reset; sampling the transient USB "guest" state hid that distinction.
        # Complete NAND/reset behavior is exercised by test-prime-g2-nand-rom-boot.
        self.process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True)
        self.qtest = QTest(self.qtest_path)
        self.qmp = QMP(self.qmp_path)
        self.usb = PrimeUSBHost(self.usb_path)
        if self.usb.command("CONNECT") != "OK":
            raise RuntimeError("failed to attach the emulated USB cable")

    def close(self) -> None:
        self.usb.close()
        self.qmp.close()
        self.qtest.close()
        self.process.terminate()
        try:
            _, stderr = self.process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            _, stderr = self.process.communicate(timeout=5)
        if self.process.returncode not in (0, -15):
            raise RuntimeError(f"QEMU failed with {self.process.returncode}: {stderr}")

    def wait_for_mode(self, mode: str, timeout: float = 3.0) -> str:
        deadline = time.monotonic() + timeout
        while True:
            status = self.usb.command("STATUS")
            if f"mode={mode}" in status:
                return status
            if time.monotonic() >= deadline:
                raise AssertionError(f"USB did not reach {mode}: {status}")
            time.sleep(0.01)


def arm_rom_usb_boot(qtest: QTest, boot_cfg: int = ROM_USB_BOOT_CFG) -> None:
    qtest.writel(SRC_GPR9, boot_cfg)
    qtest.writel(SRC_GPR10, SRC_GPR10_BMODE)


def find_stock_nand() -> Path | None:
    manifest_path = STOCK_FIXTURE / "nand-fixture.json"
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "hp-prime-g2-raw-nand-v1":
        raise RuntimeError("unsupported private stock NAND fixture format")
    path = STOCK_FIXTURE / manifest["image"]["path"]
    return path if path.is_file() else None


def assert_nand_untouched(qtest: QTest) -> None:
    counters = {
        "overlay pages": qtest.readl(NAND_OVERLAY_PAGES),
        "program failures": qtest.readl(NAND_PROGRAM_FAILURES),
        "ECC writes": qtest.readl(NAND_ECC_WRITES),
    }
    if any(counters.values()):
        raise AssertionError(f"transition touched NAND: {counters}")


def test_watchdog_transition(directory: Path) -> None:
    vm = RecoveryVM(directory)
    try:
        arm_rom_usb_boot(vm.qtest)
        # Clearing SRS requests the same warm reset used by U-Boot's reset_cpu.
        vm.qtest.writew(WDOG1_WCR, 0x0004)
        status = vm.wait_for_mode("rom-sdp")
        if "vid=15a2 pid=0080" not in status:
            raise AssertionError(f"wrong ROM USB identity: {status}")
        if vm.qtest.readl(SRC_GPR9) != ROM_USB_BOOT_CFG:
            raise AssertionError("watchdog reset did not preserve SRC_GPR9")
        if vm.qtest.readl(SRC_GPR10) != SRC_GPR10_BMODE:
            raise AssertionError("watchdog reset did not preserve SRC_GPR10")

        device, configuration = vm.usb.connect_and_enumerate()
        if device[8:12] != bytes.fromhex("a2158000"):
            raise AssertionError(f"unexpected ROM descriptor: {device.hex()}")
        if len(configuration) != 18 or configuration[1] != 2:
            raise AssertionError("ROM configuration descriptor was not readable")
        assert_nand_untouched(vm.qtest)
    finally:
        vm.close()


def test_ram_stub_transition(directory: Path) -> None:
    vm = RecoveryVM(directory, payload=ROM_STUB)
    try:
        status = vm.wait_for_mode("rom-sdp")
        if "vid=15a2 pid=0080" not in status:
            raise AssertionError(f"wrong ROM USB identity: {status}")
        device, _ = vm.usb.connect_and_enumerate()
        if device[8:12] != bytes.fromhex("a2158000"):
            raise AssertionError(f"unexpected ROM descriptor: {device.hex()}")
        assert_nand_untouched(vm.qtest)
    finally:
        vm.close()


def test_wrong_boot_cfg(directory: Path) -> None:
    vm = RecoveryVM(directory)
    try:
        arm_rom_usb_boot(vm.qtest, boot_cfg=0x21)
        vm.qtest.writew(WDOG1_WCR, 0x0004)
        vm.wait_for_mode("guest")
        assert_nand_untouched(vm.qtest)
    finally:
        vm.close()


def test_cold_reset_clears_override(directory: Path) -> None:
    vm = RecoveryVM(directory)
    try:
        arm_rom_usb_boot(vm.qtest)
        vm.qmp.execute("system_reset")
        vm.wait_for_mode("guest")
        if vm.qtest.readl(SRC_GPR9) or vm.qtest.readl(SRC_GPR10):
            raise AssertionError("cold reset incorrectly preserved boot override")
        assert_nand_untouched(vm.qtest)
    finally:
        vm.close()


def test_reset_status_and_recovery_exit(directory: Path) -> None:
    """Exercise the installer's clear-override/reset sequence repeatedly.

    SRSR is sticky and write-one-to-clear: firmware must acknowledge POR
    before a later watchdog reset can be reported as watchdog alone.
    """
    vm = RecoveryVM(directory)
    try:
        assert vm.qtest.readl(SRC_SRSR) == 1
        vm.qtest.writel(SRC_SRSR, 0)
        assert vm.qtest.readl(SRC_SRSR) == 1, "zero write cleared POR"
        for watchdog, cause in ((WDOG1_WCR, 0x10), (0x021E4000, 0x80)):
            arm_rom_usb_boot(vm.qtest)
            vm.qtest.writew(watchdog, 0x0004)
            vm.wait_for_mode("rom-sdp")
            assert vm.qtest.readl(SRC_SRSR) == (1 | cause)
            vm.qtest.writel(SRC_SRSR, 1)
            assert vm.qtest.readl(SRC_SRSR) == cause
            vm.qtest.writel(SRC_SRSR, cause)
            assert vm.qtest.readl(SRC_SRSR) == 0
            vm.qtest.writel(SRC_SRSR, 0xffffffff)
            assert vm.qtest.readl(SRC_SRSR) == 0, "software set reset flags"

            # The installer clears both retained words before reset.
            vm.qtest.writel(SRC_GPR9, 0)
            vm.qtest.writel(SRC_GPR10, 0)
            vm.qtest.writew(watchdog, 0x0004)
            vm.wait_for_mode("guest")
            assert vm.qtest.readl(SRC_SRSR) == cause
            assert vm.qtest.readl(SRC_GPR9) == 0
            assert vm.qtest.readl(SRC_GPR10) == 0
            vm.qmp.execute("system_reset")
            vm.wait_for_mode("guest")
            assert vm.qtest.readl(SRC_SRSR) == 1
        assert_nand_untouched(vm.qtest)
    finally:
        vm.close()


def test_physical_src_profile(directory: Path) -> None:
    captured = json.loads((ROOT / "hardware/prime_g2/reference/"
                           "rom-src-snapshot.json").read_text())["src_registers"]
    vm = RecoveryVM(directory)
    try:
        for name, register in captured.items():
            address = int(register["address"], 16)
            expected = int(register["value"], 16)
            actual = vm.qtest.readl(address)
            assert actual == expected, f"{name}: {actual:#x} != physical {expected:#x}"
        for name in ("SRC_SBMR1", "SRC_SBMR2"):
            address = int(captured[name]["address"], 16)
            expected = int(captured[name]["value"], 16)
            for write in (0, 0xffffffff):
                vm.qtest.writel(address, write)
                assert vm.qtest.readl(address) == expected, f"{name} is software-writable"
        arm_rom_usb_boot(vm.qtest)
        vm.qtest.writew(WDOG1_WCR, 4)
        vm.wait_for_mode("rom-sdp")
        vm.usb.connect_and_enumerate()
        for name in ("SRC_SBMR1", "SRC_SBMR2"):
            register = captured[name]
            address = int(register["address"], 16)
            expected = int(register["value"], 16)
            sdp_command(vm.usb, 0x0101, address, 4)
            sdp_security(vm.usb)
            assert vm.usb.endpoint_in(1, 65) == b"\x04" + struct.pack("<I", expected)
        vm.qmp.execute("system_reset")
        vm.wait_for_mode("guest")
        for name, register in captured.items():
            assert vm.qtest.readl(int(register["address"], 16)) == int(register["value"], 16), name
    finally:
        vm.close()


def test_generic_evk_has_no_prime_straps(directory: Path) -> None:
    directory.mkdir()
    path = directory / "qtest.sock"
    process = subprocess.Popen([
        str(QEMU), "-machine", "mcimx6ul-evk", "-S", "-display", "none",
        "-serial", "none", "-monitor", "none", "-qtest",
        f"unix:{path},server=on,wait=off"], stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE)
    qtest = None
    try:
        qtest = QTest(path)
        assert qtest.readl(0x020d8004) == 0, "Prime SBMR1 leaked into generic EVK"
        assert qtest.readl(0x020d801c) == 0, "Prime SBMR2 leaked into generic EVK"
    finally:
        if qtest is not None:
            qtest.close()
        process.terminate()
        try:
            _, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            _, stderr = process.communicate(timeout=5)
        if process.returncode not in (0, -15):
            raise RuntimeError(f"generic EVK failed: {stderr!r}")


def sdp_command(usb: PrimeUSBHost, command: int, address: int = 0,
                count: int = 0) -> None:
    payload = b"\x01" + struct.pack(">HIBIIB", command, address, 32, count, 0, 0)
    usb.control_out(0x21, 9, 0x201, payload=payload)


def sdp_security(usb: PrimeUSBHost) -> None:
    assert usb.endpoint_in(1, 65) == bytes.fromhex("0356787856")


def sdp_download(usb: PrimeUSBHost, address: int, payload: bytes) -> None:
    sdp_command(usb, 0x0404, address, len(payload))
    for offset in range(0, len(payload), 1024):
        report = b"\x02" + payload[offset:offset + 1024].ljust(1024, b"\xa5")
        usb.control_out(0x21, 9, 0x202, payload=report)
    sdp_security(usb)
    assert usb.endpoint_in(1, 65) == bytes.fromhex("0488888888")


def test_sdp_download_and_execute(directory: Path) -> None:
    vm = RecoveryVM(directory)
    try:
        arm_rom_usb_boot(vm.qtest)
        vm.qtest.writew(WDOG1_WCR, 4)
        vm.wait_for_mode("rom-sdp")
        device, _ = vm.usb.connect_and_enumerate()
        config = vm.usb.control_in(0x80, 6, 0x200, length=255)
        report = vm.usb.control_in(0x81, 6, 0x2200, length=255)
        assert len(config) == int.from_bytes(config[2:4], "little") == 34
        assert config[13] == 1 and config[29] == 0x81
        assert len(report) == int.from_bytes(config[25:27], "little") == 76
        captured = json.loads((ROOT / "hardware/prime_g2/reference/"
                               "rom-usb-descriptors.json").read_text())
        assert device.hex() == captured["device"]
        assert config.hex() == captured["configuration"]
        assert report.hex() == captured["hid_report"]
        for index, expected in captured["strings"].items():
            actual = vm.usb.control_in(0x80, 6, 0x300 | int(index),
                                       0x409 if int(index) else 0, length=255)
            assert actual.hex() == expected, f"ROM USB string {index} differs"
        for register in (SRC_SRSR, SRC_GPR9, SRC_GPR10):
            expected = vm.qtest.readl(register)
            sdp_command(vm.usb, 0x0101, register, 4)
            sdp_security(vm.usb)
            assert vm.usb.endpoint_in(1, 65) == b"\x04" + struct.pack("<I", expected)

        # This transfer test starts after an explicit nominal DDR setup.
        # test-prime-g2-ddr-usb.py covers the pre-init rejection and USB DCD path.
        import importlib
        importlib.import_module('test-prime-g2-mmdc').initialize(vm.qtest)
        address = 0x80800000
        payload = bytes(range(256)) * 8 + b"last"
        sentinel = address + len(payload)
        vm.qtest.writel(sentinel, 0xdeadbeef)
        sdp_download(vm.usb, address, payload)
        assert vm.qtest.readl(sentinel) == 0xdeadbeef, "HID padding overwrote RAM"
        sdp_command(vm.usb, 0x0101, address, len(payload))
        sdp_security(vm.usb)
        readback = bytearray()
        while len(readback) < len(payload):
            data = vm.usb.endpoint_in(1, 65)
            assert data[0] == 4
            readback.extend(data[1:])
        assert readback == payload

        # An interrupted SET_REPORT and download must not survive USB reset.
        sdp_command(vm.usb, 0x0404, address, 1024)
        vm.usb.setup_packet(0x21, 9, 0x202, length=1025)
        vm.usb.out_packet(b"\x02" + b"x" * 31)
        assert vm.usb.command("RESET") == "OK"
        assert vm.usb.command("OUT 02aa") == "NAK"
        sdp_command(vm.usb, 0x0505)
        sdp_security(vm.usb)
        assert vm.usb.endpoint_in(1, 65) == b"\x04" + bytes(4)

        # Host-supplied DCD must actually execute before its acknowledgement.
        # Its words use big endian, unlike the little-endian IVT and status.
        dcd_target = address + 0x3000
        dcd = bytes.fromhex("d2001040cc000c04") + struct.pack(">II", dcd_target, 0x1234abcd)
        sdp_command(vm.usb, 0x0a0a, 0x00910000, len(dcd))
        vm.usb.control_out(0x21, 9, 0x202, payload=b"\x02" + dcd)
        sdp_security(vm.usb)
        assert vm.usb.endpoint_in(1, 65) == bytes.fromhex("04128a8a12")
        assert vm.qtest.readl(dcd_target) == 0x1234abcd
        sdp_command(vm.usb, 0x0c0c)
        sdp_security(vm.usb)
        assert vm.usb.endpoint_in(1, 65) == bytes.fromhex("0409d00d90")

        # Reject a non-IVT jump without executing arbitrary RAM.
        sdp_command(vm.usb, 0x0b0b, address)
        sdp_security(vm.usb)
        assert vm.usb.endpoint_in(1, 65) == bytes.fromhex("0433050a00")
        vm.wait_for_mode("rom-sdp")

        # Download an open ARM test image over USB, then enter it through IVT.
        # The guest writes a marker; qtest does not inject code or an entry PC.
        marker = 0x80900000
        ivt = struct.pack("<8I", 0x402000d1, address + 32, 0, 0,
                          0, address, 0, 0)
        code = struct.pack("<6I", 0xe59f0008, 0xe59f1008, 0xe5801000,
                           0xeafffffe, marker, 0x51d0cafe)
        sdp_download(vm.usb, address, ivt + code)
        sdp_command(vm.usb, 0x0b0b, address)
        sdp_security(vm.usb)
        vm.wait_for_mode("guest")
        deadline = time.monotonic() + 3
        while vm.qtest.readl(marker) != 0x51d0cafe:
            if time.monotonic() >= deadline:
                registers = vm.qmp.execute("human-monitor-command",
                                           {"command-line": "info registers"})
                raise AssertionError(f"SDP-downloaded ARM image did not execute: {registers}")
            time.sleep(0.01)
        assert_nand_untouched(vm.qtest)
    finally:
        vm.close()


def main() -> int:
    if not QEMU.is_file():
        raise SystemExit(f"Prime G2 QEMU is missing: {QEMU}")
    with tempfile.TemporaryDirectory(prefix="lefony-rom-recovery-") as tmp:
        root = Path(tmp)
        test_watchdog_transition(root / "warm")
        stub_tested = ROM_STUB.is_file()
        if stub_tested:
            test_ram_stub_transition(root / "ram-stub")
        test_wrong_boot_cfg(root / "wrong-cfg")
        test_cold_reset_clears_override(root / "cold")
        test_reset_status_and_recovery_exit(root / "reset-status")
        test_physical_src_profile(root / "physical-src")
        test_generic_evk_has_no_prime_straps(root / "generic-evk")
        test_sdp_download_and_execute(root / "sdp")
    fixture = "synthetic NAND"
    stub = " and the RAM stub" if stub_tested else ""
    print(f"PASS: exact boot override{stub} + watchdog reset enters ROM SDP "
          "(15a2:0080), negative controls stay in guest mode, and "
          f"{fixture} is untouched; SDP downloads/readback/IVT execution and "
          "sticky reset causes pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
