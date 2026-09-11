#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Create a deterministic standalone SDK source kit from an explicit allowlist."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]


def package(output):
    files={}
    for directory in ('tools','include','lib','cmake','templates','examples','publisher'):
        for path in sorted((ROOT/'sdk'/directory).rglob('*')):
            if not path.is_file() or path.is_symlink() or any(part in ('build','__pycache__') for part in path.relative_to(ROOT/'sdk').parts):
                continue
            if path.suffix not in ('.py','.h','.s','.ld','.cpp','.json','.md','.service','.timer','.txt') and path.name not in ('lefony-sdk','Dockerfile','Dockerfile.toolchain'):
                continue
            files['sdk/'+path.relative_to(ROOT/'sdk').as_posix()]=(path.read_bytes(),0o755 if path.name=='lefony-sdk' else 0o644)
    for name in ('.dockerignore','scripts/package_native_sdk.py','LICENSE.md','THIRD_PARTY_NOTICES.md','sdk/README.md','sdk/publisher/README.md','docs/NATIVE-APP-SDK-STATUS.md','docs/NATIVE-APP-SDK-PLAN.md','docs/NATIVE-APP-PACKAGE-FORMAT.md','docs/NATIVE-APP-SETUP.md','docs/NATIVE-APP-STORAGE.md','sdk/requirements-desktop.txt','sdk/DESKTOP-README.md'):
        files[name]=((ROOT/name).read_bytes(),0o644)
    for path in sorted((ROOT/'LICENSES').glob('*.txt')):
        files['LICENSES/'+path.name]=(path.read_bytes(),0o644)
    files['sdk/trust/app-signing.pem']=((ROOT/'ports/lefony-prime-g2/app-signing.pub').read_bytes(),0o644)
    files['SHA256SUMS']=(''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name,(data,_) in sorted(files.items())).encode(),0o644)
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('wb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as compressed, tarfile.open(fileobj=compressed,mode='w') as archive:
        for name,(data,mode) in sorted(files.items()):
            item=tarfile.TarInfo('lefony-native-sdk/'+name); item.size=len(data); item.mode=mode
            archive.addfile(item,io.BytesIO(data))
    print(output)
    print(hashlib.sha256(output.read_bytes()).hexdigest())

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    package(parser.parse_args().output)
