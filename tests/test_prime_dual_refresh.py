# SPDX-License-Identifier: GPL-3.0-or-later
"""Update boundaries and retained ownership; no hardware or private firmware."""
import pytest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prime_dual_boot_transaction import Change, Transaction, RAW_BLOCK, journal_page
from prime_dual_refresh import completed_owner, run


def change(block,phase):
    return Change(block,b'\xff'*RAW_BLOCK,b'x'*RAW_BLOCK,phase)


def test_refresh_preserves_hp_apps_and_preferences():
    for block,phase in ((2048,'stage-images'),(2208,'stage-images'),(260,'stage-images'),
                         (261,'stage-images'),(392,'migrate-data'),(3456,'migrate-data')):
        with pytest.raises(ValueError):
            Transaction([change(block,phase)],b'a'*32,mode='refresh-dual')


def test_refresh_routes_must_precede_streams_and_descriptors_follow_images():
    changes=[change(0,'redirect-rom'),change(248,'stage-recovery'),
             change(240,'stage-recovery'),change(2128,'stage-images'),change(257,'commit-layout')]
    Transaction(changes,b'a'*32,mode='refresh-dual')
    for a,b in ((0,1),(3,4)):
        wrong=list(changes);wrong[a],wrong[b]=wrong[b],wrong[a]
        with pytest.raises(ValueError,match='ordering'):
            Transaction(wrong,b'a'*32,mode='refresh-dual')


def test_refresh_requires_complete_matching_previous_owner():
    tx=Transaction([change(248,'stage-recovery')],b'a'*32,mode='repair-boot')
    review={'purpose':'phase6-boot-marker-repair','backup_sha256':tx.backup_digest.hex(),
            'transaction':tx.id.hex(),'changes':[c.identity() for c in tx.changes]}
    pending=journal_page(tx,2,0,True);done=journal_page(tx,3,1,False)
    assert completed_owner(review,[pending,done])==tx.id
    with pytest.raises(ValueError,match='incomplete'):
        completed_owner(review,[pending,pending])
    with pytest.raises(ValueError,match='conflicting'):
        completed_owner(review,[journal_page(tx,3,0,True),done])
    foreign=Transaction(tx.changes,b'b'*32,mode='repair-boot')
    with pytest.raises(ValueError,match='invalid previous'):
        completed_owner(review,[done,journal_page(foreign,4,1,False)])
    review['changes'][0]['after']='00'*32
    with pytest.raises(ValueError,match='identity mismatch'):
        completed_owner(review,[done,done])


def test_refresh_rejects_unapproved_before_files_or_usb(tmp_path):
    with pytest.raises(ValueError,match='explicit physical'):
        run(tmp_path/'missing')
