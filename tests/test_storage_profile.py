# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import struct
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prime_g2_storage_profile import decode,difference,NAMES,SIZE,ProfileUSB

def record(calls=0):
    header=struct.pack('<8I',0x3150464c,1,SIZE,3000000,len(NAMES),123,1,0)
    return header+b''.join(struct.pack('<3Q4I',calls,calls*2048,calls*3000,3000 if calls else 0,3000 if calls else 0,0,0) for _ in NAMES)

def test_counter_differences_measure_driver_time_without_usb_overhead():
    result=difference(decode(record(7)),decode(record(10)))['counters']['program']
    assert result['calls']==3 and result['bytes']==6144
    assert result['seconds']==.003 and result['MB_per_second']==2.048

def test_profile_transport_is_read_only():
    assert ProfileUSB.READ_REQUESTS==(0x56,) and not ProfileUSB.WRITE_REQUESTS

def test_counter_reset_is_not_interpreted_as_bandwidth():
    with pytest.raises(ValueError,match='reset'):difference(decode(record(10)),decode(record(2)))

@pytest.mark.parametrize('offset,value',[(0,0),(12,1),(16,8),(24,2),(28,1),(64,1),(68,1)])
def test_malformed_profile_rejected(offset,value):
    data=bytearray(record());struct.pack_into('<I',data,offset,value)
    with pytest.raises(ValueError):decode(data)

def test_failed_io_is_not_reported_as_successful_bandwidth():
    data=bytearray(record(1));struct.pack_into('<I',data,64,1)
    result=difference(decode(record()),decode(data))
    assert result['counters']['read']['MB_per_second'] is None
