#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Repackage, verify and exercise the source SDK outside the OS checkout."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = ROOT / 'build/sdk-source-kit-qualification'
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'lefony-native-sdk-source.tar.gz'
    qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    firmware = ROOT / 'dist/lefony-os-prime-g2-vm-native.elf'
    subprocess.run([sys.executable, str(ROOT / 'scripts/package_native_sdk.py'), '--output', str(archive)], check=True)
    with tempfile.TemporaryDirectory(prefix='SDK archive é ') as folder:
        temporary = Path(folder)
        repeat = temporary / 'repeat.tar.gz'
        subprocess.run([sys.executable, str(ROOT / 'scripts/package_native_sdk.py'), '--output', str(repeat)], check=True)
        assert sha(archive) == sha(repeat), 'source archive is not reproducible'
        with tarfile.open(archive) as source:
            for item in source.getmembers():
                target = temporary / item.name
                assert item.isfile() and not item.name.startswith('/') and '..' not in Path(item.name).parts
                assert item.name.startswith('lefony-native-sdk/') and item.size <= 8 * 1024 * 1024
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.extractfile(item).read())
                target.chmod(item.mode)
        kit = temporary / 'lefony-native-sdk'
        checksums = {}
        for line in (kit / 'SHA256SUMS').read_text().splitlines():
            digest, path = line.split('  ', 1)
            assert sha(kit / path) == digest, path
            checksums[path] = digest
        assert set(checksums) == {p.relative_to(kit).as_posix() for p in kit.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'}
        assert not any(part in ('.lefony', 'build', '__pycache__') for name in checksums for part in Path(name).parts)
        cli = [sys.executable, str(kit / 'sdk/tools/cli.py')]
        project = temporary / 'External project é'
        subprocess.run([*cli, 'new', str(project), '--template', 'pocket-lab'], check=True)
        subprocess.run([*cli, 'build'], cwd=project, check=True)
        subprocess.run(['cmake', '-S', str(project), '-B', str(project / 'build/cmake'),
                        f'-DLEFONY_SDK_ROOT={kit / "sdk"}', '-DCMAKE_BUILD_TYPE=Debug'], check=True)
        subprocess.run(['cmake', '--build', str(project / 'build/cmake')], check=True)
        assert json.loads((project / 'build/build.json').read_text())['profile'] == 'debug'
        subprocess.run([*cli, 'test', '--workspace', 'source-kit', '--qemu', str(qemu), '--firmware', str(firmware)],
                       cwd=project, check=True, timeout=180)
        report = json.loads((project / 'build/run.json').read_text())
        assert report['status'] == 'passed'
        graph = temporary / 'External graph é'
        subprocess.run([*cli, 'new', str(graph), '--template', 'graph-explorer'], check=True)
        assert not (graph / '.lefony').exists(), 'new template copied an existing private workspace'
        subprocess.run([*cli, 'test', '--workspace', 'source-kit', '--qemu', str(qemu), '--firmware', str(firmware)],
                       cwd=graph, check=True, timeout=180)
        graph_report = json.loads((graph / 'build/run.json').read_text())
        assert graph_report['status'] == 'passed'
        cards = temporary / 'External resource cards é'
        subprocess.run([*cli, 'new', str(cards), '--template', 'reference-cards'], check=True)
        subprocess.run([*cli, 'test', '--workspace', 'source-kit', '--qemu', str(qemu), '--firmware', str(firmware)],
                       cwd=cards, check=True, timeout=180)
        subprocess.run([*cli, 'source', '--format', '1'], cwd=cards, check=True)
        cards_report = json.loads((cards / 'build/run.json').read_text())
        assert cards_report['status'] == 'passed'
        assert json.loads((cards / 'build/app.lfsrc').read_text())['files']['assets/book.png']['encoding'] == 'base64'
        manifest = {'schema': 1, 'validation': 'developer-local', 'physical': 'not_tested',
                    'status': 'passed', 'archive_sha256': sha(archive),
                    'files': len(checksums), 'compiler': '16.2.0',
                    'firmware_sha256': sha(firmware), 'qemu_sha256': sha(qemu), 'test': report, 'graph': graph_report, 'resources': cards_report}
        (output / 'report.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print('PASS: reproducible source kit, complete checksums, external CLI/CMake build, installed Pocket Lab, Graph Explorer and Reference Cards replays')


if __name__ == '__main__':
    main()
