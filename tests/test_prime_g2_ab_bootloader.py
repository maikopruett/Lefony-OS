import struct
import unittest
import zlib
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class PrimeG2ABBootloaderContractTests(unittest.TestCase):
    def test_binary_metadata_abi_is_144_bytes_with_standard_crc32(self):
        slot = struct.Struct("<I4I32s")
        metadata = struct.Struct("<8I52s52s2I")
        self.assertEqual(slot.size, 52)
        self.assertEqual(metadata.size, 144)
        value = bytearray(metadata.pack(
            0x314D4241, 1, metadata.size, 7, 0, 1, 0, 3,
            bytes(slot.size), bytes(slot.size), 0x434F4D4D, 0,
        ))
        expected = zlib.crc32(value) & 0xFFFFFFFF
        value[-4:] = struct.pack("<I", expected)
        self.assertNotEqual(expected, 0)

        firmware = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/nand_update.cpp").read_text()
        bootloader = (REPO / "vm/u-boot/lefony_ab.c").read_text()
        self.assertIn("0xedb88320u", firmware)
        self.assertIn("crc32(0,", bootloader)
        self.assertIn("sizeof(*metadata)", bootloader)

    def test_only_booted_runtime_can_confirm_a_pending_slot(self):
        usb = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/usb_diagnostics.cpp").read_text()
        boot_progress = (REPO / "ports/lefony-prime-g2/patches/physical-boot-progress.patch").read_text()
        nand = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/nand_update.cpp").read_text()
        self.assertNotIn("case 0x4A", usb)
        self.assertIn("PrimeG2UpdateBootReady();", boot_progress)
        self.assertIn("prime_g2_update_boot_ready", nand)

    def test_emulator_boot_mode_uses_real_reboots_and_custom_nand_loader(self):
        builder = (REPO / "vm/build-u-boot.sh").read_text()
        runner = (REPO / "vm/run-native-vm.sh").read_text()
        bootloader = (REPO / "vm/u-boot/lefony_ab.c").read_text()
        self.assertIn("UBOOT_BOOT_FORMAT must be elf, capsule, or ab", builder)
        self.assertIn("lefony_ab boot", builder)
        self.assertIn('if [ "$BOOT_MODE" != ab ]', runner)
        for marker in (
            "pending slot %c attempt %u/%u",
            "rolling back pending slot",
            "sha256_csum_wd",
            "commit_metadata",
        ):
            self.assertIn(marker, bootloader)

    def test_physical_commit_remains_locked_until_layout_is_provisioned(self):
        nand = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/nand_update.cpp").read_text()
        layout = (REPO / "native/prime_g2/nand_layout.json").read_text()
        self.assertIn("#if PRIME_G2_EMULATOR", nand)
        self.assertIn("Error::LayoutNotProvisioned", nand)
        self.assertIn('"physical_ab_migration_allowed": false', layout)

    def test_physical_bootloader_and_runtime_share_full_handoff(self):
        physical = (REPO / "native/prime_g2/lefony_ab_physical.c").read_text()
        patch = (REPO / "native/prime_g2/u-boot-lefony-ab.patch").read_text()
        runtime = (REPO / "ports/lefony-prime-g2/ion/src/prime_g2/nand_update.cpp").read_text()
        for marker in ("active_slot", "pending_slot", "boot_limit", "generation",
                       "schema", "version[4]"):
            self.assertIn(marker, physical)
        self.assertIn("BootHandoffSchema=2", runtime)
        self.assertIn("ConfirmMagicAddress", runtime)
        self.assertIn("nand read ${fdt_addr} 0xc00000 0x100000", patch)
        self.assertIn("bootz ${loadaddr} - ${fdt_addr}", patch)


if __name__ == "__main__":
    unittest.main()
