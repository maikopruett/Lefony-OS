import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "prime_g2_update_capsule.py"
SPEC = importlib.util.spec_from_file_location("prime_g2_update_capsule", SCRIPT)
capsule = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = capsule
SPEC.loader.exec_module(capsule)
PRIVATE = REPO / "tests/fixtures/prime_g2_emulator_update_private.pem"
PUBLIC = REPO / "tests/fixtures/prime_g2_emulator_update_public.pem"


def zimage(length: int = 4096) -> bytes:
    payload = bytearray((index * 17 + 3) & 0xFF for index in range(length))
    payload[0x24:0x28] = capsule.ZIMAGE_MAGIC.to_bytes(4, "little")
    payload[0x2C:0x30] = length.to_bytes(4, "little")
    return bytes(payload)


class SignedUpdateCapsuleTests(unittest.TestCase):
    def test_signed_round_trip_preserves_boot_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "lefony.zImage"
            package = root / "lefony.lfu"
            payload.write_bytes(zimage())
            built = capsule.build(payload, package, (1, 2, 3, 4), PRIVATE)
            parsed = capsule.inspect(package, PUBLIC)
            self.assertEqual(parsed.version, (1, 2, 3, 4))
            self.assertEqual(parsed.payload, payload.read_bytes())
            self.assertEqual(parsed.digest, built.digest)

    def test_payload_corruption_is_rejected_before_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "lefony.zImage"
            package = root / "lefony.lfu"
            payload.write_bytes(zimage())
            capsule.build(payload, package, (1, 0, 1, 0), PRIVATE)
            damaged = bytearray(package.read_bytes())
            damaged[-1] ^= 1
            package.write_bytes(damaged)
            with self.assertRaisesRegex(capsule.CapsuleError, "SHA-256"):
                capsule.inspect(package, PUBLIC)

    def test_wrong_signing_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "lefony.zImage"
            package = root / "lefony.lfu"
            payload.write_bytes(zimage())
            capsule.build(payload, package, (1, 0, 1, 0), PRIVATE)
            wrong_private = root / "wrong-private.pem"
            wrong_public = root / "wrong-public.pem"
            subprocess.run(
                ["openssl", "genrsa", "-out", str(wrong_private), "2048"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["openssl", "rsa", "-in", str(wrong_private), "-pubout", "-out", str(wrong_public)],
                check=True,
                capture_output=True,
            )
            with self.assertRaisesRegex(capsule.CapsuleError, "OpenSSL failed"):
                capsule.inspect(package, wrong_public)


if __name__ == "__main__":
    unittest.main()
