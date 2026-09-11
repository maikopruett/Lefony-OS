# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lfapp", ROOT / "sdk/tools/lfapp.py")
lfapp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lfapp)
META = {"id": "sample", "name": "Sample", "version": "0.1.0", "abi": 0, "license": "CC-BY-NC-SA-4.0"}


def image():
    result = bytearray(4100)
    result[:16] = b"\x7fELF\x01\x01\x01" + bytes(9)
    struct.pack_into("<HHIIIIIHHHHHH", result, 16, 2, 40, 1, 0x10000000, 52, 0, 0x05000400, 52, 32, 1, 0, 0, 0)
    struct.pack_into("<IIIIIIII", result, 52, 1, 4096, 0x10000000, 0x10000000, 4, 4, 5, 4096)
    result[4096:] = bytes.fromhex("000000ef")
    return result


def test_deterministic_roundtrip():
    value = lfapp.pack(META, image())
    assert value == lfapp.pack(dict(reversed(list(META.items()))), image())
    assert lfapp.unpack(value) == (META, image())


@pytest.mark.parametrize("offset,value", [(18, 183), (36, 0), (24, 0x10201000), (52, 2), (76, 7), (72, 0xffffffff), (56, 0xfffffff0)])
def test_invalid_elf_rejected(offset, value):
    data = image()
    struct.pack_into("<I", data, offset, value)
    with pytest.raises(lfapp.PackageError):
        lfapp.pack(META, data)


def test_every_truncation_and_trailing_data_rejected():
    data = lfapp.pack(META, image())
    for size in range(len(data)):
        with pytest.raises(lfapp.PackageError):
            lfapp.unpack(data[:size])
    with pytest.raises(lfapp.PackageError):
        lfapp.unpack(data+b"\0")


def test_tampering_and_reserved_flags_rejected():
    good = lfapp.pack(META, image())
    for offset in (8, 20, 24, 56, len(good)-1):
        data = bytearray(good)
        data[offset] ^= 1
        with pytest.raises(lfapp.PackageError):
            lfapp.unpack(data)


def test_duplicate_manifest_fields_rejected_even_with_correct_hash():
    encoded = json.dumps(META, separators=(",", ":")).replace('"abi":0', '"abi":0,"abi":0').encode()
    body = encoded + image()
    data = lfapp.HEADER.pack(lfapp.MAGIC, 0, len(encoded), len(image()), 0, hashlib.sha256(body).digest(), bytes(8)) + body
    with pytest.raises(lfapp.PackageError):
        lfapp.unpack(data)


@pytest.mark.parametrize("key,value", [("id", "../app"), ("abi", True), ("version", "latest"), ("name", "<\n>"), ("extra", 1)])
def test_manifest_contract(key, value):
    with pytest.raises(lfapp.PackageError):
        lfapp.pack({**META, key: value}, image())


def test_abi_one_contract_and_abi_zero_compatibility():
    import struct
    for abi in (0,1):
        metadata={**META,"abi":abi}
        package=lfapp.pack(metadata,image())
        assert struct.unpack_from("<I",package,20)[0]==abi
        assert lfapp.unpack(package)[0]==metadata
    with pytest.raises(lfapp.PackageError):
        lfapp.pack({**META,"abi":2},image())
