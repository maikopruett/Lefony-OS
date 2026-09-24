# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import gzip
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sdk/tools'))
from bundled_data import CONFIG, descriptor, prepare, sha, unpack
from test_sdk_store_publication import project, prepared
from store_snapshot import verify


def inputs(project):
    raw=b'IWAD synthetic fixture\0'*200
    spec={'schema':1,'encoding':'gzip','bytes':len(raw),'sha256':sha(raw),'files':[{'path':'freedoom1.wad','offset':0,'bytes':len(raw),'sha256':sha(raw)}]}
    (project/'notices').mkdir(exist_ok=True)
    (project/CONFIG).write_text(json.dumps(spec))
    (project/'data').mkdir()
    (project/'data/freedoom1.wad').write_bytes(raw)
    return spec,raw


def test_publication_snapshots_data_and_detects_tampering(project):
    spec,raw=inputs(project)
    result=prepared(project);attempt=Path(result['directory'])
    submission=verify(attempt)
    assert submission['schema']==2 and submission['data']==spec
    # Accepted-release tracking must not treat companion parts as PNG media.
    from store_listing import submission_content
    content = submission_content(submission)
    assert content['icon']['width'] > 0 and len(content['screenshots']) == 1
    assert (attempt/'project/data/freedoom1.wad').read_bytes()==raw
    (project/'data/freedoom1.wad').write_bytes(b'changed original')
    assert verify(attempt)==submission
    part=attempt/'upload/data/00.gzpart';part.chmod(0o600);part.write_bytes(b'corrupt')
    with pytest.raises(ValueError):verify(attempt)


def test_round_trip_and_oversize_expansion(project):
    spec,raw=inputs(project);spec,parts=prepare(project)
    assert unpack(spec,[data for _,data in parts])[0][1]==raw
    with pytest.raises(ValueError):unpack(spec,[gzip.compress(raw+b'extra')])
    with pytest.raises((ValueError,EOFError,OSError)):unpack(spec,[parts[0][1][:-1]])
    (project/'data/freedoom1.wad').write_bytes(b'bad')
    with pytest.raises(ValueError):prepare(project)


@pytest.mark.parametrize('path',['../file.wad','/file.wad','default.cfg','.savegame','a/b.wad','foo.wad\n'])
def test_unsafe_or_mutable_paths_rejected(project,path):
    spec,_=inputs(project);spec['files'][0]['path']=path
    with pytest.raises(ValueError):descriptor(spec)


def test_alias_ranges_hashes_and_symlinks(project):
    spec,raw=inputs(project)
    bad=copy.deepcopy(spec);bad['files'][0]['offset']=1
    with pytest.raises(ValueError):descriptor(bad)
    bad=copy.deepcopy(spec);bad['files'].append(copy.deepcopy(bad['files'][0]))
    with pytest.raises(ValueError):descriptor(bad)
    target=project/'data/freedoom1.wad';target.unlink();other=project/'outside';other.write_bytes(raw);target.symlink_to(other)
    with pytest.raises(ValueError):prepare(project)


def test_complete_download_requires_signatures_and_exact_package_binding(tmp_path):
    import struct
    from bundled_data import load_bundle, verify_metadata
    from lfapp import pack, canonical
    from signing import sign, HEADER, MAGIC, public_der, openssl
    from test_native_app_package import image
    root=Path(__file__).resolve().parents[1]
    private=root/'tests/fixtures/prime_g2_emulator_update_private.pem';public=root/'tests/fixtures/prime_g2_emulator_update_public.pem'
    package=sign(pack({'id':'bundle-test','name':'Bundle','version':'1.0.0','abi':1,'license':'MIT'},image()),private)
    raw=b'game fixture';part=gzip.compress(raw,mtime=0)
    spec={'schema':1,'encoding':'gzip','bytes':len(raw),'sha256':sha(raw),'files':[{'path':'game.wad','offset':0,'bytes':len(raw),'sha256':sha(raw)}]}
    meta={'schema':1,'kind':'lefony-install-data-1','package_sha256':sha(package),'data':spec,'parts':[{'path':'data/00.gzpart','bytes':len(part),'sha256':sha(part)}]}
    payload=canonical(meta)
    header=HEADER.pack(MAGIC,1,len(payload),1,0,bytes.fromhex(sha(public_der(private,private=True))),bytes.fromhex(sha(payload)),bytes(8))
    signed=header+openssl('dgst','-sha256','-sign',private,data=header)+payload
    members=[('package.lfapp',package),('data.signed',signed),('data/00.gzpart',part)]
    index=canonical({'schema':1,'files':[{'path':n,'bytes':len(b),'sha256':sha(b)} for n,b in members]})
    output=tmp_path/'app.lfbundle';output.write_bytes(b'LFBNDL1\0'+struct.pack('<I',len(index))+index+b''.join(b for _,b in members))
    assert load_bundle(output,[public])[0]==package
    with pytest.raises(ValueError):verify_metadata(signed,[public],'f'*64)
    bad=bytearray(signed);bad[100]^=1
    with pytest.raises(ValueError):verify_metadata(bad,[public],sha(package))
    with pytest.raises(ValueError):load_bundle(output,[])
    output.write_bytes(output.read_bytes()+b'extra')
    with pytest.raises(ValueError):load_bundle(output,[public])


def test_large_data_replay_has_a_finite_startup_budget():
    from replay import validate
    case = {"schema": 1, "name": "large-data", "steps": [{"wait_ms": 5000}] * 36}
    assert validate(case) == case
    case["steps"].append({"wait_ms": 1})
    with pytest.raises(ValueError, match="180 seconds"):
        validate(case)
