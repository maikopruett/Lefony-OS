#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Extract an exact math subset from the existing pinned Upsilon git objects.

Never runs uploaded code or changes an upstream revision. Existing differing
vendor files are rejected; this is an idempotent extraction, not an update hook.
"""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f36520e0ed5faabbfea8a2b9f4e1309edc077927'
BASE = 'liba/src/external/openbsd/'
SOURCES = '''e_acos e_asin e_atan2 e_exp e_fmod e_hypot e_log e_log10 e_log2 e_pow e_rem_pio2 e_sqrt
k_cos k_rem_pio2 k_sin k_tan s_atan s_ceil s_copysign s_cos s_erf s_expm1 s_fabs s_floor
s_frexp s_log1p s_modf s_nextafter s_rint s_round s_scalbn s_sin s_tan s_trunc'''.split()


def main():
    checkout = ROOT / 'build/lefony-prime-g2'
    destination = ROOT / 'sdk/lib/vendor/openbsd-math'
    contents = {}
    for name in [*(s + '.c' for s in SOURCES), 'math_private.h']:
        data = subprocess.check_output(['git', '-C', str(checkout), 'show', f'{REVISION}:{BASE}{name}'])
        path = destination / name
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f'{path.relative_to(ROOT)} differs from the pinned source; refusing to overwrite')
        contents[name] = data
    manifest = {'schema': 1, 'component': 'OpenBSD/fdlibm subset from pinned Upsilon',
                'source_repository': 'https://github.com/UpsilonNumworks/Upsilon', 'source_revision': REVISION,
                'source_directory': BASE, 'modifications': 'none; original per-file license notices retained',
                'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(contents.items())}}
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in contents.items():
        (destination / name).write_bytes(data)
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Extracted {len(contents)} exact pinned source files; per-file licenses retained')


if __name__ == '__main__':
    main()
