# SPDX-License-Identifier: GPL-3.0-or-later
"""Production large files on synthetic NAND; optional pinned WAD qualification."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / 'ports/lefony-prime-g2/ion/src/prime_g2'


def compile_fixture(directory, *, source=None, extra_sources=()):
    backend = (ROOT / 'tests/native/app_storage.cpp').read_text()
    (directory / 'app_storage_fixture.h').write_text(backend[backend.index('struct PowerCut'):backend.index('static void finish')])
    raw = (ROOT / 'tests/native/app_documents.cpp').read_text()
    (directory / 'app_raw_fixture.h').write_text(raw[raw.index('struct Raw {'):raw.index('\nint main()')])
    flags = ['-DLFS_NO_MALLOC', '-DLFS_NO_DEBUG', '-DLFS_NO_WARN', '-DLFS_NO_ERROR', '-DLFS_NO_ASSERT',
             '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fexceptions', '-O1', '-g',
             '-I', str(PORT), '-I', str(directory), '-I', str(ROOT / 'sdk/include')]
    objects = []
    for name in ('lfs', 'lfs_util'):
        obj = directory / (name + '.o')
        subprocess.run([shutil.which('cc'), '-std=c99', *flags, '-DLFS_DEFINES=littlefs_compat/defines.h',
                        '-c', str(PORT / f'littlefs/{name}.c'), '-o', str(obj)], check=True, timeout=60)
        objects.append(str(obj))
    binary = directory / 'app-files'
    sources = [source or ROOT / 'tests/native/app_files.cpp', *[PORT / name for name in
               ('app_storage.cpp', 'app_document_store.cpp', 'app_root_record.cpp', 'app_file_store.cpp', 'legacy_app_storage.cpp', *extra_sources)]]
    subprocess.run([shutil.which('c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags,
                    *map(str, sources), *objects, '-o', str(binary)], check=True, timeout=60)
    return binary


def run(binary, wad=None):
    result = subprocess.run([str(binary), *([str(wad)] if wad else [])], capture_output=True, text=True, timeout=600)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    if wad:
        with wad.open('rb') as source:
            assert report['read_sha256'] == hashlib.file_digest(source, 'sha256').hexdigest()
        expected = hashlib.sha256()
        start, end, offset = 128 * 1024 - 128 + 7, 128 * 1024 - 128 + 44, 0
        with wad.open('rb') as source:
            while chunk := source.read(2048):
                content = bytearray(chunk)
                low, high = max(offset, start), min(offset + len(content), end)
                if low < high:
                    content[low - offset:high - offset] = bytes([0xa7]) * (high - low)
                expected.update(content)
                offset += len(content)
        assert report['patched_sha256'] == expected.hexdigest()
        assert report['input_bytes'] == wad.stat().st_size
    else:
        assert report['interruption_cases'] > 100
        assert report['growing_interruption_cases'] > 100
        expected = bytearray()
        for offset in range(report['growing_input_bytes']):
            value = ((offset * 131 + (offset >> 8)) ^ 0x5d) & 255
            if value & 1:
                expected.extend((value, value ^ 0xa5))
        expected = b'LFW1' + len(expected).to_bytes(4, 'little') + expected
        assert len(expected) == report['growing_output_bytes']
        assert hashlib.sha256(expected).hexdigest() == report['growing_output_sha256']
    output = ROOT / 'build/sdk-large-files'
    output.mkdir(parents=True, exist_ok=True)
    (output / ('wad-report.json' if wad else 'report.json')).write_text(json.dumps(report, indent=2) + '\n')
    return report


def test_production_large_files_and_recovery(tmp_path):
    run(compile_fixture(tmp_path))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wad', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='lefony-large-files-') as temporary:
        print(json.dumps(run(compile_fixture(Path(temporary)), args.wad), indent=2))
