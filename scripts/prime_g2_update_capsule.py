#!/usr/bin/env python3
"""Build and inspect signed Lefony OS HP Prime G2 update capsules.

The container keeps the bootable zImage byte-for-byte intact.  A fixed 512-byte
manifest precedes it for the running-device updater; recovery installation
extracts the embedded zImage and writes only the provisioned inactive slot.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


MAGIC = b"LFU1"
SCHEMA = 1
HEADER_BYTES = 512
MODEL_HP_PRIME_G2 = b"HPG2"
SIGNATURE_BYTES = 256
SIGNED_PREFIX = struct.Struct("<4sHH4s4I I 32s")
ZIMAGE_MAGIC_OFFSET = 0x24
ZIMAGE_SIZE_OFFSET = 0x2C
ZIMAGE_MAGIC = 0x016F2818


class CapsuleError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdateCapsule:
    path: Path
    version: tuple[int, int, int, int]
    model: bytes
    payload: bytes
    digest: bytes
    signature: bytes

    @property
    def signed_prefix(self) -> bytes:
        return SIGNED_PREFIX.pack(
            MAGIC,
            SCHEMA,
            HEADER_BYTES,
            self.model,
            *self.version,
            len(self.payload),
            self.digest,
        )


def parse_version(value: str) -> tuple[int, int, int, int]:
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\+(0|[1-9]\d*))?", value)
    if not match:
        raise argparse.ArgumentTypeError("version must be MAJOR.MINOR.PATCH[+BUILD]")
    version = tuple(int(part or 0) for part in match.groups())
    if any(part > 0xFFFFFFFF for part in version):
        raise argparse.ArgumentTypeError("version component exceeds 32 bits")
    return version  # type: ignore[return-value]


def validate_zimage(payload: bytes) -> None:
    if len(payload) < 0x30:
        raise CapsuleError("payload is shorter than its zImage header")
    if int.from_bytes(payload[ZIMAGE_MAGIC_OFFSET:ZIMAGE_MAGIC_OFFSET + 4], "little") != ZIMAGE_MAGIC:
        raise CapsuleError("payload has no ARM zImage magic")
    declared = int.from_bytes(payload[ZIMAGE_SIZE_OFFSET:ZIMAGE_SIZE_OFFSET + 4], "little")
    if declared != len(payload):
        raise CapsuleError(f"zImage declares {declared} bytes, actual payload is {len(payload)}")


def _openssl(command: list[str], *, data: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            command,
            input=data,
            capture_output=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CapsuleError(f"could not run OpenSSL: {error}") from error
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise CapsuleError(f"OpenSSL failed: {detail or result.returncode}")
    return result.stdout


def sign_prefix(prefix: bytes, private_key: Path) -> bytes:
    signature = _openssl(
        ["openssl", "dgst", "-sha256", "-sign", str(private_key)], data=prefix
    )
    if len(signature) != SIGNATURE_BYTES:
        raise CapsuleError("signing key must be RSA-2048")
    return signature


def verify_signature(prefix: bytes, signature: bytes, public_key: Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        message = root / "manifest.bin"
        signed = root / "manifest.sig"
        message.write_bytes(prefix)
        signed.write_bytes(signature)
        _openssl(
            [
                "openssl", "dgst", "-sha256", "-verify", str(public_key),
                "-signature", str(signed), str(message),
            ]
        )


def build(payload_path: Path, output: Path, version: tuple[int, int, int, int],
          private_key: Path, model: bytes = MODEL_HP_PRIME_G2) -> UpdateCapsule:
    payload = payload_path.read_bytes()
    validate_zimage(payload)
    digest = hashlib.sha256(payload).digest()
    unsigned = UpdateCapsule(output, version, model, payload, digest, b"")
    signature = sign_prefix(unsigned.signed_prefix, private_key)
    capsule = UpdateCapsule(output, version, model, payload, digest, signature)
    header = capsule.signed_prefix + signature
    if len(header) > HEADER_BYTES:
        raise CapsuleError("manifest exceeds its fixed header")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(header.ljust(HEADER_BYTES, b"\0") + payload)
    return capsule


def inspect(path: Path, public_key: Path | None = None) -> UpdateCapsule:
    package = path.read_bytes()
    if len(package) < HEADER_BYTES + 0x30:
        raise CapsuleError("signed update capsule is truncated")
    fields = SIGNED_PREFIX.unpack(package[:SIGNED_PREFIX.size])
    magic, schema, header_bytes, model = fields[:4]
    version = fields[4:8]
    payload_bytes = fields[8]
    digest = fields[9]
    if magic != MAGIC or schema != SCHEMA or header_bytes != HEADER_BYTES:
        raise CapsuleError("unsupported signed update manifest")
    if model != MODEL_HP_PRIME_G2:
        raise CapsuleError("update capsule targets a different device model")
    if payload_bytes > 8 * 1024 * 1024 or payload_bytes < 0x30:
        raise CapsuleError("signed payload length is outside the A/B slot")
    if len(package) != HEADER_BYTES + payload_bytes:
        raise CapsuleError("signed payload length does not match the container")
    signature_start = SIGNED_PREFIX.size
    signature = package[signature_start:signature_start + SIGNATURE_BYTES]
    payload = package[HEADER_BYTES:]
    validate_zimage(payload)
    actual = hashlib.sha256(payload).digest()
    if actual != digest:
        raise CapsuleError("signed payload SHA-256 does not match the manifest")
    capsule = UpdateCapsule(path, version, model, payload, digest, signature)
    if public_key is not None:
        verify_signature(capsule.signed_prefix, signature, public_key)
    return capsule


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("payload", type=Path)
    create.add_argument("output", type=Path)
    create.add_argument("--version", required=True, type=parse_version)
    create.add_argument("--private-key", required=True, type=Path)
    check = subparsers.add_parser("inspect")
    check.add_argument("capsule", type=Path)
    check.add_argument("--public-key", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "create":
            capsule = build(args.payload, args.output, args.version, args.private_key)
        else:
            capsule = inspect(args.capsule, args.public_key)
    except (CapsuleError, OSError) as error:
        parser.error(str(error))
    print(
        f"{capsule.path}: version={'.'.join(map(str, capsule.version[:3]))}+{capsule.version[3]} "
        f"payload_bytes={len(capsule.payload)} sha256={capsule.digest.hex()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
