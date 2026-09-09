import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_tree', ROOT / 'scripts/check_public_tree.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_rejects_private_key_disguised_as_source(tmp_path):
    path = tmp_path / 'credentials.py'
    path.write_text('-----BEGIN ' + 'PRIVATE KEY-----\nsecret\n')
    assert any('private signing material' in p for p in guard.check_paths(tmp_path, [path.name]))


def test_rejects_forced_generated_and_binary_imports(tmp_path):
    (tmp_path / 'build').mkdir()
    (tmp_path / 'build/output.c').write_text('generated')
    (tmp_path / 'capture.raw').write_bytes(b'\0' * 12)
    problems = guard.check_paths(tmp_path, ['build/output.c', 'capture.raw'])
    assert any('generated/private directory' in p for p in problems)
    assert any('artifact extension' in p for p in problems)


def test_public_key_exception_is_content_pinned(tmp_path):
    for name in guard.PUBLIC_KEYS:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
        assert not guard.check_paths(tmp_path, [name])
        path.write_bytes(b'replacement key')
        assert guard.check_paths(tmp_path, [name])


def test_port_build_definitions_and_register_facts_are_source(tmp_path):
    names = ['ports/lefony-prime-g2/build/platform.mak', 'hardware/registers.txt']
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('0x021c8000')
    assert not guard.check_paths(tmp_path, names)


def test_rejects_symlink_to_private_file(tmp_path):
    (tmp_path / 'alias').symlink_to(tmp_path / 'nonexistent-private-file')
    assert any('symlink' in p for p in guard.check_paths(tmp_path, ['alias']))
