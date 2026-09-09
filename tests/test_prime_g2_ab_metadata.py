import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "prime_g2_ab_metadata", REPO / "scripts/prime_g2_ab_metadata.py"
)
metadata = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = metadata
SPEC.loader.exec_module(metadata)


def image(marker: int = 0) -> bytes:
    raw = bytearray(4096)
    struct.pack_into("<I", raw, 0x24, metadata.ZIMAGE_MAGIC)
    struct.pack_into("<I", raw, 0x2C, len(raw))
    raw[-1] = marker
    return bytes(raw)


class MetadataTests(unittest.TestCase):
    def test_seed_round_trip_and_page_padding(self):
        value = metadata.seed(image(), (1, 0, 0, 0))
        raw = value.pack(page=True)
        self.assertEqual(len(raw), metadata.PAGE_BYTES)
        self.assertEqual(raw[metadata.RECORD.size:], b"\xff" *
                         (metadata.PAGE_BYTES - metadata.RECORD.size))
        self.assertEqual(metadata.Metadata.unpack(raw), value)

    def test_crc_rejects_corruption(self):
        raw = bytearray(metadata.seed(image(), (1, 0, 0, 0)).pack())
        raw[20] ^= 1
        with self.assertRaisesRegex(metadata.MetadataError, "CRC32"):
            metadata.Metadata.unpack(raw)

    def test_newest_tolerates_one_torn_copy(self):
        first = metadata.seed(image(), (1, 0, 0, 0))
        second = first.with_update(1, image(1), (1, 0, 1, 0))
        selected, source = metadata.newest(bytes(2048), second.pack(page=True))
        self.assertEqual((selected, source), (second, 1))

    def test_update_only_targets_inactive_newer_slot(self):
        first = metadata.seed(image(), (1, 0, 0, 0))
        updated = first.with_update(1, image(2), (1, 1, 0, 0))
        self.assertEqual(updated.pending, 1)
        self.assertEqual(updated.active, 0)
        self.assertEqual(updated.generation, 2)
        with self.assertRaises(metadata.MetadataError):
            first.with_update(0, image(3), (1, 2, 0, 0))
        with self.assertRaises(metadata.MetadataError):
            first.with_update(1, image(3), (0, 9, 0, 0))


if __name__ == "__main__":
    unittest.main()
