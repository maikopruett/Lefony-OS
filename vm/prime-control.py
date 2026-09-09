#!/usr/bin/env python3
"""Send exact HP Prime G2 keypad and touch events to the Lefony VM."""

from __future__ import annotations

import argparse
import re
import socket
import sys
import time
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SOCKET = REPO_DIR / "build" / "prime-g2-native-vm" / "input.sock"

KEYMAP_PATH = REPO_DIR / "ports" / "lefony-prime-g2" / "ion" / "src" / "prime_g2" / "keymap.inc"
KEY_PATTERN = re.compile(
    r"^PRIME_G2_KEY\(\s*([a-z0-9_]+)\s*,\s*([0-9]+)\s*,\s*([A-Za-z0-9_]+)\s*,"
)


def load_keys() -> tuple[dict[str, int], dict[str, str]]:
    keys: dict[str, int] = {}
    ion_keys: dict[str, str] = {}
    for line in KEYMAP_PATH.read_text().splitlines():
        match = KEY_PATTERN.match(line)
        if match:
            keys[match.group(1)] = int(match.group(2))
            ion_keys[match.group(1)] = match.group(3)
    if not keys:
        raise RuntimeError(f"no Prime keys found in {KEYMAP_PATH}")
    return keys, ion_keys


KEYS, ION_KEYS = load_keys()


def send_command(socket_path: Path, command: str, timeout: float = 15.0) -> str:
    # Descriptive artifact paths can exceed macOS' AF_UNIX sockaddr limit.
    # run-native-vm exposes a symlink to its short private runtime socket.
    if socket_path.is_symlink():
        socket_path = socket_path.resolve(strict=False)
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(timeout)
                client.connect(str(socket_path))
                client.sendall((command + "\n").encode())
                chunks: list[bytes] = []
                response_size = 0
                while response_size < 4096:
                    chunk = client.recv(min(512, 4096 - response_size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    response_size += len(chunk)
                    if b"\n" in chunk:
                        break
                response = b"".join(chunks).split(b"\n", 1)[0].decode(
                    errors="replace"
                ).strip()
                if not response:
                    raise RuntimeError("VM input bridge returned no response")
                if response_size == 4096 and b"\n" not in b"".join(chunks):
                    raise RuntimeError("VM input bridge response exceeded 4096 bytes")
                return response
        except OSError as error:
            last_error = error
            time.sleep(0.1)
    raise RuntimeError(f"cannot reach Prime VM at {socket_path}: {last_error}")


def key_code(name: str) -> int:
    try:
        return KEYS[name.lower()]
    except KeyError as error:
        choices = ", ".join(sorted(KEYS))
        raise SystemExit(f"unknown key {name!r}; choices: {choices}") from error


def is_success_response(response: str) -> bool:
    payload = response
    if response.startswith("V1 "):
        fields = response.split(" ", 2)
        payload = fields[2] if len(fields) == 3 else ""
    return payload in {"OK", "PONG", "VALID", "INVALID"} or payload.startswith(
        ("DATA ", "VALUE ", "INFO ", "STATE ", "TEXT ")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, default=DEFAULT_SOCKET)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("ping")
    commands.add_parser("keys")
    raw = commands.add_parser("raw")
    raw.add_argument("command", nargs="+")
    v1 = commands.add_parser("v1")
    v1.add_argument("request_id", type=int)
    v1.add_argument("command", nargs="+")
    for action in ("press", "down", "up"):
        subparser = commands.add_parser(action)
        subparser.add_argument("key")
    tap = commands.add_parser("tap")
    tap.add_argument("x", type=int)
    tap.add_argument("y", type=int)
    swipe = commands.add_parser("swipe")
    swipe.add_argument("x1", type=int)
    swipe.add_argument("y1", type=int)
    swipe.add_argument("x2", type=int)
    swipe.add_argument("y2", type=int)
    sequence = commands.add_parser("sequence")
    sequence.add_argument("key", nargs="+")
    args = parser.parse_args()

    if args.action == "keys":
        print("\n".join(sorted(KEYS)))
        return 0
    if args.action == "ping":
        command = "PING"
    elif args.action == "raw":
        command = " ".join(args.command)
    elif args.action == "v1":
        if args.request_id < 0 or args.request_id > 0xFFFFFFFF:
            parser.error("request_id must be between 0 and 4294967295")
        command = f"V1 {args.request_id} {' '.join(args.command)}"
    elif args.action == "press":
        command = f"PRESS {key_code(args.key)}"
    elif args.action == "down":
        command = f"KEY {key_code(args.key)} 1"
    elif args.action == "up":
        command = f"KEY {key_code(args.key)} 0"
    elif args.action == "tap":
        command = f"TAP {args.x} {args.y}"
    elif args.action == "swipe":
        command = f"SWIPE {args.x1} {args.y1} {args.x2} {args.y2}"
    elif args.action == "sequence":
        for name in args.key:
            response = send_command(args.socket, f"PRESS {key_code(name)}")
            if response != "OK":
                raise RuntimeError(f"VM rejected {name}: {response}")
            # PRESS holds a key for 100 guest milliseconds. Preserve a release
            # interval between sequence entries on the hardware-accurate timer.
            time.sleep(0.12)
        print("OK")
        return 0
    else:
        raise AssertionError(args.action)

    response = send_command(args.socket, command)
    if args.action == "press" and response == "OK":
        time.sleep(0.12)
    print(response)
    return 0 if is_success_response(response) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, KeyboardInterrupt) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
