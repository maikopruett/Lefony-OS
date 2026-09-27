# SPDX-License-Identifier: GPL-3.0-or-later
import json,struct,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_prime_hp_write_trace import analyze,region
from analyze_hp_prime_compatibility import AuditError


def fixture(tmp_path,blocks):
 log=tmp_path/'log';overlay=tmp_path/'overlay'
 log.write_text(''.join('prime-nand-write: '+json.dumps({'operation':'program','block':b,'page':b*64})+'\n' for b in blocks))
 overlay.write_bytes(b'PG2RAW1\n'+b''.join(struct.pack('<B3xI',1,b*64)+bytes(2112) for b in blocks))
 return log,overlay


def test_detects_protected_regions(tmp_path):
 log,overlay=fixture(tmp_path,[0,391,392,2047,2048,4095]);r=analyze(log,overlay)
 assert [e['block'] for e in r['escaped_attempts']]==[0,391,2048,4095]
 assert r['escaped_commits']


def test_nonempty_in_range_trace(tmp_path):
 r=analyze(*fixture(tmp_path,[392,2047]));assert r['result'].startswith('PASS')


def test_empty_trace_is_not_success(tmp_path):
 with pytest.raises(AuditError,match='missing NAND'):analyze(*fixture(tmp_path,[]))


def test_torn_overlay_fails(tmp_path):
 log,overlay=fixture(tmp_path,[392]);overlay.write_bytes(overlay.read_bytes()[:-1])
 with pytest.raises(AuditError,match='torn'):analyze(log,overlay)


@pytest.mark.parametrize('block',range(4,8))
def test_metadata_only_owns_two_pages_per_copy(block):
 assert region({'operation':'erase','block':block})=='hp-bad-block-metadata'
 for page in range(64):
  expected='hp-bad-block-metadata' if page in (0,4) else 'protected'
  assert region({'operation':'program','block':block,'page':block*64+page})==expected
