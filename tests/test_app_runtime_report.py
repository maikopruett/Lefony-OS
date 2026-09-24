# SPDX-License-Identifier: GPL-3.0-or-later
import struct
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prime_g2_app_runtime import decode


def test_startup_report_retains_measurement_and_flags():
    data = struct.pack('<16I', 0x5452464c, 1, 64, 7, 100, 800, 600, 500, 5, 9, 10, 0, 0, 0, 0, 0)
    report = decode(data)
    assert report['startup_ms'] == 500 and report['pixel_frames'] == 5 and report['flags'] == 7
    for position in (0, 1, 2, 3, 13, 14, 15):
        bad = bytearray(data)
        struct.pack_into('<I', bad, position * 4, 0xffffffff)
        with pytest.raises(ValueError):
            decode(bad)
    with pytest.raises(ValueError):
        decode(data[:-1])
