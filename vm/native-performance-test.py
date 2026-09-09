#!/usr/bin/env python3
"""Measure bounded native VM responsiveness and emit machine-readable budgets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path

CONTROL_PATH = Path(__file__).resolve().with_name("prime-control.py")
SPEC = importlib.util.spec_from_file_location("prime_control", CONTROL_PATH)
assert SPEC and SPEC.loader
CONTROL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROL)
REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--boot-seconds", type=float, required=True)
    args = parser.parse_args()
    request_id = 60_000

    def command(text: str) -> str:
        nonlocal request_id
        current = request_id
        request_id += 1
        response = CONTROL.send_command(args.socket, f"V1 {current} {text}")
        prefix = f"V1 {current} "
        if not response.startswith(prefix):
            raise AssertionError(response)
        return response[len(prefix) :]

    def press(name: str) -> None:
        key = CONTROL.KEYS[name]
        response = CONTROL.send_command(args.socket, f"PRESS {key}")
        if response != "OK":
            raise AssertionError(response)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if command(f"KEY STATE {key}") == "VALUE 0":
                time.sleep(0.04)
                return
            time.sleep(0.02)
        raise AssertionError(f"{name} did not release")

    def value(text: str) -> int:
        response = command(text)
        if not response.startswith("VALUE "):
            raise AssertionError(f"expected integer for {text}: {response}")
        return int(response.split()[1])

    publishes_before_navigation = value("DISPLAY PUBLISHES")
    started = time.monotonic()
    for _ in range(30):
        press("right")
        press("left")
    navigation_seconds = time.monotonic() - started
    publishes_after_navigation = value("DISPLAY PUBLISHES")

    press("ok")
    started = time.monotonic()
    if command(f"TEXT {'123456*789'.encode().hex()}") != "OK":
        raise AssertionError("text event rejected")
    # The acknowledgement means the ExternalText event is queued. Give the
    # UI one event-loop turn to consume it before queuing the validating key.
    time.sleep(0.12)
    press("ok")
    deadline = time.monotonic() + 2.0
    result = ""
    while time.monotonic() < deadline:
        result = command("RESULT EXACT")
        if result == "TEXT 97406784":
            break
        time.sleep(0.02)
    calculation_seconds = time.monotonic() - started
    if result != "TEXT 97406784":
        raise AssertionError(f"calculation did not settle: {result}")

    app_open_samples: list[float] = []
    heap_before_switching = value("HEAP CURRENT")
    for _ in range(20):
        press("apps")
        started = time.monotonic()
        press("ok")
        state = command("STATE")
        app_open_samples.append(time.monotonic() - started)
        if state.startswith("STATE app=0"):
            raise AssertionError("app did not open")
    heap_after_switching = value("HEAP CURRENT")

    # Measure a complete electrical key actuation through the resulting frame.
    # Return to the launcher first: Left in an arbitrary app can legitimately
    # be a no-op, which measures the timeout rather than rendering latency.
    press("apps")
    publishes = value("DISPLAY PUBLISHES")
    started = time.monotonic()
    response = CONTROL.send_command(args.socket, f"PRESS {CONTROL.KEYS['right']}")
    if response != "OK":
        raise AssertionError(response)
    deadline = time.monotonic() + 0.5
    while value("DISPLAY PUBLISHES") <= publishes and time.monotonic() < deadline:
        time.sleep(0.005)
    key_to_frame_seconds = time.monotonic() - started
    if value("DISPLAY PUBLISHES") <= publishes:
        raise AssertionError("launcher selection key did not publish a frame")

    # A bottom-edge touch is the advertised Home gesture and must redraw.
    press("ok")
    if command("STATE").startswith("STATE app=0"):
        raise AssertionError("selected launcher app did not open before touch test")
    publishes = value("DISPLAY PUBLISHES")
    started = time.monotonic()
    if command("TAP 160 239") != "OK":
        raise AssertionError("touch rejected")
    deadline = time.monotonic() + 0.5
    state = ""
    while time.monotonic() < deadline:
        state = command("STATE")
        if value("DISPLAY PUBLISHES") > publishes and state.startswith("STATE app=0"):
            break
        time.sleep(0.005)
    touch_to_frame_seconds = time.monotonic() - started
    if not state.startswith("STATE app=0"):
        raise AssertionError("Home touch did not return to launcher")

    if command("STORAGE PUT perf.bin 70657266") != "OK":
        raise AssertionError("performance record rejected")
    started = time.monotonic()
    if command("STORAGE COMMIT") != "OK":
        raise AssertionError("performance commit failed")
    storage_commit_seconds = time.monotonic() - started

    memory_sizes = {
        region.lower(): value(f"MEMORY SIZE {region}")
        for region in ("CODE", "DATA", "HEAP", "STACK", "FRAMEBUFFER")
    }

    metrics = {
        "boot_to_control_ready_seconds": round(args.boot_seconds, 4),
        "calculation_seconds": round(calculation_seconds, 4),
        "sixty_navigation_events_seconds": round(navigation_seconds, 4),
        "app_open_max_seconds": round(max(app_open_samples), 4),
        "app_open_mean_seconds": round(sum(app_open_samples) / len(app_open_samples), 4),
        "key_to_frame_seconds": round(key_to_frame_seconds, 4),
        "touch_to_frame_seconds": round(touch_to_frame_seconds, 4),
        "storage_commit_seconds": round(storage_commit_seconds, 4),
        "redraw_publishes_per_second": round(
            (publishes_after_navigation - publishes_before_navigation) / navigation_seconds, 2
        ),
        "heap_before_switching": heap_before_switching,
        "heap_after_switching": heap_after_switching,
        "heap_high_water": value("HEAP HIGHWATER"),
        "stack_high_water": value("STACK HIGHWATER"),
        "memory_sizes": memory_sizes,
        "irq_max_latency_microseconds": value("IRQ LATENCY"),
        "timer_missed_deadlines": value("TIMER MISSED"),
        "native_elf_bytes": (REPO / "dist/lefony-os-prime-g2-vm-native.elf").stat().st_size,
        "budgets": {
            "boot_to_control_ready_seconds": 20.0,
            "calculation_seconds": 2.0,
            "app_open_max_seconds": 1.0,
            "key_to_frame_seconds": 0.5,
            "touch_to_frame_seconds": 0.5,
            "storage_commit_seconds": 2.0,
        },
    }
    args.output.write_text(json.dumps(metrics, indent=2) + "\n")
    if (
        args.boot_seconds > 20
        or calculation_seconds > 2
        or max(app_open_samples) > 1
        or key_to_frame_seconds > 0.5
        or touch_to_frame_seconds > 0.5
        or storage_commit_seconds > 2
        or heap_after_switching > heap_before_switching + 1024 * 1024
    ):
        raise AssertionError(f"performance budget exceeded: {metrics}")
    print(json.dumps(metrics, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
