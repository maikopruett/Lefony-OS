# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
from pathlib import Path
import random
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'vm'))
spec = importlib.util.spec_from_file_location('stock_conversion', ROOT/'vm/convert-prime-stock-nand.py')
conversion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(conversion)


def test_bulk_projection_matches_independent_bit_reference():
    rng = random.Random(192)
    records = [b'\xff'*2112, bytes(2112), bytes(range(256))*8+bytes(range(64))]
    records += [rng.randbytes(2112) for _ in range(8)]
    for record in records:
        assert conversion.reconstruct(record) == conversion.reconstruct_physical_page(record)


def test_bad_record_length_rejected():
    for length in (0, 2111, 2113):
        with pytest.raises(ValueError):
            conversion.reconstruct(bytes(length))


def test_partial_capture_rejected_before_output(tmp_path):
    source = tmp_path/'partial';source.write_bytes(bytes(2112))
    with pytest.raises(ValueError, match='full 512 MiB'):
        conversion.convert(source, tmp_path/'output')
    assert not (tmp_path/'output').exists()
