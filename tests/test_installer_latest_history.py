import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import test_lefony_installer as fixtures

installer = fixtures.installer
history = installer.build_history


class LatestHistoryTests(unittest.TestCase):
    def record(self, root, marker, status="unverified", kind="recovery-capsule"):
        image = root / f"{marker}.zImage"
        fixtures.make_capsule(image)
        data = bytearray(image.read_bytes())
        data[-1] = marker
        image.write_bytes(data)
        return history.record_build(image, kind, history_dir=root / "os-history", status=status)

    def test_newest_candidate_not_old_known_good_is_default(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.record(root, 1, "known-good")
            latest = self.record(root, 2)
            self.assertEqual(installer.preferred_recovery_image(root / "os-history"),
                             root / "os-history" / latest.artifact)
            self.record(root, 3, kind="native")
            self.assertEqual(installer.preferred_recovery_image(root / "os-history"),
                             root / "os-history" / latest.artifact)

    def test_failed_build_is_retired_and_not_selectable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            good = self.record(root, 1, "known-good")
            failed = self.record(root, 2)
            history.annotate_build(root / "os-history", failed.build_id, status="failed")
            self.assertEqual(history.load_history(root / "os-history"), [good])
            self.assertFalse((root / "os-history" / failed.artifact).exists())
            self.assertTrue((root / "os-history-retired" / failed.artifact).is_file())
            raw = json.loads((root / "os-history/index.json").read_text())
            self.assertEqual(len(raw["builds"]), 1)

    def test_hash_mismatch_is_not_auto_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            good = self.record(root, 1)
            corrupted = self.record(root, 2)
            (root / "os-history" / corrupted.artifact).write_bytes(b"corrupt")
            self.assertEqual(installer.preferred_recovery_image(root / "os-history"),
                             root / "os-history" / good.artifact)

    def test_auto_refresh_follows_new_build_but_not_during_flash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            first = self.record(root, 1)
            args = fixtures.OperationGuardTests().make_args(root)
            args.image = None
            with mock.patch.object(installer.Detector, "probe"):
                app = installer.LefonyOSPrimeInstaller(args)
                self.assertEqual(app.image_path, root / "os-history" / first.artifact)
                latest = self.record(root, 2)
                with mock.patch.object(app, "job") as job:
                    job.running = True
                    job.kind = "install"
                    app.refresh(force=True)
                self.assertEqual(app.image_path, root / "os-history" / first.artifact)
                app.refresh(force=True)
                self.assertEqual(app.image_path, root / "os-history" / latest.artifact)
