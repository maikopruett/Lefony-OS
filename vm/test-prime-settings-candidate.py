"""Capture Settings candidate screens through the emulated physical matrix."""
import importlib
from pathlib import Path
import socket
import subprocess
import tempfile
import time

boot = importlib.import_module("test-prime-g2-nand-rom-boot")
screen = importlib.import_module("qmp-screendump")
output = boot.ROOT / "build/lefony-settings-candidate"
boot.CURRENT_CAPSULE = output / "lefony-settings.zImage"


def main():
    with tempfile.TemporaryDirectory(prefix="lfui-", dir="/tmp") as folder:
        tmp = Path(folder)
        overlay = boot.capsule_overlay(tmp)
        qmp = tmp / "qmp"
        qtest = tmp / "qtest"
        uart = tmp / "uart"
        args = boot.command(overlay, serial=f"file:{uart}", qmp_path=qmp)
        args += ["-qtest", f"unix:{qtest},server=on,wait=off", "-qtest-log", "/dev/null"]
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 25
            while not uart.exists() or b"entering calculator runtime" not in uart.read_bytes():
                if time.monotonic() > deadline or process.poll() is not None:
                    raise RuntimeError("Candidate failed to boot")
                time.sleep(.1)
            time.sleep(2)
            with socket.socket(socket.AF_UNIX) as keys, socket.socket(socket.AF_UNIX) as display:
                keys.settimeout(3)
                display.settimeout(3)
                keys.connect(str(qtest))
                display.connect(str(qmp))
                key_stream = keys.makefile("rb")
                display_stream = display.makefile("rb")
                screen.receive_message(display_stream)
                screen.execute(display, display_stream, {"execute": "qmp_capabilities"})
                matrix = {"down": (4,5), "up": (5,4), "right": (7,1),
                          "left": (1,7), "ok": (7,0), "apps": (4,4), "back": (4,6)}
                def press(name):
                    row, col = matrix[name]
                    for down in (True, False):
                        keys.sendall(f"writew 0x020b8008 {((row << 8) | col | (0x8000 if down else 0)):#x}\n".encode())
                        assert key_stream.readline().startswith(b"OK")
                        time.sleep(.18)
                def capture(name):
                    response = screen.execute(display, display_stream, {
                        "execute": "screendump", "arguments": {"filename": str(output / f"{name}.ppm")}})
                    assert "error" not in response, response
                press("apps")
                capture("home-before-settings")
                for _ in range(3): press("down")
                for _ in range(2): press("right")
                press("ok")
                capture("settings")
                if (output / "settings.ppm").read_bytes() == (output / "home-before-settings.ppm").read_bytes():
                    raise AssertionError("KPP injection did not navigate: physical GPIO scan needs a supported input backend")
                for _ in range(12): press("down")
                press("ok")
                capture("about-version")
                for _ in range(8): press("down")
                capture("about-build")
                press("down")
                press("ok")
                capture("recovery-confirmation")
                press("ok")  # Cancel is selected by default; never request reset here.
                capture("recovery-cancelled")
                assert process.poll() is None
        finally:
            boot.stop(process)


if __name__ == "__main__":
    main()
