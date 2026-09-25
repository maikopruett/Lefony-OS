from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_recovery_is_not_a_launcher_app():
    platform = (
        ROOT / "ports/lefony-prime-g2/build/platform.prime_g2.mak"
    ).read_text()
    apps = next(line for line in platform.splitlines() if line.startswith("EPSILON_APPS ="))
    assert "recovery" not in apps.split()
    assert "regression settings" in apps


def test_all_app_suite_uses_settings_without_recovery_slot():
    suite = (ROOT / "vm/native-app-test.py").read_text()
    assert '("Settings", 11)' in suite
    assert "Recovery is launcher slot 11" not in suite
