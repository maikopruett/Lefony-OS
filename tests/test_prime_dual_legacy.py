# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'vm')]
from prime_dual_boot_transaction import Transaction,Change,RAW_BLOCK
from prime_dual_installer import bundle_paths
import prime_dual_migration as m
import prime_dual_legacy as legacy


def test_hp_system_restore_requires_explicit_add_hp_profile():
    c=Change(32,b'\xff'*RAW_BLOCK,bytes(RAW_BLOCK),'restore-hp-system')
    with pytest.raises(ValueError):Transaction([c],b'a'*32)
    assert Transaction([c],b'a'*32,mode='add-hp').mode=='add-hp'
    with pytest.raises(ValueError):
        Transaction([Change(3456,c.before,c.after,c.phase)],b'a'*32,mode='add-hp')


def test_unrecognized_legacy_profile_cannot_supply_hp_backup():
    fields={k:'x' for k in ('backup','candidate','uboot','archive','recreated','public_key')}
    fields.update(backup_sha256='ab'*32,hp_backup='x',hp_backup_sha256='cd'*32,source_profile='guessed')
    with pytest.raises(ValueError):bundle_paths(fields)


def test_bad_block_metadata_exception_requires_exact_complete_record(monkeypatch):
    monkeypatch.setattr(m,'bad_inventory',lambda p:{6,7,99})
    monkeypatch.setattr(m,'read_block',lambda p,b:bytes(RAW_BLOCK))
    assert m.factory_inventory('x')=={6,7,99}
    monkeypatch.setattr(m,'STOCK_BLOCK6_SHA256',m.sha(bytes(RAW_BLOCK)).hex())
    assert m.factory_inventory('x')=={7,99}


def test_occupied_legacy_staging_fails_before_decoding_or_planning(monkeypatch):
    monkeypatch.setattr(m,'file_hash',lambda p:b'a'*32)
    monkeypatch.setattr(m,'bad_inventory',lambda p:set())
    monkeypatch.setattr(m,'read_block',lambda p,b:bytes(RAW_BLOCK) if b==258 else m.ERASED)
    with pytest.raises(ValueError,match='staging area'):
        legacy.inspect_legacy(Path('x'),b'a'*32)
