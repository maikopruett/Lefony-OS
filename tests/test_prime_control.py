from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "vm" / "prime-control.py"
SPEC = importlib.util.spec_from_file_location("prime_control", MODULE_PATH)
assert SPEC and SPEC.loader
prime_control = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prime_control)


class ProtocolTests(unittest.TestCase):
    def test_every_named_key_has_a_unique_code(self):
        self.assertEqual(len(prime_control.KEYS), len(set(prime_control.KEYS.values())))

    def test_versioned_success_responses(self):
        for response in (
            "V1 1 PONG",
            "V1 2 OK",
            "V1 3 INFO protocol=1",
            "V1 4 STATE app=0",
            "V1 5 TEXT 3",
            "V1 6 VALUE 1",
        ):
            with self.subTest(response=response):
                self.assertTrue(prime_control.is_success_response(response))

    def test_errors_and_malformed_envelopes_are_not_success(self):
        for response in ("ERR unknown command", "V1 1 ERR unknown command", "V1", ""):
            with self.subTest(response=response):
                self.assertFalse(prime_control.is_success_response(response))


if __name__ == "__main__":
    unittest.main()
