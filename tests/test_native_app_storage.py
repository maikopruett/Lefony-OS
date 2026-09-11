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
    flags=['-DLFS_NO_MALLOC','-DLFS_NO_DEBUG','-DLFS_NO_WARN','-DLFS_NO_ERROR','-DLFS_NO_ASSERT']
    cc=shutil.which('cc')
    if not cc: pytest.skip('Host C compiler unavailable')
    objects=[]
    for name in ('lfs','lfs_util'):
        obj=tmp_path/(name+'.o');objects.append(str(obj))
        subprocess.run([cc,'-std=c99','-fsanitize=address,undefined','-fexceptions','-g',*flags,
                        '-I',str(PORT),'-DLFS_DEFINES=littlefs_compat/defines.h',
                        '-c',str(PORT/f'littlefs/{name}.c'),'-o',str(obj)],check=True,timeout=60)
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',*flags,
                    '-I',str(PORT),str(ROOT/'tests/native/app_storage.cpp'),str(PORT/'app_storage.cpp'),
                    str(PORT/'legacy_app_storage.cpp'),*objects,'-o',str(binary)],check=True,timeout=60)
    subprocess.run([str(binary)],check=True,timeout=240)

def test_app_layout_does_not_overlap_firmware_or_bad_block_table():
    import json
    layout=json.loads((ROOT/'native/prime_g2/app_layout.json').read_text())
    nand=json.loads((ROOT/'native/prime_g2/nand_layout.json').read_text())
    start,end=layout['offset'],layout['offset']+layout['size']
    assert start==3456*64*2048 and end==496*1024*1024
    assert layout['profile']==2
    assert layout['filesystem']['first_relative_block']==2
    assert layout['filesystem']['block_count']+2==layout['block_count']==512
    assert layout['filesystem']['update_reserve_blocks']==24
    assert 'slot_count' not in layout
    assert layout['backup_raw_bytes']==512*64*(2048+64)
    for region in nand['physical_ab_layout']:
        if region['name']!='retired_rootfs':
            assert end<=region['offset'] or start>=region['offset']+region['size']
    assert nand['physical_ab_migration_allowed'] is False


def test_legacy_storage_reader_and_recovery(tmp_path):
    compiler=shutil.which('c++')
    if not compiler: pytest.skip('Host C++ compiler unavailable')
    binary=tmp_path/'legacy-storage-test'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',
                    '-I',str(PORT),str(ROOT/'tests/native/legacy_app_storage.cpp'),
                    str(PORT/'legacy_app_storage.cpp'),'-o',str(binary)],check=True,timeout=60)
    subprocess.run([str(binary)],check=True,timeout=120)
