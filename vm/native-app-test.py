#!/usr/bin/env python3
"""Launch every enabled native app and run deterministic core workflows."""

from __future__ import annotations

import argparse
import importlib.util
import re
import time
from pathlib import Path


CONTROL_PATH = Path(__file__).resolve().with_name("prime-control.py")
CONTROL_SPEC = importlib.util.spec_from_file_location("prime_control", CONTROL_PATH)
assert CONTROL_SPEC is not None and CONTROL_SPEC.loader is not None
CONTROL = importlib.util.module_from_spec(CONTROL_SPEC)
CONTROL_SPEC.loader.exec_module(CONTROL)
STATE_PATTERN = re.compile(r"STATE app=(-?\d+) home_row=(-?\d+) home_column=(-?\d+)$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, required=True)
    args = parser.parse_args()
    request_id = 20_000

    def command(text: str) -> str:
        nonlocal request_id
        current = request_id
        request_id += 1
        response = CONTROL.send_command(args.socket, f"V1 {current} {text}")
        prefix = f"V1 {current} "
        if not response.startswith(prefix):
            raise AssertionError(f"request envelope mismatch: {response!r}")
        return response[len(prefix) :]

    def press(name: str) -> None:
        key = CONTROL.KEYS[name]
        response = CONTROL.send_command(args.socket, f"PRESS {key}")
        if response != "OK":
            raise AssertionError(f"{name} rejected: {response}")
        # PRESS schedules release inside the guest. Wait until the modeled
        # matrix has actually returned low before issuing another edge; with
        # the Prime's single-step D-pad policy, overlapping presses correctly
        # collapse rather than pretending a release occurred.
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if command(f"KEY STATE {key}") == "VALUE 0":
                time.sleep(0.04)
                return
            time.sleep(0.02)
        raise AssertionError(f"{name} did not release")

    def enter_text(value: str) -> None:
        response = command(f"TEXT {value.encode().hex()}")
        if response != "OK":
            raise AssertionError(f"text injection rejected {value!r}: {response}")
        time.sleep(0.12)

    def state() -> tuple[int, int, int]:
        response = command("STATE")
        match = STATE_PATTERN.fullmatch(response)
        if not match:
            raise AssertionError(f"malformed state: {response!r}")
        return tuple(map(int, match.groups()))

    def select_home(row: int, column: int) -> None:
        press("apps")
        for _ in range(4):
            press("up")
            press("left")
        for _ in range(row):
            press("down")
        for _ in range(column):
            press("right")
        actual = state()
        if actual != (0, row, column):
            raise AssertionError(f"home selection expected {(0, row, column)}, got {actual}")

    enabled_apps = [
        ("Calculation", 1),
        ("Functions", 2),
        ("RPN", 3),
        ("Python", 4),
        ("Statistics", 5),
        ("Probability", 6),
        ("Solver", 7),
        ("Elements", 8),
        ("Sequences", 9),
        ("Regression", 10),
        # Recovery is confirmed inside Settings, never a launcher app.
        ("Settings", 11),
    ]
    workflows = {
        "Calculation": ("one", "plus", "two", "ok", "up", "down"),
        "Functions": ("down", "up", "ok", "back"),
        "RPN": ("one", "ok", "two", "plus"),
        "Python": ("down", "up", "ok", "back"),
        "Statistics": ("one", "ok", "two", "ok", "right", "left"),
        "Probability": ("down", "up", "ok", "back"),
        "Solver": ("one", "plus", "two", "ok", "back"),
        "Elements": ("right", "down", "ok", "back"),
        "Sequences": ("down", "up", "ok", "back"),
        "Regression": ("one", "ok", "two", "ok", "right", "left"),
        "Settings": ("down", "ok", "right", "back"),
    }

    # Prime's dedicated navigation row is global: HOME and CAS enter the
    # calculator, APPS opens the launcher, and Toolbox/Mem opens the math
    # toolbox without leaving Calculation.
    press("home")
    if state()[0] != 1:
        raise AssertionError("Prime Home did not enter Calculation")
    toolbox_crc = int(command("DISPLAY CRC").split()[1])
    press("toolbox")
    if state()[0] != 1:
        raise AssertionError("Toolbox left the Calculation app")
    if int(command("DISPLAY CRC").split()[1]) == toolbox_crc:
        raise AssertionError("Toolbox/Mem did not open the math toolbox")
    press("back")
    press("apps")
    if state()[0] != 0:
        raise AssertionError("Prime Apps did not open the app launcher")
    press("cas")
    if state()[0] != 1:
        raise AssertionError("Prime CAS did not enter Calculation")
    press("apps")
    if state()[0] != 0:
        raise AssertionError("Prime Apps did not return to the app launcher")

    for app_name, app_index in enabled_apps:
        icon = app_index - 1
        select_home(icon // 3, icon % 3)
        press("ok")
        active, _, _ = state()
        if active != app_index:
            raise AssertionError(f"{app_name} launched app {active}, expected {app_index}")
        crc_before = int(command("DISPLAY CRC").split()[1])
        publishes_before = int(command("DISPLAY PUBLISHES").split()[1])
        # Exercise a representative edit/navigation/confirmation path for the
        # app, not merely snapshot unpacking and one arbitrary responder.
        saw_visual_change = False
        for key in workflows[app_name]:
            press(key)
            saw_visual_change |= int(command("DISPLAY CRC").split()[1]) != crc_before
        active_after_event, _, _ = state()
        if active_after_event != app_index:
            raise AssertionError(f"{app_name} left active state during workflow")
        crc_after = int(command("DISPLAY CRC").split()[1])
        publishes_after = int(command("DISPLAY PUBLISHES").split()[1])
        if not saw_visual_change or publishes_after <= publishes_before:
            raise AssertionError(f"{app_name} workflow did not redraw the native UI")

        # Suspend and reconstruct the complete peripheral stack from every
        # enabled application, retaining both app state and framebuffer data.
        if command("POWER SUSPEND") != "OK" or command("POWER STATE") != "VALUE 1":
            raise AssertionError(f"{app_name} did not suspend")
        if command("POWER RESUME") != "OK" or command("POWER STATE") != "VALUE 0":
            raise AssertionError(f"{app_name} did not resume")
        if state()[0] != app_index or command("DISPLAY GUARDS") != "OK":
            raise AssertionError(f"{app_name} did not survive resume")
        press("apps")
        if state()[0] != 0:
            raise AssertionError(f"{app_name} could not return to Apps")

    select_home(0, 0)
    press("ok")
    calculations = [
        (("one", "plus", "two", "ok"), "3"),
        (("eight", "minus", "three", "ok"), "5"),
        (("six", "multiply", "seven", "ok"), "42"),
        (("eight", "divide", "two", "ok"), "4"),
        (("two", "power", "three", "ok"), "8"),
        (("nine", "square", "ok"), "81"),
        (("sin", "zero", "ok"), "0"),
    ]
    for keys, expected in calculations:
        for key in keys:
            press(key)
        exact = command("RESULT EXACT")
        if exact != f"TEXT {expected}":
            expression = command("RESULT INPUT")
            raise AssertionError(
                f"{' '.join(keys)} expected {expected}, got {exact!r}; "
                f"input was {expression!r}"
            )

    text_calculations = [
        ("(1+2)*3", "9"),
        ("√(9)", "3"),
        ("1/3", "1/3"),
        ("-2+5", "3"),
        ("1ᴇ3", "1000"),
        ("𝐢^2", "-1"),
    ]
    for expression, expected in text_calculations:
        enter_text(expression)
        press("ok")
        exact = command("RESULT EXACT")
        if exact != f"TEXT {expected}":
            raise AssertionError(
                f"injected {expression!r} expected {expected}, got {exact!r}; "
                f"input was {command('RESULT INPUT')!r}"
            )

    edge_calculations = [
        ("1/0", "undef"),
        ("√(-1)", "unreal"),
        ("3→a", "3"),
        ("a+4", "7"),
        ("5", "5"),
        ("ans*2", "10"),
    ]
    for expression, expected in edge_calculations:
        enter_text(expression)
        press("ok")
        exact = command("RESULT EXACT")
        if exact != f"TEXT {expected}":
            raise AssertionError(f"edge case {expression!r}: {exact!r}")

    angle_calculations = [
        (0, "sin(30)", "1/2"),
        (1, "sin(π/2)", "1"),
        (2, "sin(100)", "1"),
    ]
    for angle, expression, expected in angle_calculations:
        if command(f"PREF SET ANGLE {angle}") != "OK":
            raise AssertionError(f"could not select angle mode {angle}")
        enter_text(expression)
        press("ok")
        exact = command("RESULT EXACT")
        if exact != f"TEXT {expected}":
            raise AssertionError(
                f"angle {angle} expression {expression!r}: {exact!r}"
            )
    command("PREF SET ANGLE 0")

    press("apps")
    if state()[0] != 0:
        raise AssertionError("calculation workflow did not return to Apps")
    print(
        f"PASS: completed redraw and suspend/resume workflows in {len(enabled_apps)} apps and verified "
        f"{len(calculations) + len(text_calculations) + len(edge_calculations) + len(angle_calculations)} "
        "exact calculation workflows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
