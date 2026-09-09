import hashlib
import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stock_fixture", ROOT / "scripts" / "prepare_hp_prime_stock_fixture.py"
)
stock_fixture = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = stock_fixture
SPEC.loader.exec_module(stock_fixture)


def image(payload: bytes, include_delay: bool = False) -> bytes:
    result = bytearray(b"\xff" * 0x1000)
    struct.pack_into(
        "<8I",
        result,
        stock_fixture.IVT_OFFSET,
        stock_fixture.IVT_HEADER,
        0x80002000,
        0,
        0x80000440,
        0x80000420,
        0x80000400,
        0,
        0,
    )
    result.extend(payload)
    if include_delay:
        result.extend(stock_fixture.DELAY_SIGNATURE)
    return bytes(result)


def block(name: str, data: bytes) -> bytes:
    encoded_name = name.encode() + b"\0"
    encoded_name += b"\0" * ((4 - len(encoded_name) % 4) % 4)
    size = 16 + len(encoded_name) + len(data)
    return struct.pack("<III", size, len(data), len(encoded_name)) + encoded_name + b"\0" * 4 + data


def container(*blocks: bytes) -> bytes:
    body = b"".join(blocks)
    return struct.pack("<I", len(body) + 4) + body


class StockFixtureTests(unittest.TestCase):
    def test_extracts_private_images_and_records_ivt(self):
        firmware = container(
            block("", image(b"os", include_delay=True)),
            block("", image(b"boot")),
            block("files.sig", b"signature"),
            block("HelpEn.hpresource", b"resource"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "HPPrime_OS.img"
            source.write_bytes(firmware)
            manifest = stock_fixture.prepare(source, root / "out", True)
            self.assertEqual(manifest["format"], "hp-prime-g2-private-emulator-fixture-v1")
            self.assertEqual(manifest["images"]["os"]["ivt"]["entry"], 0x80002000)
            self.assertEqual(manifest["resources"][0]["name"], "HelpEn.hpresource")
            fast = (root / "out" / "HPPrime.fast.img").read_bytes()
            offset = image(b"os", include_delay=True).find(stock_fixture.DELAY_SIGNATURE)
            self.assertEqual(fast[offset : offset + 2], stock_fixture.THUMB_RETURN)
            self.assertNotEqual(
                manifest["images"]["os_fast"]["sha256"],
                hashlib.sha256(image(b"os", include_delay=True)).hexdigest(),
            )

    def test_rejects_size_mismatch(self):
        malformed = struct.pack("<I", 999) + b"short"
        with self.assertRaises(stock_fixture.FixtureError):
            stock_fixture.parse_blocks(malformed)

    def test_rejects_image_without_ivt(self):
        with self.assertRaises(stock_fixture.FixtureError):
            stock_fixture.parse_ivt(b"\xff" * 0x1000, "bad")

    def test_exploratory_shim_is_exact_and_labeled(self):
        original = image(stock_fixture.EXPLORATORY_LOOP_SIGNATURE, include_delay=True)
        patched, offset = stock_fixture.exploratory_copy(original)
        self.assertEqual(patched[offset : offset + 2], stock_fixture.THUMB_BRANCH_TO_EXIT)
        self.assertEqual(original[offset : offset + 2], bytes.fromhex("cfe7"))

    def test_bootloader_exploratory_shim_supplies_only_direct_load_handoffs(self):
        original = image(
            stock_fixture.BOOTLOADER_SETTLE_SIGNATURE
            + stock_fixture.BOOTLOADER_ROLE_DEBOUNCE_SIGNATURE
            + stock_fixture.BOOTLOADER_WORKER_IDLE_SIGNATURE
        )
        patched, offsets = stock_fixture.exploratory_bootloader_copy(original)
        self.assertEqual(
            patched[offsets[0] : offsets[0] + 4],
            stock_fixture.THUMB_CALL_NAND_INITIALIZER,
        )
        self.assertEqual(original[offsets[0] : offsets[0] + 4], bytes.fromhex("02f0defa"))
        self.assertEqual(
            patched[offsets[1] : offsets[1] + 4], stock_fixture.THUMB_TRUE_RETURN
        )
        self.assertEqual(
            patched[offsets[2] : offsets[2] + 2], stock_fixture.THUMB_ZERO
        )
        self.assertEqual(original[offsets[2] : offsets[2] + 2], bytes.fromhex("6420"))
        changed = [
            index for index, pair in enumerate(zip(original, patched))
            if pair[0] != pair[1]
        ]
        expected = set()
        for offset, size in (
            (offsets[0], 4),
            (offsets[1], 4),
            (offsets[2], 2),
        ):
            expected.update(range(offset, offset + size))
        self.assertTrue(set(changed).issubset(expected))
        self.assertEqual(len(patched), len(original))


if __name__ == "__main__":
    unittest.main()
