# SPDX-License-Identifier: GPL-3.0-or-later
"""Boot-marker repair authorization and journal ownership; no USB or HP inputs."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prime_dual_boot_transaction import Transaction, Change, RAW_BLOCK, journal_page
from prime_phase6_boot_repair import completed_install, run


def original():
    digest=bytes(range(32))
    tx=Transaction([Change(240,b'\xff'*RAW_BLOCK,b'x'*RAW_BLOCK,'stage-recovery')],digest,mode='add-hp')
    review={'purpose':'phase6-stock-install-trial','transaction':tx.id.hex(),
            'bundle':{'source_profile':'lefony-menu1','backup_sha256':digest.hex()},
            'changes':[c.identity() for c in tx.changes]}
    return tx,review


def test_completed_install_requires_latest_journal_complete():
    tx,review=original()
    pages=[journal_page(tx,2,0,True),journal_page(tx,3,1,False)]
    assert completed_install(review,pages,tx.backup_digest)==tx.id
    with pytest.raises(ValueError,match='not completely verified'):
        completed_install(review,[pages[0],journal_page(tx,3,0,True)],tx.backup_digest)
    with pytest.raises(ValueError,match='conflicting'):
        completed_install(review,[journal_page(tx,3,0,True),pages[1]],tx.backup_digest)


def test_completed_install_rejects_changed_review_or_foreign_journal():
    tx,review=original()
    pages=[journal_page(tx,2,0,True),journal_page(tx,3,1,False)]
    foreign=Transaction(tx.changes,b'z'*32,mode='add-hp')
    with pytest.raises(ValueError,match='invalid original'):
        completed_install(review,[pages[0],journal_page(foreign,3,1,False)],tx.backup_digest)
    review['changes'][0]['after']='ff'*32
    with pytest.raises(ValueError,match='identity mismatch'):
        completed_install(review,pages,tx.backup_digest)


@pytest.mark.parametrize('block,phase',[(0,'redirect-rom'),(256,'commit-layout'),
                                      (2048,'stage-images'),(3456,'migrate-data')])
def test_boot_repair_cannot_change_rom_controls_layout_or_os_data(block,phase):
    with pytest.raises(ValueError,match='only replace boot streams'):
        Transaction([Change(block,b'\xff'*RAW_BLOCK,b'x'*RAW_BLOCK,phase)],bytes(range(32)),mode='repair-boot')


def test_boot_repair_requires_explicit_approval_before_opening_files_or_usb(tmp_path):
    with pytest.raises(ValueError,match='explicit physical'):
        run(tmp_path/'missing')
