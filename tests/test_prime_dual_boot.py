# SPDX-License-Identifier: GPL-3.0-or-later
"""Phase 5 descriptor, media interruption and isolation tests; no HP inputs."""
from pathlib import Path
import copy
import hashlib
import json
import struct
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import prime_dual_boot_contract as c
from prime_dual_boot_transaction import Change, Transaction, Engine, RAW_BLOCK

KEY = ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem'
PUB = ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'
ERASED = b'\xff'*RAW_BLOCK


def images(monkeypatch):
    payloads = {name:(name.encode()+b'\0')*32 for name in c.COMPONENTS}
    for name in ('lefony_image', 'rescue'):
        payload = bytearray(payloads[name])
        payload[0x30:0x40] = struct.pack('<4s3I', b'LFL5', 5, 1, 0)
        payloads[name] = bytes(payload)
    monkeypatch.setitem(c.INPUTS, 'HPPrime.img', (len(payloads['hp_image']), c.sha(payloads['hp_image']).hex()))
    return payloads


def test_layout_covers_chip_and_preserves_hp_and_app_contracts():
    doc, regions = c.load_layout()
    assert sum(r.count for r in regions.values()) == 4096
    assert regions['hp_filesystem'].end == 2048
    assert regions['lefony_apps'].first == 3456
    assert not doc['physical_migration_allowed']


@pytest.mark.parametrize('fault', ['overlap', 'gap', 'duplicate', 'geometry', 'profile', 'physical'])
def test_invalid_layout_rejected(tmp_path, fault):
    data = json.loads(c.LAYOUT.read_text())
    if fault == 'overlap': data['regions'][1]['first'] -= 1
    if fault == 'gap': data['regions'][-1]['count'] -= 1
    if fault == 'duplicate': data['regions'][1]['name'] = data['regions'][0]['name']
    if fault == 'geometry': data['geometry']['page_bytes'] = 4096
    if fault == 'profile': data['hp_profile'] = 'future-build'
    if fault == 'physical': data['physical_migration_allowed'] = True
    path = tmp_path/'layout.json'; path.write_text(json.dumps(data))
    with pytest.raises(c.ContractError): c.load_layout(path)


def test_capacity_reserves_good_block_for_failed_update():
    assert c.capacity('lefony_image', 8*1024*1024, set()) == list(range(2128,2192))
    with pytest.raises(c.ContractError): c.capacity('lefony_image', 8*1024*1024, set(range(2192,2208)))
    with pytest.raises(c.ContractError): c.capacity('hp_filesystem', 2048, set())


def test_descriptor_authenticates_profile_layout_and_every_image(monkeypatch):
    payloads = images(monkeypatch)
    signed = c.sign_descriptor(payloads, 1, KEY)
    assert c.verify_descriptor(signed, PUB, payloads)['release'] == 1
    for offset in (0, 8, 32, 64, 96, 140, 220, 255, 256, 511):
        bad = bytearray(signed); bad[offset] ^= 1
        with pytest.raises(Exception): c.verify_descriptor(bytes(bad), PUB)
    changed = dict(payloads); changed['rescue'] += b'changed'
    with pytest.raises(c.ContractError): c.verify_descriptor(signed, PUB, changed)
    with pytest.raises(c.ContractError): c.verify_descriptor(b'LFU1'+signed[4:], PUB)


def test_unknown_original_hp_image_cannot_be_signed(monkeypatch):
    payloads = images(monkeypatch); payloads['hp_image'] += b'unknown'
    with pytest.raises(c.ContractError): c.sign_descriptor(payloads, 1, KEY)


def test_legacy_capsule_is_rejected_even_when_signing_is_available(monkeypatch):
    payloads = images(monkeypatch)
    payloads['lefony_image'] = bytes(len(payloads['lefony_image']))
    with pytest.raises(c.ContractError, match='legacy firmware'):
        c.sign_descriptor(payloads, 1, KEY)


def test_redundant_layout_tear_conflict_and_pending(monkeypatch):
    signed = c.sign_descriptor(images(monkeypatch), 1, KEY)
    txid = c.sha(b'transaction')
    old = c.record(1, 'recovery', txid)
    new = c.record(2, 'committed', txid, signed)
    assert c.select_record((old,new))['state'] == 'committed'
    for cut in (0, 4, 64, 256, 512, 2044, 2047):
        torn = new[:cut] + b'\xff'*(2048-cut)
        assert c.select_record((old,torn))['state'] == 'recovery'
    with pytest.raises(c.ContractError): c.select_record((old,c.record(1,'committed',txid,signed)))
    with pytest.raises(c.ContractError): c.select_record((new,c.record(3,'recovery',c.sha(b'other'))))
    with pytest.raises(c.ContractError): c.select_record((bytes(2048),bytes(2048)))


class PowerLoss(RuntimeError): pass


class Media:
    kind = 'offline-emulator'
    def __init__(self, transaction):
        self.transaction = transaction
        self.blocks = {item.block:item.before for item in transaction.changes}
        self.journals = [b'\xff'*2048]*2
        self.bad_blocks = set()
        self.operations = 0
        self.cut = None
        self.backup_valid = True
        self.barrier = False
        self.allow_barrier = True
        self.trace = []
    def checkpoint(self):
        self.operations += 1
        if self.cut == self.operations: raise PowerLoss()
    def read_block(self, block): return self.blocks.get(block, ERASED)
    def erase_block(self, block):
        self.checkpoint()
        self.blocks[block] = ERASED
        self.trace.append(('erase', block))
        self.checkpoint()
    def program_raw_page(self, page, data):
        self.checkpoint()
        block, index = divmod(page,64)
        raw = bytearray(self.read_block(block)); at=index*c.RAW_PAGE
        assert all((old & new) == new for old,new in zip(raw[at:at+c.RAW_PAGE],data))
        # Inject a cut midway through a page program as well as after success.
        raw[at:at+1056] = data[:1056]; self.blocks[block] = bytes(raw)
        self.checkpoint()
        raw[at:at+c.RAW_PAGE] = data; self.blocks[block] = bytes(raw)
        self.trace.append(('program',block)); self.checkpoint()
    def read_journal(self, slot): return self.journals[slot]
    def write_journal(self, slot, page):
        self.checkpoint(); self.journals[slot] = b'\xff'*2048
        self.checkpoint(); self.journals[slot] = page[:1024]+b'\xff'*1024
        self.checkpoint(); self.journals[slot] = page
        self.checkpoint()
    def verify_backup(self, digest):
        c.require(self.backup_valid and digest == self.transaction.backup_digest,'backup is missing or corrupt')
    def verify_recovery_barrier(self, transaction):
        c.require(self.allow_barrier,'boot routes not verified')
        for change in transaction.changes:
            if change.phase in ('stage-recovery','redirect-rom'):
                c.require(self.read_block(change.block)==change.after,'recovery route changed')
        self.barrier = True


def plan():
    changes=[]
    for block, phase in [(240,'stage-recovery'),(248,'stage-recovery'),
                         (3,'redirect-rom'),(2,'redirect-rom'),(1,'redirect-rom'),(0,'redirect-rom'),
                         (392,'migrate-data'),(2048,'stage-images'),(256,'commit-layout'),(257,'commit-layout')]:
        after=(bytes([block%251])*c.RAW_PAGE).ljust(RAW_BLOCK,b'\xff')
        changes.append(Change(block,ERASED,after,phase))
    return Transaction(changes,c.sha(b'complete verified external backup'))


def test_every_persistent_transition_can_resume_after_power_loss():
    tx=plan(); baseline=Media(tx); Engine(baseline,tx).prepare()
    starting=copy.deepcopy(baseline)
    Engine(baseline,tx).run()
    # All before/after erases, page tears, successful writes with lost replies,
    # and redundant journal erase/program boundaries in the complete operation.
    for cut in range(starting.operations+1,baseline.operations+1):
        media=copy.deepcopy(starting); media.cut=cut
        with pytest.raises(PowerLoss): Engine(media,tx).run()
        media.cut=None
        Engine(media,tx).run()
        assert all(media.read_block(item.block)==item.after for item in tx.changes),cut
        assert media.barrier
        assert set(block for _,block in media.trace) <= {item.block for item in tx.changes}
        # A second resume verifies everything and performs no more writes.
        operations=media.operations; Engine(media,tx).run(); assert media.operations==operations


def test_bad_backup_media_mismatch_and_unverified_boot_barrier_stop_writes():
    tx=plan()
    media=Media(tx); media.backup_valid=False
    with pytest.raises(c.ContractError): Engine(media,tx).prepare()
    assert media.operations==0
    media=Media(tx); media.blocks[392]=bytes(RAW_BLOCK)
    with pytest.raises(c.ContractError): Engine(media,tx).prepare()
    assert media.operations==0
    media=Media(tx); Engine(media,tx).prepare(); media.allow_barrier=False
    with pytest.raises(c.ContractError): Engine(media,tx).run()
    assert media.read_block(392)==ERASED
    assert media.read_block(2048)==ERASED


def test_foreign_journal_and_changed_completed_data_are_rejected():
    tx=plan(); media=Media(tx); Engine(media,tx).prepare(); Engine(media,tx).run()
    media.blocks[240]=bytes(RAW_BLOCK)
    with pytest.raises(c.ContractError,match='completed write'): Engine(media,tx).run()
    other=Transaction(tx.changes,c.sha(b'other backup'))
    with pytest.raises(c.ContractError): Engine(media,other)._read_state()


@pytest.mark.parametrize('block,phase',[(4,'stage-images'),(3456,'stage-images'),(2048,'stage-recovery'),(0,'migrate-data'),(258,'commit-layout')])
def test_plan_cannot_write_outside_declared_phase(block,phase):
    with pytest.raises(c.ContractError): Transaction([Change(block,ERASED,bytes(RAW_BLOCK),phase)],c.sha(b'backup'))


def test_no_physical_backend_can_execute():
    tx=plan(); media=Media(tx); media.kind='usb'
    with pytest.raises(c.ContractError): Engine(media,tx)


def test_one_foreign_valid_journal_is_not_ignored():
    from prime_dual_boot_transaction import journal_page
    tx=plan();media=Media(tx);Engine(media,tx).prepare()
    other=Transaction(tx.changes,c.sha(b'foreign backup'))
    media.journals[1]=journal_page(other,2,0,False)
    with pytest.raises(c.ContractError,match='foreign journal'):Engine(media,tx).run()


def test_bounded_step_never_reports_full_completion():
    tx=plan();media=Media(tx);Engine(media,tx).prepare()
    assert Engine(media,tx).run(max_changes=1) is None
    assert Engine(media,tx)._read_state()[2:]==(1,False)
    assert Engine(media,tx).run()==tx.id.hex()


def test_native_layout_handoff_guard_rejects_corruption(tmp_path):
    import subprocess
    import zlib
    source=ROOT/'ports/lefony-prime-g2/ion/src/prime_g2'
    (tmp_path/'dual_boot_guard.h').write_bytes((source/'dual_boot_guard.h').read_bytes())
    digest=c.layout_digest()
    (tmp_path/'dual_boot_build.h').write_text('#pragma once\n#define LEFONY_DUAL_BOOT_CANDIDATE 1\n'
        +'static const unsigned char LefonyDualLayoutSHA[32]={'+','.join(str(v) for v in digest)+'};\n')
    record=bytearray(64);struct.pack_into('<I',record,0,0x3548464c)
    record[4:36]=digest;struct.pack_into('<I',record,36,1)
    struct.pack_into('<I',record,60,zlib.crc32(record[:60]))
    harness='''#include "dual_boot_guard.h"
#include <cassert>
#include <cstring>
int main() {
  unsigned char p[64]={DATA};
  assert(PrimeG2::DualBoot::Enabled);
  assert(!PrimeG2::DualBoot::legacyUpdateAllowed());
  assert(!PrimeG2::DualBoot::validHandoff(nullptr));
  assert(PrimeG2::DualBoot::validHandoff(p));
  for (unsigned i=0;i<64;i++) {
    p[i]^=1;assert(!PrimeG2::DualBoot::validHandoff(p));p[i]^=1;
  }
}
'''.replace('DATA',','.join(str(v) for v in record))
    (tmp_path/'check.cpp').write_text(harness)
    subprocess.run(['clang++','-std=c++11',str(tmp_path/'check.cpp'),'-o',str(tmp_path/'check')],check=True)
    subprocess.run([str(tmp_path/'check')],check=True)
