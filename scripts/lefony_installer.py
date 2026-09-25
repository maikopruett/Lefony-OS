#!/usr/bin/env python3
"""Native Lefony OS installer and HP Prime G2 USB monitor.

Legacy recovery operations remain limited to the documented slot A.  A
running Lefony OS may additionally authorize an Android-style A/B update: the
installer then boots the proven recovery Linux writer, writes only the
inactive provisioned slot, verifies it, and commits redundant boot metadata.
"""
from __future__ import annotations

import argparse
import curses
import glob
import hashlib
import json
import os
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prime_g2_update_capsule as update_capsule
import prime_g2_usb_diag as usb_update
import prime_g2_ab_metadata as ab_metadata
import lefony_build_history as build_history
import lefony_uboot_history as uboot_history


REPO = Path(__file__).resolve().parent.parent
DEFAULT_PRINUX = Path.home() / "prinux"
DEFAULT_IMAGE = REPO / "build" / "lefony-os-native-nand" / "lefony-os-native.lfu"
DEFAULT_BACKUP_DIR = REPO / "build" / "lefony-os-native-nand" / "backups"
DEFAULT_HISTORY_DIR = REPO / "build" / "lefony-os-history"
DEFAULT_UBOOT_HISTORY_DIR = REPO / "build" / "lefony-uboot-history"
NAND_SLOT = "/dev/mtd1"
NAND_SLOT_BYTES = 8 * 1024 * 1024
AB_MISC = "/dev/mtd3"
AB_ROOTFS = "/dev/mtd4"
AB_METADATA_ERASE_BYTES = 128 * 1024
AB_METADATA_PAGE_BYTES = 2048
AB_SLOT_B_OFFSET_IN_ROOTFS = 482 * 1024 * 1024
AB_SLOT_B_ERASE_BLOCK = AB_SLOT_B_OFFSET_IN_ROOTFS // AB_METADATA_ERASE_BYTES
MIN_IMAGE_BYTES = 1024 * 1024
ZIMAGE_MAGIC_OFFSET = 36
ZIMAGE_SIZE_OFFSET = 44
ZIMAGE_MAGIC = b"\x18\x28\x6f\x01"
UBOOT_NAND_SLOT = "/dev/mtd0"
UBOOT_PRIMARY_OFFSET = 1024 * 1024
UBOOT_SECONDARY_OFFSET = 2560 * 1024
CLEAR_RESET_ENV_KEY = b"bootcmd_mfg="
CLEAR_RESET_ENV = b"bootcmd_mfg=reset;"
LINUX_PORT_PATTERNS = (
    "/dev/cu.usbmodem*",
    "/dev/tty.usbmodem*",
    "/dev/cu.usbserial*",
    "/dev/tty.usbserial*",
)
RECOVERY_ASSETS = {
    "u-boot-dtb.imx": "boot/u-boot-dtb.imx",
    "recovery-zImage": "boot/zImage",
    "recovery.dtb": "boot/imx6ull-14x14-prime-nobbt.dtb",
    "recovery-initramfs.u-boot":
        "boot/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.gz.u-boot",
}
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


@dataclass(frozen=True)
class OperationProgress:
    phase: str
    current: int
    total: int
    percent: int
    transfer_percent: int | None = None


PROGRESS_MILESTONES: dict[str, tuple[tuple[str, str], ...]] = {
    "backup": (
        ("start cmd:sdp:", "Booting recovery Linux"),
        ("nanddump -f /tmp/lefony-os-prime-installer/pre-operation.mtd", "Reading the current NAND slot"),
        ("ucp t:/tmp/lefony-os-prime-installer/pre-operation.mtd", "Copying the backup to this Mac"),
        ("ucmd sync", "Syncing recovery storage"),
        ("===upsilon-backup-complete===", "Device-side backup complete"),
    ),
    "verify": (
        ("start cmd:sdp:", "Booting recovery Linux"),
        ("nanddump -f /tmp/lefony-os-prime-installer/pre-operation.mtd", "Reading the current NAND slot"),
        ("ucp t:/tmp/lefony-os-prime-installer/pre-operation.mtd", "Copying the safety backup to this Mac"),
        ("ucp lefony-os-native.zimage", "Uploading the selected image"),
        ("dd if=/dev/mtd1 of=/tmp/lefony-os-prime-installer/readback.mtd", "Reading the installed image"),
        ("ucmd cmp /tmp/lefony-os-prime-installer/lefony-os-native.zimage", "Comparing the installed image"),
        ("ucp t:/tmp/lefony-os-prime-installer/readback.mtd", "Copying the readback to this Mac"),
        ("===upsilon-verify-complete===", "Device-side verification complete"),
    ),
    "install": (
        ("start cmd:sdp:", "Booting recovery Linux"),
        ("nanddump -q -s 1048576", "Preflight: reading primary U-Boot"),
        ("nanddump -q -s 2621440", "Preflight: reading secondary U-Boot"),
        ("cmp /tmp/lefony-os-uboot-audit/expected-u-boot.imx", "Preflight: verifying U-Boot history baseline"),
        ("nanddump -f /tmp/lefony-os-prime-installer/pre-operation.mtd", "Reading the current NAND slot"),
        ("ucp t:/tmp/lefony-os-prime-installer/pre-operation.mtd", "Copying the safety backup to this Mac"),
        ("ucp lefony-os-native.zimage", "Uploading the native Lefony OS image"),
        ("flash_erase /dev/mtd1", "Erasing the Lefony OS NAND slot"),
        ("nandwrite -p /dev/mtd1", "Writing native Lefony OS to NAND"),
        ("dd if=/dev/mtd1 of=/tmp/lefony-os-prime-installer/readback.mtd", "Reading the written image back"),
        ("ucmd cmp /tmp/lefony-os-prime-installer/lefony-os-native.zimage", "Comparing the NAND readback"),
        ("ucp t:/tmp/lefony-os-prime-installer/readback.mtd", "Copying the readback to this Mac"),
        ("===upsilon-install-complete===", "Device-side installation verified"),
    ),
    "erase": (
        ("start cmd:sdp:", "Booting recovery Linux"),
        ("nanddump -f /tmp/lefony-os-prime-installer/pre-operation.mtd", "Reading the current NAND slot"),
        ("ucp t:/tmp/lefony-os-prime-installer/pre-operation.mtd", "Copying the safety backup to this Mac"),
        ("flash_erase /dev/mtd1", "Erasing the Lefony OS NAND slot"),
        ("nanddump -l 8388608", "Reading the erased slot back"),
        ("ucp t:/tmp/lefony-os-prime-installer/readback.mtd", "Copying the erase readback to this Mac"),
        ("===upsilon-erase-complete===", "Device-side erase verified"),
    ),
    "exit-recovery": (
        ("start cmd:fbk: acmd", "Returning recovery Linux to the ROM downloader"),
        ("start cmd:sdp: boot", "Loading the NAND-free clear/reset helper"),
        ("start cmd:sdp: jump", "Restarting into Lefony"),
    ),
    "verify-uboot": (
        ("start cmd:sdp:", "Booting read-only recovery Linux"),
        ("nanddump -q -s 1048576", "Reading primary U-Boot copy"),
        ("ucp t:/tmp/lefony-os-uboot-audit/boot-primary.readback", "Copying primary U-Boot readback"),
        ("nanddump -q -s 2621440", "Reading secondary U-Boot copy"),
        ("ucp t:/tmp/lefony-os-uboot-audit/boot-secondary.readback", "Copying secondary U-Boot readback"),
        ("===lefony-os-uboot-verify-complete===", "Host SHA-256 verification pending"),
    ),
}


def operation_progress(action: str, raw: str, bootstrap: bool = True) -> OperationProgress:
    """Translate stable UUU command milestones into honest phase progress.

    UUU restarts its byte percentage for every transfer, so that value cannot
    represent the whole operation. The primary percentage is therefore based
    on ordered, auditable phases; the current transfer percentage is exposed
    separately when UUU provides one.
    """
    milestones = list(PROGRESS_MILESTONES.get(action, ()))
    if not bootstrap:
        milestones = [item for item in milestones if item[0] != "start cmd:sdp:"]
    total = max(1, len(milestones))
    lower = ANSI_RE.sub("", raw).lower().replace("\r", "\n")
    latest = -1
    for index, (token, _label) in enumerate(milestones):
        if token in lower:
            latest = index

    if latest < 0:
        attached = "new usb device attached" in lower
        phase = (
            "Device attached; waiting for the required recovery stage"
            if attached
            else "Waiting for the calculator and administrator authorization"
        )
        current = 0
    else:
        current = latest + 1
        phase = milestones[latest][1]

    # Reserve 100% for successful device checks plus host-side verification.
    percent = min(95, round(100 * current / total))
    transfer_percent = None
    command_start = lower.rfind("start cmd:")
    if command_start >= 0:
        percentages = [
            int(value)
            for value in re.findall(r"(?<!\d)(\d{1,3})%", lower[command_start:])
            if int(value) <= 100
        ]
        if percentages:
            transfer_percent = percentages[-1]
    return OperationProgress(phase, current, total, percent, transfer_percent)


def progress_bar(percent: int, width: int = 30) -> str:
    width = max(4, width)
    bounded = max(0, min(100, percent))
    filled = round(width * bounded / 100)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


@dataclass(frozen=True)
class DeviceStatus:
    mode: str
    label: str
    detail: str
    port: str | None
    checked_at: float

    @property
    def connected(self) -> bool:
        return self.mode != "disconnected"

    @property
    def recovery(self) -> bool:
        return self.mode in ("recovery-sdp", "recovery-fastboot")


def parse_uuu_output(output: str, checked_at: float | None = None) -> DeviceStatus | None:
    """Parse the stable protocol and chip columns from ``uuu -lsusb``."""
    now = time.time() if checked_at is None else checked_at
    for line in output.splitlines():
        upper = line.upper()
        if "MX6ULL" not in upper:
            continue
        if "SDP:" in upper:
            return DeviceStatus(
                "recovery-sdp",
                "ROM RECOVERY",
                "i.MX6ULL serial downloader (15A2:0080)",
                None,
                now,
            )
        if "FBK:" in upper or "FASTBOOT" in upper:
            return DeviceStatus(
                "recovery-fastboot",
                "RECOVERY LINUX",
                "UUU fastboot recovery environment",
                None,
                now,
            )
    return None


def parse_usb_inventory(
    output: str, ports: list[str], checked_at: float | None = None
) -> DeviceStatus | None:
    """Recognize HP stock, normal Linux, and native diagnostic USB devices."""
    now = time.time() if checked_at is None else checked_at
    lower = output.lower()
    hp_vendor = '"idvendor" = 1008' in lower
    hp_stock = (hp_vendor and '"idproduct" = 9281' in lower) or "03f0:2441" in lower
    if hp_stock:
        return DeviceStatus(
            "hp-stock",
            "HP PRIME OS RUNNING",
            "Official HP USB service (03F0:2441); no safe Lefony bootstrap yet",
            None,
            now,
        )
    hp_update = (hp_vendor and '"idproduct" = 9537' in lower) or "03f0:2541" in lower
    if hp_update:
        return DeviceStatus(
            "hp-update",
            "HP PRIME UPDATE MODE",
            "Official HP maintenance USB (03F0:2541); research-only",
            None,
            now,
        )
    native_vid_pid = (
        ('"idvendor" = 51966' in lower and '"idproduct" = 20562' in lower)
        or "cafe:5052" in lower
    )
    if native_vid_pid:
        return DeviceStatus(
            "upsilon",
            "LEFONY OS RUNNING",
            "Native diagnostic USB (CAFE:5052)",
            None,
            now,
        )
    linux_vid_pid = (
        ('"idvendor" = 1317' in lower and '"idproduct" = 42151' in lower)
        or "0525:a4a7" in lower
        or "gadget serial" in lower
    )
    if linux_vid_pid and ports:
        preferred = next((port for port in ports if port.startswith("/dev/cu.")), ports[0])
        return DeviceStatus(
            "linux",
            "LINUX RUNNING",
            f"USB gadget serial: {preferred}",
            preferred,
            now,
        )
    return None


def find_linux_ports(patterns: tuple[str, ...] = LINUX_PORT_PATTERNS) -> list[str]:
    ports: set[str] = set()
    for pattern in patterns:
        ports.update(glob.glob(pattern))
    return sorted(ports)


def usb_inventory() -> str:
    commands: list[list[str]] = []
    if sys.platform == "darwin":
        commands.append(["/usr/sbin/ioreg", "-r", "-c", "IOUSBHostDevice", "-l", "-w0"])
    else:
        lsusb = shutil.which("lsusb")
        if lsusb:
            commands.append([lsusb])
    for command in commands:
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=2.0, check=False
            )
            return result.stdout + result.stderr
        except (OSError, subprocess.TimeoutExpired):
            pass
    return ""


class Detector:
    def __init__(self, uuu: str | None = None):
        self.uuu = shutil.which("uuu") if uuu is None else uuu

    def probe(self) -> DeviceStatus:
        now = time.time()
        # Recovery wins over stale serial nodes left behind by macOS.
        if self.uuu:
            try:
                result = subprocess.run(
                    [self.uuu, "-lsusb"],
                    capture_output=True,
                    text=True,
                    timeout=2.5,
                    check=False,
                )
                recovery = parse_uuu_output(result.stdout + result.stderr, now)
                if recovery:
                    return recovery
            except (OSError, subprocess.TimeoutExpired):
                pass
        normal = parse_usb_inventory(usb_inventory(), find_linux_ports(), now)
        if normal:
            return normal
        return DeviceStatus(
            "disconnected",
            "WAITING FOR DEVICE",
            "No Prime recovery, Linux, or native Lefony OS USB endpoint detected",
            None,
            now,
        )


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    exists: bool
    size: int = 0
    modified: float = 0.0
    sha256: str = ""
    magic: bytes = b""
    declared_size: int = 0
    signed_update: bool = False
    update_version: tuple[int, int, int, int] | None = None
    package_error: str = ""

    @classmethod
    def inspect(cls, path: Path) -> "ImageInfo":
        if not path.is_file():
            return cls(path, False)
        stat = path.stat()
        with path.open("rb") as stream:
            package_magic = stream.read(4)
        if package_magic == update_capsule.MAGIC:
            try:
                package = update_capsule.inspect(path)
            except (update_capsule.CapsuleError, OSError) as error:
                return cls(path, True, stat.st_size, stat.st_mtime,
                           package_error=str(error))
            payload = package.payload
            declared_size = int.from_bytes(
                payload[ZIMAGE_SIZE_OFFSET:ZIMAGE_SIZE_OFFSET + 4], "little"
            )
            return cls(
                path, True, len(payload), stat.st_mtime, package.digest.hex(),
                payload[ZIMAGE_MAGIC_OFFSET:ZIMAGE_MAGIC_OFFSET + 4], declared_size,
                True, package.version,
            )
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            stream.seek(ZIMAGE_MAGIC_OFFSET)
            magic = stream.read(4)
            stream.seek(ZIMAGE_SIZE_OFFSET)
            raw_size = stream.read(4)
        declared_size = struct.unpack("<I", raw_size)[0] if len(raw_size) == 4 else 0
        return cls(path, True, stat.st_size, stat.st_mtime, digest.hexdigest(), magic, declared_size)

    def errors(self) -> list[str]:
        errors: list[str] = []
        if not self.exists:
            return [f"image not found: {self.path}"]
        if self.package_error:
            return [self.package_error]
        if self.size < MIN_IMAGE_BYTES:
            errors.append("image is too small to be a native Lefony OS capsule")
        if self.size > NAND_SLOT_BYTES:
            errors.append("image exceeds the 8 MiB Lefony OS NAND slot")
        if self.magic != ZIMAGE_MAGIC:
            errors.append("image does not contain the ARM zImage magic")
        if self.declared_size != self.size:
            errors.append(
                f"capsule size field is {self.declared_size}, expected {self.size}"
            )
        return errors

    def update_errors(self) -> list[str]:
        errors = self.errors()
        if not errors and not self.signed_update:
            errors.append("running-device update requires a signed .lfu capsule")
        return errors

    def recovery_payload(self) -> bytes:
        if self.signed_update:
            return update_capsule.inspect(self.path).payload
        return self.path.read_bytes()


def human_size(size: int) -> str:
    value = float(size)
    for suffix in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or suffix == "GiB":
            return f"{value:.1f} {suffix}" if suffix != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def format_build_history(
    entries: list[build_history.BuildHistoryEntry], history_dir: Path
) -> list[str]:
    if not entries:
        return ["No Lefony OS builds have been recorded yet."]
    lines: list[str] = []
    for entry in entries:
        version = f" v{entry.version}" if entry.version else ""
        state = entry.status.upper().replace("-", " ")
        dirty = " | dirty source tree" if entry.dirty else ""
        lines.extend(
            [
                f"{entry.created_at}  [{state}]  {entry.kind}{version}",
                f"  SHA-256 {entry.sha256}  |  {human_size(entry.size)}{dirty}",
                f"  Source {entry.source_revision or 'unknown'}"
                + (f"  |  upstream {entry.upstream_revision}" if entry.upstream_revision else ""),
                f"  Notes: {entry.notes or '(none)'}",
                f"  Artifact: {history_dir / entry.artifact}",
                "",
            ]
        )
    return lines


def format_uboot_history(
    entries: list[uboot_history.UBootHistoryEntry], history_dir: Path
) -> list[str]:
    if not entries:
        return ["No HP Prime G2 U-Boot builds have been recorded yet."]
    lines: list[str] = []
    for entry in entries:
        state = entry.status.upper().replace("-", " ")
        dirty = " | dirty source tree" if entry.dirty else ""
        lines.extend([
            f"{entry.created_at}  [{state}]  {entry.version or 'unknown U-Boot'}",
            f"  SHA-256 {entry.sha256}  |  {human_size(entry.size)}{dirty}",
            f"  IVT 0x{entry.ivt_offset:x} | {entry.bootcmd_mfg}",
            f"  bootcmd: {entry.bootcmd}",
            f"  Source {entry.source_revision or 'unknown'}"
            + (f"  |  upstream {entry.upstream_revision}" if entry.upstream_revision else ""),
            f"  Notes: {entry.notes or '(none)'}",
            f"  Artifact: {history_dir / entry.artifact}",
            "",
        ])
    return lines


def clean_log(raw: str) -> list[str]:
    text = ANSI_RE.sub("", raw).replace("\r", "\n")
    lines: list[str] = []
    for line in text.splitlines():
        value = line.strip()
        if not value:
            continue
        if value.startswith("Erasing 128 Ki") or re.fullmatch(r"\d+%", value):
            continue
        lines.append(value)
    return lines


def uuu_failure_detail(lines: list[str]) -> str:
    """Prefer UUU's concrete error over a generic AppleScript exit line."""
    for line in reversed(lines):
        if line.lower().startswith("error:"):
            return line
    for line in reversed(lines):
        if "timeout:" in line.lower() or "fail" in line.lower():
            return line
    return lines[-1] if lines else "no diagnostic output was returned"


def terminal_clear_reset_jump_completed(raw: str) -> bool:
    """Recognize a completed final jump whose expected result is USB removal."""
    text = ANSI_RE.sub("", raw).lower().replace("\r", "\n")
    start = text.rfind("start cmd:sdp: jump -f u-boot-clearreset.imx -ivt")
    return start >= 0 and "okay" in text[start:]


def recovery_boot_lines() -> list[str]:
    return [
        "SDP: boot -f u-boot-dtb.imx -nojump",
        "SDP: write -f recovery-zImage -addr 0x80800000",
        "SDP: write -f recovery.dtb -addr 0x83000000",
        "SDP: write -f recovery-initramfs.u-boot -addr 0x86800000",
        "SDP: jump -f u-boot-dtb.imx -ivt",
        "",
    ]


def _uboot_verify_lines(image_size: int) -> list[str]:
    return [
        "FBK: ucmd mkdir -p /tmp/lefony-os-uboot-audit",
        "FBK: ucp expected-u-boot.imx T:/tmp/lefony-os-uboot-audit/expected-u-boot.imx",
        f"FBK: ucmd test $(wc -c < /tmp/lefony-os-uboot-audit/expected-u-boot.imx) -eq {image_size}",
        f"FBK: ucmd nanddump -q -s {UBOOT_PRIMARY_OFFSET} -l {image_size} -f /tmp/lefony-os-uboot-audit/boot-primary.readback {UBOOT_NAND_SLOT}",
        "FBK: ucp T:/tmp/lefony-os-uboot-audit/boot-primary.readback boot-primary.readback",
        f"FBK: ucmd nanddump -q -s {UBOOT_SECONDARY_OFFSET} -l {image_size} -f /tmp/lefony-os-uboot-audit/boot-secondary.readback {UBOOT_NAND_SLOT}",
        "FBK: ucp T:/tmp/lefony-os-uboot-audit/boot-secondary.readback boot-secondary.readback",
        "FBK: ucmd cmp /tmp/lefony-os-uboot-audit/expected-u-boot.imx /tmp/lefony-os-uboot-audit/boot-primary.readback",
        "FBK: ucmd cmp /tmp/lefony-os-uboot-audit/expected-u-boot.imx /tmp/lefony-os-uboot-audit/boot-secondary.readback",
    ]


def page_readback_command(device: str, target: str, image_size: int) -> str:
    """Exact-length MTD read without millions of one-byte NAND reads.

    Use portable dd options available in the recovery BusyBox. Only the final
    partial page is byte-trimmed, from RAM, never directly from NAND.
    """
    if image_size <= 0 or image_size > NAND_SLOT_BYTES:
        raise ValueError("invalid readback size")
    pages, tail = divmod(image_size, 2048)
    source, output = shlex.quote(device), shlex.quote(target)
    command = f"dd if={source} of={output} bs=2048 count={pages}"
    if tail:
        last_page = shlex.quote(target + ".tail-page")
        command += (
            f" && dd if={source} of={last_page} bs=2048 skip={pages} count=1"
            f" && dd if={last_page} bs=1 count={tail} >> {output}"
        )
    # dd can exit successfully after EOF/short input. Never accept that as a
    # complete readback, even before the later byte comparison and host hash.
    # This is embedded inside sh -c "..." by FBK. Command substitution here
    # would run in the OUTER shell before dd has created the output file.
    # A pipeline contains no eager expansion and runs after successful reads.
    return command + f" && wc -c < {output} | grep -q '^[[:space:]]*{image_size}[[:space:]]*$'"


def make_uuu_script(
    action: str, image_size: int = 0, bootstrap: bool = True,
    uboot_size: int = 0,
) -> str:
    """Build a fixed-target UUU script; paths and MTD selection are not user input."""
    if action not in ("backup", "verify", "install", "erase"):
        raise ValueError(f"unknown operation: {action}")
    if action in ("verify", "install") and not (MIN_IMAGE_BYTES <= image_size <= NAND_SLOT_BYTES):
        raise ValueError("invalid native image size")
    lines = ["uuu_version 1.2.135", ""]
    if bootstrap:
        lines.extend(recovery_boot_lines())
    if action == "install" and uboot_size:
        lines.extend(_uboot_verify_lines(uboot_size))
    lines.extend(
        [
            "FBK: ucmd mkdir -p /tmp/lefony-os-prime-installer",
            f"FBK: ucmd nanddump -f /tmp/lefony-os-prime-installer/pre-operation.mtd {NAND_SLOT}",
            "FBK: ucp T:/tmp/lefony-os-prime-installer/pre-operation.mtd pre-operation.mtd",
        ]
    )
    if action in ("verify", "install"):
        lines.extend(
            [
                "FBK: ucp lefony-os-native.zImage T:/tmp/lefony-os-prime-installer/lefony-os-native.zImage",
                f"FBK: ucmd test $(wc -c < /tmp/lefony-os-prime-installer/lefony-os-native.zImage) -eq {image_size}",
                "FBK: ucmd sh -c \"dd if=/tmp/lefony-os-prime-installer/lefony-os-native.zImage bs=1 skip=36 count=4 2>/dev/null | od -An -tx1 | tr -d ' \\n' | grep -q '^18286f01$'\"",
            ]
        )
    if action == "install":
        lines.extend(
            [
                f"FBK: ucmd flash_erase {NAND_SLOT} 0 0",
                f"FBK: ucmd nandwrite -p {NAND_SLOT} /tmp/lefony-os-prime-installer/lefony-os-native.zImage",
            ]
        )
    if action in ("verify", "install"):
        lines.extend(
            [
                'FBK: ucmd sh -c "' + page_readback_command(
                    NAND_SLOT, "/tmp/lefony-os-prime-installer/readback.mtd", image_size
                ) + '"',
                "FBK: ucmd cmp /tmp/lefony-os-prime-installer/lefony-os-native.zImage /tmp/lefony-os-prime-installer/readback.mtd",
                "FBK: ucp T:/tmp/lefony-os-prime-installer/readback.mtd readback.mtd",
            ]
        )
    elif action == "erase":
        lines.extend(
            [
                f"FBK: ucmd flash_erase {NAND_SLOT} 0 0",
                f"FBK: ucmd nanddump -l {NAND_SLOT_BYTES} -f /tmp/lefony-os-prime-installer/readback.mtd {NAND_SLOT}",
                "FBK: ucp T:/tmp/lefony-os-prime-installer/readback.mtd readback.mtd",
            ]
        )
    lines.extend(["FBK: ucmd sync", f"FBK: ucmd echo ===LEFONY-OS-{action.upper()}-COMPLETE===", "FBK: done", ""])
    return "\n".join(lines)


def make_uboot_verify_script(image_size: int, bootstrap: bool = True) -> str:
    """Read and compare both kobs U-Boot copies without writing NAND."""
    if image_size <= 0 or image_size > 1536 * 1024:
        raise ValueError("invalid U-Boot image size")
    lines = ["uuu_version 1.2.135", ""]
    if bootstrap:
        lines.extend(recovery_boot_lines())
    lines.extend(_uboot_verify_lines(image_size))
    lines.extend([
        "FBK: ucmd echo ===LEFONY-OS-UBOOT-VERIFY-COMPLETE===",
        "FBK: done",
        "",
    ])
    return "\n".join(lines)


def build_clear_reset_uboot(source: Path, destination: Path) -> None:
    """Patch only U-Boot's manufacturing command in a staged RAM image."""
    data = bytearray(source.read_bytes())
    start = data.find(CLEAR_RESET_ENV_KEY)
    end = data.find(b"\0", start)
    if start < 0 or end < 0:
        raise ValueError("bootcmd_mfg was not found in the recovery U-Boot image")
    room = end - start
    if len(CLEAR_RESET_ENV) > room:
        raise ValueError("recovery U-Boot bootcmd_mfg field is too small")
    # Preserve the one existing string terminator.  A NUL-padded shorter value
    # introduces an empty environment entry and hides every later variable.
    data[start:end] = CLEAR_RESET_ENV + b" " * (room - len(CLEAR_RESET_ENV))
    destination.write_bytes(data)


def make_exit_recovery_script(mode: str) -> str:
    """Reset from recovery without accessing NAND or SRC overrides."""
    if mode not in ("recovery-sdp", "recovery-fastboot"):
        raise ValueError(f"cannot exit unsupported device mode: {mode}")
    lines = ["uuu_version 1.2.135", ""]
    if mode == "recovery-fastboot":
        lines.append('FBK: acmd sh -c "echo b > /proc/sysrq-trigger"')
    lines.extend(
        [
            "SDP: boot -f u-boot-clearreset.imx -nojump",
            "SDP: jump -f u-boot-clearreset.imx -ivt",
            "",
        ]
    )
    return "\n".join(lines)


def make_ab_metadata_read_script(bootstrap: bool = True) -> str:
    """Read both boot-control copies without modifying NAND."""
    lines = ["uuu_version 1.2.135", ""]
    if bootstrap:
        lines.extend(recovery_boot_lines())
    lines.extend([
        "FBK: ucmd mkdir -p /tmp/lefony-os-prime-installer",
        f"FBK: ucmd dd if={AB_MISC} of=/tmp/lefony-os-prime-installer/metadata-0.bin bs={AB_METADATA_PAGE_BYTES} count=1",
        f"FBK: ucmd dd if={AB_MISC} of=/tmp/lefony-os-prime-installer/metadata-1.bin bs={AB_METADATA_PAGE_BYTES} skip=64 count=1",
        "FBK: ucp T:/tmp/lefony-os-prime-installer/metadata-0.bin metadata-0.bin",
        "FBK: ucp T:/tmp/lefony-os-prime-installer/metadata-1.bin metadata-1.bin",
        "FBK: ucmd echo ===LEFONY-OS-AB-METADATA-READ-COMPLETE===",
        "",
    ])
    return "\n".join(lines)


def make_ab_install_script(target: int, image_size: int,
                           stale_copy: int) -> str:
    """Write/verify one inactive slot, then atomically publish its metadata."""
    if target not in (0, 1) or stale_copy not in (0, 1):
        raise ValueError("invalid A/B slot or metadata copy")
    if not MIN_IMAGE_BYTES <= image_size <= NAND_SLOT_BYTES:
        raise ValueError("invalid native image size")
    device = NAND_SLOT if target == 0 else AB_ROOTFS
    offset = 0 if target == 0 else AB_SLOT_B_OFFSET_IN_ROOTFS
    erase_offset = offset
    metadata_offsets = (0, AB_METADATA_ERASE_BYTES)
    commit_order = (stale_copy, 1 - stale_copy)
    lines = [
        "uuu_version 1.2.135", "",
        "FBK: ucmd mkdir -p /tmp/lefony-os-prime-installer",
        f"FBK: ucmd nanddump -l {NAND_SLOT_BYTES} -s {offset} -f /tmp/lefony-os-prime-installer/pre-target.mtd {device}",
        f"FBK: ucmd nanddump -l {1024 * 1024} -f /tmp/lefony-os-prime-installer/pre-misc.mtd {AB_MISC}",
        "FBK: ucp T:/tmp/lefony-os-prime-installer/pre-target.mtd pre-target.mtd",
        "FBK: ucp T:/tmp/lefony-os-prime-installer/pre-misc.mtd pre-misc.mtd",
        "FBK: ucp lefony-os-native.zImage T:/tmp/lefony-os-prime-installer/lefony-os-native.zImage",
        "FBK: ucp metadata.bin T:/tmp/lefony-os-prime-installer/metadata.bin",
        f"FBK: ucmd test $(wc -c < /tmp/lefony-os-prime-installer/lefony-os-native.zImage) -eq {image_size}",
        f"FBK: ucmd test $(wc -c < /tmp/lefony-os-prime-installer/metadata.bin) -eq {AB_METADATA_PAGE_BYTES}",
        f"FBK: ucmd flash_erase {device} {erase_offset} 64",
        f"FBK: ucmd nandwrite -p -N -s {offset} {device} /tmp/lefony-os-prime-installer/lefony-os-native.zImage",
        f"FBK: ucmd nanddump -l {image_size} -s {offset} -f /tmp/lefony-os-prime-installer/readback.mtd {device}",
        "FBK: ucmd cmp /tmp/lefony-os-prime-installer/lefony-os-native.zImage /tmp/lefony-os-prime-installer/readback.mtd",
        "FBK: ucp T:/tmp/lefony-os-prime-installer/readback.mtd readback.mtd",
    ]
    for copy in commit_order:
        metadata_offset = metadata_offsets[copy]
        lines.extend([
            f"FBK: ucmd flash_erase {AB_MISC} {metadata_offset} 1",
            f"FBK: ucmd nandwrite -p -N -s {metadata_offset} {AB_MISC} /tmp/lefony-os-prime-installer/metadata.bin",
            f"FBK: ucmd dd if={AB_MISC} of=/tmp/lefony-os-prime-installer/metadata-check.bin bs={AB_METADATA_PAGE_BYTES} skip={metadata_offset // AB_METADATA_PAGE_BYTES} count=1",
            "FBK: ucmd cmp /tmp/lefony-os-prime-installer/metadata.bin /tmp/lefony-os-prime-installer/metadata-check.bin",
        ])
    lines.extend([
        "FBK: ucmd sync",
        "FBK: ucmd echo ===LEFONY-OS-AB-INSTALL-COMPLETE===",
        # The Prime mfgtool gadget rejects Android's fastboot `reboot`
        # command. Complete the durable transaction and let the installer
        # explicitly request one physical RESET from the user.
        "FBK: done",
        "",
    ])
    return "\n".join(lines)


@dataclass
class PreparedOperation:
    action: str
    stage: Path
    script: Path
    stamp: str
    image_sha256: str = ""
    uboot_entry: uboot_history.UBootHistoryEntry | None = None
    uboot_read_size: int = 0


class BackgroundJob:
    def __init__(self) -> None:
        self.kind = ""
        self.thread: threading.Thread | None = None
        self.exit_code: int | None = None
        self.error = ""
        self.warning = ""
        self.started_at: float | None = None
        self.finished_at: float | None = None

    @property
    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start(self, kind: str, target) -> None:
        if self.running:
            raise RuntimeError("another operation is already running")
        self.kind = kind
        self.exit_code = None
        self.error = ""
        self.warning = ""
        self.started_at = time.monotonic()
        self.finished_at = None

        def runner() -> None:
            try:
                self.exit_code = int(target())
            except Exception as exc:
                self.error = str(exc)
                self.exit_code = 1
            finally:
                self.finished_at = time.monotonic()

        self.thread = threading.Thread(target=runner, daemon=True)
        self.thread.start()

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        end = time.monotonic() if self.finished_at is None else self.finished_at
        return max(0.0, end - self.started_at)


class LefonyOSPrimeInstaller:
    BLUE = 1
    HEADER = 2
    GOOD = 3
    WARN = 4
    ERROR = 5

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.prinux = args.prinux.expanduser().resolve()
        self.follow_latest = args.image is None
        self.backup_dir = args.backup_dir.expanduser().resolve()
        self.history_dir = getattr(args, "history_dir", DEFAULT_HISTORY_DIR).expanduser().resolve()
        build_history.prune_failed_builds(self.history_dir)
        self.image_path = (args.image or preferred_recovery_image(self.history_dir)).expanduser().resolve()
        self.uboot_history_dir = getattr(
            args, "uboot_history_dir", DEFAULT_UBOOT_HISTORY_DIR
        ).expanduser().resolve()
        self.uuu = args.uuu or shutil.which("uuu")
        self.detector = Detector(self.uuu)
        self.status = self.detector.probe()
        self.image = ImageInfo.inspect(self.image_path)
        self.history = build_history.load_history(self.history_dir)
        self.uboot_history = uboot_history.load_history(self.uboot_history_dir)
        self.selected_uboot = uboot_history.preferred_entry(self.uboot_history)
        self.log_path = Path(tempfile.gettempdir()) / "lefony-os-prime-installer.log"
        self.job = BackgroundJob()
        self.notice = "Ready. Connect a running Lefony OS calculator to update, or use recovery tools."
        self.next_probe = 0.0
        self.last_running = False
        self.last_artifacts: list[Path] = []
        self.active_bootstrap = True

    def validation_errors(self, action: str, recovery_mode: str | None = None) -> list[str]:
        errors: list[str] = []
        mode = self.status.mode if recovery_mode is None else recovery_mode
        if action == "dev-update":
            if mode != "upsilon":
                errors.append("development update requires LEFONY OS RUNNING")
            errors.extend(self.image.errors())
            if self.image.signed_update:
                errors.append("use signed Update for .lfu packages")
            return errors
        if action == "stage":
            if mode != "upsilon":
                errors.append("RAM upload requires LEFONY OS RUNNING")
            errors.extend(self.image.errors())
            return errors
        if action == "update":
            if mode != "upsilon":
                errors.append("running-device update requires LEFONY OS RUNNING")
            errors.extend(self.image.update_errors())
            return errors
        if not self.uuu:
            errors.append("uuu was not found (install with: brew install uuu)")
        if action == "exit-recovery":
            if mode not in ("recovery-sdp", "recovery-fastboot"):
                errors.append("exit recovery requires ROM or recovery-Linux mode")
            source = self.prinux / RECOVERY_ASSETS["u-boot-dtb.imx"]
            if not source.is_file():
                errors.append(f"missing recovery U-Boot image: {source}")
            return errors
        if action in ("verify-uboot", "install"):
            if mode not in ("recovery-sdp", "recovery-fastboot"):
                errors.append("U-Boot verification requires ROM or recovery-Linux mode")
            if self.selected_uboot is None:
                errors.append("no qualified U-Boot history baseline is selected")
            else:
                if (action == "install"
                        and self.selected_uboot.status not in uboot_history.QUALIFIED_STATUSES):
                    errors.append("selected U-Boot history entry is not qualified for Lefony NAND installation")
                artifact = self.uboot_history_dir / self.selected_uboot.artifact
                if not artifact.is_file():
                    errors.append(f"archived U-Boot artifact is missing: {artifact}")
                else:
                    info = uboot_history.inspect_image(artifact)
                    if info.sha256 != self.selected_uboot.sha256:
                        errors.append("archived U-Boot artifact does not match its history hash")
                    contract_errors = uboot_history.validation_errors(
                        info,
                        require_nand_handoff=not (
                            self.selected_uboot.status == "lefony-nand-boot-verified"
                            or (action == "verify-uboot"
                                and self.selected_uboot.status == "linux-nand-boot-verified")
                        ),
                    )
                    if contract_errors:
                        errors.append(
                            "archived U-Boot is not cold-boot safe: "
                            + contract_errors[0]
                        )
        if action in ("install", "verify"):
            errors.extend(self.image.errors())
        if mode == "recovery-sdp":
            for staged_name, relative in RECOVERY_ASSETS.items():
                source = self.prinux / relative
                if not source.is_file():
                    errors.append(f"missing recovery asset {staged_name}: {source}")
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            errors.append(f"backup directory is not writable: {exc}")
        return errors

    def prepare_operation(self, action: str, recovery_mode: str | None = None) -> PreparedOperation:
        # Snapshot the protocol before the UI changes its public status to
        # "working". Reading self.status again later introduced a race that
        # could build an FBK-only script for a calculator detected in SDP.
        recovery_mode = recovery_mode or self.status.mode
        if recovery_mode not in ("recovery-sdp", "recovery-fastboot"):
            raise RuntimeError("calculator is not in a detected recovery mode")
        errors = self.validation_errors(action, recovery_mode)
        if errors:
            raise RuntimeError(errors[0])
        stage = Path(tempfile.mkdtemp(prefix="lefony-os-prime-installer."))
        if action == "exit-recovery":
            build_clear_reset_uboot(
                self.prinux / RECOVERY_ASSETS["u-boot-dtb.imx"],
                stage / "u-boot-clearreset.imx",
            )
            script = stage / "exit-recovery.uu"
            script.write_text(make_exit_recovery_script(recovery_mode))
            self.active_bootstrap = recovery_mode == "recovery-sdp"
            return PreparedOperation(
                action, stage, script, time.strftime("%Y%m%d-%H%M%S")
            )
        if recovery_mode == "recovery-sdp":
            for staged_name, relative in RECOVERY_ASSETS.items():
                shutil.copy2(self.prinux / relative, stage / staged_name)
        if action == "verify-uboot":
            assert self.selected_uboot is not None
            artifact = self.uboot_history_dir / self.selected_uboot.artifact
            audit_size = max(entry.size for entry in self.uboot_history)
            expected = artifact.read_bytes()
            trailing = audit_size - len(expected)
            (stage / "expected-u-boot.imx").write_bytes(
                expected
                + b"\0" * min(2048, trailing)
                + b"\xff" * max(0, trailing - 2048)
            )
            script = stage / "verify-uboot.uu"
            self.active_bootstrap = recovery_mode == "recovery-sdp"
            script.write_text(
                make_uboot_verify_script(audit_size, self.active_bootstrap)
            )
            return PreparedOperation(
                action, stage, script, time.strftime("%Y%m%d-%H%M%S"),
                uboot_entry=self.selected_uboot, uboot_read_size=audit_size,
            )
        image_sha = ""
        if action in ("install", "verify"):
            (stage / "lefony-os-native.zImage").write_bytes(
                self.image.recovery_payload()
            )
            image_sha = self.image.sha256
            if hashlib.sha256((stage / "lefony-os-native.zImage").read_bytes()).hexdigest() != image_sha:
                shutil.rmtree(stage)
                raise RuntimeError("selected image changed; refresh before installing")
        selected_uboot = None
        if action == "install":
            assert self.selected_uboot is not None
            selected_uboot = self.selected_uboot
            shutil.copy2(
                self.uboot_history_dir / selected_uboot.artifact,
                stage / "expected-u-boot.imx",
            )
        script = stage / f"{action}.uu"
        self.active_bootstrap = recovery_mode == "recovery-sdp"
        script.write_text(
            make_uuu_script(
                action, self.image.size, self.active_bootstrap,
                selected_uboot.size if selected_uboot else 0,
            )
        )
        stamp = time.strftime("%Y%m%d-%H%M%S")
        return PreparedOperation(
            action, stage, script, stamp, image_sha, selected_uboot
        )

    def _run_uuu(
        self,
        operation: PreparedOperation,
        *,
        transition_timeout: int = 30,
        accept_terminal_clear_reset: bool = False,
    ) -> int:
        # Bound waits for the initial protocol and the SDP-to-FBK transition.
        # A recovery environment can reset between confirmation and launch;
        # without these limits UUU otherwise waits forever with no NAND access.
        command = [
            str(self.uuu), "-v", "-t", "30", "-T", str(transition_timeout),
            str(operation.script),
        ]
        self.log_path.unlink(missing_ok=True)
        # Pre-create the log as the desktop user. The elevated shell truncates
        # this existing inode rather than creating a root-owned file, allowing
        # the TUI to keep reading it and append an AppleScript failure message.
        self.log_path.write_text("")
        self.log_path.chmod(0o600)
        if sys.platform == "darwin" and os.geteuid() != 0 and not self.args.no_admin:
            shell_command = (
                f"cd {shlex.quote(str(operation.stage))} && "
                f"{shlex.join(command)} > {shlex.quote(str(self.log_path))} 2>&1"
            )
            escaped = shell_command.replace("\\", "\\\\").replace('"', '\\"')
            result = subprocess.run(
                ["osascript", "-e", f'do shell script "{escaped}" with administrator privileges'],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode and result.stderr:
                try:
                    with self.log_path.open("a") as log:
                        log.write("\n" + result.stderr)
                except OSError:
                    # Preserve the original UUU exit status even if macOS
                    # unexpectedly changes the staged log permissions.
                    pass
        else:
            with self.log_path.open("w") as log:
                result = subprocess.run(
                    command,
                    cwd=operation.stage,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
        if result.returncode and accept_terminal_clear_reset:
            raw = self.read_raw_log()
            if terminal_clear_reset_jump_completed(raw):
                status = self.detector.probe()
                if status.mode not in ("recovery-sdp", "recovery-fastboot"):
                    with self.log_path.open("a") as log:
                        log.write(
                            "\nClear/reset helper jumped successfully; recovery USB "
                            "disconnected as expected.\n"
                        )
                    return 0
        return result.returncode

    def _save_artifacts(self, operation: PreparedOperation) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.last_artifacts = []
        names = {
            "pre-operation.mtd": f"pre-{operation.action}-{operation.stamp}-mtd1.mtd",
            "readback.mtd": f"{operation.action}-{operation.stamp}-readback.mtd",
            "boot-primary.readback": f"verify-uboot-{operation.stamp}-primary.imx",
            "boot-secondary.readback": f"verify-uboot-{operation.stamp}-secondary.imx",
        }
        for source_name, destination_name in names.items():
            source = operation.stage / source_name
            if source.is_file():
                destination = self.backup_dir / destination_name
                shutil.copy2(source, destination)
                self.last_artifacts.append(destination)

    def _host_verify(self, operation: PreparedOperation) -> None:
        readback = operation.stage / "readback.mtd"
        if operation.action in ("install", "verify"):
            if not readback.is_file():
                raise RuntimeError("UUU did not return a NAND readback")
            digest = hashlib.sha256(readback.read_bytes()).hexdigest()
            if digest != operation.image_sha256:
                raise RuntimeError("host SHA-256 check of NAND readback failed")
        elif operation.action == "erase":
            if not readback.is_file() or readback.stat().st_size != NAND_SLOT_BYTES:
                raise RuntimeError("erase verification did not return the full 8 MiB slot")
            with readback.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    if any(byte != 0xFF for byte in chunk):
                        raise RuntimeError("NAND erase verification found programmed bytes")

    def _host_verify_uboot(self, operation: PreparedOperation) -> None:
        entry = operation.uboot_entry
        if entry is None:
            raise RuntimeError("U-Boot verification has no selected history entry")
        actual: list[str] = []
        read_size = operation.uboot_read_size or entry.size
        for label in ("primary", "secondary"):
            readback = operation.stage / f"boot-{label}.readback"
            if not readback.is_file():
                raise RuntimeError(f"U-Boot {label} NAND readback was not returned")
            data = readback.read_bytes()
            if len(data) != read_size:
                raise RuntimeError(
                    f"U-Boot {label} size mismatch: expected {read_size}, got {len(data)}"
                )
            info = uboot_history.inspect_bytes(data[:entry.size])
            actual.append(info.sha256)
            if info.sha256 != entry.sha256:
                identified = next((
                    candidate for candidate in self.uboot_history
                    if len(data) >= candidate.size
                    and hashlib.sha256(data[:candidate.size]).hexdigest() == candidate.sha256
                ), None)
                detail = (
                    f"; installed image matches history build {identified.build_id} "
                    f"[{identified.status}]"
                    if identified else ""
                )
                raise RuntimeError(
                    f"U-Boot {label} mismatch: expected {entry.sha256}, got {info.sha256}{detail}"
                )
            trailing = data[entry.size:]
            guard_size = min(2048, len(trailing))
            if (
                any(byte != 0x00 for byte in trailing[:guard_size])
                or any(byte != 0xFF for byte in trailing[guard_size:])
            ):
                raise RuntimeError(
                    f"U-Boot {label} has unexpected programmed data after the history image"
                )
            if info.ivt_offset != entry.ivt_offset:
                raise RuntimeError(f"U-Boot {label} IVT offset does not match history")
            if info.bootcmd != entry.bootcmd or info.bootcmd_mfg != entry.bootcmd_mfg:
                raise RuntimeError(f"U-Boot {label} environment does not match history")
        if actual[0] != actual[1]:
            raise RuntimeError("primary and secondary U-Boot copies differ")
        with self.log_path.open("a") as log:
            log.write(
                f"\nHost SHA-256 verified both U-Boot copies as {entry.sha256}\n"
                f"History build: {entry.build_id} [{entry.status}]\n"
                f"Environment: {entry.bootcmd_mfg}; {entry.bootcmd}\n"
            )

    def _recovery_mode_after_operation(self, timeout: float = 5.0) -> str | None:
        deadline = time.monotonic() + timeout
        while True:
            status = self.detector.probe()
            if status.mode in ("recovery-sdp", "recovery-fastboot"):
                return status.mode
            if status.mode == "upsilon":
                return None
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "install verified, but the recovery endpoint disappeared before "
                    "automatic boot; reconnect in recovery and press X"
                )
            time.sleep(0.25)

    def _exit_recovery(self, mode: str) -> None:
        install_log = self.read_raw_log()
        previous_status = self.status
        self.status = DeviceStatus(
            mode,
            "ROM RECOVERY" if mode == "recovery-sdp" else "RECOVERY LINUX",
            "Restarting into Lefony",
            None,
            time.time(),
        )
        operation = self.prepare_operation("exit-recovery")
        try:
            code = self._run_uuu(
                operation,
                transition_timeout=5,
                accept_terminal_clear_reset=True,
            )
            exit_log = self.read_raw_log()
            self.log_path.write_text(
                install_log + "\n--- VERIFIED INSTALL: EXIT RECOVERY ---\n" + exit_log
            )
            if code:
                raise RuntimeError(
                    f"exit recovery failed (exit {code}): "
                    f"{uuu_failure_detail(self.read_log())}"
                )
        finally:
            self.status = previous_status
            shutil.rmtree(operation.stage, ignore_errors=True)

    def _physical_ab_requirements(self) -> None:
        if not self.uuu:
            raise RuntimeError("uuu was not found (install with: brew install uuu)")
        for staged_name, relative in RECOVERY_ASSETS.items():
            source = self.prinux / relative
            if not source.is_file():
                raise RuntimeError(f"missing recovery asset {staged_name}: {source}")

    def _save_ab_artifacts(self, stage: Path, stamp: str) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.last_artifacts = []
        names = {
            "metadata-0.bin": f"pre-update-{stamp}-metadata-primary.bin",
            "metadata-1.bin": f"pre-update-{stamp}-metadata-redundant.bin",
            "pre-target.mtd": f"pre-update-{stamp}-inactive-slot.mtd",
            "pre-misc.mtd": f"pre-update-{stamp}-misc.mtd",
            "readback.mtd": f"update-{stamp}-readback.mtd",
            "metadata.bin": f"update-{stamp}-metadata.bin",
        }
        for source_name, destination_name in names.items():
            source = stage / source_name
            if source.is_file():
                destination = self.backup_dir / destination_name
                shutil.copy2(source, destination)
                self.last_artifacts.append(destination)

    def _physical_ab_update(self, status: dict[str, object],
                            package: update_capsule.UpdateCapsule) -> None:
        """Finish an authenticated update with the recovery NAND backend."""
        self._physical_ab_requirements()
        stage = Path(tempfile.mkdtemp(prefix="lefony-os-ab-update."))
        stamp = time.strftime("%Y%m%d-%H%M%S")
        try:
            for staged_name, relative in RECOVERY_ASSETS.items():
                shutil.copy2(self.prinux / relative, stage / staged_name)
            probe_script = stage / "ab-metadata-read.uu"
            probe_script.write_text(make_ab_metadata_read_script(bootstrap=True))
            probe = PreparedOperation("ab-metadata-read", stage, probe_script, stamp)
            code = self._run_uuu(probe)
            if code:
                raise RuntimeError(
                    f"UUU metadata read failed (exit {code}): "
                    f"{uuu_failure_detail(self.read_log())}"
                )
            try:
                current, source_copy = ab_metadata.newest(
                    (stage / "metadata-0.bin").read_bytes(),
                    (stage / "metadata-1.bin").read_bytes(),
                )
            except (OSError, ab_metadata.MetadataError) as error:
                raise RuntimeError(
                    "physical A/B layout is not provisioned; refusing to write NAND"
                ) from error
            active = int(status["active_slot"])
            generation = int(status["generation"])
            if current.active != active or current.generation != generation:
                raise RuntimeError(
                    "bootloader metadata changed after authentication; reconnect and retry"
                )
            if current.pending != ab_metadata.NO_SLOT:
                raise RuntimeError(
                    "a previous update is still pending; reboot once to commit or roll it back"
                )
            target = 1 - current.active
            updated = current.with_update(target, package.payload, package.version)
            (stage / "lefony-os-native.zImage").write_bytes(package.payload)
            (stage / "metadata.bin").write_bytes(updated.pack(page=True))
            install_script = stage / "ab-install.uu"
            install_script.write_text(
                make_ab_install_script(target, len(package.payload), 1 - source_copy)
            )
            install = PreparedOperation(
                "ab-install", stage, install_script, stamp, package.digest.hex()
            )
            code = self._run_uuu(install)
            if code:
                raise RuntimeError(
                    f"UUU inactive-slot install failed (exit {code}): "
                    f"{uuu_failure_detail(self.read_log())}"
                )
            readback = stage / "readback.mtd"
            if not readback.is_file() or hashlib.sha256(readback.read_bytes()).digest() != package.digest:
                raise RuntimeError("host SHA-256 check of inactive-slot readback failed")
            with self.log_path.open("a") as log:
                log.write(
                    f"\nInactive slot {target} verified and published as generation "
                    f"{updated.generation}; physical RESET required\n"
                )
        finally:
            self._save_ab_artifacts(stage, stamp)
            shutil.rmtree(stage, ignore_errors=True)

    def run_operation(self, action: str) -> int:
        if action == "dev-update":
            return self._development_update()
        if action == "stage":
            errors = self.validation_errors(action)
            if errors:
                raise RuntimeError(errors[0])
            self.log_path.write_text("USB RAM upload test; NAND and U-Boot are untouched\n")
            last_percent = -1
            def progress(received, total):
                nonlocal last_percent
                percent = received * 100 // total
                if percent != last_percent:
                    last_percent = percent
                    with self.log_path.open("a") as log:
                        log.write(f"RAM upload {percent}%: {received}/{total} bytes\n")
            with usb_update.LibUSB() as device:
                result = usb_update.stage_capsule(device, self.image_path, progress)
                device.write(usb_update.REQUEST_RECOVERY_ABORT)
            with self.log_path.open("a") as log:
                log.write(f"Device CRC verified: {result['crc32']:08x}; "
                          "RAM staging cleared. OS was not installed or rebooted.\n")
            return 0
        if action == "update":
            errors = self.validation_errors(action)
            if errors:
                raise RuntimeError(errors[0])
            self.log_path.write_text("Opening native Lefony OS USB updater\n")
            package = update_capsule.inspect(self.image_path)
            package_file_digest = hashlib.sha256(self.image_path.read_bytes()).digest()
            try:
                with usb_update.LibUSB() as device:
                    status = usb_update.install_signed_capsule(
                        device, self.image_path, reboot=False
                    )
                    handoff = str(status.get("handoff", "direct"))
                    if handoff == "recovery":
                        # Check every host-side prerequisite before resetting a
                        # healthy calculator into ROM serial-download mode.
                        self._physical_ab_requirements()
                        device.write(usb_update.REQUEST_UPDATE_RECOVERY,
                                     timeout_ms=10000)
                    else:
                        device.write(usb_update.REQUEST_UPDATE_REBOOT,
                                     timeout_ms=10000)
                if hashlib.sha256(self.image_path.read_bytes()).digest() != package_file_digest:
                    raise RuntimeError("signed update file changed during authentication")
            except (usb_update.USBError, update_capsule.CapsuleError, OSError) as error:
                with self.log_path.open("a") as log:
                    log.write(f"Update failed: {error}\n")
                raise RuntimeError(str(error)) from error
            if handoff == "recovery":
                self._physical_ab_update(status, package)
            else:
                with self.log_path.open("a") as log:
                    log.write(
                        f"Inactive slot {status['pending_slot']} committed; reboot requested; "
                        f"generation {status['generation']}\n"
                    )
            return 0
        if action == "exit-recovery":
            operation = self.prepare_operation(action)
            try:
                code = self._run_uuu(
                    operation,
                    transition_timeout=5,
                    accept_terminal_clear_reset=True,
                )
                if code:
                    raise RuntimeError(
                        f"exit recovery failed (exit {code}): "
                        f"{uuu_failure_detail(self.read_log())}"
                    )
                return 0
            finally:
                shutil.rmtree(operation.stage, ignore_errors=True)
        operation = self.prepare_operation(action)
        return self._execute_recovery_operation(action, operation)

    def _execute_recovery_operation(self, action: str, operation: PreparedOperation) -> int:
        try:
            code = self._run_uuu(operation)
            if operation.uboot_entry is not None:
                self._host_verify_uboot(operation)
            if action == "verify-uboot":
                # Readbacks are copied before device-side cmp, so a mismatch
                # still produces an exact expected/actual host diagnostic.
                if code != 0:
                    raise RuntimeError(
                        f"UUU U-Boot verification failed (exit {code}): "
                        f"{uuu_failure_detail(self.read_log())}"
                    )
                return 0
            if code != 0:
                lines = self.read_log()
                detail = uuu_failure_detail(lines)
                raise RuntimeError(f"UUU failed (exit {code}): {detail}")
            self._host_verify(operation)
            if action == "install":
                # NAND is already compared on-device and SHA-256 verified on
                # the host before recovery state is changed or reset.
                try:
                    mode = self._recovery_mode_after_operation()
                    if mode is not None:
                        self._exit_recovery(mode)
                except RuntimeError as error:
                    self.job.warning = (
                        f"NAND verified; automatic boot not confirmed: {error}. "
                        "Press rear RESET; do not reinstall."
                    )
                    with self.log_path.open("a") as log:
                        log.write(f"\nWARNING: {self.job.warning}\n")
            return 0
        finally:
            # Preserve any backup or readback UUU managed to return, including
            # when a later USB transfer, comparison, or host check fails.
            self._save_artifacts(operation)
            shutil.rmtree(operation.stage, ignore_errors=True)

    def _development_update(self) -> int:
        errors = self.validation_errors("dev-update")
        if errors:
            raise RuntimeError(errors[0])
        with usb_update.LibUSB() as device:
            capabilities = usb_update.development_capabilities(device)
            if not capabilities["flags"] & 2:
                raise RuntimeError("install the native-updater build once through recovery; "
                                   "this OS only supports the older recovery handoff. NAND untouched.")
            return self._native_development_update(device)

    def _native_development_update(self, device) -> int:
        self.log_path.write_text("Native development update; U-Boot untouched; no recovery Linux\n")
        # Freeze the selected bytes before transfer, even if a build finishes
        # or history changes while the worker is running.
        with tempfile.TemporaryDirectory(prefix="lefony-native-update.") as directory:
            path = Path(directory) / "image.zImage"
            payload = self.image.recovery_payload()
            if hashlib.sha256(payload).hexdigest() != self.image.sha256:
                raise RuntimeError("selected image changed before upload")
            path.write_bytes(payload)
            previous = None
            def progress(phase, done, total):
                nonlocal previous
                percent = done * 100 // total if total else 0
                current = (phase, percent)
                if current != previous:
                    previous = current
                    with self.log_path.open("a") as log:
                        log.write(f"Native {phase} {percent}%\n")
            usb_update.install_native_capsule(device, path, progress)
        with self.log_path.open("a") as log:
            log.write(f"Native NAND byte-for-byte verified against SHA-256 {self.image.sha256}\n")
        try:
            device.write(0x54, timeout_ms=10000)
        except usb_update.USBError as error:
            self.job.warning = f"NAND verified; reboot ACK uncertain: {error}"
        # Endpoint reappearance is not proof of the new UI; report that limit.
        with self.log_path.open("a") as log:
            log.write("Normal reboot requested; physical boot confirmation still required\n")
        self.job.warning = self.job.warning or "NAND verified; reboot requested. Confirm the new build on the calculator."
        return 0

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if self.job.running:
            self.status = DeviceStatus(
                "working", "USB RAM UPLOAD ACTIVE" if self.job.kind == "stage" else
                "NAND OPERATION ACTIVE", self.job.kind.upper(), None, time.time()
            )
            return
        if force or now >= self.next_probe:
            self.status = self.detector.probe()
            build_history.prune_failed_builds(self.history_dir)
            if self.follow_latest:
                self.image_path = preferred_recovery_image(self.history_dir).expanduser().resolve()
            self.image = ImageInfo.inspect(self.image_path)
            self.history = build_history.load_history(self.history_dir)
            selected_id = self.selected_uboot.build_id if self.selected_uboot else ""
            self.uboot_history = uboot_history.load_history(self.uboot_history_dir)
            self.selected_uboot = next(
                (entry for entry in self.uboot_history if entry.build_id == selected_id),
                uboot_history.preferred_entry(self.uboot_history),
            )
            self.next_probe = now + self.args.interval

    @staticmethod
    def add_line(screen, row: int, col: int, value: str, attr: int = 0) -> None:
        height, width = screen.getmaxyx()
        if 0 <= row < height and 0 <= col < width:
            try:
                screen.addnstr(row, col, value, max(0, width - col - 1), attr)
            except curses.error:
                pass

    @staticmethod
    def set_cursor(value: int) -> None:
        try:
            curses.curs_set(value)
        except curses.error:
            pass

    def configure_theme(self, screen) -> None:
        # Preserve the terminal's working default canvas
        # and apply colors only to status text. Painting the whole curses
        # window caused some macOS terminal profiles to render black-on-black.
        if not curses.has_colors():
            return
        curses.start_color()
        try:
            curses.use_default_colors()
            background = -1
        except curses.error:
            background = curses.COLOR_BLACK
        curses.init_pair(self.ERROR, curses.COLOR_RED, background)
        curses.init_pair(self.GOOD, curses.COLOR_GREEN, background)
        curses.init_pair(self.WARN, curses.COLOR_YELLOW, background)

    def draw(self, screen) -> None:
        screen.erase()
        height, width = screen.getmaxyx()
        blue = 0
        header = curses.A_REVERSE
        good = curses.color_pair(self.GOOD) if curses.has_colors() else curses.A_BOLD
        warn = curses.color_pair(self.WARN) if curses.has_colors() else curses.A_BOLD
        error = curses.color_pair(self.ERROR) if curses.has_colors() else curses.A_BOLD
        self.add_line(screen, 0, 0, " LEFONY OS PRIME INSTALLER - HP PRIME G2 ".center(width - 1), header | curses.A_BOLD)

        status_attr = {
            "recovery-sdp": good,
            "recovery-fastboot": good,
            "upsilon": good,
            "hp-stock": warn,
            "hp-update": warn,
            "linux": warn,
            "working": warn,
            "disconnected": error,
        }.get(self.status.mode, blue)
        self.add_line(screen, 2, 2, f"DEVICE  {self.status.label}", status_attr | curses.A_BOLD)
        self.add_line(screen, 3, 4, self.status.detail, blue)
        checked = time.strftime("%H:%M:%S", time.localtime(self.status.checked_at))
        self.add_line(screen, 4, 4, f"Live detection every {self.args.interval:.1f}s | Last probe {checked}", blue)

        self.add_line(screen, 6, 2, "NATIVE LEFONY OS IMAGE", header | curses.A_BOLD)
        if self.image.exists:
            self.add_line(screen, 7, 4, f"Path: {self.image.path}", blue)
            self.add_line(screen, 8, 4, f"Size: {human_size(self.image.size)} / 8.0 MiB", blue)
            self.add_line(screen, 9, 4, f"SHA-256: {self.image.sha256}", blue)
            image_errors = self.image.errors()
            if image_errors:
                state = f"INVALID: {image_errors[0]}"
            elif self.image.signed_update:
                version = ".".join(map(str, self.image.update_version[:3]))
                state = f"VALID SIGNED A/B UPDATE v{version}+{self.image.update_version[3]}"
            else:
                state = "VALID DEVELOPMENT CAPSULE (unsigned; single-slot update)"
            self.add_line(screen, 10, 4, state, error if image_errors else good | curses.A_BOLD)
        else:
            self.add_line(screen, 7, 4, f"MISSING: {self.image.path}", error)
        if self.history:
            latest = self.history[0]
            self.add_line(
                screen, 11, 4,
                f"OS history: {len(self.history)} builds | latest {latest.created_at} [{latest.status}]",
                blue,
            )
        else:
            self.add_line(screen, 11, 4, "OS history: no recorded builds yet", blue)

        self.add_line(screen, 12, 2, "SAFE UPDATE TARGET", header | curses.A_BOLD)
        if self.status.mode == "upsilon" and self.image.signed_update:
            self.add_line(screen, 13, 4, "Inactive A/B NAND slot; signed manifest + readback required", blue | curses.A_BOLD)
            self.add_line(screen, 14, 4, "Active slot remains bootable until the new boot is confirmed", blue)
        elif self.status.mode in ("hp-stock", "hp-update"):
            self.add_line(screen, 13, 4, "Stock HP firmware detected; direct Lefony installation is research-only", warn | curses.A_BOLD)
            self.add_line(screen, 14, 4, "No NAND command will be sent; use ROM recovery for first installation", blue)
        else:
            self.add_line(screen, 13, 4, "/dev/mtd1 - 8 MiB Lefony OS/kernel recovery slot", blue | curses.A_BOLD)
            self.add_line(screen, 14, 4, "mtd0 boot, mtd2 DTB, misc, and rootfs are locked out", blue)
        uboot_summary = (
            f"U-Boot history: {len(self.uboot_history)} builds | selected "
            f"{self.selected_uboot.sha256[:12]} [{self.selected_uboot.status}]"
            if self.selected_uboot else "U-Boot history: no recorded builds yet"
        )
        self.add_line(screen, 15, 4, uboot_summary, blue)

        if self.job.running:
            progress = (
                OperationProgress("Authenticating and writing the inactive A/B slot", 1, 1, 50)
                if self.job.kind == "update"
                else operation_progress(self.job.kind, self.read_raw_log(), self.active_bootstrap)
            )
            if self.job.kind == "stage":
                percentages = re.findall(r"RAM upload (\d+)%", self.read_raw_log())
                percent = int(percentages[-1]) if percentages else 0
                progress = OperationProgress("RAM transfer and CRC test (no NAND writes)",
                                             1, 1, percent)
            if self.job.kind == "dev-update":
                raw = self.read_raw_log()
                native = re.findall(r"Native (\w+) (\d+)%", raw)
                if native:
                    phase, percent = native[-1]
                    progress = OperationProgress(f"Native {phase} (U-Boot untouched)", 1, 1, int(percent))
                elif "RAM upload" in raw or "preflight complete" in raw:
                    percentages = re.findall(r"RAM upload (\d+)%", raw)
                    percent = int(percentages[-1]) if percentages else 0
                    phase = ("Waiting for recovery; NAND untouched" if
                             "Waiting for ROM/recovery" in raw else "Uploading and CRC-checking image")
                    progress = OperationProgress(phase, 1, 2, percent // 2)
                else:
                    progress = operation_progress("install", raw, self.active_bootstrap)
            elapsed = time.strftime("%M:%S", time.gmtime(self.job.elapsed))
            self.add_line(
                screen,
                17,
                2,
                f"{self.job.kind.upper()}  {progress.phase}",
                warn | curses.A_BOLD,
            )
            transfer = (
                f" | current transfer {progress.transfer_percent}%"
                if progress.transfer_percent is not None
                else ""
            )
            self.add_line(
                screen,
                18,
                4,
                f"{progress_bar(progress.percent)} {progress.percent:3d}%  "
                f"Phase {progress.current}/{progress.total} | elapsed {elapsed}{transfer}",
                warn,
            )
            if progress.current == 0 and self.job.elapsed >= 10:
                self.add_line(
                    screen,
                    19,
                    4,
                    "Still waiting for the expected USB recovery protocol; NAND is untouched.",
                    warn,
                )
        elif self.job.exit_code is not None:
            success = self.job.exit_code == 0 and not self.job.error
            message = f"{self.job.kind.upper()} {'COMPLETED AND VERIFIED' if success else 'FAILED'}"
            if success and self.job.warning:
                message = "NAND VERIFIED — BOOT NEEDS ATTENTION"
            self.add_line(screen, 17, 2, message, good if success else error)
            elapsed = time.strftime("%M:%S", time.gmtime(self.job.elapsed))
            self.add_line(screen, 18, 4, f"Elapsed: {elapsed}", blue)
            if self.job.error:
                self.add_line(screen, 19, 4, self.job.error, error)
            elif self.job.warning:
                self.add_line(screen, 19, 4, self.job.warning, warn)
        else:
            self.add_line(screen, 17, 2, self.notice, blue)

        footer = "[T] USB RAM test [U] Update [I] Install [V] Verify OS [K] Verify U-Boot [H] History [G] U-Boot history [L] Log [Q] Quit"
        self.add_line(screen, height - 2, 0, footer.center(width - 1), header | curses.A_BOLD)
        if width < 96 or height < 22:
            self.add_line(screen, height - 1, 0, "Enlarge the terminal for the full installer view.", blue)
        screen.refresh()

    def read_log(self) -> list[str]:
        return clean_log(self.read_raw_log())

    def read_raw_log(self) -> str:
        try:
            return self.log_path.read_text(errors="replace")
        except OSError:
            return ""

    def confirm(self, screen, action: str) -> bool:
        if action in ("update", "dev-update", "stage") and self.status.mode != "upsilon":
            self.notice = "Blocked: connect a calculator showing LEFONY OS RUNNING"
            return False
        if action not in ("update", "dev-update", "stage") and not self.status.recovery:
            self.notice = "Blocked: the calculator must be in ROM or recovery-Linux mode"
            return False
        errors = self.validation_errors(action)
        if errors:
            self.notice = f"Blocked: {errors[0]}"
            return False
        phrase = {"update": "UPDATE", "dev-update": "UPDATE", "install": "INSTALL", "erase": "ERASE MTD1"}.get(action)
        if phrase is None:
            return True
        height, width = screen.getmaxyx()
        target = "the inactive A/B slot" if action == "update" else "/dev/mtd1"
        prompt = f"Type {phrase} to confirm {action} of {target}: "
        safety = (
            "The active slot is preserved; the new slot stays pending until boot confirmation."
            if action == "update" else
            "Only mtd1 is targeted; a timestamped backup is mandatory."
        )
        if action == "dev-update":
            safety = "Development update overwrites mtd1; no A/B rollback. Keep USB power connected. U-Boot is preserved."
        self.add_line(screen, height - 4, 2, safety, curses.A_BOLD)
        self.add_line(screen, height - 3, 2, prompt, curses.A_BOLD)
        screen.refresh()
        screen.timeout(-1)
        curses.echo()
        self.set_cursor(1)
        try:
            raw = screen.getstr(height - 3, min(width - 2, 2 + len(prompt)), 20)
        except curses.error:
            raw = b""
        finally:
            curses.noecho()
            self.set_cursor(0)
            screen.timeout(200)
        return raw.decode("utf-8", "replace") == phrase

    def show_log(self, screen) -> None:
        lines = self.read_log() or ["No UUU operation log is available yet."]
        offset = max(0, len(lines) - max(1, screen.getmaxyx()[0] - 4))
        while True:
            screen.erase()
            height, width = screen.getmaxyx()
            attr = curses.A_REVERSE
            self.add_line(screen, 0, 0, " UUU / NAND LOG ".center(width - 1), attr | curses.A_BOLD)
            for index, line in enumerate(lines[offset : offset + max(1, height - 3)], 1):
                self.add_line(screen, index, 1, line)
            self.add_line(screen, height - 1, 0, "[Up/Down/PgUp/PgDn] Scroll  [L/Q/Esc] Back", attr)
            screen.refresh()
            key = screen.getch()
            if key in (ord("l"), ord("L"), ord("q"), ord("Q"), 27):
                return
            if key == curses.KEY_UP:
                offset = max(0, offset - 1)
            elif key == curses.KEY_DOWN:
                offset = min(max(0, len(lines) - 1), offset + 1)
            elif key == curses.KEY_PPAGE:
                offset = max(0, offset - max(1, height - 4))
            elif key == curses.KEY_NPAGE:
                offset = min(max(0, len(lines) - 1), offset + max(1, height - 4))

    def show_history(self, screen) -> None:
        self.history = build_history.load_history(self.history_dir)
        selected = 0
        top = 0
        while True:
            screen.erase()
            height, width = screen.getmaxyx()
            attr = curses.A_REVERSE
            self.add_line(screen, 0, 0, " LEFONY OS BUILD HISTORY ".center(width - 1), attr | curses.A_BOLD)
            visible = max(1, (height - 3) // 5)
            if not self.history:
                self.add_line(screen, 2, 2, "No Lefony OS builds have been recorded yet.")
            for slot, entry in enumerate(self.history[top : top + visible]):
                index = top + slot
                row = 1 + slot * 5
                marker = ">" if index == selected else " "
                version = f" v{entry.version}" if entry.version else ""
                state = entry.status.upper().replace("-", " ")
                candidate = self.history_dir / entry.artifact
                installable = not ImageInfo.inspect(candidate).errors()
                selectable = "installable" if installable else "archive only"
                self.add_line(
                    screen, row, 1,
                    f"{marker} {entry.created_at} [{state}] {entry.kind}{version} ({selectable})",
                    curses.A_BOLD if index == selected else 0,
                )
                self.add_line(screen, row + 1, 4, f"SHA-256 {entry.sha256} | {human_size(entry.size)}")
                self.add_line(screen, row + 2, 4, f"Source {entry.source_revision or 'unknown'}")
                self.add_line(screen, row + 3, 4, f"Notes: {entry.notes or '(none)'}")
            self.add_line(
                screen, height - 1, 0,
                "[Up/Down/PgUp/PgDn] Select  [Enter] Use build  [H/Q/Esc] Back",
                attr,
            )
            screen.refresh()
            key = screen.getch()
            if key in (ord("h"), ord("H"), ord("q"), ord("Q"), 27):
                return
            if not self.history:
                continue
            if key == curses.KEY_UP:
                selected = max(0, selected - 1)
            elif key == curses.KEY_DOWN:
                selected = min(len(self.history) - 1, selected + 1)
            elif key == curses.KEY_PPAGE:
                selected = max(0, selected - visible)
            elif key == curses.KEY_NPAGE:
                selected = min(len(self.history) - 1, selected + visible)
            elif key in (curses.KEY_ENTER, 10, 13):
                entry = self.history[selected]
                candidate = self.history_dir / entry.artifact
                info = ImageInfo.inspect(candidate)
                errors = info.errors()
                if errors:
                    self.notice = f"History item cannot be installed directly: {errors[0]}"
                    return
                self.image_path = candidate
                self.follow_latest = False  # Explicit history selection pins a rollback build.
                self.image = info
                self.notice = f"Selected history build {entry.build_id} [{entry.status}]"
                return
            top = min(top, selected)
            if selected >= top + visible:
                top = selected - visible + 1

    def show_uboot_history(self, screen) -> None:
        self.uboot_history = uboot_history.load_history(self.uboot_history_dir)
        selected = 0
        if self.selected_uboot is not None:
            selected = next(
                (index for index, entry in enumerate(self.uboot_history)
                 if entry.build_id == self.selected_uboot.build_id),
                0,
            )
        top = selected
        while True:
            screen.erase()
            height, width = screen.getmaxyx()
            attr = curses.A_REVERSE
            self.add_line(screen, 0, 0, " HP PRIME G2 U-BOOT HISTORY ".center(width - 1), attr | curses.A_BOLD)
            visible = max(1, (height - 3) // 7)
            if not self.uboot_history:
                self.add_line(screen, 2, 2, "No U-Boot builds have been recorded yet.")
            for slot, entry in enumerate(self.uboot_history[top:top + visible]):
                index = top + slot
                row = 1 + slot * 7
                marker = ">" if index == selected else " "
                state = entry.status.upper().replace("-", " ")
                self.add_line(
                    screen, row, 1,
                    f"{marker} {entry.created_at} [{state}] {entry.version}",
                    curses.A_BOLD if index == selected else 0,
                )
                self.add_line(screen, row + 1, 4, f"SHA-256 {entry.sha256} | {human_size(entry.size)}")
                self.add_line(screen, row + 2, 4, f"IVT 0x{entry.ivt_offset:x} | {entry.bootcmd_mfg}")
                self.add_line(screen, row + 3, 4, entry.bootcmd)
                self.add_line(screen, row + 4, 4, f"Source {entry.source_revision or 'unknown'} | upstream {entry.upstream_revision or 'unknown'}")
                self.add_line(screen, row + 5, 4, f"Notes: {entry.notes or '(none)'}")
            self.add_line(
                screen, height - 1, 0,
                "[Up/Down/PgUp/PgDn] Select  [Enter] Use for verification  [G/Q/Esc] Back",
                attr,
            )
            screen.refresh()
            key = screen.getch()
            if key in (ord("g"), ord("G"), ord("q"), ord("Q"), 27):
                return
            if not self.uboot_history:
                continue
            if key == curses.KEY_UP:
                selected = max(0, selected - 1)
            elif key == curses.KEY_DOWN:
                selected = min(len(self.uboot_history) - 1, selected + 1)
            elif key == curses.KEY_PPAGE:
                selected = max(0, selected - visible)
            elif key == curses.KEY_NPAGE:
                selected = min(len(self.uboot_history) - 1, selected + visible)
            elif key in (curses.KEY_ENTER, 10, 13):
                self.selected_uboot = self.uboot_history[selected]
                self.notice = (
                    f"Selected U-Boot {self.selected_uboot.build_id} "
                    f"[{self.selected_uboot.status}] for read-only verification"
                )
                return
            top = min(top, selected)
            if selected >= top + visible:
                top = selected - visible + 1

    def run(self, screen) -> None:
        self.set_cursor(0)
        curses.noecho()
        curses.cbreak()
        screen.keypad(True)
        screen.timeout(200)
        self.configure_theme(screen)
        actions = {
            ord("u"): "update", ord("i"): "install", ord("v"): "verify",
            ord("b"): "backup", ord("e"): "erase", ord("x"): "exit-recovery",
            ord("k"): "verify-uboot",
        }
        actions.update({ord(key.upper()): value for key, value in (("u", "update"), ("i", "install"), ("v", "verify"), ("b", "backup"), ("e", "erase"), ("x", "exit-recovery"), ("k", "verify-uboot"))})
        actions.update({ord("t"): "stage", ord("T"): "stage"})
        while True:
            was_running = self.job.running
            self.refresh()
            if self.last_running and not was_running:
                self.next_probe = 0.0
                self.notice = "Operation ended; open the log for complete details"
            self.last_running = was_running
            self.draw(screen)
            key = screen.getch()
            if key in (ord("q"), ord("Q")):
                if self.job.running:
                    self.notice = "Cannot quit during a NAND operation"
                else:
                    return
            elif key in (ord("r"), ord("R")):
                self.refresh(force=True)
                self.notice = "Device and image status refreshed"
            elif key in (ord("l"), ord("L")):
                self.show_log(screen)
            elif key in (ord("h"), ord("H")):
                self.show_history(screen)
            elif key in (ord("g"), ord("G")):
                self.show_uboot_history(screen)
            elif key in actions:
                action = actions[key]
                if action == "update" and not self.image.signed_update:
                    action = "dev-update"
                if self.job.running:
                    self.notice = "Another operation is already running"
                elif self.confirm(screen, action):
                    self.notice = f"{action.capitalize()} started; approve the macOS prompt if shown"
                    self.job.start(action, lambda action=action: self.run_operation(action))
                else:
                    self.notice = f"{action.capitalize()} cancelled or blocked"


def preferred_recovery_image(history_dir: Path = DEFAULT_HISTORY_DIR) -> Path:
    for entry in build_history.load_history(history_dir):
        if entry.status != "superseded" and entry.kind != "native":
            artifact = history_dir / entry.artifact
            if (artifact.resolve().is_relative_to(history_dir.resolve())
                    and artifact.is_file()
                    and build_history.sha256_file(artifact) == entry.sha256
                    and not ImageInfo.inspect(artifact).errors()):
                return artifact
    # An existing history must never silently fall back to a stale output file.
    return history_dir / "no-installable-build.zImage" if (history_dir / "index.json").exists() else DEFAULT_IMAGE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prinux", type=Path, default=DEFAULT_PRINUX, help="recovery asset directory")
    parser.add_argument("--image", type=Path, default=None, help="pin an image; default automatically follows the newest valid history build")
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--history-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    parser.add_argument(
        "--uboot-history-dir", type=Path, default=DEFAULT_UBOOT_HISTORY_DIR
    )
    parser.add_argument("--uuu", help="path to the uuu executable")
    parser.add_argument("--interval", type=float, default=1.0, help="USB probe interval in seconds")
    parser.add_argument("--once", action="store_true", help="print device and image status, then exit")
    parser.add_argument("--json", action="store_true", help="emit JSON with --once")
    parser.add_argument("--no-admin", action="store_true", help=argparse.SUPPRESS)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.interval < 0.2:
        parser.error("--interval must be at least 0.2 seconds")
    detector = Detector(args.uuu)
    if args.once:
        status = detector.probe()
        build_history.prune_failed_builds(args.history_dir.expanduser().resolve())
        image = ImageInfo.inspect((args.image or preferred_recovery_image(
            args.history_dir.expanduser().resolve())).expanduser().resolve())
        history = build_history.load_history(args.history_dir.expanduser().resolve())
        uboot_builds = uboot_history.load_history(
            args.uboot_history_dir.expanduser().resolve()
        )
        selected_uboot = uboot_history.preferred_entry(uboot_builds)
        payload = {
            "device": {**asdict(status), "connected": status.connected, "recovery": status.recovery},
            "image": {
                "path": str(image.path),
                "exists": image.exists,
                "size": image.size,
                "sha256": image.sha256,
                "valid": not image.errors(),
                "errors": image.errors(),
                "signed_update": image.signed_update,
                "update_version": image.update_version,
                "runtime_update_ready": status.mode == "upsilon" and not image.update_errors(),
                "update_errors": image.update_errors(),
                "development_update_candidate": status.mode == "upsilon" and
                    not image.signed_update and not image.errors(),
                "development_handoff_verified": False,
                "development_update_note": "U selects the single-slot development writer for unsigned capsules; "
                    "device capability and recovery handoff are checked at operation start",
            },
            "nand_target": NAND_SLOT,
            "nand_target_bytes": NAND_SLOT_BYTES,
            "history": {
                "directory": str(args.history_dir.expanduser().resolve()),
                "count": len(history),
                "latest": asdict(history[0]) if history else None,
            },
            "uboot_history": {
                "directory": str(args.uboot_history_dir.expanduser().resolve()),
                "count": len(uboot_builds),
                "verification_baseline": asdict(selected_uboot) if selected_uboot else None,
            },
        }
        if args.json:
            print(json.dumps(payload, sort_keys=True))
        else:
            validity = "valid" if not image.errors() else "invalid"
            print(f"{status.label}: {status.detail}")
            print(f"Image: {image.path} ({validity}, {human_size(image.size)})")
        return 0 if status.connected else 1
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("interactive mode requires a terminal; use --once for scripts")
    curses.wrapper(LefonyOSPrimeInstaller(args).run)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
