import importlib.util
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "lefony_build_history", ROOT / "scripts/lefony_build_history.py"
)
history = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = history
SPEC.loader.exec_module(history)


def test_record_archives_artifact_and_notes():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        artifact = root / "lefony.zImage"
        artifact.write_bytes(b"verified image")
        entry = history.record_build(
            artifact,
            "recovery-capsule",
            history_dir=root / "history",
            source=ROOT,
            notes="Physical LCD, keyboard, and recovery app verified.",
            status="known-good",
        )
        entries = history.load_history(root / "history")
        assert entries == [entry]
        archived = root / "history" / entry.artifact
        assert archived.read_bytes() == artifact.read_bytes()
        assert entry.status == "known-good"
        assert "Physical LCD" in entry.notes


def test_multiple_builds_are_retained_newest_first():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        artifact = root / "lefony.bin"
        artifact.write_bytes(b"first")
        first = history.record_build(
            artifact, "native", history_dir=root / "history", source=ROOT
        )
        artifact.write_bytes(b"second")
        second = history.record_build(
            artifact, "native", history_dir=root / "history", source=ROOT
        )
        entries = history.load_history(root / "history")
        assert [entry.sha256 for entry in entries] == [second.sha256, first.sha256]
        document = json.loads((root / "history" / history.INDEX_NAME).read_text())
        assert document["schema_version"] == 1
        assert len(document["builds"]) == 2


def test_build_notes_and_qualification_status_can_be_updated():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        artifact = root / "lefony.bin"
        artifact.write_bytes(b"candidate")
        entry = history.record_build(
            artifact, "native", history_dir=root / "history", source=ROOT
        )
        updated = history.annotate_build(
            root / "history",
            entry.build_id,
            notes="Physical boot and keyboard verified.",
            status="known-good",
        )
        assert updated.status == "known-good"
        assert history.load_history(root / "history")[0].notes.startswith("Physical boot")


def test_installer_has_history_view_and_build_scripts_record_outputs():
    installer = (ROOT / "scripts/lefony_installer.py").read_text()
    native = (ROOT / "scripts/build_lefony_prime_g2.sh").read_text()
    capsule = (ROOT / "scripts/build_prime_g2_nand_capsule.sh").read_text()
    signed = (ROOT / "scripts/build_prime_g2_signed_update.sh").read_text()
    assert "show_history" in installer
    assert "[H] History" in installer
    assert '"history"' in installer
    assert "show_uboot_history" in installer
    assert "[K] Verify U-Boot" in installer
    assert '"uboot_history"' in installer
    for source in (native, capsule, signed):
        assert "lefony_build_history.py" in source
