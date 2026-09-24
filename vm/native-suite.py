#!/usr/bin/env python3
"""Run bounded, artifact-producing HP Prime G2 native emulator suites."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


@dataclass
class Result:
    name: str
    command: list[str]
    elapsed_seconds: float
    return_code: int
    log: str


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(name: str, command: list[str], timeout: int, log_dir: Path, env: dict[str, str]) -> Result:
    log_path = log_dir / f"{name}.log"
    started = time.monotonic()
    with log_path.open("wb") as log:
        log.write(("$ " + shlex.join(command) + "\n").encode())
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=REPO,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            return_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            return_code = 124
            log.write(f"\nTIMEOUT after {timeout} seconds\n".encode())
    elapsed = time.monotonic() - started
    result = Result(name, command, round(elapsed, 3), return_code, str(log_path))
    print(f"{'PASS' if return_code == 0 else 'FAIL'} {name} ({elapsed:.1f}s)")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        choices=("all", "build", "smoke", "application", "storage", "fault", "long-run"),
        default="all",
    )
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    root = args.artifacts or REPO / "build" / f"prime-g2-native-suite-{stamp}"
    root.mkdir(parents=True, exist_ok=True)
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    env = os.environ.copy()
    artifact_env = {
        "NATIVE_VM_TEST_DIR": root / "smoke",
        "NATIVE_DIRECT_TEST_DIR": root / "direct-elf",
        "NATIVE_PROTOCOL_TEST_DIR": root / "protocol",
        "NATIVE_KEYPAD_TEST_DIR": root / "keypad",
        "NATIVE_DISPLAY_TEST_DIR": root / "display",
        "NATIVE_DISPLAY_FIDELITY_DIR": root / "display-fidelity",
        "NATIVE_SERVICES_TEST_DIR": root / "services",
        "NATIVE_USB_TEST_DIR": root / "usb",
        "NATIVE_TOUCH_TEST_DIR": root / "touch",
        "NATIVE_APPS_TEST_DIR": root / "apps",
        "NATIVE_PERSISTENCE_TEST_DIR": root / "persistence",
        "NATIVE_PREFERENCES_TEST_DIR": root / "preferences",
        "NATIVE_READONLY_TEST_DIR": root / "readonly",
        "NATIVE_STORAGE_BOUNDARY_TEST_DIR": root / "storage-boundaries",
        "NATIVE_STORAGE_FUZZ_TEST_DIR": root / "storage-fuzz",
        "NATIVE_PROTOCOL_FUZZ_TEST_DIR": root / "protocol-fuzz",
        "NATIVE_RUNTIME_TEST_DIR": root / "runtime-hardware",
        "NATIVE_POWER_LOSS_TEST_DIR": root / "power-loss",
        "NATIVE_EXCEPTION_TEST_DIR": root / "exceptions",
        "NATIVE_COLD_RESET_TEST_DIR": root / "cold-reset",
        "NATIVE_PERFORMANCE_TEST_DIR": root / "performance",
        "NATIVE_COLD_BOOT_DIR": root / "cold-boots",
        "NATIVE_BOOT_RECOVERY_DIR": root / "boot-recovery",
        "NATIVE_SOAK_TEST_DIR": root / "soak",
    }
    env.update({key: str(value) for key, value in artifact_env.items()})

    groups: dict[str, list[tuple[str, list[str], int]]] = {
        "build": [
            ("host-unit", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], 120),
            ("qemu-peripherals", [sys.executable, "./vm/test-prime-g2-peripherals.py"], 30),
            ("physical-build", ["./scripts/build_lefony_prime_g2.sh"], 1200),
            ("native-vm-build", ["./scripts/build_lefony_prime_g2_vm.sh"], 1200),
            ("upstream-unit", ["./vm/test-upstream-unit.sh"], 1800),
            ("u-boot-build", ["./vm/build-u-boot.sh"], 1200),
            ("boot-media-build", ["./vm/build-native-boot-media.sh"], 300),
            ("sbom", ["./vm/generate-native-sbom.py"], 30),
        ],
        "smoke": [
            ("usb-protocol-stall", [sys.executable, "./vm/test-prime-g2-usb-stall.py",
                                    "--output", str(root / "usb-protocol-stall")], 45),
            ("direct-elf", ["./vm/test-native-direct.sh"], 240),
            ("smoke", ["./vm/test-native-vm.sh"], 240),
            ("protocol", ["./vm/test-native-protocol.sh"], 300),
        ],
        "application": [
            ("runtime-hardware", ["./vm/test-native-runtime-hardware.sh"], 600),
            ("keypad", ["./vm/test-native-keypad.sh"], 600),
            ("display", ["./vm/test-native-display.sh"], 600),
            ("display-fidelity", ["./vm/test-native-display-fidelity.sh"], 1200),
            ("services", ["./vm/test-native-services.sh"], 600),
            ("usb", ["./vm/test-native-usb.sh"], 600),
            ("touch", ["./vm/test-native-touch.sh"], 600),
            ("applications", ["./vm/test-native-apps.sh"], 900),
        ],
        "storage": [
            ("protocol-fuzz", ["./vm/test-native-protocol-fuzz.sh"], 600),
            ("storage-boundaries", ["./vm/test-native-storage-boundaries.sh"], 300),
            ("storage-fuzz", ["./vm/test-native-storage-fuzz.sh"], 600),
            ("persistence", ["./vm/test-native-persistence.sh"], 600),
            ("preferences", ["./vm/test-native-preferences.sh"], 600),
            ("readonly", ["./vm/test-native-readonly.sh"], 300),
        ],
        "fault": [
            ("exceptions", ["./vm/test-native-exceptions.sh"], 900),
            ("cold-reset", ["./vm/test-native-cold-reset.sh"], 600),
            ("power-loss", ["./vm/test-native-power-loss.sh"], 1200),
            ("boot-recovery", ["./vm/test-native-boot-recovery.sh"], 1200),
        ],
        "long-run": [
            ("performance", ["./vm/test-native-performance.sh"], 600),
            ("cold-boots", ["./vm/test-native-cold-boots.sh"], 1800),
            ("accelerated-24h-soak", ["./vm/test-native-soak.sh"], 900),
        ],
    }

    selected = list(groups) if args.suite == "all" else [args.suite]
    results: list[Result] = []
    failed = False
    for group in selected:
        for name, command, timeout in groups[group]:
            result = run(name, command, timeout, logs, env)
            results.append(result)
            if result.return_code != 0:
                failed = True
                break
        if failed:
            break

    metadata = {
        "suite": args.suite,
        "timestamp": stamp,
        "host": platform.platform(),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
        ).stdout.strip(),
        "upstream": (REPO / "ports" / "lefony-prime-g2" / "UPSTREAM").read_text().strip(),
        "artifacts": {
            # Honor the same explicit candidate paths passed to each runner.
            "native_elf_sha256": sha256(REPO / env.get("NATIVE_ELF", "dist/lefony-os-prime-g2-vm-native.elf")),
            "boot_media_sha256": sha256(REPO / env.get("NATIVE_BOOT_MEDIA", "build/prime-g2-native-vm/lefony-os-boot.img")),
            "u_boot_sha256": sha256(REPO / env.get("UBOOT_ELF", "build/prime-g2-native-vm/u-boot/u-boot.elf")),
        },
        "results": [asdict(result) for result in results],
        "passed": not failed,
    }
    (root / "summary.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Artifacts: {root}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
