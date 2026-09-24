#!/usr/bin/env python3
"""Exercise coordinate touch through modeled Goodix I2C and the actual UI.

Uses the emulator-target ELF/KPP driver; no physical device is changed.
"""
import argparse
import importlib
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time

boot = importlib.import_module("test-prime-g2-nand-rom-boot")
recovery = importlib.import_module("test-prime-g2-rom-recovery")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--display-settings", action="store_true")
    parser.add_argument("--display-settings-only", action="store_true")
    parser.add_argument("--calculation-history", action="store_true")
    parser.add_argument("--functions", action="store_true")
    options = parser.parse_args()
    output = boot.ROOT / "build/lefony-touch-qualification"
    output.mkdir(parents=True, exist_ok=True)
    matrix = {name: (int(row), int(col)) for name, row, col in re.findall(
        r"PRIME_G2_KEY\((\w+),\s*\d+,\s*\w+,\s*(\d+),\s*(\d+)\)",
        (boot.ROOT / "ports/lefony-prime-g2/ion/src/prime_g2/keymap.inc").read_text())}
    with tempfile.TemporaryDirectory(prefix="lf-touch-", dir="/tmp") as folder:
        directory = Path(folder)
        uart, qtest, qmp, control = (directory / name for name in ("uart", "qtest", "qmp", "control"))
        args = [str(boot.QEMU), "-machine", "mcimx6ul-evk", "-m", "256M",
                "-global", "imx6ul-lcdif.prime-g2-panel=on",
                "-global", "prime-g2-pf1550.external-power=on",
                "-display", "none", "-monitor", "none", "-serial", f"file:{uart}",
                "-qmp", f"unix:{qmp},server=on,wait=off", "-no-reboot"]
        args += ["-kernel", str(options.elf.resolve()), "-serial", "null", "-chardev",
                 f"socket,id=touchcontrol,path={control},server=on,wait=off", "-serial", "chardev:touchcontrol",
                 "-qtest", f"unix:{qtest},server=on,wait=off", "-qtest-log", "/dev/null"]
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = monitor = channel = None
        try:
            q, monitor = recovery.QTest(qtest), recovery.QMP(qmp)
            deadline = time.monotonic() + 30
            while not uart.exists() or "entering calculator runtime" not in uart.read_text(errors="replace"):
                if time.monotonic() > deadline or process.poll() is not None:
                    raise AssertionError("guest failed to boot")
                time.sleep(.1)
            channel = socket.socket(socket.AF_UNIX)
            channel.settimeout(5)
            channel.connect(str(control))
            time.sleep(2)

            def raw(command):
                channel.sendall((command + "\n").encode())
                answer = b""
                while b"\n" not in answer:
                    chunk = channel.recv(1)
                    if not chunk:
                        raise RuntimeError("control UART closed before a reply")
                    answer += chunk
                return answer.decode().strip()

            def wait_guest_ms(milliseconds):
                # GPT virtual time can lag host wall time under TCG load.
                # Wait for the normal firmware timer, without advancing it or
                # changing the input path/acceptance assertions.
                start = int(raw('TIME GET').split()[1])
                deadline = time.monotonic() + 10
                while int(raw('TIME GET').split()[1]) - start < milliseconds:
                    assert time.monotonic() < deadline, 'guest timer stopped during input synchronization'
                    time.sleep(.01)

            def press(name):
                row, col = matrix[name]
                for down in (True, False):
                    q.command(f"writew 0x020b8008 {((row << 8) | col | (0x8000 if down else 0)):#x}")
                    wait_guest_ms(200)

            def touch(command):
                assert raw(command) == "OK"
                wait_guest_ms(500)

            def app(index):
                state = raw("STATE")
                assert state.startswith(f"STATE app={index} "), state
                print(state, flush=True)

            def capture(name):
                path = output / f"{name}.ppm"
                monitor.execute("screendump", {"filename": str(path)})
                print(f"Captured {name}", flush=True)
                return path.read_bytes()

            assert raw("PING") == "PONG"
            if options.functions:
                press("back")
                importlib.import_module('prime-functions-touch-check').check(raw, press, touch, app, capture)
                return
            if options.calculation_history:
                press("back")
                importlib.import_module('prime-calculation-touch-check').check(raw, press, touch, app, capture)
                return
            if options.display_settings_only:
                press("back")
                importlib.import_module('prime-display-settings-check').check(raw, press, touch, app, capture, q)
                return
            first_frames = int(raw("DISPLAY FRAMES").split()[1])
            assert first_frames > 0
            press("back") # Dismiss the initial USB-power modal before launcher hit-testing.
            press("apps")
            app(0)
            capture("launcher")
            # No prior keyboard selection: tap two different visible icons.
            touch("TAP 260 75")
            assert raw("TOUCH X") == "VALUE 260"
            assert raw("TOUCH Y") == "VALUE 75"
            capture("after-first-tap")
            app(3)
            capture("third-app")
            press("apps")
            touch("TAP 52 178")
            app(4)
            press("apps")
            top = capture("launcher-before-scroll")
            touch("SWIPE 160 190 160 65")
            app(0)
            assert capture("launcher-scrolled") != top
            touch("TAP 52 75")
            app(4) # Row 1 is now under this coordinate, not row 0.
            assert int(raw("DISPLAY FRAMES").split()[1]) > first_frames
            assert raw("DISPLAY TIMEOUTS") == "VALUE 0"
            assert raw("DISPLAY GUARDS") == "OK"
            press("home")
            app(1)
            press("toolbox")
            menu = capture("menu")
            # Exercise cell recycling repeatedly: animation timers must not
            # retain offscreen cells or become registered more than once.
            for _ in range(3):
                touch("SWIPE 180 190 180 75")
                touch("SWIPE 180 75 180 215")
            touch("SWIPE 180 190 180 75")
            app(1)
            assert capture("menu-scrolled") != menu
            touch("SWIPE 180 75 180 215")
            touch("TAP 150 73")
            capture("menu-inserted-absolute-value")
            press("shift")
            press("back")
            press("three")
            press("units")
            capture("palette")
            touch("TAP 192 51")
            capture("touch-square-input")
            press("ok")
            capture("touch-square-result")
            assert raw("RESULT EXACT") == "TEXT 9"
            press("units")
            assert raw("HOLD 192 51 700") == "OK"
            time.sleep(.12)
            press("back")
            time.sleep(.8)
            capture("key-cancels-touch")
            app(1)
            # Status bar and outside coordinates no longer impersonate Back/Apps.
            touch("TAP 10 5")
            app(1)
            assert raw("DISPLAY TIMEOUTS") == "VALUE 0"
            print("PASS: frame-boundary presentation throughout scrolling; zero timeouts", flush=True)
            # A stopped scanout must not hang input or overwrite DMA-owned
            # memory. Restore RUN and verify that queued/dirty frames recover.
            press("toolbox")
            q.command("writel 0x021c8008 0x1") # LCDIF CTRL_CLR: RUN
            touch("SWIPE 180 190 180 75")
            failed = int(raw("DISPLAY TIMEOUTS").split()[1])
            assert failed > 0
            assert raw("DISPLAY GUARDS") == "OK"
            frames = int(raw("DISPLAY FRAMES").split()[1])
            q.command("writel 0x021c8004 0x1") # LCDIF CTRL_SET: RUN
            press("back")
            time.sleep(.2)
            assert int(raw("DISPLAY FRAMES").split()[1]) > frames
            assert raw("DISPLAY GUARDS") == "OK"
            print("PASS: stopped LCDIF stays responsive and frame swaps recover", flush=True)
            if options.display_settings:
                importlib.import_module('prime-display-settings-check').check(raw, press, touch, app, capture, q)
            assert process.poll() is None
            print("PASS: coordinate app selection, launcher/menu scrolling, palette tap, cancellation", flush=True)
        finally:
            if uart.exists(): shutil.copy2(uart, output / "uart.log")
            if channel: channel.close()
            if monitor: monitor.close()
            if q: q.close()
            boot.stop(process)


if __name__ == "__main__":
    main()
