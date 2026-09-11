# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the firmware's real storage engine against torn-write NAND injection."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
PORT=ROOT/'ports/lefony-prime-g2/ion/src/prime_g2'

def test_native_app_storage_power_loss(tmp_path):
    compiler=shutil.which('c++')
    if not compiler:
        pytest.skip('Host C++ compiler unavailable')
    binary=tmp_path/'storage-test'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',
                    '-I',str(PORT),str(ROOT/'tests/native/app_storage.cpp'),str(PORT/'app_storage.cpp'),'-o',str(binary)],check=True,timeout=60)
    subprocess.run([str(binary)],check=True,timeout=120)

def test_app_layout_does_not_overlap_firmware_or_bad_block_table():
    import json
    layout=json.loads((ROOT/'native/prime_g2/app_layout.json').read_text())
    nand=json.loads((ROOT/'native/prime_g2/nand_layout.json').read_text())
    start,end=layout['offset'],layout['offset']+layout['size']
    assert start==3456*64*2048 and end==496*1024*1024
    assert layout['block_count']==16+8*2*31
    assert layout['backup_raw_bytes']==512*64*(2048+64)
    for region in nand['physical_ab_layout']:
        if region['name']!='retired_rootfs':
            assert end<=region['offset'] or start>=region['offset']+region['size']
    assert nand['physical_ab_migration_allowed'] is False
