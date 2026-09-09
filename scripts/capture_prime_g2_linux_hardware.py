#!/usr/bin/env python3
"""Capture a read-only HP Prime G2 hardware reference over Linux USB serial.

The calculator must be booted into the pristine Prinux image with its root
console available on ttyGS0.  This tool intentionally avoids i2c scans,
register writes, NAND reads beyond hashing the known DTB payload, and any
persistent changes to the target.  debugfs is mounted only when needed and is
unmounted again when this tool mounted it.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import select
import sys
import termios
import time
from typing import Iterable


BAUD = termios.B115200
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "hardware" / "prime_g2"


# Configuration/status registers that are safe and useful to read after the
# stock Linux drivers have initialized the board.  Do not add FIFO/data-port or
# read-to-clear registers without checking the relevant reference manual.
REGISTER_GROUPS: dict[str, tuple[tuple[str, int, int], ...]] = {
    "ccm": (
        ("CCM_CCR", 0x020C4000, 32),
        ("CCM_CBCDR", 0x020C4014, 32),
        ("CCM_CBCMR", 0x020C4018, 32),
        ("CCM_CSCMR1", 0x020C401C, 32),
        ("CCM_CSCDR2", 0x020C4038, 32),
        ("CCM_CCGR0", 0x020C4068, 32),
        ("CCM_CCGR1", 0x020C406C, 32),
        ("CCM_CCGR2", 0x020C4070, 32),
        ("CCM_CCGR3", 0x020C4074, 32),
        ("CCM_CCGR4", 0x020C4078, 32),
        ("CCM_CCGR5", 0x020C407C, 32),
        ("CCM_CCGR6", 0x020C4080, 32),
    ),
    "src": (
        ("SRC_SCR", 0x020D8000, 32),
        ("SRC_SBMR1", 0x020D8004, 32),
        ("SRC_SRSR", 0x020D8008, 32),
        ("SRC_SBMR2", 0x020D801C, 32),
        ("SRC_GPR9", 0x020D8040, 32),
        ("SRC_GPR10", 0x020D8044, 32),
    ),
    "lcdif": (
        ("LCDIF_CTRL", 0x021C8000, 32),
        ("LCDIF_CTRL1", 0x021C8010, 32),
        ("LCDIF_CTRL2", 0x021C8020, 32),
        ("LCDIF_TRANSFER_COUNT", 0x021C8030, 32),
        ("LCDIF_CUR_BUF", 0x021C8040, 32),
        ("LCDIF_NEXT_BUF", 0x021C8050, 32),
        ("LCDIF_VDCTRL0", 0x021C8070, 32),
        ("LCDIF_VDCTRL1", 0x021C8080, 32),
        ("LCDIF_VDCTRL2", 0x021C8090, 32),
        ("LCDIF_VDCTRL3", 0x021C80A0, 32),
        ("LCDIF_VDCTRL4", 0x021C80B0, 32),
        ("LCDIF_DEBUG0", 0x021C81D0, 32),
    ),
    "pwm7": (
        ("PWM7_CR", 0x020F8000, 32),
        ("PWM7_SR", 0x020F8004, 32),
        ("PWM7_IR", 0x020F8008, 32),
        ("PWM7_SAR", 0x020F800C, 32),
        ("PWM7_PR", 0x020F8010, 32),
        ("PWM7_CNR", 0x020F8014, 32),
    ),
    "gpio": tuple(
        (f"GPIO{bank}_{register}", base + offset, 32)
        for bank, base in ((1, 0x0209C000), (2, 0x020A0000),
                           (3, 0x020A4000), (4, 0x020A8000))
        # DR/GDIR/PSR are enough to reconstruct current pin direction and
        # level.  Interrupt registers are deliberately omitted: the old 4.14
        # /dev/mem path has stalled while reading the full GPIO window.
        for register, offset in (("DR", 0x0), ("GDIR", 0x4), ("PSR", 0x8))
    ),
    "kpp": (
        ("KPP_KPCR", 0x020B8000, 16),
        ("KPP_KPSR", 0x020B8002, 16),
        ("KPP_KDDR", 0x020B8004, 16),
        ("KPP_KPDR", 0x020B8006, 16),
    ),
    "iomuxc_display": (
        ("MUX_LCD_CLK", 0x020E0104, 32),
        ("MUX_LCD_ENABLE", 0x020E0108, 32),
        ("MUX_LCD_HSYNC", 0x020E010C, 32),
        ("MUX_LCD_VSYNC", 0x020E0110, 32),
        ("MUX_LCD_RESET", 0x020E0114, 32),
        *((f"MUX_LCD_DATA{i:02d}", 0x020E0118 + i * 4, 32) for i in range(8)),
        ("MUX_BACKLIGHT_PWM7", 0x020E01DC, 32),
        ("MUX_PANEL_SPI_SCK", 0x020E01E4, 32),
        ("MUX_PANEL_SPI_CS", 0x020E01E8, 32),
        ("MUX_PANEL_SPI_MOSI", 0x020E01EC, 32),
        ("PAD_LCD_CLK", 0x020E0390, 32),
        ("PAD_LCD_ENABLE", 0x020E0394, 32),
        ("PAD_LCD_HSYNC", 0x020E0398, 32),
        ("PAD_LCD_VSYNC", 0x020E039C, 32),
        ("PAD_LCD_RESET", 0x020E03A0, 32),
        *((f"PAD_LCD_DATA{i:02d}", 0x020E03A4 + i * 4, 32) for i in range(8)),
        ("PAD_BACKLIGHT_PWM7", 0x020E0468, 32),
        ("PAD_PANEL_SPI_SCK", 0x020E0470, 32),
        ("PAD_PANEL_SPI_CS", 0x020E0474, 32),
        ("PAD_PANEL_SPI_MOSI", 0x020E0478, 32),
    ),
}


CAPTURES: tuple[tuple[str, str], ...] = (
    ("system.txt", "uname -a; hostname; cat /etc/os-release; cat /proc/version; cat /proc/cmdline; cat /proc/cpuinfo; uptime"),
    ("memory-map.txt", "cat /proc/iomem; cat /proc/meminfo; cat /proc/devices; cat /proc/partitions; cat /proc/mtd"),
    ("interrupts.txt", "cat /proc/interrupts; cat /proc/softirqs"),
    ("kernel-log.txt", "dmesg"),
    ("modules.txt", "cat /proc/modules"),
    ("mounts.txt", "cat /proc/mounts; df -h"),
    ("input.txt", "cat /proc/bus/input/devices; for p in /sys/class/input/input*; do printf '\\n[%s]\\n' \"$p\"; cat \"$p/name\" 2>/dev/null; cat \"$p/id/bustype\" \"$p/id/vendor\" \"$p/id/product\" \"$p/id/version\" 2>/dev/null; find \"$p/capabilities\" -maxdepth 1 -type f -exec sh -c 'printf \"%s=\" \"$1\"; cat \"$1\"' sh {} \\; 2>/dev/null; done"),
    ("framebuffer.txt", "fbset -i 2>&1; for p in /sys/class/graphics/fb* /sys/class/backlight/*; do test -e \"$p\" || continue; printf '\\n[%s]\\n' \"$p\"; for f in \"$p\"/*; do test -f \"$f\" || continue; printf '%s=' \"$f\"; cat \"$f\" 2>/dev/null; done; done"),
    ("power-thermal-rtc.txt", "for c in power_supply thermal rtc watchdog leds; do for p in /sys/class/$c/*; do test -e \"$p\" || continue; printf '\\n[%s]\\n' \"$p\"; for f in \"$p\"/*; do test -f \"$f\" || continue; printf '%s=' \"$f\"; cat \"$f\" 2>/dev/null; done; done; done"),
    ("platform-devices.txt", "for p in /sys/bus/platform/devices/*; do printf '%s|driver=%s|modalias=' \"$p\" \"$(basename \"$(readlink \"$p/driver\" 2>/dev/null)\" 2>/dev/null)\"; cat \"$p/modalias\" 2>/dev/null || printf '\\n'; done"),
    ("i2c-spi-devices.txt", "for bus in i2c spi; do for p in /sys/bus/$bus/devices/*; do test -e \"$p\" || continue; printf '\\n[%s] driver=%s\\n' \"$p\" \"$(basename \"$(readlink \"$p/driver\" 2>/dev/null)\" 2>/dev/null)\"; cat \"$p/name\" \"$p/modalias\" \"$p/uevent\" 2>/dev/null; done; done"),
    ("usb.txt", "for p in /sys/class/udc/* /sys/class/tty/ttyGS* /sys/bus/usb/devices/*; do test -e \"$p\" || continue; printf '\\n[%s]\\n' \"$p\"; cat \"$p/uevent\" \"$p/product\" \"$p/manufacturer\" \"$p/idVendor\" \"$p/idProduct\" 2>/dev/null; done"),
    ("storage.txt", "cat /sys/class/ubi/ubi*/uevent 2>/dev/null; for p in /sys/class/mtd/mtd*; do printf '\\n[%s]\\n' \"$p\"; cat \"$p/name\" \"$p/type\" \"$p/size\" \"$p/erasesize\" \"$p/writesize\" \"$p/oobsize\" 2>/dev/null; done"),
    ("boot-dtb-hash.txt", "dd if=/dev/mtd2 bs=1 count=30960 2>/dev/null | sha256sum"),
)


class SerialShell:
    def __init__(self, port: str, timeout: float = 30.0):
        self.port = port
        self.timeout = timeout
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        attrs = termios.tcgetattr(self.fd)
        attrs[0] = 0
        attrs[1] = 0
        attrs[2] = (attrs[2] & ~(termios.CSIZE | termios.PARENB | termios.CSTOPB)) | termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] = 0
        attrs[4] = BAUD
        attrs[5] = BAUD
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        self.sequence = 0
        self.watchdog_lease: str | None = None
        self.watchdog_stop: str | None = None

    def close(self) -> None:
        os.close(self.fd)

    def _drain(self, seconds: float = 0.3) -> bytes:
        result = bytearray()
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            ready, _, _ = select.select([self.fd], [], [], 0.05)
            if ready:
                try:
                    result.extend(os.read(self.fd, 65536))
                except BlockingIOError:
                    pass
        return bytes(result)

    def prepare(self) -> None:
        self._drain()
        os.write(self.fd, b"\n")
        banner = self._drain(1.0)
        if b"login:" in banner:
            os.write(self.fd, b"root\n")
            self._drain(1.0)
        # Suppress command echo so marker parsing cannot mistake an echoed
        # command for the command's actual completion marker.
        os.write(self.fd, b"stty -echo\n")
        self._drain(0.5)
        probe = self.run("uname -s", timeout=5.0)
        if "Linux" not in probe:
            raise RuntimeError(f"serial console did not return a Linux shell: {probe!r}")

    def restore(self) -> None:
        try:
            os.write(self.fd, b"stty echo\n")
            self._drain(0.2)
        except OSError:
            pass

    def run(self, command: str, timeout: float | None = None) -> str:
        self.sequence += 1
        token = f"PRIMEG2_{os.getpid()}_{self.sequence}"
        begin = f"__{token}_BEGIN__"
        end_prefix = f"__{token}_END__:"
        lease_seconds = max(20, int(timeout or self.timeout) + 10)
        lease_refresh = ""
        if self.watchdog_lease:
            lease_refresh = (
                f"prime_capture_now=$(date +%s); "
                f"echo $((prime_capture_now + {lease_seconds})) > {self.watchdog_lease}\n"
            )
        payload = (
            f"printf '\\n{begin}\\n'\n"
            f"{lease_refresh}{command}\n"
            "prime_capture_rc=$?\n"
            f"printf '\\n{end_prefix}%s\\n' \"$prime_capture_rc\"\n"
        ).encode()
        self._drain()
        os.write(self.fd, payload)
        data = bytearray()
        deadline = time.monotonic() + (timeout or self.timeout)
        end_re = re.compile(re.escape(end_prefix.encode()) + rb"([0-9]+)\r?\n")
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.fd], [], [], 0.25)
            if not ready:
                continue
            try:
                data.extend(os.read(self.fd, 65536))
            except BlockingIOError:
                continue
            match = end_re.search(data)
            if match:
                start = data.find(begin.encode())
                if start < 0:
                    raise RuntimeError(f"missing begin marker for {token}")
                start += len(begin)
                body = bytes(data[start:match.start()]).lstrip(b"\r\n")
                rc = int(match.group(1))
                text = body.replace(b"\r\n", b"\n").decode("utf-8", "replace")
                if rc:
                    text += f"\n[capture command exit status: {rc}]\n"
                return text
        # A blocked /dev/mem read must not strand the ttyGS0 shell.  Ctrl-C is
        # non-persistent and returns the console to a known state so later,
        # independent probes may continue.
        os.write(self.fd, b"\x03\n")
        self._drain(1.0)
        raise TimeoutError(f"timed out after {timeout or self.timeout}s: {command}")

    def arm_watchdog(self, timeout_seconds: int = 15) -> bool:
        """Arm a renewable watchdog lease before risky MMIO probes."""
        token = f"prime-capture-{os.getpid()}"
        lease = f"/tmp/{token}.lease"
        stop = f"/tmp/{token}.stop"
        probe = self.run(
            "test -c /dev/watchdog && test -w /dev/watchdog && printf yes || printf no",
            timeout=5.0,
        )
        if "yes" not in probe:
            return False
        command = (
            f"rm -f {stop}; now=$(date +%s); echo $((now + 30)) > {lease}; "
            f"test ! -w /sys/class/watchdog/watchdog0/timeout || "
            f"echo {timeout_seconds} > /sys/class/watchdog/watchdog0/timeout; "
            "( exec 9>/dev/watchdog || exit 1; "
            f"while test ! -e {stop}; do now=$(date +%s); until=$(cat {lease} 2>/dev/null || echo 0); "
            "test \"$now\" -lt \"$until\" || break; printf '\\0' >&9; sleep 2; done; "
            f"if test -e {stop}; then printf V >&9; rm -f {lease} {stop}; "
            "else sleep 3600; fi ) >/dev/null 2>&1 & printf armed"
        )
        result = self.run(command, timeout=5.0)
        if "armed" not in result:
            return False
        self.watchdog_lease = lease
        self.watchdog_stop = stop
        return True

    def disarm_watchdog(self) -> None:
        if not self.watchdog_stop:
            return
        try:
            self.run(f"touch {self.watchdog_stop}; sleep 3", timeout=7.0)
        finally:
            self.watchdog_lease = None
            self.watchdog_stop = None


def auto_port() -> str:
    ports = sorted(Path("/dev").glob("cu.usbmodem*"))
    if len(ports) != 1:
        raise RuntimeError(f"expected one /dev/cu.usbmodem* device, found: {ports}")
    return str(ports[0])


def register_command(entries: Iterable[tuple[str, int, int]]) -> str:
    commands = []
    for name, address, width in entries:
        commands.append(
            f"printf '{name}|0x{address:08x}|{width}|' && devmem 0x{address:08x} {width}"
        )
    return "; ".join(commands)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_offline_manifest(directory: Path, reason: str) -> Path:
    """Seal an interrupted capture without reconnecting to the calculator."""
    directory = directory.resolve()
    if not directory.is_dir():
        raise RuntimeError(f"capture directory does not exist: {directory}")
    files = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            files.append({
                "file": path.name,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            })
    manifest = {
        "schema": 1,
        "captured_at_utc": directory.name,
        "status": "incomplete",
        "incomplete_reason": reason,
        "port": "unknown (offline recovery)",
        "capture_policy": "read-only; no I2C scan; no MMIO writes; no NAND modification",
        "files": files,
    }
    target = directory / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="USB serial port (auto-detected by default)")
    parser.add_argument("--output", type=Path, help="capture directory")
    parser.add_argument("--dtb", type=Path, help="matching DTB to preserve alongside the capture")
    parser.add_argument(
        "--finalize-existing", type=Path,
        help="write a hash manifest for an interrupted existing capture and exit",
    )
    parser.add_argument(
        "--incomplete-reason",
        default="capture interrupted before normal finalization",
        help="reason recorded with --finalize-existing",
    )
    parser.add_argument(
        "--watchdog-safe", action="store_true",
        help="arm a renewable hardware-watchdog lease before bounded probes",
    )
    args = parser.parse_args()

    if args.finalize_existing:
        print(write_offline_manifest(args.finalize_existing, args.incomplete_reason))
        return 0

    port = args.port or auto_port()
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or DEFAULT_ROOT / "captures" / timestamp
    output.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, object]] = []

    shell = SerialShell(port)
    watchdog_armed = False
    try:
        shell.prepare()
        if args.watchdog_safe:
            watchdog_armed = shell.arm_watchdog()
            if not watchdog_armed:
                raise RuntimeError(
                    "--watchdog-safe requested but /dev/watchdog could not be armed"
                )
        for filename, command in CAPTURES:
            path = output / filename
            try:
                result = shell.run(command, timeout=60.0)
                path.write_text(result)
                records.append({"file": filename, "sha256": sha256(path), "command": command})
            except Exception as exc:
                path.write_text(f"capture failed: {exc}\n")
                records.append({"file": filename, "error": str(exc), "command": command})

        for group, entries in REGISTER_GROUPS.items():
            filename = f"registers-{group}.txt"
            path = output / filename
            lines = []
            failed = []
            # Probe one address at a time.  This lets us interrupt and record a
            # clock-gated/unreadable peripheral without losing the rest of the
            # snapshot or leaving the console blocked in devmem.
            for entry in entries:
                try:
                    lines.append(shell.run(register_command((entry,)), timeout=5.0))
                except Exception as exc:
                    name, address, width = entry
                    failed.append(name)
                    lines.append(f"{name}|0x{address:08x}|{width}|UNREADABLE|{exc}\n")
            path.write_text("".join(lines))
            record: dict[str, object] = {
                "file": filename,
                "sha256": sha256(path),
                "register_count": len(entries),
            }
            if failed:
                record["unreadable_registers"] = failed
            records.append(record)

        try:
            debug_was_mounted = "yes" in shell.run(
                "grep -q ' /sys/kernel/debug ' /proc/mounts && printf yes || printf no",
                timeout=5.0,
            )
            if not debug_was_mounted:
                shell.run("mount -t debugfs debugfs /sys/kernel/debug", timeout=5.0)
            try:
                debug_files = {
                    "debugfs-clocks.txt": "/sys/kernel/debug/clk/clk_summary",
                    "debugfs-gpio.txt": "/sys/kernel/debug/gpio",
                    "debugfs-pinmux.txt": "/sys/kernel/debug/pinctrl/*/pinmux-pins",
                }
                for filename, remote in debug_files.items():
                    path = output / filename
                    try:
                        result = shell.run(
                            f"for p in {remote}; do test -f \"$p\" || continue; printf '[%s]\\n' \"$p\"; cat \"$p\"; done",
                            timeout=60.0,
                        )
                        path.write_text(result)
                        records.append({"file": filename, "sha256": sha256(path), "runtime_only_debugfs_mount": not debug_was_mounted})
                    except Exception as exc:
                        path.write_text(f"capture failed: {exc}\n")
                        records.append({"file": filename, "error": str(exc)})
            finally:
                if not debug_was_mounted:
                    try:
                        shell.run("umount /sys/kernel/debug", timeout=5.0)
                    except Exception as exc:
                        records.append({"operation": "unmount-debugfs", "error": str(exc)})
        except Exception as exc:
            records.append({"operation": "capture-debugfs", "error": str(exc)})

        # Preserve a byte-exact view of the live kernel's expanded device tree.
        try:
            encoded = shell.run("tar -cz -C /sys/firmware/devicetree base 2>/dev/null | base64", timeout=90.0)
            live_tree = base64.b64decode("".join(encoded.split()), validate=True)
            path = output / "live-device-tree.tar.gz"
            path.write_bytes(live_tree)
            records.append({"file": path.name, "sha256": sha256(path)})
        except Exception as exc:
            (output / "live-device-tree.base64-error.txt").write_text(locals().get("encoded", ""))
            records.append({"file": "live-device-tree.base64-error.txt", "error": str(exc)})
    finally:
        if watchdog_armed:
            try:
                shell.disarm_watchdog()
            except Exception:
                # If USB disappeared, lease expiry performs the requested reset.
                pass
        shell.restore()
        shell.close()

    if args.dtb:
        dtb = args.dtb.resolve()
        target = output / "imx6ull-14x14-prime.dtb"
        target.write_bytes(dtb.read_bytes())
        records.append({"file": target.name, "sha256": sha256(target), "source": str(dtb)})

    manifest = {
        "schema": 1,
        "captured_at_utc": timestamp,
        "port": port,
        "capture_policy": "read-only; temporary debugfs mount; no I2C scan; no MMIO writes; no NAND modification",
        "watchdog_safe": watchdog_armed,
        "files": records,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
