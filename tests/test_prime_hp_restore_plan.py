# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prime_hp_restore_plan as plan


class RestorePlanTests(unittest.TestCase):
    def test_physical_fixture_cannot_be_used_as_linux_raw(self):
        sys.path.insert(0, str(ROOT / "vm"))
        from prime_gpmi_bch import Layout
        from prime_nand_image import checksum
        payload = bytearray(1024)
        payload[4:8] = b"FCB "
        struct.pack_into("<I", payload, 0, checksum(payload))
        physical = Layout(0x0720a020, 0x0840a020).encode(payload, bytes(32))
        with self.assertRaisesRegex(ValueError, "Linux BCH2 stock capture"):
            plan.validate_stock_record(physical)
        # Independent reference of the Linux raw-read projection: metadata,
        # four data/ECC chunks, unused tail, and the conventional marker swap.
        swapped = bytearray(physical)
        swapped[0], swapped[2048] = swapped[2048], swapped[0]
        bits = int.from_bytes(swapped, "little")
        data, oob, offset, oob_offset = bytearray(), bits & ((1 << 80) - 1), 80, 80
        for _ in range(4):
            data.extend(((bits >> offset) & ((1 << 4096) - 1)).to_bytes(512, "little"))
            offset += 4096
            oob |= ((bits >> offset) & ((1 << 26) - 1)) << oob_offset
            offset += 26
            oob_offset += 26
        oob |= (bits >> offset) << oob_offset
        plan.validate_stock_record(bytes(data) + oob.to_bytes(64, "little"))

    def test_factory_bad_changes_stop_without_relocation(self):
        blank = b"\xff" * plan.RAW_BLOCK
        changed = b"\x00" + blank[1:]
        with self.assertRaisesRegex(ValueError, "factory-bad block 1"):
            plan.differences([blank, blank], [changed, changed], {1})
        report = plan.differences([blank, changed], [changed, changed], {1})
        self.assertEqual([c["block"] for c in report["changed_blocks"]], [0])

    def test_fcb_marker_difference_is_visible(self):
        blank = b"\xff" * plan.RAW_BLOCK
        fcb = blank[:2048] + b"\x00" + blank[2049:]
        report = plan.differences([blank], [fcb], set())
        self.assertEqual(report["target_extra_marker_blocks"], [0])

    def test_truncated_or_mismatched_streams_rejected(self):
        blank = b"\xff" * plan.RAW_BLOCK
        for before, after in (([blank], []), ([blank[:-1]], [blank])):
            with self.assertRaises(ValueError):
                plan.differences(before, after, set())

    def test_physical_inventory_requires_exact_geometry(self):
        lines = [f"mtd {i} size {size} bad" for i, (_, size) in enumerate(plan.PARTITIONS)]
        lines[0] += " 7"
        lines[4] += " 204 205"
        text = "\n".join(lines + ["INVENTORY-READONLY-OK"])
        self.assertEqual(plan.inventory(text), {7, 316, 317})
        for wrong in (text.replace("4194304", "4194305"),
                      text.replace("bad 7", "bad 7 7"),
                      text.replace("bad 7", "bad 32"), text.rsplit("\n", 1)[0]):
            with self.assertRaises(ValueError):
                plan.inventory(wrong)


if __name__ == "__main__":
    unittest.main()
