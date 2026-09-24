# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import subprocess
from test_app_files import ROOT, compile_fixture
from test_sdk_archive import signed, snapshot, encoded, PUBLIC, signing


def test_archive_session_uses_real_storage_signatures_and_commit_boundaries(tmp_path):
    binary=compile_fixture(tmp_path,source=ROOT/'tests/native/app_archive_session.cpp',extra_sources=(
        'app_archive_restore.cpp','app_archive_source.cpp','app_archive_export.cpp','app_archive_session.cpp'))
    old,current=signed('1.0.0'),signed()
    entries=(('notes',b'content'*10000),('empty',b''),('folder',None))
    for name,data in {'old.pkg':old,'current.arc':encoded(snapshot(current,entries=entries)),
            'pending.arc':encoded(snapshot(current,entries=entries),snapshot(old,b'old')),
            'changed.arc':encoded(snapshot(signed(schema=7),schema=7)),
            'original.arc':encoded(snapshot(old,b'old'),high=(1,0,0)),
            'wrong-private.arc':encoded(snapshot(old,b'new'),high=(1,0,0)),
            'same.arc':encoded(snapshot(old,b'restored'),high=(1,0,0))}.items():
        (tmp_path/name).write_bytes(data)
    # A real second RSA identity proves the retained signature boundary.
    private=tmp_path/'second-private.pem';public=tmp_path/'second-public.pem'
    private.write_bytes(signing.openssl('genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048'))
    public.write_bytes(signing.openssl('pkey','-in',private,'-pubout'))
    previous=signing.sign(signing.envelope(old)[1],private)
    (tmp_path/'cross.arc').write_bytes(encoded(snapshot(current,entries=entries),snapshot(previous,b'other signer')))
    (tmp_path/'downgrade.arc').write_bytes(encoded(snapshot(signed('3.0.0')),high=(3,0,0)))
    outsider=signing.sign(signing.envelope(signed('10.0.0'))[1],private)
    (tmp_path/'wrong-owner.arc').write_bytes(encoded(snapshot(outsider),high=(10,0,0)))
    der2=signing.public_der(public)
    (tmp_path/'second-modulus.bin').write_bytes(der2[len(signing.SPKI_PREFIX):-len(signing.SPKI_SUFFIX)])
    (tmp_path/'second-identity.bin').write_bytes(hashlib.sha256(der2).digest())
    der=signing.public_der(PUBLIC)
    (tmp_path/'modulus.bin').write_bytes(der[len(signing.SPKI_PREFIX):-len(signing.SPKI_SUFFIX)])
    (tmp_path/'identity.bin').write_bytes(hashlib.sha256(der).digest())
    result=subprocess.run([binary,tmp_path],capture_output=True,text=True,timeout=300)
    assert result.returncode==0,result.stdout+result.stderr
    report=json.loads(result.stdout);assert report['cases']>=44 and report['repair_cases']>=28 and report['repair_interruption_cases']>20
    assert report['unreadable_media_cases']==8
    assert report['root_recovery_cases']==10 and report['root_authority_refusals']==30
    output=ROOT/'build/sdk-code-repair';output.mkdir(parents=True,exist_ok=True)
    (output/'session-report.json').write_text(json.dumps(report,indent=2)+'\n')
    output=ROOT/'build/sdk-root-recovery';output.mkdir(parents=True,exist_ok=True)
    (output/'session-report.json').write_text(json.dumps(report,indent=2)+'\n')
