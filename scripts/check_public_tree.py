#!/usr/bin/env python3
"""Check tracked and non-ignored source for accidental private/generated imports.

This is a repository boundary check, not a general secret scanner or license audit.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEYS = {
    'tests/fixtures/prime_g2_emulator_update_private.pem': '8103c3448b7257026cc0f9639524f5c1b4c9cdb60670f01b47a56aa76cc5f54b',
    'tests/fixtures/prime_g2_emulator_update_public.pem': '90f5157ff9743a69ef05250c207ecbadaeb072d0513848739eb4a3e1245a0c6c',
}
PRIVATE_SUFFIXES = {'.mtd', '.readback', '.bin', '.elf', '.imx', '.img', '.raw',
                    '.qcow2', '.dtb', '.dts', '.zimage', '.lfu', '.lfapp', '.lfsrc', '.pdf', '.zip',
                    '.tar', '.gz', '.bz2', '.xz', '.key', '.pem', '.ppm', '.pyc'}
OUTPUT_ROOTS = {'build', 'dist', '.venv', '.private', '.cache', 'tmp', '.git'}
PRIVATE_KEY = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----')
LOCAL_HOME = re.compile(rb'/(?:Users|home)/[A-Za-z0-9_.-]+/')


def check_paths(root: Path, paths: list[str]) -> list[str]:
    problems = []
    for name in sorted(set(paths)):
        path = root / name
        parts = Path(name).parts
        if not parts or Path(name).is_absolute() or '..' in parts:
            problems.append(f'{name}: path escapes repository')
            continue
        if not path.exists() and not path.is_symlink():
            continue  # Worktree deletion awaiting staging.
        if path.is_symlink():
            problems.append(f'{name}: symlinks must be reviewed; distribute source files')
            continue
        if not path.is_file():
            problems.append(f'{name}: nested repository or non-file source entry')
            continue
        if parts[0] in OUTPUT_ROOTS or '__pycache__' in parts or '.pytest_cache' in parts:
            problems.append(f'{name}: generated/private directory')
        if path.stat().st_size > 1024 * 1024:
            problems.append(f'{name}: file exceeds 1 MiB; review public-source suitability')
            continue
        data = path.read_bytes()
        if name in PUBLIC_KEYS:
            if hashlib.sha256(data).hexdigest() != PUBLIC_KEYS[name]:
                problems.append(f'{name}: public emulator key fixture changed')
            continue
        if path.suffix.lower() in PRIVATE_SUFFIXES or path.name == '.env' or path.name.startswith('.env.'):
            problems.append(f'{name}: private/generated artifact extension')
        if PRIVATE_KEY.search(data):
            problems.append(f'{name}: private signing material')
        if LOCAL_HOME.search(data):
            problems.append(f'{name}: personal absolute home path')
        if b'\x00' in data and path.suffix.lower() != '.png':
            problems.append(f'{name}: unexpected binary content')
    return problems


def main() -> int:
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                            cwd=ROOT, check=True, stdout=subprocess.PIPE)
    paths = result.stdout.decode().rstrip('\0').split('\0') if result.stdout else []
    problems = check_paths(ROOT, paths)
    if problems:
        print('\n'.join(problems), file=sys.stderr)
        return 1
    print(f'Public source boundary passed ({len(set(paths))} files).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
