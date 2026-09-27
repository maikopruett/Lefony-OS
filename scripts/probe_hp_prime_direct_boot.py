#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, unmodified V15751 direct-load observation on the Prime QEMU model.

Synthetic erased NAND only. No hardware, firmware patches, or persistent NAND
overlay. A completed observation is not a passing boot qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time

from analyze_hp_prime_compatibility import ROOT, private_output, verify_input


def connect(path, process):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        sock = socket.socket(socket.AF_UNIX)
        sock.settimeout(5)
        try:
            sock.connect(str(path))
            return sock
        except (FileNotFoundError, ConnectionRefusedError):
            sock.close()
            if process.poll() is not None:
                raise RuntimeError("QEMU exited before its control socket opened")
            time.sleep(0.05)
    raise TimeoutError("QEMU control socket did not open")


def observe(qemu, image, out, seconds):
    original = image.read_bytes()
    verify_input(image.name, original)
    out.mkdir(parents=True, exist_ok=False)
    # Short socket paths avoid macOS's Unix-domain path limit.
    with tempfile.TemporaryDirectory(prefix="hp-phase2-") as temporary:
        control = Path(temporary)
        command = [str(qemu), "-machine", "hp-prime-g2", "-cpu", "cortex-a7", "-m", "256M",
                   # A RAM loader assumes preceding ROM/U-Boot DDR setup.
                   # This explicit model fixture does not execute HP's DCD.
                   "-global", "prime-g2-mmdc.preinitialized=on",
                   "-global", "imx6ul-lcdif.prime-g2-panel=on",
                   "-global", "prime-g2-pf1550.external-power=on",
                   "-global", "prime-g2-goodix-gt5688.drive-irq=off",
                   "-device", f"loader,file={image},addr=0x80000000,force-raw=on",
                   "-device", "loader,addr=0x80002000,cpu-num=0",
                   "-serial", f"file:{out / 'uart.log'}", "-serial", "null", "-serial", "null",
                   "-display", "none", "-monitor", "none", "-no-reboot", "-S",
                   "-d", "cpu_reset", "-D", str(out / "qemu.log"),
                   "-qmp", f"unix:{control / 'qmp'},server=on,wait=off",
                   "-qtest", f"unix:{control / 'qtest'},server=on,wait=off"]
        with (out / "stderr.log").open("wb") as log:
            process = subprocess.Popen(command, stdout=log, stderr=log)
            try:
                with connect(control / "qmp", process) as sock, sock.makefile("rb") as stream:
                    json.loads(stream.readline())
                    def qmp(name, arguments=None):
                        sock.sendall((json.dumps({"execute": name, "arguments": arguments or {}})+"\n").encode())
                        while True:
                            result = json.loads(stream.readline())
                            if "error" in result:
                                raise RuntimeError(result["error"])
                            if "return" in result:
                                return result["return"]
                    qmp("qmp_capabilities")
                    samples = [{"elapsed_wall_seconds": 0,
                                "status": qmp("query-status"),
                                "registers": qmp("human-monitor-command", {"command-line": "info registers"}),
                                "entry_memory": qmp("human-monitor-command", {"command-line": "xp /8wx 0x80002000"})}]
                    for index in range(2):
                        qmp("cont")
                        time.sleep(seconds / 2)
                        qmp("stop")
                        samples.append({"elapsed_wall_seconds": seconds * (index+1) / 2,
                                        "status": qmp("query-status"),
                                        "registers": qmp("human-monitor-command", {"command-line": "info registers"})})
                    counters = {}
                    with connect(control / "qtest", process) as qt, qt.makefile("rb") as qs:
                        for name, address in {"nand_commands": 0x0180615C,
                                              "overlay_pages": 0x01806160,
                                              "program_failures": 0x01806164,
                                              "ecc_writes": 0x01806170}.items():
                            qt.sendall(f"readl {address:#x}\n".encode())
                            counters[name] = qs.readline().decode().strip()
                    qmp("screendump", {"filename": str(out / "screen.ppm")})
                    qmp("quit")
                    process.wait(timeout=5)
                report = {"image": image.name, "sha256": hashlib.sha256(original).hexdigest(),
                          "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                          "qemu_sha256": hashlib.sha256(qemu.read_bytes()).hexdigest(),
                          "command": command, "samples": samples, "model_counters": counters,
                          "nand": "synthetic erased", "ddr": "model preinitialized; DCD not executed", "patches": [],
                          "qualification": "observation only; inspect screen and progress separately"}
                (out / "observation.json").write_text(json.dumps(report, indent=2)+"\n")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
    if image.read_bytes() != original:
        raise RuntimeError("input image changed during observation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--qemu", type=Path, default=ROOT / "build/qemu-prime-g2/qemu-system-arm")
    parser.add_argument("--seconds", type=int, choices=range(2, 61), default=20)
    args = parser.parse_args()
    out = private_output(args.output_dir)
    for name in ("HPPrime.img", "bootloader.img"):
        observe(args.qemu.resolve(), (args.fixture_dir / name).resolve(), out / name, args.seconds)
        print(name, "observation saved; no boot-success assertion")


if __name__ == "__main__":
    main()
