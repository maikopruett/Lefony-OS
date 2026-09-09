#!/usr/bin/env python3
"""Black-box qualification of HP Prime G2 cold boot from a raw NAND capture."""

from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
import selectors
import struct
import subprocess
import tempfile
import time

from prime_usb_host import PrimeUSBHost


ROOT = Path(__file__).resolve().parents[1]
QEMU = Path(os.environ.get(
    "PRIME_G2_QEMU", ROOT / "build/qemu-prime-g2/qemu-system-arm"))
NAND = Path(os.environ.get(
    "PRIME_G2_EXACT_NAND",
    ROOT / "build/prime-g2-a606-emulator/exact-capture/exact-a606-nand.raw"))
CURRENT_CAPSULE = Path(os.environ.get(
    "PRIME_G2_CURRENT_CAPSULE",
    ROOT / "build/lefony-os-history/artifacts/"
    "20260903T045252Z-ram-verified-nonblocking-adc-38cc819c/"
    "lefony-os-nonblocking-adc.zImage"))
AB_UBOOT = ROOT / "build/lefony-prime-g2-u-boot-output/u-boot-dtb-lefony-ab.imx"
PHYSICAL_AB = (ROOT / "build/prime-g2-physical-qualification/read-only-20260902"
               / "postboot-black-screen")
PHYSICAL_DTB = (ROOT / "build/prime-g2-physical-qualification"
                / "post-normal-reset-white-20260902/dtb.readback")

PAGE_BYTES = 2048 + 64
DATA_BYTES = 2048
TOTAL_PAGES = 4096 * 64
OVERLAY_MAGIC = b"PG2OVL1\n"


def read_record(page: int) -> bytearray:
    with NAND.open("rb") as source:
        source.seek(page * PAGE_BYTES)
        record = bytearray(source.read(PAGE_BYTES))
    if len(record) != PAGE_BYTES:
        raise RuntimeError(f"short NAND record at page {page}")
    return record


def write_overlay(path: Path, records: dict[int, bytearray]) -> None:
    with path.open("wb") as overlay:
        overlay.write(OVERLAY_MAGIC)
        for page, record in records.items():
            overlay.write(struct.pack("<B3xI", 1, page))
            overlay.write(record)


def command(overlay: Path | None = None, usb_path: Path | None = None,
            serial: str = "stdio", qmp_path: Path | None = None) -> list[str]:
    result = [
        str(QEMU), "-machine", "hp-prime-g2", "-m", "256M",
        "-global", "imx6ul-lcdif.prime-g2-panel=on",
        "-global", "prime-g2-pf1550.external-power=on",
        "-global", f"prime-g2-gpmi-bch.stock-nand={NAND}",
        "-display", "none", "-monitor", "none", "-serial", serial,
        "-no-reboot",
    ]
    if overlay is not None:
        result += [
            "-global", f"prime-g2-gpmi-bch.stock-overlay={overlay}",
        ]
    if usb_path is not None:
        result += [
            "-chardev",
            f"socket,id=primeusb,path={usb_path},server=on,wait=off",
            "-global", "prime-g2-usbotg-device.chardev=primeusb",
        ]
    if qmp_path is not None:
        result += ["-qmp", f"unix:{qmp_path},server=on,wait=off"]
    return result


def stop(process: subprocess.Popen[bytes]) -> bytes:
    process.terminate()
    try:
        stdout, stderr = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=5)
    if process.returncode not in (0, -15):
        raise RuntimeError(
            f"QEMU failed with {process.returncode}:\n"
            f"{(stdout + stderr).decode(errors='replace')}")
    return stdout + stderr


def run_until(marker: bytes, overlay: Path | None = None,
              timeout: float = 20.0) -> bytes:
    process = subprocess.Popen(
        command(overlay), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    selected = selectors.DefaultSelector()
    selected.register(process.stdout, selectors.EVENT_READ)
    selected.register(process.stderr, selectors.EVENT_READ)
    output = bytearray()
    deadline = time.monotonic() + timeout
    try:
        while marker not in output:
            if process.poll() is not None:
                output.extend(process.stdout.read())
                output.extend(process.stderr.read())
                raise AssertionError(
                    f"QEMU exited before {marker!r}:\n"
                    f"{output.decode(errors='replace')}")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(
                    f"timed out waiting for {marker!r}:\n"
                    f"{output.decode(errors='replace')}")
            for key, _ in selected.select(min(remaining, 0.25)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if chunk:
                    output.extend(chunk)
        return bytes(output)
    finally:
        selected.close()
        output.extend(stop(process))


def run_for(timeout: float, overlay: Path | None = None) -> bytes:
    process = subprocess.Popen(
        command(overlay), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(timeout)
    return stop(process)


def test_exact_chain() -> None:
    output = run_until(b"Lefony OS: entering calculator runtime")
    required = [
        b"loaded 389120 bytes from NAND page 512",
        b"executed i.MX DCD",
        b"U-Boot 2018.03",
        b"Model: HP Prime G2 Calculator",
        b"NAND:  512 MiB",
        b"Starting kernel",
    ]
    missing = [item for item in required if item not in output]
    if missing:
        raise AssertionError(f"cold-boot evidence missing: {missing}")
    assert b"cannot support the NAND" not in output, output.decode(errors="replace")


def add_image_records(records: dict[int, bytearray], first_page: int,
                      image: bytes) -> None:
    for index in range((len(image) + DATA_BYTES - 1) // DATA_BYTES):
        record = read_record(first_page + index)
        chunk = image[index * DATA_BYTES:(index + 1) * DATA_BYTES]
        record[:DATA_BYTES] = chunk.ljust(DATA_BYTES, b"\xff")
        records[first_page + index] = record


def capsule_overlay(directory: Path,
                    records: dict[int, bytearray] | None = None,
                    name: str = "current-lefony-capsule.overlay") -> Path:
    records = {} if records is None else records
    add_image_records(
        records, 4 * 1024 * 1024 // DATA_BYTES,
        CURRENT_CAPSULE.read_bytes())
    overlay = directory / name
    write_overlay(overlay, records)
    return overlay


def captured_uboot() -> bytearray:
    image = bytearray()
    for page in range(512, 512 + 190):
        image.extend(read_record(page)[:DATA_BYTES])
    return image


def patch_manufacturing_command(image: bytearray, *, safe: bool) -> None:
    key = b"bootcmd_mfg="
    replacement = b"bootcmd_mfg=run bootcmd;"
    start = image.find(key)
    end = image.find(b"\0", start)
    if start < 0 or end < 0 or len(replacement) > end - start:
        raise AssertionError("captured U-Boot manufacturing environment is invalid")
    # The historical patcher used NUL padding.  Since the environment is a
    # packed list, that made the following bootcmd invisible to U-Boot.
    fill = b" " if safe else b"\0"
    image[start:end] = replacement + fill * (end - start - len(replacement))


def bootstream_overlay(directory: Path, *, safe: bool) -> Path:
    image = captured_uboot()
    patch_manufacturing_command(image, safe=safe)
    expected = (
        "935a42e477b37b2988c73843218f021a243466bd9a17d05d25b18ae81fc2826e"
        if safe else
        "cbf3cf8fa0b88a4ab333e6547b049d882eeec09685ec0bbe015775cb04a93650"
    )
    if hashlib.sha256(image).hexdigest() != expected:
        raise AssertionError("captured U-Boot no longer matches physical evidence")
    records: dict[int, bytearray] = {}
    add_image_records(records, 512, image)
    add_image_records(records, 1280, image)
    return capsule_overlay(
        directory, records,
        "repaired-uboot.overlay" if safe else "truncated-uboot.overlay")


def test_environment_truncation_regression(directory: Path) -> None:
    broken = bootstream_overlay(directory, safe=False)
    output = run_for(8.0, broken)
    if b"Normal Boot" not in output or b"=> " not in output:
        raise AssertionError(
            "historical U-Boot did not stop at its command prompt:\n"
            + output.decode(errors="replace"))
    if b"Starting kernel" in output:
        raise AssertionError("NUL-truncated U-Boot unexpectedly found bootcmd")

    repaired = bootstream_overlay(directory, safe=True)
    output = run_until(b"Lefony OS: entering calculator runtime", repaired)
    if b"Starting kernel" not in output:
        raise AssertionError("repaired packed environment did not cold-boot Lefony")
    test_visible_runtime(directory, repaired, "repaired-environment")


def physical_ab_overlay(directory: Path) -> Path:
    image = bytearray(AB_UBOOT.read_bytes())
    patch_manufacturing_command(image, safe=True)
    image = bytearray(1024) + image
    if hashlib.sha256(image).hexdigest() != (
            "20495c01686deb9a965dae7a9569cca62ee01d6e2b3e6dc56ede45129403abca"):
        raise AssertionError("repaired A/B U-Boot no longer matches qualification")
    records: dict[int, bytearray] = {}
    fcb = (PHYSICAL_AB / "fcb-page.bin").read_bytes()
    for page in (0, 64, 128, 192):
        record = read_record(page)
        record[:DATA_BYTES] = fcb
        records[page] = record
    add_image_records(records, 512, image)
    add_image_records(records, 1280, image)
    add_image_records(records, 2048, (PHYSICAL_AB / "slot-a.readback").read_bytes())
    add_image_records(records, 6144, PHYSICAL_DTB.read_bytes())
    add_image_records(records, 6656, (PHYSICAL_AB / "metadata-a.readback").read_bytes())
    add_image_records(records, 6720, (PHYSICAL_AB / "metadata-b.readback").read_bytes())
    overlay = directory / "repaired-physical-ab-stack.overlay"
    write_overlay(overlay, records)
    return overlay


def test_repaired_physical_ab_stack(directory: Path) -> None:
    overlay = physical_ab_overlay(directory)
    output = run_until(b"Lefony OS: entering calculator runtime", overlay, 30.0)
    required = [
        b"loaded 405504 bytes from NAND page 512",
        b"Lefony A/B: verified slot A (2103160 bytes); booting",
        b"1048576 bytes read: OK",
        b"Starting kernel",
    ]
    missing = [item for item in required if item not in output]
    if missing:
        raise AssertionError(f"repaired physical A/B evidence missing: {missing}")
    test_visible_runtime(directory, overlay, "repaired-physical-ab")


def test_visible_runtime(directory: Path, overlay: Path | None = None,
                         stem: str = "cold-boot") -> None:
    overlay = capsule_overlay(directory) if overlay is None else overlay
    uart = directory / f"{stem}-uart.log"
    qmp = directory / f"{stem}-qmp.sock"
    screen = directory / f"{stem}-ui.ppm"
    process = subprocess.Popen(
        command(overlay, serial=f"file:{uart}", qmp_path=qmp),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if (uart.is_file() and
                    b"Lefony OS: entering calculator runtime" in uart.read_bytes()):
                break
            if process.poll() is not None:
                raise AssertionError("cold-boot UI VM exited before Lefony")
            time.sleep(0.05)
        else:
            raise AssertionError("cold-boot UI VM did not reach Lefony")
        # Allow the application event loop to submit its first complete LCDIF
        # frame, then sample through QEMU's actual display surface.
        time.sleep(1.0)
        subprocess.run(
            ["python3", str(ROOT / "vm/qmp-screendump.py"), str(qmp),
             str(screen), "--timeout", "5"], check=True)
    finally:
        stop(process)
    assert_visible_panel(screen)


def assert_visible_panel(screen: Path) -> None:
    data = screen.read_bytes()
    try:
        magic, dimensions, maximum, pixels = data.split(b"\n", 3)
        width, height = map(int, dimensions.split())
    except (ValueError, TypeError) as error:
        raise AssertionError(f"invalid cold-boot panel PPM: {data[:80]!r}") from error
    # QEMU's headless LCD surface may retain the console's 2x scale, but the
    # guest scanout and aspect ratio must remain the Prime's 320x240 raster.
    if magic != b"P6" or maximum != b"255" or (width, height) not in {
            (320, 240), (640, 480)}:
        raise AssertionError(
            f"cold NAND boot did not expose a 320x240 RGB panel: {data[:80]!r}")
    colors = {pixels[offset:offset + 3]
              for offset in range(0, len(pixels) - 2, 3)}
    if len(colors) < 16 or colors <= {b"\x00\x00\x00", b"\xff\xff\xff"}:
        raise AssertionError(
            f"cold NAND boot panel is blank or uninitialized ({len(colors)} colors)")


def test_recovery_exit_boots_nand(directory: Path) -> None:
    recovery = importlib.import_module("test-prime-g2-rom-recovery")
    overlay = bootstream_overlay(directory, safe=True)
    uart = directory / "reset-cycle-uart.log"
    qmp_path = directory / "reset-qmp.sock"
    qtest_path = directory / "reset-qtest.sock"
    usb_path = directory / "reset-usb.sock"
    args = command(overlay, usb_path, f"file:{uart}", qmp_path)
    args.remove("-no-reboot")
    args += ["-watchdog-action", "reset", "-qtest",
             f"unix:{qtest_path},server=on,wait=off"]
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    qtest = qmp = usb = None
    marker = b"Lefony OS: entering calculator runtime"

    def wait_runtime(count: int) -> None:
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if uart.is_file() and uart.read_bytes().count(marker) >= count:
                assert qtest.readl(0x01808080) == 0x030a0880
                assert qtest.readl(0x01808090) == 0x08400880
                return
            if process.poll() is not None:
                break
            time.sleep(.05)
        raise AssertionError(f"reset cycle failed to reach runtime #{count}: "
                             f"{uart.read_text(errors='replace')[-1600:]}")

    try:
        qtest = recovery.QTest(qtest_path)
        qmp = recovery.QMP(qmp_path)
        usb = PrimeUSBHost(usb_path)
        usb.command("CONNECT")
        wait_runtime(1)
        for count in (2, 3):
            recovery.arm_rom_usb_boot(qtest)
            qtest.writew(recovery.WDOG1_WCR, 4)
            deadline = time.monotonic() + 5
            while "mode=rom-sdp" not in usb.command("STATUS"):
                if time.monotonic() >= deadline:
                    raise AssertionError("NAND-booted Lefony did not enter SDP")
                time.sleep(.01)
            # A normal reset must re-read NAND after clearing retained bmode.
            qtest.writel(recovery.SRC_GPR9, 0)
            qtest.writel(recovery.SRC_GPR10, 0)
            qtest.writew(recovery.WDOG1_WCR, 4)
            wait_runtime(count)
        qmp.execute("system_reset")
        wait_runtime(4)
        time.sleep(1)
        screen = directory / "reset-cycle-ui.ppm"
        qmp.execute("screendump", {"filename": str(screen)})
        assert_visible_panel(screen)
    finally:
        for client in (usb, qmp, qtest):
            if client is not None:
                client.close()
        stop(process)


def test_sdp_uboot_to_lefony(directory: Path) -> None:
    """Recover a failed NAND ROM boot using the real U-Boot binary over USB."""
    recovery = importlib.import_module("test-prime-g2-rom-recovery")
    records: dict[int, bytearray] = {}
    for page in (0, 64, 128, 192):
        record = read_record(page)
        record[26] ^= 1
        records[page] = record
    add_image_records(records, 2048, CURRENT_CAPSULE.read_bytes())
    overlay = directory / "sdp-uboot.overlay"
    write_overlay(overlay, records)
    uart = directory / "sdp-uboot-uart.log"
    usb_path = directory / "sdp-uboot-usb.sock"
    qmp_path = directory / "sdp-uboot-qmp.sock"
    process = subprocess.Popen(command(overlay, usb_path, f"file:{uart}", qmp_path),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with PrimeUSBHost(usb_path) as usb:
            usb.connect_and_enumerate()
            assert "mode=rom-sdp" in usb.command("STATUS")
            image = captured_uboot()
            patch_manufacturing_command(image, safe=True)
            ivt = 0x400
            self_address = struct.unpack_from("<I", image, ivt + 20)[0]
            start = self_address - ivt
            dcd_address = struct.unpack_from("<I", image, ivt + 12)[0]
            dcd_offset = dcd_address - start
            dcd_size = int.from_bytes(image[dcd_offset + 1:dcd_offset + 3], "big")
            dcd = image[dcd_offset:dcd_offset + dcd_size]
            recovery.sdp_command(usb, 0x0a0a, 0x00910000, len(dcd))
            usb.control_out(0x21, 9, 0x202, payload=b"\x02" + dcd)
            recovery.sdp_security(usb)
            assert usb.endpoint_in(1, 65) == bytes.fromhex("04128a8a12")
            recovery.sdp_command(usb, 0x0c0c)
            recovery.sdp_security(usb)
            assert usb.endpoint_in(1, 65) == bytes.fromhex("0409d00d90")
            recovery.sdp_download(usb, start, image)
            recovery.sdp_command(usb, 0x0b0b, self_address)
            recovery.sdp_security(usb)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if uart.is_file() and b"Lefony OS: entering calculator runtime" in uart.read_bytes():
                break
            time.sleep(.05)
        else:
            raise AssertionError(f"SDP U-Boot did not reach Lefony: {uart.read_text()[-1600:]}")
        time.sleep(1)
        qmp = recovery.QMP(qmp_path)
        try:
            screen = directory / "sdp-uboot-ui.ppm"
            qmp.execute("screendump", {"filename": str(screen)})
            assert_visible_panel(screen)
        finally:
            qmp.close()
    finally:
        stop(process)


def test_secondary_firmware_fallback(directory: Path) -> None:
    record = read_record(512)
    record[0x400] ^= 1  # invalidate firmware 1's IVT header
    overlay = directory / "bad-primary-firmware.overlay"
    write_overlay(overlay, {512: record})
    output = run_until(b"Lefony OS: entering calculator runtime", overlay)
    if b"firmware 1 rejected" not in output:
        raise AssertionError("ROM did not report rejecting firmware copy 1")
    if b"loaded 389120 bytes from NAND page 1280" not in output:
        raise AssertionError("ROM did not boot the redundant firmware copy")


def test_invalid_dcd_falls_back_to_secondary(directory: Path) -> None:
    record = read_record(512)
    record[0x42c] ^= 1  # invalidate firmware 1's DCD header tag
    overlay = directory / "bad-primary-dcd.overlay"
    write_overlay(overlay, {512: record})
    output = run_until(b"Lefony OS: entering calculator runtime", overlay)
    if b"invalid DCD header" not in output:
        raise AssertionError("ROM did not reject the invalid primary DCD")
    if b"loaded 389120 bytes from NAND page 1280" not in output:
        raise AssertionError("ROM did not use firmware 2 after a bad DCD")


def test_physical_bad_block_marker_is_skipped(directory: Path) -> None:
    # Block 7 (pages 448..511) is physically marked bad in the exact capture.
    # Point firmware 1 at that block; a real NAND ROM skips it and begins
    # consuming the unchanged stream at page 512.
    record = read_record(0)
    struct.pack_into("<I", record, 22 + 0x68, 448)
    overlay = directory / "firmware-starts-on-bad-block.overlay"
    write_overlay(overlay, {0: record})
    output = run_until(b"Lefony OS: entering calculator runtime", overlay)
    if b"skipped 1 marked block" not in output:
        raise AssertionError("ROM ignored the physical NAND bad-block marker")
    if b"U-Boot 2018.03" not in output:
        raise AssertionError("ROM did not recover the stream after the bad block")


def test_invalid_fcb_falls_back_to_sdp(directory: Path) -> None:
    records: dict[int, bytearray] = {}
    for page in (0, 64, 128, 192):
        record = read_record(page)
        record[26] ^= 1  # FCB fingerprint begins at projected byte 26
        records[page] = record
    overlay = directory / "bad-fcbs.overlay"
    write_overlay(overlay, records)
    usb_path = directory / "rom-usb.sock"
    process = subprocess.Popen(
        command(overlay, usb_path), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    try:
        with PrimeUSBHost(usb_path) as usb:
            if usb.command("CONNECT") != "OK":
                raise AssertionError("could not connect the emulated USB host")
            deadline = time.monotonic() + 5
            status = ""
            while time.monotonic() < deadline:
                status = usb.command("STATUS")
                if "mode=rom-sdp" in status:
                    break
                time.sleep(0.01)
            if "mode=rom-sdp" not in status or "vid=15a2 pid=0080" not in status:
                raise AssertionError(f"invalid NAND did not enter i.MX SDP: {status}")
            device, _ = usb.connect_and_enumerate()
            if device[8:12] != bytes.fromhex("a2158000"):
                raise AssertionError(f"unexpected SDP USB identity: {device.hex()}")
    finally:
        output = stop(process)
    if b"no valid i.MX6ULL NAND FCB/DBBT/IVT boot chain" not in output:
        raise AssertionError("ROM failure reason was not observable")
    if b"U-Boot" in output:
        raise AssertionError("invalid FCB unexpectedly executed U-Boot")


def main() -> int:
    if not QEMU.is_file():
        raise SystemExit(f"Prime G2 QEMU is missing: {QEMU}")
    if not NAND.is_file():
        raise SystemExit(f"exact Prime G2 raw NAND capture is missing: {NAND}")
    if not CURRENT_CAPSULE.is_file():
        raise SystemExit(f"current Lefony capsule is missing: {CURRENT_CAPSULE}")
    for required in (
            AB_UBOOT, PHYSICAL_DTB, PHYSICAL_AB / "fcb-page.bin",
            PHYSICAL_AB / "slot-a.readback",
            PHYSICAL_AB / "metadata-a.readback",
            PHYSICAL_AB / "metadata-b.readback"):
        if not required.is_file():
            raise SystemExit(f"physical boot-stack evidence is missing: {required}")
    expected = TOTAL_PAGES * PAGE_BYTES
    if NAND.stat().st_size != expected:
        raise SystemExit(
            f"exact NAND capture has wrong size: {NAND.stat().st_size} != {expected}")
    with tempfile.TemporaryDirectory(prefix="lefony-nand-rom-") as tmp:
        directory = Path(tmp)
        test_exact_chain()
        test_visible_runtime(directory)
        test_environment_truncation_regression(directory)
        test_repaired_physical_ab_stack(directory)
        test_recovery_exit_boots_nand(directory)
        test_sdp_uboot_to_lefony(directory)
        test_secondary_firmware_fallback(directory)
        test_invalid_dcd_falls_back_to_secondary(directory)
        test_physical_bad_block_marker_is_skipped(directory)
        test_invalid_fcb_falls_back_to_sdp(directory)
    print("PASS: i.MX6ULL DCD + NAND FCB/DBBT -> bad-block-aware redundant "
          "U-Boot -> current Lefony UI; reproduced the historical packed-env "
          "black-screen regression and cold-booted both legacy and captured "
          "A/B repairs; recovery exits re-boot NAND; SDP DCD/download/jump "
          "boots the captured U-Boot to Lefony; invalid boot control falls "
          "back to ROM SDP 15a2:0080")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
