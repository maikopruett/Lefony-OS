import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[1]
LOADER = REPO / "native/prime_g2/nand_boot_capsule.S"


class PrimeG2NandCapsuleTest(unittest.TestCase):
    def test_copied_payload_is_cache_coherent_before_entry(self) -> None:
        source = LOADER.read_text()
        copy_complete = source.index("copy_complete:")
        native_entry = source.index("ldr pc, =NATIVE_ENTRY", copy_complete)
        handoff = source[copy_complete:native_entry]

        expected = [
            "mcr p15, 0, r0, c7, c14, 1",  # DCCIMVAC
            "dsb sy",
            "mcr p15, 0, r0, c7, c5, 0",   # ICIALLU
            "mcr p15, 0, r0, c7, c5, 6",   # BPIALL
            "isb sy",
        ]
        cursor = 0
        for operation in expected:
            cursor = handoff.index(operation, cursor) + len(operation)

        self.assertIn("cmp r0, r1", handoff)
        self.assertIn("blo clean_payload_cache", handoff)


if __name__ == "__main__":
    unittest.main()
