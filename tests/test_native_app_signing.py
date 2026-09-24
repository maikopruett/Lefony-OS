# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from test_native_app_package import META, image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from lfapp import pack
from signing import envelope, firmware_header, openssl, public_der, sign, verify


@pytest.fixture(scope='module')
def keys(tmp_path_factory):
    directory = tmp_path_factory.mktemp('app-signing')
    private, public = directory/'private.pem', directory/'public.pem'
    private.write_bytes(openssl('genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048'))
    public.write_bytes(openssl('pkey', '-in', private, '-pubout'))
    return private, public


def test_signature_roundtrip_is_deterministic_and_binds_full_payload(keys):
    private, public = keys
    payload = pack(META, image())
    signed = sign(payload, private)
    assert signed == sign(payload, private)
    assert verify(signed, [public]) == (META, image())
    assert envelope(signed)[0] == hashlib.sha256(public_der(public)).hexdigest()
    for offset in (0, 8, 12, 16, 20, 24, 56, 88, 96, 351, 352, len(signed)-1):
        modified = bytearray(signed); modified[offset] ^= 1
        with pytest.raises(ValueError): verify(modified, [public])
    with pytest.raises(ValueError): verify(signed + b'\0', [public])
    with pytest.raises(ValueError): verify(signed[:-1], [public])
    with pytest.raises(ValueError): verify(signed, [])
    with pytest.raises(ValueError): verify(signed, [public, public])
    with pytest.raises(ValueError): verify(payload, [public])


def test_signature_cannot_be_reused_after_recomputing_payload_hash(keys):
    private, public = keys
    signed = bytearray(sign(pack(META, image()), private))
    replacement = pack({**META, 'name':'Forged'}, image())
    signed[352:] = replacement
    import struct
    struct.pack_into('<I',signed,12,len(replacement))
    signed[56:88] = hashlib.sha256(replacement).digest()
    with pytest.raises(ValueError, match='signature rejected'): verify(signed, [public])


@pytest.mark.parametrize('with_progress', [False, True])
def test_guest_verifier_matches_openssl_and_rejects_tampering(keys, tmp_path, with_progress):
    private, public = keys
    port = ROOT/'ports/lefony-prime-g2/ion/src/prime_g2'
    for name in ('native_app_signature.h','native_app_digest.h'):
        shutil.copyfile(port/name,tmp_path/name)
    firmware_header([public],tmp_path/'app_trust_roots.h')
    source = tmp_path/'verify.cpp'
    source.write_text('''#include "native_app_signature.h"
#include <stdio.h>
uint8_t data[2101665];
unsigned progressCalls=0;
void progress(){progressCalls++;}
int main(int argc,char **){size_t n=fread(data,1,sizeof(data),stdin),length=0;const uint8_t *payload=nullptr;
bool ok=PrimeG2::NativeAppSignature::unwrap(data,n,&payload,&length,argc>1?progress:nullptr);
printf("%u\\n",progressCalls);
if(!ok && (payload || length)) return 2;
return ok?0:1;}
''')
    executable = tmp_path/'verify'
    subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror',str(source),'-o',str(executable)],check=True)
    def run(data):
        return subprocess.run([executable, *(['progress'] if with_progress else [])],
                              input=data, capture_output=True, timeout=10)
    signed = sign(pack(META,image()),private)
    accepted = run(signed)
    assert accepted.returncode == 0
    assert (int(accepted.stdout) > 0) == with_progress
    large = run(sign(pack(META, image()+bytes(512*1024)), private))
    assert large.returncode == 0
    if with_progress:assert int(large.stdout)>int(accepted.stdout)
    for offset in (8, 12, 16, 20, 24, 56, 88, 96, 200, len(signed)-1):
        modified=bytearray(signed); modified[offset]^=1
        rejected=run(modified)
        assert rejected.returncode == 1
        if with_progress and offset in (96,200):assert int(rejected.stdout)>0
    # An attacker recomputing the payload hash still needs a valid signature,
    # even after the OS has observed progress through verification.
    modified=bytearray(signed);modified[-1]^=1
    modified[56:88]=hashlib.sha256(modified[352:]).digest()
    assert run(modified).returncode == 1
    assert run(signed[:-1]).returncode == 1
    assert run(pack(META,image())).returncode == 1
    shutil.copyfile(port/'app_trust_roots.h',tmp_path/'app_trust_roots.h')
    subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror',str(source),'-o',str(executable)],check=True)
    rejected=run(signed)
    assert rejected.returncode == 1 and int(rejected.stdout)==0


def test_key_generation_never_replaces_an_identity(tmp_path):
    private, public=tmp_path/'private.pem',tmp_path/'public.pem'
    command=[sys.executable,str(ROOT/'sdk/tools/signing.py'),'keygen',str(private),str(public)]
    subprocess.run(command,check=True,capture_output=True)
    original=private.read_bytes()
    assert private.stat().st_mode & 0o777 == 0o600
    assert subprocess.run(command,capture_output=True).returncode != 0
    assert private.read_bytes() == original

@pytest.mark.parametrize('options',[['rsa_keygen_bits:3072'],['rsa_keygen_bits:2048','rsa_keygen_pubexp:3']])
def test_noncontract_rsa_keys_are_rejected(options,tmp_path):
    private=tmp_path/'key.pem';arguments=[]
    for option in options:arguments+=['-pkeyopt',option]
    private.write_bytes(openssl('genpkey','-algorithm','RSA',*arguments))
    with pytest.raises(ValueError,match='RSA-2048'):public_der(private,private=True)
