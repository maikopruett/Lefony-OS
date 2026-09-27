# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from collections import deque
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prime_hp_raw_restore import Change, GEOMETRY, RAW_BLOCK, PrimeSDP, restore_blocks, restore_image, sha

OLD = bytes([0x5a]) * RAW_BLOCK
NEW = bytes([0xa5]) * RAW_BLOCK


class FakeDevice:
    def __init__(self):
        self.blocks = {0: OLD, 1: OLD}
        self.bad = {7}
        self.events = []
        self.corrupt_upload = self.corrupt_readback = self.fail_program = False
        self.fail_erase = False

    def inventory(self):
        return GEOMETRY, self.bad

    def read_block(self, block):
        return self.blocks[block]

    def stage(self, data):
        self.staged = bytes(RAW_BLOCK) if self.corrupt_upload else data

    def read_stage(self):
        return self.staged

    def erase(self, block, *, stock_metadata=False):
        self.events.append(("erase", block, stock_metadata))
        if not self.fail_erase:
            self.blocks[block] = bytes([255]) * RAW_BLOCK

    def program(self, block):
        self.events.append(("program", block))
        if self.fail_program:
            raise TimeoutError("ambiguous USB write")
        self.blocks[block] = OLD if self.corrupt_readback else self.staged


class RawRestoreTests(unittest.TestCase):
    def setUp(self):
        self.d = FakeDevice()
        self.changes = [Change(0, OLD, NEW), Change(1, OLD, NEW)]
        self.journal = []

    def run_restore(self, changes=None, approved=True):
        restore_blocks(self.d, self.changes if changes is None else changes,
                       {7}, self.journal.append, approved=approved)

    def test_explicit_approval_and_good_block_success(self):
        with self.assertRaisesRegex(ValueError, "approval"):
            self.run_restore(approved=False)
        self.assertEqual(self.d.events, [])
        self.run_restore()
        self.assertEqual(self.d.blocks, {0: NEW, 1: NEW})
        self.assertEqual([x["state"] for x in self.journal],
                         ["erase-pending", "program-pending", "verified"] * 2)

    def test_all_before_images_checked_before_any_erase(self):
        self.d.blocks[1] = NEW
        with self.assertRaisesRegex(ValueError, "stale before-image"):
            self.run_restore()
        self.assertEqual(self.d.events, [])

    def test_new_bad_block_and_factory_destination_rejected(self):
        self.d.bad.add(100)
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            self.run_restore()
        self.d.bad.remove(100)
        with self.assertRaisesRegex(ValueError, "factory-bad"):
            self.run_restore([Change(7, OLD, NEW)])
        self.assertEqual(self.d.events, [])

    def test_bad_upload_stops_before_erase(self):
        self.d.corrupt_upload = True
        with self.assertRaisesRegex(ValueError, "upload verification"):
            self.run_restore()
        self.assertEqual(self.d.events, [])

    def test_silently_failed_erase_stops_before_program(self):
        self.d.fail_erase = True
        with self.assertRaisesRegex(ValueError, "erase verification failed"):
            self.run_restore()
        self.assertEqual(self.d.events, [("erase", 0, False)])
        self.assertEqual(self.journal[-1]["state"], "erase-pending")

    def test_ambiguous_write_is_never_retried(self):
        self.d.fail_program = True
        with self.assertRaises(TimeoutError):
            self.run_restore()
        self.assertEqual(self.d.events, [("erase", 0, False), ("program", 0)])
        self.assertEqual(self.journal[-1]["state"], "program-pending")

    def test_bad_readback_stops_before_next_block(self):
        self.d.corrupt_readback = True
        with self.assertRaisesRegex(ValueError, "readback mismatch"):
            self.run_restore()
        self.assertEqual(self.d.events, [("erase", 0, False), ("program", 0)])

    def test_metadata_exception_requires_exact_bytes_and_fixed_block(self):
        self.d.bad.add(0)
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            self.run_restore()
        with self.assertRaisesRegex(ValueError, "exact matching bytes"):
            self.run_restore([Change(0, OLD, NEW, "0" * 64)])
        self.run_restore([Change(0, OLD, NEW, sha(OLD))])
        self.assertEqual(self.d.events[0], ("erase", 0, True))
        with self.assertRaisesRegex(ValueError, "exact matching bytes"):
            self.run_restore([Change(8, OLD, NEW, sha(OLD))])

    def test_duplicate_and_short_blocks_rejected(self):
        for changes in ([self.changes[0]] * 2, [Change(0, OLD[:-1], NEW)],
                        [Change(4096, OLD, NEW)]):
            with self.assertRaises(ValueError):
                self.run_restore(changes)
        self.assertEqual(self.d.events, [])


class FullRestoreTests(unittest.TestCase):
    def setUp(self):
        self.d = FakeDevice()
        self.d.blocks = {n: OLD for n in range(4096)}
        self.d.hash_blocks = lambda first, count: [
            sha(self.d.blocks[b]) for b in range(first, first + count)]
        self.target = [sha(OLD)] * 4096
        self.target[100] = sha(NEW)
        self.journal, self.captures = [], {}

    def run_image(self, **kwargs):
        return restore_image(
            self.d, self.target, lambda b: NEW if b == 100 else OLD, {7},
            self.journal.append, lambda b, data: self.captures.update({b: data}),
            approved=True, **kwargs)

    def test_full_image_and_before_capture(self):
        self.run_image(expected_before=[sha(OLD)] * 4096)
        self.assertEqual(self.captures, {100: OLD})
        self.assertEqual(self.journal[-1]['state'], 'complete-device-verified')

    def test_stale_block_outside_write_plan_stops_all_erases(self):
        self.d.blocks[200] = NEW
        with self.assertRaisesRegex(ValueError, 'before-image changed'):
            self.run_image(expected_before=[sha(OLD)] * 4096)
        self.assertEqual(self.d.events, [])

    def test_source_disappears_before_any_erase(self):
        def missing(block):
            raise FileNotFoundError("validated source was removed")
        with self.assertRaises(FileNotFoundError):
            restore_image(self.d, self.target, missing, {7}, self.journal.append,
                          lambda b, data: self.captures.update({b: data}),
                          expected_before=[sha(OLD)] * 4096, approved=True)
        self.assertEqual(self.d.events, [])
        self.assertEqual(self.captures, {})

    def test_rollback_discovers_hp_changes_outside_original_plan(self):
        self.d.blocks[200] = NEW
        self.run_image()
        self.assertEqual(self.captures, {100: OLD, 200: NEW})
        self.assertEqual(self.d.blocks[200], OLD)

    def test_final_scan_detects_unrelated_corruption(self):
        original = self.d.program
        def corrupt(block):
            original(block)
            self.d.blocks[300] = NEW
        self.d.program = corrupt
        with self.assertRaisesRegex(ValueError, 'complete-device readback mismatch'):
            self.run_image()
        self.assertNotEqual(self.journal[-1]['state'], 'complete-device-verified')

    def test_modified_stock_metadata_rejects_exception(self):
        with self.assertRaisesRegex(ValueError, 'metadata bytes changed'):
            self.run_image(stock_metadata={0: sha(NEW)})
        self.assertEqual(self.d.events, [])


class TransportTests(unittest.TestCase):
    def test_complete_raw_read_survives_small_hid_queue_and_host_delay(self):
        data = bytes(range(256)) * (RAW_BLOCK // 256)
        queue = deque(maxlen=32)
        class HID:
            def read(self, size, timeout):
                return queue.popleft() if queue else []
        class Transport(PrimeSDP):
            def __init__(self): self.device = HID()
            def _command(self, command, address, data=b'', read_count=0):
                self.assert_command(command)
                queue.append(b'\x03' + struct.pack('<I', 0x56787856))
                # Entire response arrives before host execution resumes, just
                # as when the IOHID callback runs while Python is descheduled.
                payload = original[address-base:address-base+read_count]
                for offset in range(0, len(payload), 64):
                    queue.append(b'\x04' + payload[offset:offset+64].ljust(64,b'\0'))
                assert self._ack(3, 4) == 0x56787856
            def assert_command(self, command): assert command == 0x0101
        original, base = data, 0x84200000
        self.assertEqual(Transport().read(base, len(data)), data)

    def test_empty_ack_waits_without_reissuing_command(self):
        replies = iter([[], b'\x03' + struct.pack('<I', 0x56787856)])
        d = PrimeSDP.__new__(PrimeSDP)
        class HID:
            def read(self, size, timeout): return next(replies)
        d.device = HID()
        self.assertEqual(d._ack(3, 4), 0x56787856)
        with patch('prime_hp_raw_restore.time.monotonic', side_effect=[0,11]):
            with self.assertRaisesRegex(TimeoutError, 'not retried'):
                d._ack(3, 4)


if __name__ == "__main__":
    unittest.main()
