import csv
import hashlib
import json
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HARDWARE = ROOT / "hardware" / "prime_g2"
REFERENCE = HARDWARE / "reference"
PRIVATE_REFERENCE = Path(os.environ.get("LEFONY_PRIVATE_HARDWARE_DIR", "/nonexistent"))
PRIMARY_CAPTURE = HARDWARE / "captures" / "20260831T154107Z"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PrimeG2HardwareReferenceTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("LEFONY_PRIVATE_HARDWARE_DIR"),
                         "requires privately supplied DTB/DTS; see docs/STATUS.md")
    def test_preserved_dtb_identity(self) -> None:
        expected = "ba6febaffca915a1fe43fe986980cc78d83d93ede559ae9bb7056aa677440bee"
        self.assertEqual(expected, sha256(PRIVATE_REFERENCE / "imx6ull-14x14-prime.dtb"))
        live_hash = (PRIMARY_CAPTURE / "boot-dtb-hash.txt").read_text()
        self.assertIn(expected, live_hash)

    @unittest.skipUnless(os.environ.get("LEFONY_PRIVATE_HARDWARE_DIR"),
                         "requires privately supplied DTB/DTS; see docs/STATUS.md")
    def test_device_tree_contains_fitted_board_contract(self) -> None:
        dts = (PRIVATE_REFERENCE / "imx6ull-14x14-prime.dts").read_text()
        for contract in (
            'model = "HP Prime G2 Calculator"',
            'compatible = "fsl,imx6ull-14x14-prime", "fsl,imx6ull"',
            "lcdif@021c8000",
            "bits-per-pixel = <0x20>",
            "bus-width = <0x08>",
            "clock-frequency = <0x112a880>",
            'compatible = "ilitek,ili9322"',
            'compatible = "goodix,gt928"',
            'compatible = "fsl,pf1550"',
            "kpp@020b8000",
        ):
            self.assertIn(contract, dts)

    def test_complete_keypad_matrix_is_decoded(self) -> None:
        with (REFERENCE / "keypad-matrix.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(50, len(rows))
        positions = {(int(row["row"]), int(row["column"])) for row in rows}
        self.assertEqual(50, len(positions))
        self.assertIn((7, 0), positions)
        self.assertIn((7, 1), positions)

    def test_live_display_state_is_regression_locked(self) -> None:
        registers = (PRIMARY_CAPTURE / "registers-lcdif.txt").read_text()
        for value in (
            "LCDIF_CTRL|0x021c8000|32|0x000A4521",
            "LCDIF_CTRL2|0x021c8020|32|0x00A00000",
            "LCDIF_TRANSFER_COUNT|0x021c8030|32|0x00F003C0",
            "LCDIF_VDCTRL0|0x021c8070|32|0x11300001",
            "LCDIF_VDCTRL1|0x021c8080|32|0x00000108",
            "LCDIF_VDCTRL2|0x021c8090|32|0x0004046C",
            "LCDIF_VDCTRL3|0x021c80a0|32|0x00480012",
            "LCDIF_VDCTRL4|0x021c80b0|32|0x000403C0",
        ):
            self.assertIn(value, registers)

    def test_capture_is_explicitly_marked_incomplete(self) -> None:
        manifest = json.loads((PRIMARY_CAPTURE / "manifest.json").read_text())
        self.assertEqual("incomplete", manifest["status"])
        self.assertTrue(manifest["incomplete_reason"])


if __name__ == "__main__":
    unittest.main()
