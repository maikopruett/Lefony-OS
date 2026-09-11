#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Collect checked Homebrew source archives, recipes, patches and license notices.

Read local installed recipes, not the newer formula versions in the API. Never
execute downloaded source or extract it into the checkout. This records source
inputs for the explicit macOS SDK dependency set; inspect the resulting manifest
before distributing the corresponding binary candidate.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import tarfile
import urllib.request


def download(url,destination,expected=None):
    if destination.exists() and (not expected or hashlib.sha256(destination.read_bytes()).hexdigest()==expected):return
    request=urllib.request.Request(url,headers={'User-Agent':'Lefony-SDK-Builder/1'})
    with urllib.request.urlopen(request,timeout=60) as response, destination.with_suffix(destination.suffix+'.part').open('wb') as output:
        total=0;digest=hashlib.sha256()
        while data:=response.read(1024*1024):
            total+=len(data)
            if total>300*1024*1024:raise ValueError('Source exceeds bound')
            output.write(data);digest.update(data)
    if expected and digest.hexdigest()!=expected:raise ValueError(f'Checksum mismatch: {destination.name}')
    destination.with_suffix(destination.suffix+'.part').replace(destination)


def collect(bundle,output,prefix):
    output.mkdir(parents=True,exist_ok=True)
    components={}
    for library in (bundle/'_internal').glob('*.dylib'):
        path=(prefix/'lib'/library.name).resolve()
        if not path.is_file() or 'Cellar' not in path.parts:raise ValueError(f'Unmapped library: {library.name}')
        i=path.parts.index('Cellar');components[path.parts[i+1]]=Path(*path.parts[:i+3])
    for name in ('arm-none-eabi-gcc','arm-none-eabi-binutils','python@3.14','openssl@3'):
        components[name]=(prefix/'opt'/name).resolve()
    cache=Path.home()/'Library/Caches/Homebrew/api/internal/packages.arm64_tahoe.jws.json'
    api=json.loads(json.loads(cache.read_text())['payload'])
    core=api['formula_tap_git_head']
    if not re.fullmatch('[0-9a-f]{40}',core):raise ValueError('Missing pinned Homebrew patch reference')
    jobs=[];manifest=[]
    for name,directory in sorted(components.items()):
        recipe=directory/'.brew'/f'{name}.rb'
        source=recipe.read_text();target=output/name;target.mkdir(exist_ok=True)
        shutil.copyfile(recipe,target/'formula.rb')
        receipt=json.loads((directory/'INSTALL_RECEIPT.json').read_text())
        version=receipt['source']['versions']['stable']
        notices=target/'notices';notices.mkdir(exist_ok=True)
        inputs=[]
        # url/mirror/version lines followed by sha256; excludes livecheck URLs,
        # unpinned HEAD repositories and architecture-specific bottle blobs.
        for match in re.finditer(r'^\s*url "(https://[^"\n]+)"[^\n]*\n(?:(?:\s*(?:mirror|version) [^\n]+)\n)*\s*sha256 "([0-9a-f]{64})"',source,re.M):
            url,digest=match.groups()
            if '#{' in url:raise ValueError(f'Unresolved source URL: {name}')
            if 'ftpmirror.gnu.org/gnu/' in url:url=url.replace('ftpmirror.gnu.org/gnu/','ftp.gnu.org/gnu/')
            filename=url.split('/')[-1]
            path=target/(digest[:12]+'-'+filename)
            jobs.append((url,path,digest));inputs.append({'file':str(path.relative_to(output)),'url':url,'sha256':digest})
        if not inputs:raise ValueError(f'No pinned source: {name}')
        for relative in re.findall(r'file "(Patches/[^"\n]+)"',source):
            path=target/Path(relative).name;url=f'https://raw.githubusercontent.com/Homebrew/homebrew-core/{core}/{relative}'
            jobs.append((url,path,None));inputs.append({'file':str(path.relative_to(output)),'url':url,'patch_reference':core})
        manifest.append({'component':name,'version':version,'recipe_sha256':hashlib.sha256(recipe.read_bytes()).hexdigest(),'inputs':inputs})
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures=[executor.submit(download,*job) for job in jobs]
        for job,future in zip(jobs,futures):future.result();print('Verified',job[1].name,flush=True)
    for component in manifest:
        notices=output/component['component']/'notices'
        for item in component['inputs']:
            path=output/item['file'];item['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            if not tarfile.is_tarfile(path):continue
            with tarfile.open(path) as archive:
                for member in archive:
                    name=Path(member.name)
                    if not member.isfile() or member.size>2*1024*1024 or len(name.parts)>4 or not re.match(r'^(COPYING|COPYRIGHT|LICENSE|NOTICE|AUTHORS)([._-]|$)',name.name,re.I):continue
                    data=archive.extractfile(member).read();filename=hashlib.sha256(member.name.encode()).hexdigest()[:8]+'-'+name.name
                    (notices/filename).write_bytes(data)
    for name in ('pyinstaller','pyinstaller-hooks-contrib'):
        version=importlib.metadata.version(name)
        with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json',timeout=30) as response:
            metadata=json.loads(response.read(1024*1024))
        source=next(item for item in metadata['urls'] if item['packagetype']=='sdist')
        folder=output/name;folder.mkdir(exist_ok=True);path=folder/source['filename']
        download(source['url'],path,source['digests']['sha256'])
        notices=folder/'notices';notices.mkdir(exist_ok=True)
        with tarfile.open(path) as archive:
            for member in archive:
                n=Path(member.name)
                if member.isfile() and len(n.parts)<4 and n.name.upper().startswith(('COPYING','LICENSE','NOTICE','COPYRIGHT')) and member.size<2000000:
                    (notices/(hashlib.sha256(member.name.encode()).hexdigest()[:8]+'-'+n.name)).write_bytes(archive.extractfile(member).read())
        manifest.append({'component':name,'version':version,'inputs':[{'file':str(path.relative_to(output)),'url':source['url'],'sha256':source['digests']['sha256']}]})
    (output/'manifest.json').write_text(json.dumps({'schema':1,'platform':'darwin-arm64','components':manifest},indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--prefix',type=Path,default=Path('/opt/homebrew'))
    args=parser.parse_args();collect(args.bundle,args.output,args.prefix)
