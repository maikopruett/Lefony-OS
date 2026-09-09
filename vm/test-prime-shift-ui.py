#!/usr/bin/env python3
"""Exercise Shift chords using the emulator-target KPP matrix driver.

Captures screens for visual qualification; never sends keys to real hardware.
This does not qualify the physical GPIO keyboard scanner or physical NAND boot.
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
    parser.add_argument("--elf", type=Path, required=True, help="emulator-target ELF for the modeled KPP driver")
    options = parser.parse_args()
    output = boot.ROOT / "build/lefony-keyboard-qualification"
    output.mkdir(exist_ok=True)
    keymap = (boot.ROOT / "ports/lefony-prime-g2/ion/src/prime_g2/keymap.inc").read_text()
    matrix = {name: (int(row), int(col)) for name, row, col in
              re.findall(r"PRIME_G2_KEY\((\w+),\s*\d+,\s*\w+,\s*(\d+),\s*(\d+)\)", keymap)}
    with tempfile.TemporaryDirectory(prefix="lf-shift-ui-", dir="/tmp") as directory:
        directory = Path(directory)
        overlay = boot.capsule_overlay(directory)
        uart, qtest, qmp = (directory / name for name in ("uart", "qtest", "qmp"))
        args = boot.command(overlay, serial=f"file:{uart}", qmp_path=qmp)
        if options.elf:
            args[args.index("-machine") + 1] = "mcimx6ul-evk"
            args += ["-kernel", str(options.elf.resolve())]
        args += ["-qtest", f"unix:{qtest},server=on,wait=off", "-qtest-log", "/dev/null"]
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = monitor = None
        try:
            q = recovery.QTest(qtest)
            monitor = recovery.QMP(qmp)
            deadline = time.monotonic() + 30
            while not uart.exists() or "entering calculator runtime" not in uart.read_text(errors="replace"):
                if time.monotonic() > deadline or process.poll() is not None:
                    raise AssertionError("guest did not boot: " + uart.read_text(errors="replace")[-2000:])
                time.sleep(.1)
            time.sleep(2)

            def press(name):
                row, col = matrix[name]
                assert row < 8 and col < 8
                for down in (True, False):
                    q.command(f"writew 0x020b8008 {((row << 8) | col | (0x8000 if down else 0)):#x}")
                    time.sleep(.20)

            def shift(name):
                press("shift")
                press(name)

            def reset_editor():
                for _ in range(3): press("back")
                press("home")
                shift("back")

            def capture(name):
                time.sleep(.25)
                path = output / f"{name}.ppm"
                monitor.execute("screendump", {"filename": str(path)})
                print(f"Captured {path}", flush=True)
                return path.read_bytes()

            screens = []
            for key, name in (("seven", "lists"), ("four", "matrices"),
                              ("six", "calculus"), ("units", "units")):
                reset_editor()
                shift(key)
                screens.append(capture(name))
            assert len(set(screens)) == 4, "category shortcuts did not reach distinct screens"
            for key, name in (("five", "matrix-template"), ("nine", "vector-template")):
                reset_editor()
                shift(key)
                press("one")
                capture(name)
            reset_editor()
            press("one")
            press("plus")
            press("two")
            shift("ok")
            capture("shift-enter-result")
            reset_editor()
            press("toolbox")
            capture("ordinary-toolbox")
            reset_editor()
            press("three")
            press("square")
            capture("square-input")
            press("ok")
            capture("square-result")
            assert process.poll() is None
        finally:
            if uart.exists(): shutil.copy2(uart, output / "uart.log")
            if monitor: monitor.close()
            if q: q.close()
            boot.stop(process)


if __name__ == "__main__":
    main()
