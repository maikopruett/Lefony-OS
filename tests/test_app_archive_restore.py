# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import subprocess
from test_app_files import ROOT,compile_fixture
from test_sdk_archive import PUBLIC,encoded,snapshot,signed
import signing
import archive_format


def test_streamed_restore_on_production_filesystem(tmp_path):
    binary=compile_fixture(tmp_path,source=ROOT/'tests/native/app_archive_restore.cpp',extra_sources=('app_archive_restore.cpp','app_archive_source.cpp','app_archive_export.cpp'))
    current,old=signed(),signed('1.0.0')
    file=bytes(((i*131+(i>>8))^0x5d)&255 for i in range(128*1024-128+137))
    entries=(('docs/note.bin',file),('docs',None),('empty',b''))
    (tmp_path/'current.arc').write_bytes(encoded(snapshot(current,entries=entries)))
    (tmp_path/'pending.arc').write_bytes(encoded(snapshot(current,entries=entries),snapshot(old,entries=entries)))
    (tmp_path/'small.arc').write_bytes(encoded(snapshot(current)))
    (tmp_path/'same.arc').write_bytes(encoded(snapshot(old,entries=entries),high=(1,0,0)))
    (tmp_path/'current.pkg').write_bytes(current);(tmp_path/'old.pkg').write_bytes(old);(tmp_path/'file.bin').write_bytes(file)
    der=signing.public_der(PUBLIC)
    (tmp_path/'modulus.bin').write_bytes(der[len(signing.SPKI_PREFIX):-len(signing.SPKI_SUFFIX)])
    (tmp_path/'identity.bin').write_bytes(hashlib.sha256(der).digest())
    result=subprocess.run([binary,tmp_path],text=True,capture_output=True,timeout=300)
    assert result.returncode==0,result.stdout+result.stderr
    report=json.loads(result.stdout)
    assert report['interruption_cases']>300 and report['cancellation_cases']>100
    assert report['damaged_data_cases']==3 and report['rejection_cases']>=20
    assert report['namespace_cases']==8
    assert report['uncertain_commit_cases']==1
    assert report['export_cancellations']>20 and report['export_engine_bytes']<150*1024
    for name,count in [('current',1),('pending',2),('legacy',1)]:
        path=tmp_path/f'export-{name}.arc';exported=archive_format.inspect(path,[PUBLIC])
        assert len(exported.snapshots)==count and exported.signatures_checked
        if name=='legacy':assert path.read_bytes()==encoded(snapshot(old,b'old'),high=(1,0,0))
    assert report['reused_bytes']==len(file) and report['engine_bytes']<400*1024
    directory=ROOT/'build/sdk-archive';directory.mkdir(parents=True,exist_ok=True)
    (directory/'restore-report.json').write_text(json.dumps(report,indent=2)+'\n')
