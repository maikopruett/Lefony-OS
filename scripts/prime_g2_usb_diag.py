#!/usr/bin/env python3
"""Read bare-metal Lefony OS/Prime G2 hardware diagnostics over USB EP0."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import json
import hashlib
import struct
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prime_g2_update_capsule as update_capsule


VID = 0xCAFE
PID = 0x5052
REQUEST_INFO = 0x40
REQUEST_EVENT = 0x41
REQUEST_SNAPSHOT = 0x42
REQUEST_RECOVERY_INFO = 0x43
REQUEST_RECOVERY_BEGIN = 0x44
REQUEST_RECOVERY_CHUNK = 0x45
REQUEST_RECOVERY_FINISH = 0x46
REQUEST_RECOVERY_ABORT = 0x47
REQUEST_UPDATE_STATUS = 0x48
REQUEST_UPDATE_MANIFEST = 0x48
REQUEST_UPDATE_COMMIT = 0x49
REQUEST_UPDATE_REBOOT = 0x4B
REQUEST_UPDATE_RECOVERY = 0x4C
REQUEST_DEVELOPMENT_RECOVERY = 0x4E
REQUEST_NAND_PROBE = 0x50
FLAG_DIRECT_INSTALL = 1 << 8
FLAG_RECOVERY_INSTALL = 1 << 9
INFO_MAGIC = 0x4D474449
EVENT_MAGIC = 0x4D474445
SNAPSHOT_MAGIC = 0x4D475253

EVENT_NAMES = {
    0x0001: "BOOT_START",
    0x00FD: "FATAL_FAULT_REGISTERS",
    0x00FE: "FATAL_ABORT",
    0x00FF: "FATAL_EXCEPTION",
    0x0101: "USB_CLOCK",
    0x0102: "USB_PHY_RESET",
    0x0103: "USB_CONTROLLER_RESET",
    0x0104: "USB_STARTED",
    0x0105: "USB_BUS_RESET",
    0x0106: "USB_SETUP",
    0x0107: "USB_CONFIGURED",
    0x01FF: "USB_ERROR",
    0x0201: "DISPLAY_INIT_START",
    0x0202: "DISPLAY_PINS_READY",
    0x0203: "DISPLAY_CLOCK_READY",
    0x0210: "PANEL_RESET_HIGH",
    0x0211: "PANEL_RESET_LOW",
    0x0212: "PANEL_RESET_RELEASED",
    0x0213: "PANEL_REGISTER_WRITE",
    0x0214: "PANEL_READY",
    0x0220: "LCDIF_RESET_STEP",
    0x0221: "LCDIF_RESET_FAILED",
    0x0222: "LCDIF_CONFIGURED",
    0x0223: "LCDIF_STARTED",
    0x0224: "FRAME_SWAP_TIMEOUT",
    0x0225: "FRAME_SWAP_RECOVERED",
    0x02FE: "LCDIF_FAULT",
    0x02FF: "DISPLAY_INIT_COMPLETE",
    0x0301: "BACKLIGHT_READY",
    0x0401: "ION_MAIN_ENTRY",
    0x0402: "BOOT_PROGRESS",
}

SNAPSHOT_NAMES = [
    "magic", "protocol", "first_sequence", "next_sequence",
    "anatop_pll_usb1", "ccm_cbcmr", "ccm_cscdr2", "ccm_ccgr2",
    "ccm_ccgr3", "ccm_ccgr6", "lcdif_ctrl", "lcdif_ctrl1",
    "lcdif_ctrl2", "lcdif_transfer_count", "lcdif_cur_buf",
    "lcdif_next_buf", "lcdif_timing", "lcdif_vdctrl0",
    "lcdif_vdctrl1", "lcdif_vdctrl2", "lcdif_vdctrl3",
    "lcdif_vdctrl4", "lcdif_debug0", "iomux_lcd_clk",
    "iomux_lcd_reset", "iomux_panel_sck", "iomux_panel_cs",
    "iomux_panel_mosi", "gpio3_dr", "gpio3_gdir", "gpio4_dr",
    "gpio4_gdir", "pwm7_cr", "pwm7_sar", "pwm7_pr",
    "usbphy_pwd", "usbphy_tx", "usbphy_ctrl", "usbnc_ctrl0",
    "usbnc_phy_ctrl", "usb_usbcmd", "usb_usbsts", "usb_usbintr",
    "usb_deviceaddr", "usb_endptlistaddr", "usb_portsc1", "usb_otgsc",
    "usb_usbmode", "usb_setupstat", "usb_prime", "usb_flush",
    "usb_endptstat", "usb_complete", "usb_endptctrl0", "fb_pixel_0_0",
    "fb_pixel_1_0", "fb_pixel_0_1", "fb_pixel_center",
    "fb_pixel_bottom_right", "battery_adc_raw", "battery_mv",
    "battery_status", "adc1_cfg", "adc1_gc",
]


class USBError(RuntimeError):
    pass


class LibUSB:
    def __init__(self, vid: int = VID, pid: int = PID) -> None:
        candidates = [
            ctypes.util.find_library("usb-1.0"),
            "/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib",
            "/usr/local/opt/libusb/lib/libusb-1.0.dylib",
        ]
        path = next((candidate for candidate in candidates if candidate), None)
        if path is None:
            raise USBError("libusb-1.0 is not installed")
        self.lib = ctypes.CDLL(path)
        self.lib.libusb_init.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        self.lib.libusb_init.restype = ctypes.c_int
        self.lib.libusb_exit.argtypes = [ctypes.c_void_p]
        self.lib.libusb_open_device_with_vid_pid.argtypes = [
            ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16
        ]
        self.lib.libusb_open_device_with_vid_pid.restype = ctypes.c_void_p
        self.lib.libusb_close.argtypes = [ctypes.c_void_p]
        self.lib.libusb_control_transfer.argtypes = [
            ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint8,
            ctypes.c_uint16, ctypes.c_uint16,
            ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint16,
            ctypes.c_uint,
        ]
        self.lib.libusb_control_transfer.restype = ctypes.c_int
        self.context = ctypes.c_void_p()
        result = self.lib.libusb_init(ctypes.byref(self.context))
        if result < 0:
            raise USBError(f"libusb_init failed: {result}")
        self.handle = self.lib.libusb_open_device_with_vid_pid(
            self.context, vid, pid
        )
        if not self.handle:
            self.lib.libusb_exit(self.context)
            raise USBError(
                f"USB device {vid:04X}:{pid:04X} not found or inaccessible"
            )

    def close(self) -> None:
        if getattr(self, "handle", None):
            self.lib.libusb_close(self.handle)
            self.handle = None
        if getattr(self, "context", None):
            self.lib.libusb_exit(self.context)
            self.context = None

    def read(self, request: int, value: int = 0, index: int = 0,
             length: int = 64) -> bytes:
        buffer = (ctypes.c_ubyte * length)()
        result = self.lib.libusb_control_transfer(
            self.handle, 0xC0, request, value, index, buffer, length, 1500
        )
        if result < 0:
            raise USBError(
                f"control request 0x{request:02X} failed: libusb {result}"
            )
        return bytes(buffer[:result])

    def write(self, request: int, data: bytes = b"", value: int = 0,
              index: int = 0, timeout_ms: int = 3000) -> None:
        length = len(data)
        buffer = (ctypes.c_ubyte * max(length, 1))()
        if length:
            buffer[:length] = data
        result = self.lib.libusb_control_transfer(
            self.handle, 0x40, request, value, index, buffer, length, timeout_ms
        )
        if result < 0:
            raise USBError(
                f"control request 0x{request:02X} failed: libusb {result}"
            )
        if result != length:
            raise USBError(f"short recovery write: {result} of {length} bytes")

    def __enter__(self) -> "LibUSB":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def decode_info(data: bytes) -> dict[str, int]:
    if len(data) != 64:
        raise USBError(f"short INFO response: {len(data)} bytes")
    values = struct.unpack("<16I", data)
    if values[0] != INFO_MAGIC:
        raise USBError(f"invalid INFO magic: 0x{values[0]:08X}")
    names = [
        "magic", "protocol", "status", "first_sequence", "next_sequence",
        "event_size", "snapshot_size", "event_capacity", "usb_portsc1",
        "usb_usbsts", "usb_usbmode", "usb_endptctrl0", "lcdif_ctrl",
        "lcdif_ctrl1", "lcdif_debug0", "reserved",
    ]
    return dict(zip(names, values))


def decode_event(data: bytes) -> dict[str, int | str]:
    if len(data) != 28:
        raise USBError(f"invalid event size: {len(data)}")
    magic, sequence, timestamp, code, value0, value1, value2 = struct.unpack(
        "<7I", data
    )
    if magic != EVENT_MAGIC:
        raise USBError(f"invalid event magic: 0x{magic:08X}")
    return {
        "sequence": sequence,
        "timestamp_ms": timestamp,
        "code": code,
        "name": EVENT_NAMES.get(code, f"UNKNOWN_0x{code:04X}"),
        "value0": value0,
        "value1": value1,
        "value2": value2,
    }


def decode_snapshot(data: bytes) -> dict[str, int]:
    if len(data) != 256:
        raise USBError(f"invalid snapshot size: {len(data)}")
    values = struct.unpack("<64I", data)
    if values[0] != SNAPSHOT_MAGIC:
        raise USBError(f"invalid snapshot magic: 0x{values[0]:08X}")
    return dict(zip(SNAPSHOT_NAMES, values))


def elapsed_millis(device: LibUSB) -> int:
    """Read sleep-aware battery scheduling time without modifying the clock."""
    data = device.read(0x55, value=2, length=16)
    if len(data) != 16:
        raise USBError("invalid elapsed clock size")
    magic, version, low, high = struct.unpack("<4I", data)
    if (magic, version) != (0x3143544c, 1):
        raise USBError("invalid elapsed clock version")
    return (high << 32) | low


def battery_display_status(device: LibUSB) -> dict[str, int]:
    data = device.read(0x55, value=1, length=16)
    if len(data) != 16:
        raise USBError("invalid battery display status size")
    magic, version, level, percent = struct.unpack("<4I", data)
    if (magic, version) != (0x3154424c, 1) or level > 3 or percent > 100:
        raise USBError("invalid battery display status")
    return {"level": level, "percent": percent}


def battery_diagnostics(device: LibUSB) -> dict[str, int]:
    data = device.read(0x55, length=96)
    if len(data) != 96:
        raise USBError("invalid battery diagnostic size")
    values = struct.unpack("<24I", data)
    if values[:2] != (0x3154424c, 1):
        raise USBError("invalid battery diagnostic version")
    names = ("magic", "version", "millis", "cpu_cycles", "gpt_cr", "gpt_pr",
             "gpt_count", "ccgr1", "adc_hc0", "adc_hs", "adc_cfg", "adc_gc",
             "adc_gs", "adc_initialized", "adc_pending", "raw", "millivolts",
             "valid", "snvs_lpcr", "snvs_rtc_high", "snvs_rtc_low", "cscmr1",
             "clpcr", "gpt_sr")
    return dict(zip(names, values))


def collect(device: LibUSB) -> dict[str, object]:
    info = decode_info(device.read(REQUEST_INFO, length=64))
    events = []
    for sequence in range(info["first_sequence"], info["next_sequence"]):
        events.append(decode_event(device.read(
            REQUEST_EVENT, sequence & 0xFFFF, sequence >> 16,
            info["event_size"],
        )))
    snapshot_bytes = bytearray()
    for offset in range(0, info["snapshot_size"], 64):
        snapshot_bytes.extend(device.read(
            REQUEST_SNAPSHOT, offset, 0,
            min(64, info["snapshot_size"] - offset),
        ))
    snapshot = decode_snapshot(bytes(snapshot_bytes))
    return {"info": info, "events": events, "snapshot": snapshot}


def recovery_info(device: LibUSB) -> dict[str, int]:
    data = device.read(REQUEST_RECOVERY_INFO, length=32)
    if len(data) != 32:
        raise USBError(f"short recovery status: {len(data)} bytes")
    values = struct.unpack("<8I", data)
    if values[0] != 0x4D475243:
        raise USBError(f"invalid recovery magic: 0x{values[0]:08X}")
    names = ("magic", "protocol", "state", "capacity", "length",
             "received", "crc32", "max_chunk")
    return dict(zip(names, values))


def ion_crc32(payload: bytes) -> int:
    """Match Ion::crc32Byte, including its reversed 32-bit word traversal."""
    crc = 0xFFFFFFFF
    complete = len(payload) // 4 * 4
    ordered = bytearray()
    for offset in range(0, complete, 4):
        ordered.extend(reversed(payload[offset:offset + 4]))
    ordered.extend(payload[complete:])
    for byte in ordered:
        crc ^= byte << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF \
                if crc & 0x80000000 else (crc << 1) & 0xFFFFFFFF
    return crc


def read_nand_page(device: LibUSB, page: int) -> tuple[bytes, dict[str, int]]:
    if not 2048 <= page < 6144:
        raise USBError("page outside the read-only OS qualification slot")
    device.write(0x51, value=page & 0xffff, index=page >> 16)
    raw = device.read(0x51, length=24)
    if len(raw) != 24:
        raise USBError("short NAND page status")
    status = dict(zip(("magic", "page", "error", "corrected", "marker", "ready"),
                      struct.unpack("<6I", raw)))
    if status["magic"] != 0x3152504c or status["page"] != page or \
       status["error"] or status["ready"] != 1:
        raise USBError(f"NAND page read rejected: {status}")
    chunks = [device.read(0x52, value=offset, length=512)
              for offset in range(0, 2048, 512)]
    if any(len(chunk) != 512 for chunk in chunks):
        raise USBError("short NAND page data")
    return b"".join(chunks), status


def verify_nand_image(device: LibUSB, path: Path, progress=None) -> dict[str, object]:
    expected = path.read_bytes()
    if not 0x30 <= len(expected) <= 8 * 1024 * 1024 or \
       struct.unpack_from("<I", expected, 0x24)[0] != 0x016f2818 or \
       struct.unpack_from("<I", expected, 0x2c)[0] != len(expected):
        raise USBError("invalid reference recovery capsule")
    digest = hashlib.sha256()
    corrected = 0
    pages = (len(expected) + 2047) // 2048
    for index in range(pages):
        page, status = read_nand_page(device, 2048 + index)
        # Initial qualification refuses bad-block remapping instead of hiding
        # a physical/logical address mismatch. Support follows separate tests.
        if index % 64 in (0, 1) and status["marker"] != 0xff:
            raise USBError(f"bad block marker at page {2048 + index}; mapping qualification required")
        offset = index * 2048
        wanted = expected[offset:offset + 2048]
        actual = page[:len(wanted)]
        if actual != wanted:
            mismatch = next(i for i, (a, b) in enumerate(zip(actual, wanted)) if a != b)
            raise USBError(f"NAND differs from reference at image byte {offset + mismatch:#x}")
        digest.update(actual)
        corrected += status["corrected"]
        if progress:
            progress(min(offset + 2048, len(expected)), len(expected))
    return {"verified_bytes": len(expected), "pages": pages,
            "sha256": digest.hexdigest(), "corrected_bits": corrected,
            "nand_writes": False}


def probe_nand(device: LibUSB) -> dict[str, object]:
    """READID and controller snapshot only; no erase/program/reset of NAND."""
    device.write(REQUEST_NAND_PROBE, value=0x4e50)
    data = device.read(REQUEST_NAND_PROBE, length=72)
    if len(data) != 72:
        raise USBError(f"invalid NAND probe report length: {len(data)}")
    names = ("magic", "version", "error", "phase", "id0", "id1",
             "apbh_control", "apbh_irq", "apbh_error", "semaphore",
             "gpmi_control", "gpmi_control1", "gpmi_timing0", "gpmi_timing1",
             "gpmi_status", "bch_layout0", "bch_layout1", "bch_select")
    report = dict(zip(names, struct.unpack("<18I", data)))
    if report["magic"] != 0x31504e4c or report["version"] != 1:
        raise USBError("unsupported NAND probe report")
    report["nand_id_hex"] = data[16:24].hex()
    report["probe_wrote_nand"] = False
    return report


def development_capabilities(device: LibUSB) -> dict[str, int]:
    try:
        data = device.read(REQUEST_DEVELOPMENT_RECOVERY, length=16)
    except USBError as error:
        raise USBError("installed OS lacks development USB handoff; install the "
                       "bootstrap build once through ROM recovery") from error
    if len(data) != 16:
        raise USBError("invalid development USB capabilities length")
    magic, version, flags, capacity = struct.unpack("<4I", data)
    if magic != 0x3156444c or version != 1 or not flags & 1:
        raise USBError("unsupported development USB handoff protocol")
    return {"version": version, "flags": flags, "capacity": capacity}


def native_install_status(device: LibUSB) -> dict[str, int]:
    data = device.read(0x53, length=32)
    if len(data) != 32:
        raise USBError("short native install status")
    result = dict(zip(("magic", "version", "state", "done", "total", "error", "changed", "crc"),
                      struct.unpack("<8I", data)))
    if result["magic"] != 0x3155444c or result["version"] != 1:
        raise USBError("unsupported native install status")
    return result


def install_native_capsule(device: LibUSB, path: Path, progress=None) -> dict[str, int]:
    if not development_capabilities(device)["flags"] & 2:
        raise USBError("installed firmware has no native NAND writer")
    staged = stage_capsule(device, path,
        (lambda done, total: progress("receiving", done, total)) if progress else None)
    device.write(0x53, value=staged["crc32"] & 0xffff, index=staged["crc32"] >> 16)
    deadline = time.monotonic() + 300
    names = {4: "checking", 5: "erasing", 6: "writing", 7: "verifying", 8: "verified"}
    while time.monotonic() < deadline:
        status = native_install_status(device)
        if status["state"] == 9:
            raise USBError(f"native installation stopped: {status}; keep power connected")
        if progress:
            progress(names.get(status["state"], "starting"), status["done"], status["total"])
        if status["state"] == 8:
            if status["total"] != staged["length"] or status["done"] != staged["length"] or \
               status["crc"] != staged["crc32"]:
                raise USBError("native install completion does not match transferred image")
            return status
        time.sleep(0.1)
    raise USBError("native installation not confirmed; keep power connected, do not reset")


def request_development_recovery(device: LibUSB, staged: dict[str, int]) -> None:
    if staged["state"] != 2 or staged["received"] != staged["length"]:
        raise USBError("development handoff requires a fully CRC-verified image")
    checksum = staged["crc32"]
    device.write(REQUEST_DEVELOPMENT_RECOVERY, value=checksum & 0xFFFF,
                 index=checksum >> 16, timeout_ms=10000)


def stage_capsule(device: LibUSB, path: Path, progress=None) -> dict[str, int]:
    """Upload to volatile RAM only; progress(received, total) follows each ACK.

    Never retry an ambiguous OUT transfer: the device may have consumed it.
    Abort on failure so the next attempt starts at a known offset.
    """
    payload = path.read_bytes()
    if len(payload) < 0x30 or struct.unpack_from("<I", payload, 0x24)[0] != 0x016F2818 \
       or struct.unpack_from("<I", payload, 0x2C)[0] != len(payload):
        raise USBError("invalid native zImage capsule header or declared length")
    status = recovery_info(device)
    if len(payload) > status["capacity"]:
        raise USBError(
            f"capsule is {len(payload)} bytes; device capacity is {status['capacity']}"
        )
    chunk_size = min(status["max_chunk"], 512)
    if chunk_size <= 0:
        raise USBError("device advertised an invalid transfer chunk size")
    checksum = ion_crc32(payload)
    try:
        device.write(REQUEST_RECOVERY_BEGIN, value=len(payload) & 0xFFFF,
                     index=len(payload) >> 16)
        if progress:
            progress(0, len(payload))
        for offset in range(0, len(payload), chunk_size):
            chunk = payload[offset:offset + chunk_size]
            device.write(REQUEST_RECOVERY_CHUNK, chunk, offset & 0xFFFF,
                         offset >> 16)
            if progress:
                progress(offset + len(chunk), len(payload))
        device.write(REQUEST_RECOVERY_FINISH, value=checksum & 0xFFFF,
                     index=checksum >> 16)
        status = recovery_info(device)
        if status["state"] != 2 or status["received"] != len(payload) or \
           status["crc32"] != checksum:
            raise USBError(f"device rejected staged capsule: {status}")
    except (Exception, KeyboardInterrupt):
        try:
            device.write(REQUEST_RECOVERY_ABORT)
        except Exception:
            pass  # Preserve the original failure, including disconnect errors.
        raise
    return status


def update_status(device: LibUSB) -> dict[str, object]:
    data = device.read(REQUEST_UPDATE_STATUS, length=64)
    if len(data) != 64:
        raise USBError(f"short A/B update status: {len(data)} bytes")
    values = struct.unpack("<16I", data)
    if values[0] != 0x31554241:
        raise USBError(f"invalid A/B update status magic: 0x{values[0]:08X}")
    states = ("idle", "manifest-ready", "capsule-ready", "installing",
              "pending-reboot", "confirmed", "error")
    state = states[values[2]] if values[2] < len(states) else f"unknown-{values[2]}"
    return {
        "magic": values[0], "protocol": values[1], "state_code": values[2],
        "state": state, "error": values[3], "active_slot": values[4],
        "pending_slot": None if values[5] == 0xFFFFFFFF else values[5],
        "attempts": values[6], "boot_limit": values[7],
        "version": tuple(values[8:12]), "total_bytes": values[12],
        "written_bytes": values[13], "generation": values[14], "flags": values[15],
    }


def install_signed_capsule(device: LibUSB, path: Path,
                           reboot: bool = False) -> dict[str, object]:
    package = update_capsule.inspect(path)
    raw = path.read_bytes()
    manifest = raw[:update_capsule.SIGNED_PREFIX.size + update_capsule.SIGNATURE_BYTES]
    device.write(REQUEST_UPDATE_MANIFEST, manifest, timeout_ms=30000)
    status = update_status(device)
    if status["state"] != "manifest-ready":
        raise USBError(f"device rejected signed update manifest: {status}")

    with tempfile.NamedTemporaryFile(suffix=".zImage") as staged:
        staged.write(package.payload)
        staged.flush()
        stage_capsule(device, Path(staged.name))
    status = update_status(device)
    if status["state"] != "capsule-ready":
        raise USBError(f"device rejected signed update payload: {status}")
    flags = int(status["flags"])
    if flags & FLAG_DIRECT_INSTALL:
        device.write(REQUEST_UPDATE_COMMIT, timeout_ms=120000)
        status = update_status(device)
        if status["state"] != "pending-reboot" or status["pending_slot"] is None:
            raise USBError(f"device failed to commit inactive A/B slot: {status}")
        status["handoff"] = "direct"
        if reboot:
            device.write(REQUEST_UPDATE_REBOOT, timeout_ms=10000)
    elif flags & FLAG_RECOVERY_INSTALL:
        status["handoff"] = "recovery"
        status["target_slot"] = 1 - int(status["active_slot"])
        if reboot:
            device.write(REQUEST_UPDATE_RECOVERY, timeout_ms=10000)
    else:
        raise USBError("device exposes no supported authenticated install path")
    return status


def analyze(report: dict[str, object]) -> list[str]:
    info = report["info"]
    events = report["events"]
    snapshot = report["snapshot"]
    assert isinstance(info, dict) and isinstance(events, list)
    assert isinstance(snapshot, dict)
    names = {event["name"] for event in events}
    conclusions: list[str] = []

    status = int(info["status"])
    fatal = next((event for event in reversed(events)
                  if event["name"] == "FATAL_EXCEPTION"), None)
    if fatal is not None:
        conclusions.append(
            "CPU exception captured: "
            f"type={fatal['value0']} PC=0x{fatal['value1']:08X} "
            f"CPSR=0x{fatal['value2']:08X}."
        )
    if "FATAL_ABORT" in names:
        conclusions.append("Upsilon called abort(); inspect the events immediately before it.")
    if status & (1 << 31):
        conclusions.append("USB diagnostic transport reported an initialization or transfer error.")
    elif (status & 0x7) == 0x7:
        conclusions.append("USB clock, PHY, and ChipIdea controller initialized successfully.")

    if "LCDIF_RESET_FAILED" in names:
        conclusions.append("LCDIF reset handshake failed; inspect the failing reset-step event.")
    elif "LCDIF_STARTED" in names:
        conclusions.append("LCDIF initialization reached RUN state.")
    else:
        conclusions.append("Boot did not reach LCDIF start; the final event identifies the stopping stage.")

    ctrl = int(snapshot["lcdif_ctrl"])
    ctrl1 = int(snapshot["lcdif_ctrl1"])
    if not (ctrl & 1):
        conclusions.append("LCDIF RUN is clear: no pixel stream is being generated.")
    if ctrl & ((1 << 31) | (1 << 30)):
        conclusions.append("LCDIF remains reset or clock-gated.")
    if ctrl1 & (1 << 10):
        conclusions.append("LCDIF FIFO underflow occurred; pixel clock or AXI fetch is invalid.")
    if ctrl1 & (1 << 11):
        conclusions.append("LCDIF FIFO overflow occurred.")
    if int(snapshot["lcdif_transfer_count"]) != ((240 << 16) | 960):
        conclusions.append("LCDIF transfer count is not the Prime's required 240x960 serialized stream.")
    # Both guarded scanout buffers are valid after frame-boundary presentation.
    if int(snapshot["lcdif_cur_buf"]) not in (0x8F000040, 0x8F04B0C0):
        conclusions.append("LCDIF current framebuffer address is wrong.")

    pixels = [int(snapshot[name]) & 0xFFFFFF for name in (
        "fb_pixel_0_0", "fb_pixel_1_0", "fb_pixel_0_1",
        "fb_pixel_center", "fb_pixel_bottom_right",
    )]
    if len(set(pixels)) == 1 and pixels[0] == 0xFFFFFF:
        conclusions.append("Framebuffer samples are still entirely white; UI rendering did not replace the boot clear.")
    elif any(pixel != 0xFFFFFF for pixel in pixels):
        conclusions.append("Framebuffer contains rendered non-white pixels; the fault is downstream in LCDIF timing, pins, panel SPI, reset, power, or the panel itself.")

    if not (int(snapshot["gpio3_gdir"]) & (1 << 4)):
        conclusions.append("Panel RESET GPIO is not configured as an output.")
    elif not (int(snapshot["gpio3_dr"]) & (1 << 4)):
        conclusions.append("Panel RESET is still asserted low.")

    battery = int(snapshot["battery_status"])
    battery_raw = int(snapshot["battery_adc_raw"])
    battery_mv = int(snapshot["battery_mv"])
    charger_operation = (battery >> 24) & 0xFF
    charger_state = (battery >> 8) & 0x0F
    external_power = bool(battery & (1 << 16))
    battery_present = bool(battery & (1 << 18))
    calibrated = bool(battery & (1 << 21))
    charger_configured = bool(battery & (1 << 22))
    pmic_available = bool(battery_mv & (1 << 30))
    telemetry_fresh = bool(battery_mv & (1 << 31))
    vbus_sense = (battery_raw >> 16) & 0xFF
    if not pmic_available:
        conclusions.append("PF1550 did not answer the most recent battery refresh.")
    elif not telemetry_fresh:
        conclusions.append(
            "PF1550 battery telemetry is incomplete; charging is suppressed."
        )
    if vbus_sense & (1 << 2) and external_power:
        conclusions.append(
            "PF1550 VBUS_SNS reports UVLO while cached external power is set."
        )
    if external_power and battery_present and (charger_operation & 3) != 2:
        conclusions.append(
            f"Battery and VBUS are present but CHG_OPER is mode "
            f"{charger_operation & 3}; battery charging is disabled."
        )
    if not charger_configured:
        conclusions.append("PF1550 charger mode was not read-back verified.")
    if battery_present and not calibrated:
        conclusions.append(
            "Battery is detected but ADC1 has not produced a calibrated "
            "ten-sample voltage estimate."
        )
    if external_power and battery_present and charger_state in (6, 7, 9, 10, 12):
        conclusions.append(f"PF1550 reports charger fault/suspend state {charger_state}.")

    if not conclusions:
        conclusions.append("No software-visible fault bit is asserted; capture the pixel clock/data/SPI lines with a logic analyzer next.")
    return conclusions


def print_report(report: dict[str, object]) -> None:
    info = report["info"]
    events = report["events"]
    snapshot = report["snapshot"]
    assert isinstance(info, dict) and isinstance(events, list)
    assert isinstance(snapshot, dict)
    print(f"Lefony OS Prime G2 diagnostics protocol {info['protocol']}")
    print(f"USB status: 0x{int(info['status']):08X}")
    print("\nBoot events:")
    for event in events:
        print(
            f"  {event['sequence']:03d} {event['timestamp_ms']:8d} ms "
            f"{event['name']:<24} "
            f"{event['value0']:08X} {event['value1']:08X} {event['value2']:08X}"
        )
    print("\nKey register snapshot:")
    for name in SNAPSHOT_NAMES[4:64]:
        print(f"  {name:<25} 0x{int(snapshot[name]):08X}")
    battery = int(snapshot["battery_status"])
    battery_raw = int(snapshot["battery_adc_raw"])
    battery_mv = int(snapshot["battery_mv"])
    print("\nBattery/charger:")
    print(f"  ADC raw / converted       {battery_raw & 0xFFFF} / {battery_mv & 0xFFFF} mV")
    print(f"  VBUS_SNS / CHG_INT_OK     0x{(battery_raw >> 16) & 0xFF:02X} / 0x{(battery_raw >> 24) & 0xFF:02X}")
    print(f"  displayed estimate        {battery & 0xFF}%")
    print(f"  CHG_SNS / BATT_SNS        {(battery >> 8) & 0xF} / {(battery >> 12) & 0x7}")
    print(f"  CHG_OPER                  0x{(battery >> 24) & 0xFF:02X}")
    print(
        "  ext/charging/present/full/fault/calibrated/configured "
        + "/".join(str((battery >> bit) & 1) for bit in range(16, 23))
    )
    print(
        "  PMIC available/fresh     "
        f"{(battery_mv >> 30) & 1}/{(battery_mv >> 31) & 1}"
    )
    print("\nDiagnosis:")
    for conclusion in analyze(report):
        print(f"  - {conclusion}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--battery", action="store_true",
                        help="read battery ADC and timer diagnostics without starting a conversion")
    parser.add_argument("--watch", type=float, metavar="SECONDS",
                        help="repeat collection at this interval")
    parser.add_argument("--stage", type=Path, metavar="CAPSULE",
                        help="CRC-verify and stage a native capsule in RAM")
    parser.add_argument("--nand-probe", action="store_true",
                        help="read NAND chip ID and inherited controller settings; no NAND writes")
    parser.add_argument("--verify-nand", type=Path, metavar="CAPSULE",
                        help="compare ECC-corrected OS-slot reads to an exact capsule; no writes")
    parser.add_argument("--update", type=Path, metavar="SIGNED-CAPSULE",
                        help="verify and install a signed capsule to the inactive A/B slot")
    args = parser.parse_args()
    try:
        with LibUSB() as device:
            if args.verify_nand:
                last = [-1]
                def report_progress(done, total):
                    percent = done * 100 // total
                    if percent != last[0]:
                        last[0] = percent
                        print(f"NAND readback {percent}%", file=sys.stderr)
                print(json.dumps(verify_nand_image(device, args.verify_nand, report_progress), indent=2))
                return 0
            if args.nand_probe:
                report = probe_nand(device)
                print(json.dumps(report, indent=2))
                return 0 if report["error"] == 0 else 1
            if args.update is not None:
                print(json.dumps(install_signed_capsule(device, args.update), indent=2))
                return 0
            if args.stage is not None:
                started = time.monotonic()
                last_report = -1
                def progress(received, total):
                    nonlocal last_report
                    percent = received * 100 // total
                    if percent != last_report:
                        last_report = percent
                        elapsed = time.monotonic() - started
                        print(f"RAM upload {percent:3d}% | {received}/{total} bytes | "
                              f"{elapsed:.1f}s", file=sys.stderr)
                print(json.dumps(stage_capsule(device, args.stage, progress), indent=2))
                return 0
            while True:
                report = battery_diagnostics(device) if args.battery else collect(device)
                if args.json or args.battery:
                    print(json.dumps(report, indent=2))
                else:
                    print_report(report)
                if args.watch is None:
                    break
                time.sleep(max(args.watch, 0.1))
    except USBError as error:
        print(f"prime-g2-usb-diag: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
