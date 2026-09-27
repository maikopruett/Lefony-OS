"""Checked/idempotent source integration; UI/math behavior is exercised in QEMU."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "prepare_prime_derivative", ROOT / "scripts/prepare_prime_derivative.py")
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


class DerivativePreparationTest(unittest.TestCase):
    def fixture(self, root):
        files = {
            "poincare/include/poincare/layout_node.h": "    VerticalOffsetLayout\n",
            "poincare/include/poincare/layout_cursor.h": "  friend class IntegralLayoutNode;\n",
            "poincare/src/layout_cursor.cpp": "  /* Change the visibility of the neighbouring empty layout: it might be either\n",
            "poincare/Makefile": "  integral_layout.cpp \\\n",
            "poincare/src/derivative.cpp": (
                "#include <poincare/derivative.h>\n"
                "  return LayoutHelper::Prefix(this, floatDisplayMode, numberOfSignificantDigits, Derivative::s_functionHelper.name());\n"),
        }
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    def test_repeat_preparation_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            PREPARE.prepare(root)
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            PREPARE.prepare(root)
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertIn(Path("poincare/src/derivative_layout.cpp"), after)

    def test_changed_or_duplicated_upstream_context_is_rejected(self):
        for content in ("unexpected upstream enum", "    VerticalOffsetLayout\n" * 2):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.fixture(root)
                path = root / "poincare/include/poincare/layout_node.h"
                path.write_text(content)
                with self.assertRaisesRegex(ValueError, "Unexpected derivative integration context"):
                    PREPARE.prepare(root)
                self.assertEqual(path.read_text(), content)


if __name__ == "__main__":
    unittest.main()
