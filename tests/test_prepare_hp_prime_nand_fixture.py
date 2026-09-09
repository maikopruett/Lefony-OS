import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "nand_fixture", ROOT / "scripts" / "prepare_hp_prime_nand_fixture.py"
)
nand_fixture = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = nand_fixture
SPEC.loader.exec_module(nand_fixture)


class NANDFixtureTests(unittest.TestCase):
    def setUp(self):
        self.old_chunk_bytes = nand_fixture.CHUNK_RAW_BYTES
        self.old_total_bytes = nand_fixture.TOTAL_RAW_BYTES
        nand_fixture.CHUNK_RAW_BYTES = 4
        nand_fixture.TOTAL_RAW_BYTES = nand_fixture.CHUNK_COUNT * 4

    def tearDown(self):
        nand_fixture.CHUNK_RAW_BYTES = self.old_chunk_bytes
        nand_fixture.TOTAL_RAW_BYTES = self.old_total_bytes

    @staticmethod
    def write_chunks(directory: Path) -> bytes:
        expected = bytearray()
        for index in reversed(range(nand_fixture.CHUNK_COUNT)):
            data = bytes([index]) * 4
            (directory / f"{index * 64}-{(index + 1) * 64}mb.bin").write_bytes(data)
        for index in range(nand_fixture.CHUNK_COUNT):
            expected.extend(bytes([index]) * 4)
        return bytes(expected)

    def test_joins_ranges_in_physical_order_and_records_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "chunks"
            source.mkdir()
            expected = self.write_chunks(source)
            manifest = nand_fixture.prepare(source, root / "out")

            image = (root / "out" / "stock-nand.raw").read_bytes()
            self.assertEqual(image, expected)
            self.assertEqual(manifest["image"]["sha256"], hashlib.sha256(expected).hexdigest())
            self.assertEqual([row["index"] for row in manifest["chunks"]], list(range(8)))
            persisted = json.loads((root / "out" / "nand-fixture.json").read_text())
            self.assertTrue(persisted["private_fixture"])
            self.assertEqual(persisted["geometry"]["oob_bytes"], 64)

    def test_rejects_missing_or_wrong_sized_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_chunks(root)
            (root / "448-512mb.bin").unlink()
            with self.assertRaisesRegex(ValueError, "expected exactly"):
                nand_fixture.ordered_chunks(root)

            (root / "448-512mb.bin").write_bytes(b"bad")
            with self.assertRaisesRegex(ValueError, "expected 4"):
                nand_fixture.ordered_chunks(root)

    def test_rejects_misaligned_range_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_chunks(root)
            (root / "1-65mb.bin").write_bytes(b"xxxx")
            with self.assertRaisesRegex(ValueError, "invalid NAND chunk range"):
                nand_fixture.ordered_chunks(root)


if __name__ == "__main__":
    unittest.main()
