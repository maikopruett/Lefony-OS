# SPDX-License-Identifier: GPL-3.0-or-later
"""Reject unsupported, unattributed and malformed resource evidence."""
from pathlib import Path
import hashlib
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from resource_profile import arm,snapshot,SNAPSHOT,FIELDS

TARGET=hashlib.sha256(b'target fixture').hexdigest()

class Channel:
    def __init__(self,reply):self.reply=reply;self.commands=[]
    def command(self,value):self.commands.append(value);return self.reply

def response(**changes):
    fields=dict.fromkeys(FIELDS,0)
    fields.update(version=1,bytes=SNAPSHOT.size,flags=1,loads=2,finished_loads=2,
                  entries=4,samples=10,stack_capacity_bytes=65536,
                  stack_pointer_bytes=32768,stack_written_bytes=8192,
                  code_bytes=256,static_data_bytes=16,lfapp_sha256=bytes.fromhex(TARGET))
    fields.update(changes)
    return 'DATA '+SNAPSHOT.pack(*(fields[name] for name in FIELDS)).hex()

def test_observations_are_not_claimed_as_peaks_or_free_memory():
    report=snapshot(Channel(response()),TARGET)
    assert report['stack_observed_bytes']==32768
    assert report['stack_peak_bytes'] is None and report['heap_peak_bytes'] is None
    assert report['loads']==report['finished_loads']==2
    assert not report['currently_loaded'] and report['timing']=='instrumented-emulator-only'

@pytest.mark.parametrize('fields',[
    {'lfapp_sha256':bytes(32)},{'version':2},{'bytes':1},{'flags':0},{'flags':17},
    {'loads':0},{'entries':0},{'samples':0},{'finished_loads':3},
    {'stack_capacity_bytes':1},{'stack_pointer_bytes':65537},{'stack_written_bytes':65537},
    {'heap_reserved_peak_bytes':8388608},{'static_data_bytes':974849},{'code_bytes':1048577},
    {'faults':1},{'failure_result':0xfffffff2},
])
def test_invalid_or_unobserved_snapshot_is_never_a_zero_pass(fields):
    with pytest.raises(RuntimeError):snapshot(Channel(response(**fields)),TARGET)

@pytest.mark.parametrize('reply',['VALUE 0','ERR command','DATA 00','DATA '+ '00'*113])
def test_unknown_and_truncated_protocol_is_rejected(reply):
    with pytest.raises(RuntimeError):snapshot(Channel(reply),TARGET)

def test_old_firmware_refuses_opt_in_before_load():
    channel=Channel('ERR unknown command')
    with pytest.raises(RuntimeError,match='matching VM'):arm(channel,b'fixture')
    assert channel.commands==['APP PROFILE VERSION']

def test_fault_and_counter_limits_remain_visible():
    report=snapshot(Channel(response(flags=13,faults=1,failure_result=0xfffffff2,
                                    stack_pointer_bytes=65536,fault_pc=0x10000100)),TARGET)
    assert report['failure_result']==-14 and report['fault_pc']==0x10000100
    assert report['stack_pointer_out_of_bounds'] and report['counters_saturated']
    assert report['stack_observed_near_capacity']
