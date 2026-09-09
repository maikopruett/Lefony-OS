#!/usr/bin/env python3
"""Run 24 hours of deterministic virtual-time activity against native Upsilon."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()
    request_id = 90_000

    def command(text: str) -> str:
        nonlocal request_id
        current = request_id
        request_id += 1
        response = CONTROL.send_command(args.socket, f"V1 {current} {text}")
        prefix = f"V1 {current} "
        if not response.startswith(prefix):
            raise AssertionError(response)
        return response[len(prefix):]

    def value(text: str) -> int:
        response = command(text)
        if not response.startswith("VALUE "):
            raise AssertionError(f"{text}: {response}")
        return int(response.split()[1])

    def press(key: str) -> None:
        if CONTROL.send_command(args.socket, f"PRESS {CONTROL.KEYS[key]}") != "OK":
            raise AssertionError(f"key {key} rejected")
        time.sleep(0.12)

    iterations = args.hours * 12  # five virtual minutes per iteration
    # A connected development calculator is externally powered during a long
    # emulator run; depletion-to-empty is covered separately by power tests.
    if command("BATTERY SET 2 3900 1") != "OK":
        raise AssertionError("could not enable modeled external power")
    heap_start = value("HEAP CURRENT")
    feeds_start = value("WATCHDOG FEEDS")
    publishes_start = value("DISPLAY PUBLISHES")
    started = time.monotonic()
    for iteration in range(iterations):
        if command("TIME ADVANCE 300000") != "OK":
            raise AssertionError("virtual time advance failed")
        press(("right", "down", "left", "up")[iteration % 4])
        if iteration % 6 == 0:
            press("ok")
            press("right")
            press("apps")
        if iteration % 12 == 0:
            if command("POWER SUSPEND") != "OK" or command("POWER RESUME") != "OK":
                raise AssertionError("soak suspend/resume failed")
        if iteration % 24 == 0:
            payload = f"{iteration:08x}"
            if command(f"STORAGE PUT soak.bin {payload}") != "OK":
                raise AssertionError("soak record update failed")
            if command("STORAGE COMMIT") != "OK":
                raise AssertionError("soak commit failed")
        if iteration % 48 == 0:
            if command("DISPLAY GUARDS") != "OK" or command("SYSTEM SELFTEST") != "OK":
                raise AssertionError("runtime integrity failed during soak")

    metrics = {
        "virtual_hours": args.hours,
        "iterations": iterations,
        "wall_seconds": round(time.monotonic() - started, 3),
        "heap_start": heap_start,
        "heap_end": value("HEAP CURRENT"),
        "heap_high_water": value("HEAP HIGHWATER"),
        "stack_high_water": value("STACK HIGHWATER"),
        "stack_capacity": value("STACK CAPACITY"),
        "watchdog_feeds": value("WATCHDOG FEEDS") - feeds_start,
        "display_publishes": value("DISPLAY PUBLISHES") - publishes_start,
        "timer_missed_deadlines": value("TIMER MISSED"),
        "battery_percent": value("BATTERY PERCENT"),
    }
    if metrics["heap_end"] > metrics["heap_start"] + 1024 * 1024:
        raise AssertionError(f"heap growth during soak: {metrics}")
    if metrics["stack_high_water"] >= metrics["stack_capacity"]:
        raise AssertionError(f"stack exhausted during soak: {metrics}")
    if metrics["watchdog_feeds"] <= 0 or metrics["display_publishes"] <= 0:
        raise AssertionError(f"subsystems did not progress: {metrics}")
    if command("DISPLAY GUARDS") != "OK" or command("SYSTEM SELFTEST") != "OK":
        raise AssertionError("final runtime integrity failed")
    args.output.write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
