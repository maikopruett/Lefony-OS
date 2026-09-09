import importlib.util
import random
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "prime_g2_nand_update.py"
SPEC = importlib.util.spec_from_file_location("prime_g2_nand_update", SCRIPT)
nand = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(nand)


def capsule(payload_bytes=4096):
    data = bytearray(b"\x00" * payload_bytes)
    data[0x24:0x28] = (0x016F2818).to_bytes(4, "little")
    data[0x2C:0x30] = payload_bytes.to_bytes(4, "little")
    return bytes(data)


class PrimeG2NandUpdateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.image = root / "nand.bin"
        self.state = root / "state.json"
        self.payload = root / "upsilon.zImage"
        self.payload.write_bytes(capsule())
        self.manager = nand.Manager(self.image, self.state)
        self.manager.create()
        self.manager.seed_factory(self.payload)

    def tearDown(self):
        self.temp.cleanup()

    def test_install_boot_confirm_and_next_inactive_slot(self):
        state = self.manager.install(self.payload)
        self.assertEqual(state["pending"], "b")
        self.assertEqual(self.manager.select_boot(), "b")
        self.assertEqual(self.manager.mark_good()["active"], "b")
        self.assertEqual(self.manager.install(self.payload)["pending"], "a")

    def test_factory_seed_and_uboot_environment_are_complete(self):
        root = Path(self.temp.name)
        manager = nand.Manager(root / "fresh.bin", root / "fresh.json")
        manager.create()
        state = manager.seed_factory(self.payload)
        self.assertEqual(state["last_result"], "factory-seeded")
        environment = Path(self.temp.name) / "upsilon.env"
        manager.export_uboot_environment(environment)
        text = environment.read_text()
        self.assertIn("bootcmd=run upsilon_choose", text)
        self.assertIn("both native slots invalid", text)
        self.assertIn("upsilon_a_bytes=4096", text)
        self.assertIn(state["slots"]["a"]["sha256"], text)
        self.assertIn("saveenv", text)
        self.assertIn("mw.l 0x87fff000 0x3142464c", text)

    def test_factory_seed_is_one_time_only(self):
        with self.assertRaises(nand.UpdateError):
            self.manager.seed_factory(self.payload)

    def test_unconfirmed_slot_rolls_back_after_boot_limit(self):
        self.manager.install(self.payload)
        self.assertEqual([self.manager.select_boot() for _ in range(3)],
                         ["b", "b", "b"])
        self.assertEqual(self.manager.select_boot(), "a")
        self.assertIn("rollback", self.manager.state()["last_result"])

    def test_power_loss_before_metadata_never_selects_new_slot(self):
        for phase in ("erase", "write", "verify", "state"):
            with self.subTest(phase=phase):
                with self.assertRaises(nand.UpdateError):
                    self.manager.install(self.payload, phase)
                self.assertEqual(self.manager.select_boot(), "a")

    def test_bad_blocks_reduce_capacity_and_are_skipped(self):
        region = self.manager.regions["slot_b"]
        erase = self.manager.geometry["erase_block_bytes"]
        first = region.offset // erase
        manager = nand.Manager(self.image, self.state, {first, first + 1})
        state = manager.install(self.payload)
        self.assertEqual(state["slots"]["b"]["good_blocks"],
                         region.size // erase - 2)

    def test_invalid_capsule_is_rejected_without_metadata_change(self):
        self.payload.write_bytes(b"not a capsule")
        with self.assertRaises(nand.UpdateError):
            self.manager.install(self.payload)
        self.assertIsNone(self.manager.state()["pending"])

    def test_deterministic_capsule_parser_fuzz_is_bounded_and_atomic(self):
        """Malformed packages must never reach NAND or update metadata.

        This deliberately exercises all structural fields with a reproducible
        mutation corpus.  The unchanged state *and* image digest prove that a
        rejected package has no partial erase/write side effect.
        """
        rng = random.Random(0x555044415445)
        original = capsule()
        state_before = self.state.read_bytes()
        image_before = self.image.stat()
        cases = []
        for _ in range(256):
            candidate = bytearray(original)
            mutation = rng.randrange(4)
            if mutation == 0:
                candidate = candidate[:rng.randrange(0, 0x30)]
            elif mutation == 1:
                offset = rng.randrange(0x24, 0x28)
                candidate[offset] ^= rng.randrange(1, 256)
            elif mutation == 2:
                declared = rng.randrange(0, len(candidate) + 8192)
                if declared == len(candidate):
                    declared ^= 1
                candidate[0x2C:0x30] = declared.to_bytes(4, "little")
            else:
                candidate.extend(rng.randbytes(rng.randrange(1, 65)))
            cases.append(bytes(candidate))

        for index, candidate in enumerate(cases):
            with self.subTest(index=index):
                self.payload.write_bytes(candidate)
                with self.assertRaises(nand.UpdateError):
                    self.manager.install(self.payload)
                self.assertEqual(self.state.read_bytes(), state_before)
                image_after = self.image.stat()
                self.assertEqual(image_after.st_size, image_before.st_size)
                self.assertEqual(image_after.st_mtime_ns, image_before.st_mtime_ns)

    def _corrupt_slot(self, slot):
        region = self.manager.regions[f"slot_{slot}"]
        with self.image.open("r+b") as image:
            image.seek(region.offset + 0x40)
            byte = image.read(1)
            image.seek(region.offset + 0x40)
            image.write(bytes((byte[0] ^ 1,)))

    def test_corrupt_pending_rolls_back_without_spending_boot_attempt(self):
        self.manager.install(self.payload)
        self._corrupt_slot("b")
        self.assertEqual(self.manager.select_boot(), "a")
        state = self.manager.state()
        self.assertIsNone(state["pending"])
        self.assertEqual(state["attempts"], 0)
        self.assertEqual(state["last_result"], "rollback-corrupt-b")

    def test_invalid_active_recovers_other_verified_slot(self):
        self.manager.install(self.payload)
        self.manager.mark_good()
        self._corrupt_slot("b")
        self.assertEqual(self.manager.select_boot(), "a")
        self.assertEqual(self.manager.state()["active"], "a")

    def test_both_invalid_slots_select_read_only_rescue(self):
        self.manager.install(self.payload)
        self.manager.mark_good()
        self._corrupt_slot("a")
        self._corrupt_slot("b")
        self.assertEqual(self.manager.select_boot(), "rescue")
        self.assertEqual(self.manager.state()["last_result"],
                         "rescue-both-invalid")


if __name__ == "__main__":
    unittest.main()
