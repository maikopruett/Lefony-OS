#!/usr/bin/env python3
"""Check the physical-target main timer after complete NAND/UI startup.

Default: ephemeral emulator NAND overlay. --physical: read-only USB checks
on the connected calculator (no flash, reset, or peripheral writes).
"""
import argparse
import importlib
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prime_g2_usb_diag import LibUSB, battery_diagnostics, elapsed_millis
from prime_usb_host import PrimeUSBHost


def check(device, physical=False, elapsed=False):
    previous = battery_diagnostics(device)
    previous_elapsed = elapsed_millis(device) if elapsed else 0
    first = previous
    host_start = time.monotonic()
    for _ in range(10):
        time.sleep(1)
        current = battery_diagnostics(device)
        rtc_ticks = (current["snvs_rtc_low"] - previous["snvs_rtc_low"]) & 0xffffffff
        gpt_ticks = (current["gpt_count"] - previous["gpt_count"]) & 0xffffffff
        milliseconds = (current["millis"] - previous["millis"]) & 0xffffffff
        assert rtc_ticks > 0, current
        assert gpt_ticks > 0 and milliseconds > 0, (previous, current)
        rtc_ms = rtc_ticks * 1000 / 32768
        if elapsed:
            current_elapsed = elapsed_millis(device)
            elapsed_delta = current_elapsed - previous_elapsed
            assert abs(elapsed_delta - rtc_ms) < max(30, rtc_ms * .03), (elapsed_delta, rtc_ms)
            previous_elapsed = current_elapsed
        assert abs(milliseconds - gpt_ticks / 3000) < 3, (previous, current)
        # QEMU's SNVS uses its RTC/wall clock; GPT uses virtual time, which
        # excludes VM pauses. Only real hardware shares a physical time axis.
        if physical:
            assert abs(gpt_ticks / 3000 - rtc_ms) < max(10, rtc_ms * .02), (previous, current)
            assert abs(milliseconds - rtc_ms) < max(10, rtc_ms * .02), (previous, current)
        print(f'millis={current["millis"]} GPT={current["gpt_count"]} '
              f'delta={milliseconds}ms RTC={rtc_ms:.2f}ms', flush=True)
        previous = current
    elapsed = time.monotonic() - host_start
    print(f'PASS main timer: {current["millis"] - first["millis"]} ms '
          f'over {elapsed:.3f} host seconds; ten live GPT/RTC comparisons', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical", action="store_true")
    parser.add_argument("--elapsed", action="store_true", help="also check sleep-aware elapsed clock via USB")
    args = parser.parse_args()
    if args.physical:
        with LibUSB() as device:
            check(device, physical=True, elapsed=args.elapsed)
        return
    boot = importlib.import_module("test-prime-g2-nand-rom-boot")
    with tempfile.TemporaryDirectory(prefix="lf-timer-", dir="/tmp") as folder:
        directory = Path(folder)
        overlay = boot.capsule_overlay(directory)
        uart, usb = directory / "uart", directory / "usb"
        process = subprocess.Popen(boot.command(overlay, usb_path=usb, serial=f"file:{uart}"),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if uart.exists() and "entering calculator runtime" in uart.read_text(errors="replace"):
                    break
                if process.poll() is not None:
                    raise AssertionError("guest exited before runtime")
                time.sleep(.05)
            else:
                raise AssertionError("guest did not reach runtime")
            with PrimeUSBHost(usb) as host:
                host.connect_and_enumerate()

                class Device:
                    def read(self, request, length, value=0):
                        return host.control_in(0xC0, request, value=value, length=length)

                check(Device(), elapsed=args.elapsed)
        finally:
            boot.stop(process)


if __name__ == "__main__":
    main()
