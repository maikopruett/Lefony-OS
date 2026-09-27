# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
def test_boot_menu_behavior(tmp_path):
    source=ROOT/'native/prime_g2/bootmenu'
    subprocess.run([sys.executable,str(ROOT/'scripts/generate_bootmenu_font.py'),str(tmp_path/'font.h')],check=True)
    exe=tmp_path/'bootmenu'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',
                    '-I'+str(source),'-I'+str(tmp_path),str(ROOT/'tests/native/bootmenu_test.c'),
                    *(str(source/n) for n in ('menu.c','preferences.c','render.c')),'-o',str(exe)],check=True)
    subprocess.run([str(exe),str(tmp_path)],check=True)


def test_preparation_is_checked_and_idempotent(tmp_path):
    import importlib.util
    import pytest
    sys.path.insert(0, str(ROOT/'scripts'))
    spec = importlib.util.spec_from_file_location('bootmenu_prepare', ROOT/'scripts/prepare_prime_bootmenu.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    board = tmp_path/'board/hp/mx6ull_prime'
    board.mkdir(parents=True)
    (tmp_path/'configs').mkdir()
    (board/'Makefile').write_text('obj-y  := mx6ull_prime.o\n')
    (board/'mx6ull_prime.c').write_text('#include <command.h>\nint board_late_init(void) {\n\tif (recovery) {\n\t\trun_command("sdp 0", 0);\n\t}\n\treturn 0;\n}\n\nu32 get_board_rev(void) {}\n')
    (tmp_path/'configs/mx6ull_prime_defconfig').write_text('CONFIG_LOCALVERSION="-lefony-sdp1"\n')
    module.prepare(tmp_path)
    first = {p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    module.prepare(tmp_path)
    assert first == {p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    (board/'Makefile').write_text('obj-y := unexpected.o\n')
    with pytest.raises(ValueError, match='unexpected U-Boot context'):
        module.prepare(tmp_path)
