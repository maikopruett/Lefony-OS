#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Package public source, explicit upstream trees and checked dependency inputs."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
from check_public_tree import check_paths
ROOT=Path(__file__).resolve().parents[1]

def add(archive,path,name):
    if path.is_symlink():return
    if path.is_dir():
        for item in sorted(path.iterdir()):
            if item.name in ('.git','output','__pycache__','.pytest_cache'):continue
            add(archive,item,name+'/'+item.name)
    elif path.is_file():archive.add(path,arcname=name,recursive=False)

def package(materials,output,groups=('toolchain','runtime','lefony-qemu')):
    output.mkdir(parents=True,exist_ok=True)
    paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().rstrip('\0').split('\0')
    problems=check_paths(ROOT,paths)
    if problems:raise ValueError('\n'.join(problems))
    sources=json.loads((materials/'manifest.json').read_text())
    for component in sources['components']:
        for item in component['inputs']:
            path=materials/item['file']
            if path.is_symlink() or not path.resolve().is_relative_to(materials.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Source material changed')
    previous=json.loads((output/'sources.json').read_text()) if (output/'sources.json').exists() else []
    replaced={f'lefony-sdk-source-{group}.tar.gz' for group in groups}
    results=[item for item in previous if item['filename'] not in replaced]
    for group in dict.fromkeys(groups):
        path=output/f'lefony-sdk-source-{group}.tar.gz'
        with tarfile.open(path,'w:gz') as archive:
            if group=='lefony-qemu':
                for name in sorted(set(paths)):
                    if (ROOT/name).is_file():add(archive,ROOT/name,'lefony/'+name)
                add(archive,ROOT/'build/qemu-prime-g2-source-v11.1.1-r70','qemu-prime')
                add(archive,ROOT/'build/lefony-prime-g2','prepared-firmware')
            else:
                selected=[c for c in sources['components'] if (c['component'].startswith('arm-none-eabi-'))==(group=='toolchain')]
                for component in selected:add(archive,materials/component['component'],component['component'])
                data=(json.dumps({'schema':1,'components':selected},indent=2)+'\n').encode();info=tarfile.TarInfo('manifest.json');info.size=len(data);archive.addfile(info,io.BytesIO(data))
        results.append({'filename':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'kind':'corresponding-source'})
    (output/'sources.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--materials',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--group',action='append',choices=('toolchain','runtime','lefony-qemu'))
    args=parser.parse_args();package(args.materials,args.output,args.group or ('toolchain','runtime','lefony-qemu'))
