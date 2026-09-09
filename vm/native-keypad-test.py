#!/usr/bin/env python3
"""Exercise every source-of-truth Prime key mapping through native Upsilon."""

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
REPO = Path(__file__).resolve().parent.parent


def ion_key_indices() -> dict[str, int]:
    header = REPO / "build/lefony-prime-g2/ion/include/ion/keyboard/layout_B2/layout_keyboard.h"
    text = re.sub(r"/\*.*?\*/|//.*?$", "", header.read_text(), flags=re.S | re.M)
    body = re.search(r"enum class Key\s*:[^{]+\{(.*?)\};", text, re.S)
    if body is None:
        raise AssertionError("cannot parse Ion B2 key enumeration")
    result: dict[str, int] = {}
    value = -1
    for item in body.group(1).split(","):
        item = item.strip()
        if not item:
            continue
        match = re.fullmatch(
            r"([A-Za-z0-9_]+)(?:\s*=\s*([A-Za-z0-9_]+))?", item
        )
        if match is None:
            continue
        assignment = match.group(2)
        if assignment is None:
            value += 1
        elif assignment.isdigit():
            value = int(assignment)
        else:
            if assignment not in result:
                raise AssertionError(
                    f"Ion key alias {match.group(1)} references unknown {assignment}"
                )
            value = result[assignment]
        result[match.group(1)] = value
    return result


def event_definition_kinds() -> list[str]:
    source = REPO / "build/lefony-prime-g2/ion/src/shared/keyboard/layout_B2/layout_events.cpp"
    text = source.read_text()
    array = re.search(r"s_dataForEvent\[.*?\]\s*=\s*\{(.*?)\};", text, re.S)
    if array is None:
        raise AssertionError("cannot parse Ion B2 event definitions")
    kinds = re.findall(r"\b(TL|T|U)\((?:[^\"()]|\"(?:\\.|[^\"])*\")*\)", array.group(1))
    if len(kinds) != 216:
        raise AssertionError(f"expected 216 Ion events, found {len(kinds)}")
    return kinds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, required=True)
    args = parser.parse_args()
    request_id = 1000

    def request(command: str) -> str:
        nonlocal request_id
        current = request_id
        request_id += 1
        return CONTROL.send_command(args.socket, f"V1 {current} {command}")

    def expect(command: str, payload: str) -> None:
        nonlocal request_id
        current = request_id
        response = request(command)
        expected = f"V1 {current} {payload}"
        if response != expected:
            raise AssertionError(f"{command}: expected {expected!r}, got {response!r}")

    def value(command: str) -> int:
        nonlocal request_id
        current = request_id
        response = request(command)
        expected_prefix = f"V1 {current} VALUE "
        if not response.startswith(expected_prefix):
            raise AssertionError(f"{command}: malformed value response {response!r}")
        return int(response[len(expected_prefix) :])

    def text_value(command: str) -> str:
        nonlocal request_id
        current = request_id
        response = request(command)
        expected_prefix = f"V1 {current} TEXT "
        if not response.startswith(expected_prefix):
            raise AssertionError(f"{command}: malformed text response {response!r}")
        return response[len(expected_prefix) :]

    def wait_value(command: str, expected: int, timeout: float = 1.5) -> int:
        deadline = time.monotonic() + timeout
        actual = value(command)
        while actual != expected and time.monotonic() < deadline:
            time.sleep(0.02)
            actual = value(command)
        return actual

    def press(name: str) -> None:
        code = CONTROL.KEYS[name]
        response = CONTROL.send_command(args.socket, f"PRESS {code}")
        if response != "OK":
            raise AssertionError(f"{name} rejected: {response}")
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if value(f"KEY STATE {code}") == 0:
                # The UART acknowledgement proves the modeled matrix edge,
                # not that Upsilon's event loop has consumed it. Give the
                # semantic event one full scan/redraw turn before modifiers
                # are combined with the next key.
                time.sleep(0.12)
                return
            time.sleep(0.02)
        raise AssertionError(f"{name} did not release")

    # On/Off has lifecycle semantics and is verified separately; all other
    # matrix and navigation keys must expose exact press/release state.
    for name, code in CONTROL.KEYS.items():
        if name == "onoff":
            continue
        expect(f"KEY STATE {code}", "VALUE 0")
        expect(f"KEY {code} 1", "OK")
        expect(f"KEY STATE {code}", "VALUE 1")
        expect(f"KEY {code} 0", "OK")
        expect(f"KEY STATE {code}", "VALUE 0")

    shift = CONTROL.KEYS["shift"]
    one = CONTROL.KEYS["one"]
    expect(f"KEY {shift} 1", "OK")
    expect(f"KEY {one} 1", "OK")
    expect(f"KEY STATE {shift}", "VALUE 1")
    expect(f"KEY STATE {one}", "VALUE 1")
    expect(f"KEY {one} 0", "OK")
    expect(f"KEY {shift} 0", "OK")

    # Verify modifier state transitions and lock/cancellation semantics.
    expect("INPUT RESET", "OK")
    press("shift")
    assert value("MOD STATE") == 1
    press("shift")
    assert value("MOD STATE") == 0
    press("alpha")
    assert value("MOD STATE") == 2
    press("alpha")
    assert value("MOD STATE") == 4
    press("shift")
    assert value("MOD STATE") == 5
    press("shift")
    assert value("MOD STATE") == 4
    press("alpha")
    assert value("MOD STATE") == 0

    # Compare the actual event selected by Shift, Alpha, and Shift+Alpha with
    # the authoritative Upsilon B2 event table, including its fallback rules.
    indices = ion_key_indices()
    definitions = event_definition_kinds()
    page_size = 54
    for name, ion_name in CONTROL.ION_KEYS.items():
        if name in {"shift", "alpha", "onoff"}:
            continue
        plain = indices[ion_name]
        for modifiers, page in (("shift", 1), ("alpha", 2), ("shift_alpha", 3)):
            # Normalize the UI before every combination. Some semantic Prime
            # keys intentionally change apps; testing the next combination in
            # that app would test responder state rather than keyboard wiring.
            press("apps")
            expect("INPUT RESET", "OK")
            if modifiers in {"shift", "shift_alpha"}:
                press("shift")
                if wait_value("MOD STATE", 1) != 1:
                    raise AssertionError("Shift modifier was not consumed")
            if modifiers in {"alpha", "shift_alpha"}:
                press("alpha")
                expected_modifier = 3 if modifiers == "shift_alpha" else 2
                if wait_value("MOD STATE", expected_modifier) != expected_modifier:
                    raise AssertionError("Alpha modifier was not consumed")
            press(name)
            expected = page * page_size + plain
            if definitions[expected] == "U":
                expected = 2 * page_size + plain if page == 3 and definitions[2 * page_size + plain] != "U" else plain
            actual = wait_value("EVENT LAST", expected)
            if actual != expected:
                raise AssertionError(
                    f"{modifiers}+{name}: expected event {expected}, got {actual}"
                )

    # The HP Prime's orange Alpha legends do not occupy the same physical
    # positions as the NumWorks B2 legends. Verify the complete Prime alphabet
    # and every additional printed Alpha character independently of the event
    # table above, so a future upstream refresh cannot silently restore the
    # NumWorks mapping (for example Alpha+7 -> m instead of q).
    prime_alpha = {
        "var": "a", "toolbox": "b", "units": "c", "xnt": "d",
        "fraction": "e", "power": "f", "sin": "g", "cos": "h",
        "tan": "i", "ln": "j", "log": "k", "square": "l",
        "plusminus": "m", "parenthesis": "n", "comma": "o", "ee": "p",
        "seven": "q", "eight": "r", "nine": "s", "divide": "t",
        "four": "u", "five": "v", "six": "w", "multiply": "x",
        "one": "y", "two": "z", "three": "#", "minus": ":",
        "zero": '"', "plus": ";", "space": " ",
    }
    for name, expected_text in prime_alpha.items():
        press("apps")
        expect("INPUT RESET", "OK")
        press("alpha")
        press(name)
        actual = value("EVENT LAST BYTE")
        if actual != ord(expected_text):
            raise AssertionError(
                f"alpha+{name}: expected {expected_text!r}, got byte {actual}"
            )

    for name, expected_text in prime_alpha.items():
        if not expected_text.isalpha():
            continue
        press("apps")
        expect("INPUT RESET", "OK")
        press("shift")
        press("alpha")
        press(name)
        actual = value("EVENT LAST BYTE")
        if actual != ord(expected_text.upper()):
            raise AssertionError(
                f"shift+alpha+{name}: expected {expected_text.upper()!r}, "
                f"got byte {actual}"
            )

    # Verify every text-producing blue Shift legend from the Prime case. This
    # is deliberately independent of the generated event table's fallback
    # test above: an undefined Shift+5 used to fall back to plain 5 and launch
    # Statistics from Home instead of inserting a bracket template.
    prime_shift_text = {
        "units": "_",
        "fraction": "(\x11)/(\x11)",
        "xnt": "→",
        "ln": "ℯ^(\x11)",
        "log": "10^(\x11)",
        "power": "root(\x11,\x11)",
        "sin": "asin(\x11)",
        "cos": "acos(\x11)",
        "tan": "atan(\x11)",
        "square": "√(\x11)",
        "plusminus": "abs(\x11)",
        "parenthesis": "!",
        "eight": "{\x11}",
        "nine": "[\x11,\x11]",
        "five": "[\x11]",
        "six": "sum(\x11,\x11,\x11,\x11)",
        "multiply": "arg(\x11)",
        "divide": "^(-1)",
        "two": "𝐢",
        "three": "π",
        "space": "-",
        "plus": "ans",
        "dot": "=",
        "ee": "→",
    }
    for name, expected_text in prime_shift_text.items():
        press("apps")
        expect("INPUT RESET", "OK")
        press("shift")
        press(name)
        actual = text_value("EVENT LAST TEXT")
        if actual != expected_text:
            raise AssertionError(
                f"shift+{name}: expected {expected_text!r}, got {actual!r}"
            )

    # All remaining printed Shift functions are semantic events. Ensure they
    # stay on the Shift page instead of falling back to their plain launcher
    # shortcuts. Shift+On is intentionally the one fallback: it is the OFF key.
    prime_shift_semantic = {
        "back", "backspace", "home", "cas", "apps", "symb", "plot",
        "num", "help", "view", "menu", "var", "toolbox", "comma",
        "seven", "four", "one", "zero",
    }
    for name in prime_shift_semantic:
        press("apps")
        expect("INPUT RESET", "OK")
        press("shift")
        press(name)
        expected = page_size + indices[CONTROL.ION_KEYS[name]]
        actual = wait_value("EVENT LAST", expected)
        if actual != expected:
            raise AssertionError(
                f"shift+{name}: fell back from event {expected} to {actual}"
            )

    right = CONTROL.KEYS["right"]
    # Give the query a deliberately large real-time window, then expire it by
    # advancing guest time. This verifies scheduled release without racing the
    # host or QEMU scheduler.
    expect(f"PRESS {right} 5000", "OK")
    expect(f"KEY STATE {right}", "VALUE 1")
    expect("TIME ADVANCE 5001", "OK")
    expect(f"KEY STATE {right}", "VALUE 0")

    # Prime navigation is deliberately single-step: holding a D-pad direction
    # must not manufacture additional moves before release.
    expect("INPUT RESET", "OK")
    expect(f"KEY {right} 1", "OK")
    time.sleep(0.45)
    if value("EVENT REPEAT") != 0:
        raise AssertionError("held Right key repeated instead of staying single-step")
    expect(f"KEY {right} 0", "OK")
    expect("INPUT RESET", "OK")
    expect(f"KEY STATE {right}", "VALUE 0")

    # Editing keys retain normal repeat behavior; the policy is specific to
    # the D-pad rather than a global repeat disable.
    backspace = CONTROL.KEYS["backspace"]
    expect(f"KEY {backspace} 1", "OK")
    time.sleep(0.45)
    if value("EVENT REPEAT") < 1:
        raise AssertionError("held Backspace did not enter key-repeat")
    expect(f"KEY {backspace} 0", "OK")
    expect("INPUT RESET", "OK")

    # A reset while the physical state still says "down" must clear both the
    # key bit and the repeat scheduler.  This catches the stuck-key failure
    # that is otherwise hidden by a normal release before reset.
    expect(f"KEY {right} 1", "OK")
    expect("INPUT RESET", "OK")
    expect(f"KEY STATE {right}", "VALUE 0")
    expect("EVENT REPEAT", "VALUE 0")

    for _ in range(25):
        for name in ("left", "right"):
            press(name)

    response = request("KEY 65535 1")
    if not response.endswith("ERR unknown key"):
        raise AssertionError(f"unknown key was not rejected: {response!r}")

    # On/Off is dispatched through its dedicated GPIO/lifecycle path, enters
    # suspend exactly once, releases cleanly, and reconstructs on wake.
    expect("INPUT RESET", "OK")
    suspend_count = value("POWER COUNT")
    onoff_code = CONTROL.KEYS["onoff"]
    expect(f"KEY {onoff_code} 1", "OK")
    # This GPIO is sampled by the shared event loop rather than the KPP scan.
    # Leave it asserted while QEMU drains the preceding rapid-matrix workload
    # before querying the resulting semantic event.
    time.sleep(0.5)
    expected_onoff = indices[CONTROL.ION_KEYS["onoff"]]
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and value("EVENT LAST") != expected_onoff:
        time.sleep(0.02)
    if value("EVENT LAST") != expected_onoff:
        raise AssertionError("On/Off did not produce its dedicated event")
    if value("POWER STATE") != 1 or value("POWER COUNT") != suspend_count + 1:
        raise AssertionError("On/Off did not enter suspend exactly once")
    expect(f"KEY {onoff_code} 0", "OK")
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and value(
        f"KEY STATE {onoff_code}"
    ) != 0:
        time.sleep(0.02)
    expect(f"KEY STATE {onoff_code}", "VALUE 0")
    expect("POWER RESUME", "OK")
    expect("POWER STATE", "VALUE 0")

    expect("KEYMAP DRAW", "OK")

    print(
        f"PASS: {len(CONTROL.KEYS)} Prime mappings, exact Alpha and Shift "
        "legends, all defined modifiers, locks, repeat, On/Off, chords, "
        "timed release, and diagnostic"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
