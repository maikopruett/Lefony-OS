# SPDX-License-Identifier: GPL-3.0-or-later
"""The experimental preparation must remain separate from the installed menu."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_prime_bootmenu import prepare as prepare_menu
from prepare_prime_hp_handoff import prepare as prepare_hp, HP_DDR_VALUES


def fixture(tree):
    board = tree / 'board/hp/mx6ull_prime'
    board.mkdir(parents=True)
    (tree / 'configs').mkdir()
    sdp = tree / 'drivers/usb/gadget'
    sdp.mkdir(parents=True)
    (sdp / 'f_sdp.c').write_text(
        'get_timer(lefony_sdp_start) >= 180000\n'
        'get_timer(lefony_sdp_start) < 180000)\n'
        '180 second recovery window\n'
        'source(sdp_func->jmp_address, "script@1");\n')
    nand = tree / 'drivers/mtd/nand'
    nand.mkdir(parents=True)
    (nand / 'mxs_nand.c').write_text('nand->bbt_options = NAND_BBT_USE_FLASH | NAND_BBT_NO_OOB;\n')
    (board / 'Makefile').write_text('obj-y  := mx6ull_prime.o\n')
    (board / 'imximage.cfg').write_text(''.join(
        f'DATA 4 0x{address} 0x{original}\n'
        for address, original, _ in HP_DDR_VALUES))
    (board / 'mx6ull_prime.c').write_text(
        '#include <command.h>\nint board_late_init(void) {\n'
        '\tint recovery = readl(request) == 0x3153464c; /* LFS1 */\n'
        '\tif (recovery) {\n\t\tif (readl(request) != 0)\n\t\t\trecovery = 0;\n'
        '\t\trun_command("sdp 0", 0);\n\t}\n\treturn 0;\n}\n\n'
        'u32 get_board_rev(void) {}\n')
    (tree / 'configs/mx6ull_prime_defconfig').write_text(
        'CONFIG_LOCALVERSION="-lefony-sdp1"\n')
    return board


def snapshot(tree):
    return {p.relative_to(tree): p.read_bytes() for p in tree.rglob('*') if p.is_file()}


def test_separate_idempotent_preparation(tmp_path):
    normal, experiment = tmp_path / 'normal', tmp_path / 'experiment'
    fixture(normal)
    board = fixture(experiment)
    prepare_menu(normal)
    prepare_menu(experiment)
    baseline = snapshot(normal)
    prepare_hp(experiment)
    prepared = snapshot(experiment)
    prepare_hp(experiment)
    assert prepared == snapshot(experiment)
    assert baseline == snapshot(normal)
    assert not (normal / 'board/hp/mx6ull_prime/hp_ram.c').exists()
    assert (board / 'hp_menu.c').read_bytes() == (ROOT / 'native/prime_g2/hp_handoff/hp_menu.c').read_bytes()
    assert not (normal / 'board/hp/mx6ull_prime/hp_menu.c').exists()
    assert (board / 'hp_ram.c').read_bytes() == (ROOT / 'native/prime_g2/hp_handoff/hp_ram.c').read_bytes()
    config = (experiment / 'configs/mx6ull_prime_defconfig').read_text()
    assert 'CONFIG_SHA256=y' in config
    assert '-lefony-hp-ram-experiment7' in config
    assert 'DATA 4 0x021B0040 0x0000005F' in (board / 'imximage.cfg').read_text()
    assert 'DATA 4 0x021B0040 0x00000047' in (normal / 'board/hp/mx6ull_prime/imximage.cfg').read_text()
    assert 'RAM BBT only' in (experiment / 'drivers/mtd/nand/mxs_nand.c').read_text()
    assert 'NAND_BBT_USE_FLASH' in (normal / 'drivers/mtd/nand/mxs_nand.c').read_text()
    sdp = (experiment / 'drivers/usb/gadget/f_sdp.c').read_text()
    assert '>= 5400000' in sdp and '< 5400000)' in sdp
    assert 'status = source' in sdp
    assert '5400000' not in (normal / 'drivers/usb/gadget/f_sdp.c').read_text()
    source = (board / 'mx6ull_prime.c').read_text()
    assert 'run_command("sdp 0", 0)' in source
    assert 'env_set("bootcmd", "lfboot")' in source
    assert 'env_set("bootdelay", "-1")' in source
    assert 'bootdelay' not in (normal / 'board/hp/mx6ull_prime/mx6ull_prime.c').read_text()


def test_reject_unprepared_upstream(tmp_path):
    fixture(tmp_path)
    with pytest.raises(ValueError, match='unexpected U-Boot context'):
        prepare_hp(tmp_path)


def test_dual_policy_owns_usb_and_keypad_startup(tmp_path):
    from prepare_prime_dual_boot import prepare
    fixture(tmp_path);prepare_menu(tmp_path);prepare_hp(tmp_path)
    common=tmp_path/'common';common.mkdir()
    autoboot=common/'autoboot.c'
    upstream=('#if defined(is_boot_from_usb)\nmanufacturing_policy();\n#endif\n'
              '#if defined(is_boot_from_usb)\nselect_manufacturing_command();\n#endif\n')
    autoboot.write_text(upstream)
    prepare(tmp_path,ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem')
    prepared=snapshot(tmp_path)
    prepare(tmp_path,ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem')
    assert snapshot(tmp_path)==prepared
    policy=autoboot.read_text()
    assert policy.count('&& !defined(CONFIG_TARGET_MX6ULL_PRIME)')==2
    board=(tmp_path/'board/hp/mx6ull_prime/mx6ull_prime.c').read_text()
    assert 'env_set("bootcmd", "lfdualboot")' in board
    assert 'env_set("bootdelay", "-2")' in board
    # A changed upstream branch must fail rather than silently leave a path
    # which can overwrite the signed dual-boot policy.
    autoboot.write_text(upstream.replace('#if defined(is_boot_from_usb)', '#ifdef OTHER_USB_BOOT',1))
    with pytest.raises(ValueError,match='USB manufacturing policy'):
        prepare(tmp_path,ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem')
    autoboot.write_bytes(prepared[Path('common/autoboot.c')]+b'\n#if defined(is_boot_from_usb)\n#endif\n')
    with pytest.raises(ValueError,match='USB manufacturing policy'):
        prepare(tmp_path,ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem')


def test_phase6_transport_preparation_is_separate_and_idempotent(tmp_path):
    from prepare_prime_phase6_recovery import prepare
    board=fixture(tmp_path)
    prepare_menu(tmp_path);prepare_hp(tmp_path)
    prepare(tmp_path)
    result=snapshot(tmp_path)
    prepare(tmp_path)
    assert snapshot(tmp_path)==result
    assert 'hp_transfer_info.o' in (board/'Makefile').read_text()
    assert '(u8 *)0x84200000, *hashes' in (board/'hp_nand_info.c').read_text()
    assert '0x84000000' in (board/'hp_transfer_info.c').read_text()
    assert '-lefony-recovery-experiment6' in (tmp_path/'configs/mx6ull_prime_defconfig').read_text()
    assert 'int recovery = 1; /* dedicated RAM-only recovery */' in (board/'mx6ull_prime.c').read_text()
    assert 'recovery = 0;' not in (board/'mx6ull_prime.c').read_text()
