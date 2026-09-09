import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hp_prime_stock_nand", ROOT / "vm/hp_prime_stock_nand.py"
)
stock = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(stock)


class HPPrimeStockNANDTests(unittest.TestCase):
    def test_erased_capture_record_decodes_as_erased_payload(self):
        record = bytes([0xFF]) * stock.RECORD_BYTES
        self.assertEqual(
            stock.decode_stock_page(record), bytes([0xFF]) * stock.PAGE_BYTES
        )

    def test_record_size_is_strict(self):
        for length in (0, stock.RECORD_BYTES - 1, stock.RECORD_BYTES + 1):
            with self.subTest(length=length), self.assertRaises(ValueError):
                stock.decode_stock_page(bytes(length))

    def test_geometry_matches_observed_capture_and_stock_views(self):
        self.assertEqual(stock.CAPTURE_METADATA_BYTES, 10)
        self.assertEqual(stock.CAPTURE_ECC_STRENGTH, 2)
        self.assertEqual(stock.STOCK_METADATA_BYTES, 36)
        self.assertEqual(stock.STOCK_ECC_STRENGTH, 4)
        self.assertEqual(stock.STOCK_OS_FIRST_PAGE, 768)


if __name__ == "__main__":
    unittest.main()
