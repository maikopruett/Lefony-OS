#!/usr/bin/env python3
"""Serve VM control while actuating Prime matrix keys at QEMU's KPP boundary."""

from __future__ import annotations

import re
import selectors
import socket
import sys
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
KEYMAP = REPO / "ports/lefony-prime-g2/ion/src/prime_g2/keymap.inc"
KEY_RE = re.compile(
    r"^PRIME_G2_KEY\(\s*([a-z0-9_]+)\s*,\s*([0-9]+)\s*,\s*"
    r"[A-Za-z0-9_]+\s*,\s*([0-9]+)\s*,\s*([0-9]+)\s*\)"
)
KPP_INGRESS = 0x020B8008


def load_matrix() -> dict[int, tuple[int, int]]:
    result: dict[int, tuple[int, int]] = {}
    for line in KEYMAP.read_text().splitlines():
        match = KEY_RE.match(line)
        if match and int(match.group(3)) < 8 and int(match.group(4)) < 8:
            result[int(match.group(2))] = (int(match.group(3)), int(match.group(4)))
    return result


def connect(path: Path, description: str, timeout: float = 30.0) -> socket.socket:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            connection.connect(str(path))
            return connection
        except OSError:
            connection.close()
            time.sleep(0.05)
    raise TimeoutError(f"{description} did not appear: {path}")


def read_line(connection: socket.socket, description: str,
              timeout: float = 10.0) -> bytes:
    selector = selectors.DefaultSelector()
    selector.register(connection, selectors.EVENT_READ)
    data = bytearray()
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready = selector.select(deadline - time.monotonic())
            if not ready:
                break
            chunk = connection.recv(1)
            if not chunk:
                raise ConnectionError(f"{description} closed")
            data.extend(chunk)
            if chunk == b"\n":
                return bytes(data)
    finally:
        selector.close()
    raise TimeoutError(f"{description} did not respond")


def write_uart(connection: socket.socket, line: bytes) -> bytes:
    for byte in line + b"\n":
        connection.sendall(bytes((byte,)))
        # 115200 baud transmits one 8N1 byte in about 87 us. A 200 us host
        # pacing margin remains conservative without making parser fuzzing
        # twenty times slower than the physical UART.
        time.sleep(0.0002)
    return read_line(connection, "guest input UART")


class MatrixController:
    def __init__(self, qtest: socket.socket):
        self.qtest = qtest
        self.mapping = load_matrix()
        self.pressed: set[int] = set()
        self.release_at: dict[int, float] = {}
        self.time_offset_ms = 0.0

    def now_ms(self) -> float:
        return time.monotonic() * 1000.0 + self.time_offset_ms

    def write(self, code: int, down: bool) -> None:
        row, column = self.mapping[code]
        packed = (0x8000 if down else 0) | row << 8 | column
        self.qtest.sendall(f"writew 0x{KPP_INGRESS:x} 0x{packed:x}\n".encode())
        reply = read_line(self.qtest, "QEMU qtest KPP").strip()
        if reply != b"OK":
            raise RuntimeError(f"KPP actuation failed: {reply!r}")
        if down:
            self.pressed.add(code)
        else:
            self.pressed.discard(code)
            self.release_at.pop(code, None)

    def release_due(self) -> None:
        now = self.now_ms()
        for code, deadline in list(self.release_at.items()):
            if now >= deadline:
                self.write(code, False)

    def reset(self) -> None:
        for code in list(self.pressed):
            self.write(code, False)
        self.release_at.clear()

    @staticmethod
    def envelope(line: str) -> tuple[str, str]:
        match = re.fullmatch(r"V1 ([0-9]+) (.*)", line)
        return (f"V1 {match.group(1)} ", match.group(2)) if match else ("", line)

    def intercept(self, line: str) -> str | None:
        prefix, command = self.envelope(line)
        fields = command.split()
        if len(fields) >= 2 and fields[0] == "PRESS":
            try:
                code = int(fields[1])
                duration = int(fields[2]) if len(fields) == 3 else 100
            except ValueError:
                return prefix + "ERR invalid key"
            if code not in self.mapping:
                return None if code == 116 else prefix + "ERR unknown key"
            if duration <= 0 or duration > 60000:
                return prefix + "ERR invalid key"
            if code in self.pressed:
                self.write(code, False)
            self.write(code, True)
            # Schedule release against the proxy's guest-time clock. This
            # keeps PRESS observable while held and lets TIME ADVANCE test the
            # release boundary. High-level clients wait for the normal 100 ms
            # actuation before issuing their next key, preventing chords.
            self.release_at[code] = self.now_ms() + duration
            return prefix + "OK"
        if len(fields) == 3 and fields[:2] == ["KEY", "STATE"]:
            try:
                code = int(fields[2])
            except ValueError:
                return prefix + "ERR invalid key"
            if code not in self.mapping:
                return None if code == 116 else prefix + "ERR unknown key"
            return prefix + f"VALUE {int(code in self.pressed)}"
        if len(fields) == 3 and fields[0] == "KEY":
            try:
                code, state = int(fields[1]), int(fields[2])
            except ValueError:
                return prefix + "ERR invalid key state"
            if state not in (0, 1):
                return prefix + "ERR invalid key state"
            if code not in self.mapping:
                return None if code == 116 else prefix + "ERR unknown key"
            self.write(code, bool(state))
            return prefix + "OK"
        return None


def main() -> int:
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} UART_SOCKET CLIENT_SOCKET QTEST_SOCKET",
              file=sys.stderr)
        return 2
    uart_path, client_path, qtest_path = map(Path, sys.argv[1:])
    try:
        client_path.unlink(missing_ok=True)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(client_path))
        listener.listen(4)
        listener.settimeout(0.01)
        uart = connect(uart_path, "QEMU input UART")
        qtest = connect(qtest_path, "QEMU qtest socket")
        matrix = MatrixController(qtest)
        while True:
            matrix.release_due()
            try:
                client, _ = listener.accept()
            except TimeoutError:
                continue
            with client:
                request = bytearray()
                while True:
                    chunk = client.recv(256)
                    if not chunk:
                        break
                    request.extend(chunk)
                    while b"\n" in request:
                        raw, _, request = request.partition(b"\n")
                        line = raw.decode(errors="replace")
                        matrix.release_due()
                        direct = matrix.intercept(line)
                        if direct is not None:
                            client.sendall((direct + "\n").encode())
                            continue
                        _, command = matrix.envelope(line)
                        if command == "INPUT RESET":
                            matrix.reset()
                            # Let the native scan/event engine observe the
                            # electrical release before its test counters are
                            # reset by the UART control command.
                            time.sleep(0.03)
                        response = write_uart(uart, raw)
                        if command.startswith("TIME ADVANCE "):
                            try:
                                matrix.time_offset_ms += int(command.split()[2])
                            except (ValueError, IndexError):
                                pass
                            matrix.release_due()
                        client.sendall(response)
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
        print(f"Prime VM input proxy: {error}", file=sys.stderr)
        return 1
    finally:
        client_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
