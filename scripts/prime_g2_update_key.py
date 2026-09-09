#!/usr/bin/env python3
"""Create a local release key and emit Lefony's compiled RSA trust root."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path


class KeyError(RuntimeError):
    pass


def run(command: list[str]) -> bytes:
    try:
        result = subprocess.run(command, capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise KeyError(f"could not run OpenSSL: {error}") from error
    if result.returncode:
        raise KeyError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def ensure(private_key: Path, public_key: Path) -> None:
    if private_key.exists() != public_key.exists():
        raise KeyError("release keypair is incomplete; refusing to replace either half")
    if not private_key.exists():
        private_key.parent.mkdir(parents=True, exist_ok=True)
        run([
            "openssl", "genpkey", "-algorithm", "RSA",
            "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key),
        ])
        os.chmod(private_key, 0o600)
        run([
            "openssl", "pkey", "-in", str(private_key), "-pubout",
            "-out", str(public_key),
        ])


def modulus(public_key: Path) -> bytes:
    output = run([
        "openssl", "rsa", "-pubin", "-in", str(public_key),
        "-modulus", "-noout",
    ]).decode("ascii", "strict").strip()
    match = re.fullmatch(r"Modulus=([0-9A-Fa-f]+)", output)
    if not match:
        raise KeyError("OpenSSL did not return an RSA modulus")
    value = bytes.fromhex(match.group(1))
    if len(value) != 256:
        raise KeyError("update public key must be RSA-2048")
    return value


def header(public_key: Path) -> str:
    value = modulus(public_key)
    rows = []
    for offset in range(0, len(value), 16):
        rows.append("  " + ",".join(f"0x{byte:02x}" for byte in value[offset:offset + 16]))
    return (
        "#ifndef ION_PRIME_G2_UPDATE_TRUST_ROOT_H\n"
        "#define ION_PRIME_G2_UPDATE_TRUST_ROOT_H\n\n"
        "/* Generated from the release public key; never place the private key here. */\n"
        "constexpr uint8_t PrimeG2UpdateModulus[256] = {\n"
        + ",\n".join(rows)
        + "\n};\n\n#endif\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("ensure")
    create.add_argument("private_key", type=Path)
    create.add_argument("public_key", type=Path)
    emit = sub.add_parser("header")
    emit.add_argument("public_key", type=Path)
    emit.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "ensure":
            ensure(args.private_key, args.public_key)
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(header(args.public_key))
    except (KeyError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
