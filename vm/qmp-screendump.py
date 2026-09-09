#!/usr/bin/env python3
"""Save the current QEMU framebuffer through its local QMP socket."""

from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path
from typing import BinaryIO


def receive_message(stream: BinaryIO) -> dict:
    while line := stream.readline():
        if line.strip():
            return json.loads(line)
    raise ConnectionError("QMP closed the connection")


def execute(client: socket.socket, stream: BinaryIO, command: dict) -> dict:
    client.sendall(json.dumps(command).encode() + b"\n")
    while True:
        response = receive_message(stream)
        if "return" in response or "error" in response:
            return response


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("socket", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()
    socket_path = args.socket.resolve(strict=False) if args.socket.is_symlink() else args.socket

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(args.timeout)
        client.connect(str(socket_path))
        with client.makefile("rb") as stream:
            greeting = receive_message(stream)
            if "QMP" not in greeting:
                raise RuntimeError(f"invalid QMP greeting: {greeting}")
            response = execute(client, stream, {"execute": "qmp_capabilities"})
            if "error" in response:
                raise RuntimeError(response["error"])
            response = execute(
                client,
                stream,
                {
                    "execute": "screendump",
                    "arguments": {"filename": str(args.output.resolve())},
                },
            )
            if "error" in response:
                raise RuntimeError(response["error"])

    if not args.output.is_file() or args.output.stat().st_size == 0:
        raise RuntimeError(f"QEMU did not create {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
