#!/usr/bin/env python3
"""Physical-target firmware must collect ADC data even with GPT1 stopped.

Uses an ephemeral NAND overlay, USB diagnostics, and a QTest timer fault.
Set PRIME_G2_CURRENT_CAPSULE to the candidate; no physical device is touched.
"""
import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from prime_usb_host import PrimeUSBHost

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prime_g2_usb_diag import battery_diagnostics, battery_display_status, elapsed_millis

boot = importlib.import_module("test-prime-g2-nand-rom-boot")
QTest = importlib.import_module("test-prime-g2-rom-recovery").QTest
QMP = importlib.import_module("test-prime-g2-rom-recovery").QMP


def main():
    with tempfile.TemporaryDirectory(prefix="lf-battery-", dir="/tmp") as directory:
        directory = Path(directory)
        overlay = boot.capsule_overlay(directory)
        uart, usb, qtest = (directory / name for name in ("uart", "usb", "qtest"))
        qmp = directory / "qmp"
        command = boot.command(overlay, usb_path=usb, serial=f"file:{uart}", qmp_path=qmp)
        command += ["-qtest", f"unix:{qtest},server=on,wait=off", "-qtest-log", "/dev/null"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = None
        try:
            q = QTest(qtest)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if uart.exists() and "entering calculator runtime" in uart.read_text(errors="replace"):
                    break
                if process.poll() is not None:
                    raise AssertionError("guest exited before runtime")
                time.sleep(0.05)
            else:
                raise AssertionError("guest did not reach runtime")
            # Reproduce the physical failure before ten samples can accumulate.
            q.writel(0x02098000, 0)
            with PrimeUSBHost(usb) as host:
                host.connect_and_enumerate()

                class Device:
                    def read(self, request, length, value=0):
                        return host.control_in(0xC0, request, value=value, length=length)

                device = Device()
                first = battery_diagnostics(device)
                first_elapsed = elapsed_millis(device)
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    final = battery_diagnostics(device)
                    if final["valid"]:
                        break
                    time.sleep(0.1)
                assert final["valid"] == 1, final
                assert final["raw"] == 211 and final["millivolts"] == 3853, final
                assert final["gpt_count"] == first["gpt_count"], (first, final)
                assert final["snvs_rtc_low"] != first["snvs_rtc_low"], (first, final)
                assert elapsed_millis(device) > first_elapsed
                print("PASS: stopped GPT1; live SNVS; USB ADC=211, voltage=3853 mV", flush=True)
                # Mutate only the emulator's battery model, never a real PMIC.
                # Pause at an idle I2C boundary to avoid corrupting a guest poll.
                monitor = QMP(qmp)
                try:
                    for _ in range(100):
                        monitor.execute("stop")
                        if not q.readl(0x021a000c) & 0x20:
                            break
                        monitor.execute("cont")
                        time.sleep(0.01)
                    else:
                        raise AssertionError("I2C did not become idle")
                    def write8(address, value):
                        q.command(f"writeb 0x{address:x} 0x{value:x}")
                    write8(0x021a0008, 0xb0) # master transmit
                    for byte in (0x10, 0xf0, 3, 4090 & 255, 4090 >> 8, 0):
                        write8(0x021a0010, byte)
                    write8(0x021a0008, 0x80) # STOP; full model cell, USB power removed
                    write8(0x021a000c, 0)
                    monitor.execute("cont")
                finally:
                    monitor.close()
                # Let the ten-sample filter and existing 30-second percentage
                # hold settle from the initial 75% fixture to the full cell.
                # The hold is intentional hysteresis, not the icon regression.
                time.sleep(31)
                sampled = battery_diagnostics(device)
                assert sampled["valid"] and 4000 < sampled["millivolts"] < 4200, sampled
                for _ in range(100):
                    status = battery_display_status(device)
                    assert status == {"level": 3, "percent": 100}, status
                    time.sleep(0.03)
                print("PASS: unplugged full battery remains FULL / 100% across charger polls", flush=True)
                # Simulate a two-day suspend gap: pause CPU execution while
                # the always-on hardware counter advances. This is not a
                # calendar setter, so the entire interval must be counted.
                # Cross the old 32-bit counter's ~36-hour rollover too.
                before_sleep = elapsed_millis(device)
                monitor = QMP(qmp)
                try:
                    monitor.execute("stop")
                    lpcr = q.readl(0x020cc038)
                    counter = ((q.readl(0x020cc050) & 0x7fff) << 32) | q.readl(0x020cc054)
                    after = (counter + 2 * 86400 * 32768) & ((1 << 47) - 1)
                    q.writel(0x020cc038, lpcr & ~1)
                    q.writel(0x020cc054, after & 0xffffffff)
                    q.writel(0x020cc050, after >> 32)
                    q.writel(0x020cc038, lpcr)
                    monitor.execute("cont")
                finally:
                    monitor.close()
                sleep_delta = elapsed_millis(device) - before_sleep
                assert 172800000 <= sleep_delta < 172805000, sleep_delta
                assert battery_display_status(device) == {"level": 3, "percent": 100}
                print(f"PASS: two-day sleep gap counted in full ({sleep_delta} ms), USB/battery responsive", flush=True)
                if os.environ.get("PRIME_G2_BATTERY_SCREENSHOT"):
                    subprocess.run([sys.executable, str(Path(__file__).with_name("qmp-screendump.py")),
                                    str(qmp), os.environ["PRIME_G2_BATTERY_SCREENSHOT"]], check=True)
        finally:
            if q:
                q.close()
            boot.stop(process)


if __name__ == "__main__":
    main()
