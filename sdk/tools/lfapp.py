#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, deterministic experimental native application container (LFAPP0)."""
import hashlib
import json
import re
import struct

MAGIC = b"LFAPP0\0\0"
HEADER = struct.Struct("<8sIIII32s8s")
MAX_MANIFEST = 4096
MAX_IMAGE = 2 * 1024 * 1024
CODE = 0x10000000
DATA = 0x10201000
DATA_END = 0x102EF000
ABI = 1
SUPPORTED_ABIS = (0, 1)
SUPPORTED_SCHEMAS = (0, 1)
API_REVISION = 12
CAPABILITIES = 16383
BASE_FIELDS = {"id", "name", "version", "abi", "license"}
EXTENSION_FIELDS = {"schema", "required_capabilities", "optional_capabilities", "minimum_api", "data_schema"}


class PackageError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PackageError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def manifest(value):
    require(isinstance(value, dict), "manifest must be an object")
    schema = value.get("schema", 0)
    require(type(schema) is int and schema in SUPPORTED_SCHEMAS, "unsupported manifest schema")
    require(set(value) == BASE_FIELDS | (EXTENSION_FIELDS if schema else set()), "unknown or missing manifest field")
    require(isinstance(value["id"], str) and re.fullmatch(r"[a-z][a-z0-9-]{0,47}", value["id"]), "invalid app id")
    require(type(value["abi"]) is int and value["abi"] in SUPPORTED_ABIS, "unsupported ABI")
    for key in ("name", "version", "license"):
        require(isinstance(value[key], str) and 0 < len(value[key]) <= 80 and value[key].strip() and
                all(32 <= ord(c) < 127 for c in value[key]), f"invalid {key}")
    require(re.fullmatch(r"\d{1,6}\.\d{1,6}\.\d{1,6}", value["version"]), "version must be major.minor.patch")
    if schema:
        require(value["abi"] == 1, "manifest schema 1 requires ABI 1")
        for key in EXTENSION_FIELDS - {"schema"}:
            require(type(value[key]) is int and 0 <= value[key] <= 0xffffffff, f"invalid {key}: expected uint32")
        require(value["minimum_api"] >= 1, "minimum_api must be at least 1")
        require(not value["required_capabilities"] & value["optional_capabilities"], "required and optional capabilities overlap")
    return value


def compatible(metadata, *, api=API_REVISION, features=CAPABILITIES, schemas=SUPPORTED_SCHEMAS):
    """Structural validity is distinct from support by a particular device."""
    manifest(metadata)
    require(metadata.get("schema", 0) in schemas, "OS does not support this package schema; update Lefony OS")
    require(metadata.get("minimum_api", 0) <= api, "app requires a newer OS API; update Lefony OS")
    missing = metadata.get("required_capabilities", 0) & ~features
    require(not missing, f"OS lacks required app capabilities 0x{missing:08x}; update Lefony OS")
    return True


def elf_segments(image):
    require(52 <= len(image) <= MAX_IMAGE, "invalid ELF size")
    require(image[:16] == b"\x7fELF\x01\x01\x01" + b"\0" * 9, "expected ELF32 little-endian System V")
    kind, machine, version, entry, phoff, shoff, flags, ehsize, phsize, count, shsize, shnum, shstr = struct.unpack_from("<HHIIIIIHHHHHH", image, 16)
    require((kind, machine, version, ehsize, phsize) == (2, 40, 1, 52, 32), "unsupported ELF architecture/header")
    require(flags == 0x05000400, "expected ARM EABI5 hard-float")
    require(1 <= count <= 8 and 52 <= phoff <= len(image) and count * 32 <= len(image) - phoff, "invalid program headers")
    segments = []
    for i in range(count):
        typ, offset, address, physical, size, memory, perms, alignment = struct.unpack_from("<IIIIIIII", image, phoff + 32*i)
        require(typ in (0, 1, 0x6474E551), "unsupported ELF program header")
        if typ != 1:
            require(typ != 0x6474E551 or perms == 6, "executable stack rejected")
            continue
        if memory == 0 and size == 0 and address == 0 and physical == 0 and perms == 6:
            continue  # GNU ld's empty data header for stateless apps.
        require(perms in (5, 6) and size <= memory and memory > 0, "invalid segment permissions/size")
        require(offset <= len(image) and size <= len(image)-offset, "segment outside image")
        require(alignment >= 4096 and alignment <= 0x100000 and alignment & (alignment-1) == 0 and
                address % alignment == offset % alignment, "invalid segment alignment")
        lower, upper = (CODE, CODE + 0x100000) if perms == 5 else (DATA, DATA_END)
        require(lower <= address < upper and memory <= upper - address and address == physical,
                "segment outside app reservation")
        require(not any(address < a+m and a < address+memory for a, _, m, _ in segments), "overlapping memory segments")
        segments.append((address, image[offset:offset+size], memory, perms))
    require(any(p == 5 and a <= entry < a+len(data) for a, data, _, p in segments) and entry % 4 == 0,
            "entry must be ARM code in initialized executable segment")
    require(len(segments) <= 2 and len({p for _, _, _, p in segments}) == len(segments), "one code and at most one data segment required")
    return entry, segments


def pack(metadata, image):
    encoded = canonical(manifest(metadata))
    require(len(encoded) <= MAX_MANIFEST, "manifest too large")
    elf_segments(image)
    body = encoded + image
    return HEADER.pack(MAGIC, metadata.get("schema", 0), len(encoded), len(image), metadata["abi"], hashlib.sha256(body).digest(), b"\0"*8) + body


def unpack(package):
    require(HEADER.size <= len(package) <= HEADER.size + MAX_MANIFEST + MAX_IMAGE, "invalid package size")
    magic, schema, meta_len, image_len, flags, digest, reserved = HEADER.unpack_from(package)
    require(magic == MAGIC and schema in SUPPORTED_SCHEMAS and flags in SUPPORTED_ABIS and reserved == b"\0"*8, "unsupported package header")
    require(0 < meta_len <= MAX_MANIFEST and 52 <= image_len <= MAX_IMAGE and
            len(package) == HEADER.size + meta_len + image_len, "invalid package lengths")
    body = package[HEADER.size:]
    require(hashlib.sha256(body).digest() == digest, "package digest mismatch")
    try:
        metadata = manifest(json.loads(body[:meta_len]))
    except (ValueError, UnicodeError, TypeError) as exc:
        raise PackageError(f"invalid manifest: {exc}") from exc
    require(canonical(metadata) == body[:meta_len], "manifest must be canonical JSON without duplicate keys")
    require(metadata["abi"] == flags, "ABI header does not match manifest")
    require(metadata.get("schema", 0) == schema, "schema header does not match manifest")
    image = body[meta_len:]
    elf_segments(image)
    return metadata, image
