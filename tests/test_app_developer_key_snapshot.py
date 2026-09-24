# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import struct
import subprocess
from test_app_files import ROOT, compile_fixture
from test_app_developer_keys import signing


def test_partial_registry_snapshot_and_atomic_repair(tmp_path):
    faults = (ROOT/'tests/native/app_developer_keys.cpp').read_text()
    (tmp_path/'app_key_fault_fixture.h').write_text(faults[faults.index('struct KeyFlash:Flash {'):faults.index('static bool same')])
    binary = compile_fixture(tmp_path, source=ROOT/'tests/native/app_developer_key_snapshot.cpp',
                             extra_sources=('app_developer_keys.cpp','app_developer_key_snapshot.cpp'))
    der = signing.public_der(ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem')
    path = tmp_path/'modulus.bin'; path.write_bytes(der[len(signing.SPKI_PREFIX):-len(signing.SPKI_SUFFIX)])
    result = subprocess.run([binary,path,tmp_path], capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report['captures'] == 3 and report['interruption_cases'] > 30 and report['cancellation_cases'] == 36
    assert report['snapshot_bytes'] < 4*1024
    assert report['boundary_cases'] == 10
    reports = []
    original = (tmp_path/'registry-original.keys').read_bytes()
    for mask in (1,2,3):
        raw = (tmp_path/f'snapshot-{mask}.keys').read_bytes()
        assert raw[:8] == b'LFKREAD1' and struct.unpack_from('<6I',raw,8) == (1,2752,512,6,0,0)
        cursor, readable, missing = 32, 0, 0
        for index in range(6):
            offset, size, state, reserved = struct.unpack_from('<4I',raw,cursor); cursor += 16
            assert offset == index*512 and size == min(512,2752-offset) and reserved == 0
            assert state == bool(mask & (1 << (offset//2048)))
            if state: missing += 1
            else:
                assert raw[cursor:cursor+size] == original[offset:offset+size]
                cursor += size; readable += size
        assert cursor == len(raw) and readable == {1:704,2:2048,3:0}[mask]
        reports.append({'mask':mask,'bytes':len(raw),'readable':readable,'missing':missing,'sha256':hashlib.sha256(raw).hexdigest()})
    output = ROOT/'build/sdk-key-media'; output.mkdir(parents=True,exist_ok=True)
    (output/'snapshot-host-report.json').write_text(json.dumps({**report,'snapshots':reports},indent=2)+'\n')
