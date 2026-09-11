# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the actual LFAPP container through the Prime VM's guest loader."""
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from lfapp import unpack


class Channel:
    def __init__(self, path, process, timeout=30):
        end = time.monotonic() + timeout
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.settimeout(5)
        while True:
            try:
                self.socket.connect(str(path))
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if time.monotonic() > end or process.poll() is not None:
                    self.socket.close()
                    raise RuntimeError("emulator did not create its control socket")
                time.sleep(.05)
        self.file = self.socket.makefile("rwb", buffering=0)

    def command(self, command):
        self.file.write((command+"\n").encode())
        value = self.file.readline(4096)
        if not value.endswith(b"\n"):
            raise RuntimeError("emulator control response was incomplete")
        return value.decode().strip()

    def close(self):
        self.file.close()
        self.socket.close()


def exercise(package, qemu, firmware, *, headless=True, event=0, first=0, second=0, capture=None, interactive=False, events=None, controls=None, public_keys=()):
    from signing import MAGIC, verify
    content = package.read_bytes()
    metadata, _ = verify(content, public_keys) if content.startswith(MAGIC) else unpack(content)
    if not qemu.is_file() or not firmware.is_file():
        raise ValueError("VM firmware and custom QEMU are required; pass --firmware and --qemu")
    with tempfile.TemporaryDirectory(prefix="lf-sdk-", dir="/tmp") as folder:
        folder = Path(folder)
        payload = folder / "app.lfapp"
        shutil.copyfile(package, payload)
        uart = folder / "uart"
        control = folder / "control"
        qmp = folder / "qmp"
        qtest = folder / "qtest"
        command = [str(qemu), "-machine", "mcimx6ul-evk", "-m", "256M",
                   "-global", "imx6ul-lcdif.prime-g2-panel=on", "-display", "none" if headless else ("cocoa" if sys.platform == "darwin" else "sdl"),
                   "-monitor", "none", "-serial", f"file:{uart}", "-serial", "null",
                   "-chardev", f"socket,id=appcontrol,path={control},server=on,wait=off", "-serial", "chardev:appcontrol",
                   "-qtest", f"unix:{qtest},server=on,wait=off", "-qtest-log", "/dev/null",
                   "-qmp", f"unix:{qmp},server=on,wait=off", "-kernel", str(firmware), "-no-reboot",
                   "-device", f"loader,file={payload},addr=0x86000000,force-raw=on"]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        channel = monitor = None
        try:
            end = time.monotonic()+30
            while not uart.exists() or "entering calculator runtime" not in uart.read_text(errors="replace"):
                if process.poll() is not None or time.monotonic()>end:
                    raise RuntimeError("VM failed to boot: " + (uart.read_text(errors="replace")[-1500:] if uart.exists() else "no UART"))
                time.sleep(.05)
            channel = Channel(control, process)
            if channel.command("PING") != "PONG":
                raise RuntimeError("VM control handshake failed")
            reply = channel.command(f"APP LOAD {payload.stat().st_size}")
            if reply != "OK":
                raise RuntimeError(f"guest rejected app: {reply}")
            callbacks = []
            for e, a, b in (events or [(event, first, second)]):
                reply = channel.command(f"APP EVENT {e} {a} {b}")
                if not reply.startswith("RESULT "):
                    raise RuntimeError(f"unexpected app result: {reply}")
                result = int(reply.split()[1])
                callbacks.append({"event": e, "first": a, "second": b, "result": result})
                if result != 1:
                    break
            diagnostics = [channel.command(f"APP DIAG {i}") for i in range(3)]
            if channel.command("PING") != "PONG":
                raise RuntimeError("OS did not regain control after callback")
            if (interactive or controls is not None) and result == 1:
                if channel.command("APP LAUNCH") != "OK":
                    raise RuntimeError("VM firmware does not support the SDK launcher")
            if controls is not None and result == 1:
                controls(channel)
            if capture:
                monitor = Channel(qmp, process)
                json.loads(monitor.file.readline())
                def qmp_command(name, arguments=None):
                    monitor.file.write((json.dumps({"execute": name, "arguments": arguments or {}})+"\n").encode())
                    while True:
                        response = json.loads(monitor.file.readline())
                        if "event" in response:
                            continue
                        if "error" in response:
                            raise RuntimeError(str(response))
                        return response
                qmp_command("qmp_capabilities")
                time.sleep(.1)
                qmp_command("screendump", {"filename": str(capture.resolve())})
            if interactive and result == 1:
                print("Native app is running. Close the emulator window or press Ctrl-C to stop.", flush=True)
                try:
                    while process.poll() is None:
                        time.sleep(.2)
                except KeyboardInterrupt:
                    pass
            return {"app": metadata["id"], "package_sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                    "firmware_sha256": hashlib.sha256(firmware.read_bytes()).hexdigest(),
                    "result": result, "callbacks": callbacks, "diagnostics": diagnostics, "os_responsive": True, "target": "prime_g2_vm"}
        except Exception:
            if uart.exists():
                print(uart.read_text(errors="replace")[-2000:], file=sys.stderr)
            raise
        finally:
            if channel: channel.close()
            if monitor: monitor.close()
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)


def run(package, qemu, firmware, headless, testing, public_keys=()):
    report = exercise(package, qemu, firmware, headless=headless, capture=package.parent/"app.ppm", interactive=not testing, public_keys=public_keys)
    (package.parent/"run.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))
    return 0 if report["result"] == 1 else 1
