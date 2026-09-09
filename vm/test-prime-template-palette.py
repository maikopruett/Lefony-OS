#!/usr/bin/env python3
"""UI qualification of the native palette via the emulator-target KPP driver.

No physical device is touched. Screens require visual inspection; this does
not exercise the real calculator's GPIO scanner.
"""
import argparse
import importlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

boot = importlib.import_module("test-prime-g2-nand-rom-boot")
recovery = importlib.import_module("test-prime-g2-rom-recovery")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--preview-only", action="store_true", help="capture palette and test bounds/cancel only")
    options = parser.parse_args()
    output = boot.ROOT / "build/lefony-template-qualification"
    output.mkdir(exist_ok=True)
    matrix = {name: (int(row), int(col)) for name, row, col in re.findall(
        r"PRIME_G2_KEY\((\w+),\s*\d+,\s*\w+,\s*(\d+),\s*(\d+)\)",
        (boot.ROOT / "ports/lefony-prime-g2/ion/src/prime_g2/keymap.inc").read_text())}
    with tempfile.TemporaryDirectory(prefix="lf-palette-", dir="/tmp") as folder:
        directory = Path(folder)
        overlay = boot.capsule_overlay(directory)
        uart, qtest, qmp = (directory / name for name in ("uart", "qtest", "qmp"))
        args = boot.command(overlay, serial=f"file:{uart}", qmp_path=qmp)
        args[args.index("-machine") + 1] = "mcimx6ul-evk"
        args += ["-kernel", str(options.elf.resolve()), "-qtest",
                 f"unix:{qtest},server=on,wait=off", "-qtest-log", "/dev/null"]
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = monitor = None
        try:
            q, monitor = recovery.QTest(qtest), recovery.QMP(qmp)
            deadline = time.monotonic() + 30
            while not uart.exists() or "entering calculator runtime" not in uart.read_text(errors="replace"):
                if time.monotonic() > deadline or process.poll() is not None:
                    raise AssertionError("guest failed to boot")
                time.sleep(.1)
            time.sleep(2)

            def press(name):
                row, col = matrix[name]
                for down in (True, False):
                    q.command(f"writew 0x020b8008 {((row << 8) | col | (0x8000 if down else 0)):#x}")
                    time.sleep(.2)

            def reset():
                for _ in range(3): press("back")
                press("home")
                press("shift")
                press("back")

            def capture(name):
                time.sleep(.25)
                path = output / f"{name}.ppm"
                monitor.execute("screendump", {"filename": str(path)})
                print(f"Captured {name}", flush=True)
                return path.read_bytes()

            reset()
            press("units")
            palette = capture("palette")
            press("left")
            press("up")
            assert capture("boundary") == palette, "selection escaped upper-left boundary"
            press("back")
            empty = capture("cancelled")
            assert empty != palette
            if options.preview_only:
                print("PASS: palette preview, boundary navigation, and cancel", flush=True)
                return
            for index in range(16):
                reset()
                press("units")
                for _ in range(index // 4): press("down")
                for _ in range(index % 4): press("right")
                press("ok")
                assert capture(f"template-{index:02d}") != empty, f"template {index} inserted nothing"
            reset()
            press("three")
            press("units")
            press("right")
            press("right")
            press("ok")
            capture("square-input")
            press("ok")
            capture("square-result")
            reset()
            press("toolbox")
            assert capture("ordinary-toolbox") != palette
            press("back")
            press("shift")
            press("units")
            assert capture("shift-units") != palette
            assert process.poll() is None
            print("PASS: 16 insertions, cancel/boundary, square workflow, Toolbox and Units isolation", flush=True)
        finally:
            if uart.exists(): shutil.copy2(uart, output / "uart.log")
            if monitor: monitor.close()
            if q: q.close()
            boot.stop(process)


if __name__ == "__main__":
    main()
