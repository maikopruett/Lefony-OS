# SPDX-License-Identifier: GPL-3.0-or-later
"""Repair fault qualification retires old ownership in its disposable model."""
import importlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vm'))
faults = importlib.import_module('test-prime-dual-migration-faults')
from prime_dual_boot_transaction import Change, Transaction, journal_page


def test_repair_faults_start_after_old_journal_retirement(monkeypatch, tmp_path):
    before = faults.ERASED
    after = b'x' * faults.RAW_PAGE + before[faults.RAW_PAGE:]
    tx = Transaction([Change(240, before, after, 'stage-recovery')], b'a' * 32,
                     mode='repair-boot')
    old = Transaction(tx.changes, b'b' * 32, mode='add-hp')
    with faults.NativeBCH() as native:
        data, aux = faults.ECC.swap_marker(journal_page(old, 2, 1, False), b'\xff' * 10)
        raw = faults.ECC.encode(data, aux, native) + before[faults.RAW_PAGE:]
    source = {258: raw, 259: raw}
    monkeypatch.setattr(faults, 'read_block', lambda path, block: source.get(block, before))
    result = faults.qualify(tmp_path / 'source', tmp_path / 'backup', tx, set(), tmp_path / 'uboot')
    assert result['mode'] == 'repair-boot'
    assert result['persistent_cuts'] > 0 and result['initialization_cuts'] > 0
    assert source == {258: raw, 259: raw}, 'fault model changed its source snapshot'
