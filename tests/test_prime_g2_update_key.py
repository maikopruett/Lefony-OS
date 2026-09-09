import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "prime_g2_update_key", ROOT / "scripts/prime_g2_update_key.py"
)
assert SPEC and SPEC.loader
keys = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = keys
SPEC.loader.exec_module(keys)


class UpdateKeyTests(unittest.TestCase):
    def test_fixture_generates_compilable_rsa_2048_header(self):
        generated = keys.header(
            ROOT / "tests/fixtures/prime_g2_emulator_update_public.pem"
        )
        self.assertIn("PrimeG2UpdateModulus[256]", generated)
        self.assertEqual(generated.count("0x"), 256)

    def test_ensure_never_overwrites_half_a_keypair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / "private.pem"
            public = root / "public.pem"
            private.write_text("keep")
            with self.assertRaisesRegex(keys.KeyError, "incomplete"):
                keys.ensure(private, public)
            self.assertEqual(private.read_text(), "keep")
            self.assertFalse(public.exists())


if __name__ == "__main__":
    unittest.main()
