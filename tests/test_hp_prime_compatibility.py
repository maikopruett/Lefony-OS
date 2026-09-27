# SPDX-License-Identifier: GPL-3.0-or-later
"""Public research-tool guard tests. No HP images or optional engines needed."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hp_compatibility", ROOT / "scripts/analyze_hp_prime_compatibility.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class CompatibilityGuardTests(unittest.TestCase):
    def test_unknown_component_rejected(self):
        with self.assertRaisesRegex(audit.AuditError, "unknown input"):
            audit.verify_input("unknown.img", b"")

    def test_truncated_input_rejected(self):
        with self.assertRaisesRegex(audit.AuditError, "exact original"):
            audit.verify_input("HPPrime.img", b"V15751")

    def test_size_alone_is_not_identity(self):
        with self.assertRaisesRegex(audit.AuditError, "exact original"):
            audit.verify_input("bootloader.img", bytes(audit.INPUTS["bootloader.img"][0]))

    def test_output_cannot_escape_build_via_parent_or_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "build").mkdir()
            (root / "public").mkdir()
            (root / "build/link").symlink_to(root / "public", target_is_directory=True)
            with patch.object(audit, "ROOT", root):
                for path in (root / "public", root / "build/../public", root / "build/link/report"):
                    with self.assertRaisesRegex(audit.AuditError, "ignored build"):
                        audit.private_output(path)
                self.assertEqual(audit.private_output(root / "build/private"), (root / "build/private").resolve())

    def test_stock_geometry_and_rounding(self):
        self.assertEqual(audit.stock_bounds(131072, 4096), (392, 4095))
        self.assertEqual(audit.stock_bounds(262144, 2048), (200, 2047))
        self.assertEqual(audit.stock_bounds(131073, 4096), (392, 4095))
        self.assertEqual(audit.stock_bounds(131071, 4096), (393, 4095))

    def test_invalid_geometry_rejected(self):
        for block, total in ((0, 4096), (-1, 4096), (131072, 0)):
            with self.assertRaises(audit.AuditError):
                audit.stock_bounds(block, total)

    def test_cli_refuses_public_report_before_loading_firmware(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/analyze_hp_prime_compatibility.py"),
             "--fixture-dir", "missing", "--container", "missing",
             "--output-dir", str(ROOT / "docs/private-report")],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ignored build/", result.stderr)
        self.assertFalse((ROOT / "docs/private-report").exists())


if __name__ == "__main__":
    unittest.main()
