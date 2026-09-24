#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fetch/verify exact public Doom source and Freedoom qualification assets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'build/sdk-1.0-upstream')
    parser.add_argument('--offline',action='store_true')
    args=parser.parse_args()
    output=args.directory.resolve()
    output.mkdir(parents=True,exist_ok=True)
    source=json.loads((ROOT/'sdk/ports/doom/source.json').read_text())
    assets=json.loads((ROOT/'sdk/ports/doom/assets.json').read_text())
    checkout=output/'doomgeneric'
    if not checkout.exists():
        if args.offline: raise ValueError('Pinned Doom checkout unavailable offline')
        subprocess.run(['git','clone','--no-checkout',source['repository'],str(checkout)],check=True,timeout=180)
        subprocess.run(['git','-C',str(checkout),'checkout','--detach',source['commit']],check=True,timeout=60)
    head=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True,timeout=10).strip()
    if head!=source['commit']: raise ValueError('Existing Doom checkout has a different revision; it was preserved')
    for name,expected in source['source_files'].items():
        if sha(checkout/source['directory']/name)!=expected: raise ValueError('Modified Doom source was preserved: '+name)
    if sha(checkout/source['license']['path'])!=source['license']['sha256']:
        raise ValueError('Modified Doom license was preserved')
    archive=output/('freedoom-'+assets['version']+'.zip')
    if not archive.exists():
        if args.offline: raise ValueError('Pinned Freedoom archive unavailable offline')
        temporary=archive.with_suffix('.download')
        created=False
        try:
            with urllib.request.urlopen(assets['url'],timeout=30) as response,temporary.open('xb') as stream:
                created=True
                count=0
                while chunk:=response.read(1024*1024):
                    count+=len(chunk)
                    if count>64*1024*1024: raise ValueError('Freedoom download exceeds the candidate limit')
                    stream.write(chunk)
            if sha(temporary)!=assets['archive_sha256']: raise ValueError('Freedoom archive hash mismatch')
            temporary.rename(archive)
        finally:
            if created: temporary.unlink(missing_ok=True)
    if sha(archive)!=assets['archive_sha256']: raise ValueError('Existing Freedoom archive hash mismatch')
    with zipfile.ZipFile(archive) as bundle:
        for name,entry in assets['files'].items():
            destination=output/name
            if destination.exists():
                if sha(destination)!=entry['sha256']: raise ValueError('Modified asset was preserved: '+name)
                continue
            info=bundle.getinfo(entry['archive_path'])
            if info.file_size!=entry['bytes'] or info.file_size>32*1024*1024: raise ValueError('Unexpected asset size')
            data=bundle.read(info)
            if hashlib.sha256(data).hexdigest()!=entry['sha256']: raise ValueError('Asset hash mismatch')
            with destination.open('xb') as stream: stream.write(data)
    print('Verified pinned Doom source and Freedoom Phase 1 WAD, license and credits')


if __name__=='__main__': main()
