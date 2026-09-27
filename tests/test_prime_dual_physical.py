# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic transport/media tests. Never enumerate USB or open a calculator."""
from pathlib import Path
import hashlib
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'vm')]
import prime_dual_physical as p
from prime_dual_boot_transaction import Engine, Transaction, Change, journal_page


class Device:
    def __init__(self):
        self.blocks={}
        self.bad=set()
        self.events=[]
        self.staged=b''
        self.fault=None
    def verify_protocol(self):
        if self.fault=='protocol': raise ValueError('wrong recovery protocol')
    def close(self): pass
    def inventory(self): return p.GEOMETRY,self.bad.copy()
    def read_block(self,b): return self.blocks.get(b,p.ERASED)
    def hash_blocks(self,first,count): return [p.sha(self.read_block(b)).hex() for b in range(first,first+count)]
    def stage_bytes(self,raw):
        if self.fault=='upload': raise ValueError('RAM upload mismatch')
        self.staged=raw
    def stage_digest(self,n): return p.sha(self.staged[:n]) if self.fault!='stage-after-erase' else bytes(32)
    def erase(self,b,*,stock_metadata=False):
        self.events.append(('erase',b))
        if self.fault=='erase': return
        self.blocks[b]=p.ERASED
    def program_pages(self,b,n):
        self.events.append(('program',b,n))
        self.blocks[b]=self.staged[:n*2112]+b'\xff'*(p.RAW_BLOCK-n*2112)
        if self.fault=='lost-program': raise TimeoutError('ACK lost')
        if self.fault=='readback': self.blocks[b]=bytes(p.RAW_BLOCK)


@pytest.fixture(scope='module')
def backup(tmp_path_factory):
    path=tmp_path_factory.mktemp('physical-media')/'backup.raw'
    with path.open('wb') as f:
        chunk=p.ERASED*32
        for _ in range(128): f.write(chunk)
    return path,hashlib.sha256(path.read_bytes()).digest()


@pytest.fixture
def media(backup,monkeypatch):
    # Cache the immutable fixture's digest; its geometry/byte reads are real.
    path,digest=backup
    monkeypatch.setattr(p.model,'file_hash',lambda value:digest)
    d=Device();events=[]
    m=p.PhysicalMedia(d,path,digest,event=events.append)
    yield m,d,events
    m.close()


def test_no_inspection_or_approval_means_no_erase(media):
    m,d,_=media
    with pytest.raises(ValueError):m.authorize_journal_trial(approved=True)
    with pytest.raises(ValueError):m.erase_block(258)
    m.inspect()
    with pytest.raises(ValueError):m.authorize_journal_trial()
    assert d.events==[]


@pytest.mark.parametrize('fault', ['protocol','source','factory'])
def test_preflight_failures_cannot_authorize_mutation(media,fault):
    m,d,_=media
    if fault=='source':d.blocks[42]=bytes(p.RAW_BLOCK)
    elif fault=='factory':d.bad.add(42)
    else:d.fault=fault
    with pytest.raises(ValueError):m.inspect()
    with pytest.raises(ValueError):m.authorize_journal_trial(approved=True)
    assert d.events==[]


def test_journal_trial_is_limited_and_uses_one_page(media):
    m,d,events=media
    m.inspect();m.authorize_journal_trial(approved=True)
    for b in (0,6,240,257,260,2048,3456):
        with pytest.raises(ValueError):m.erase_block(b)
    page=bytes((i*7)&255 for i in range(2048))
    m.write_journal(0,page)
    assert m.read_journal(0)==page
    assert d.events==[('erase',258),('program',258,1)]
    m.erase_block(258)
    assert m.read_block(258)==p.ERASED
    assert events[-1]['state']=='block-verified'


@pytest.mark.parametrize('fault,programs', [('upload',0),('erase',0),('stage-after-erase',0),('lost-program',1),('readback',1)])
def test_failure_stops_without_retry_and_revokes_permission(media,fault,programs):
    m,d,_=media
    m.inspect();m.authorize_journal_trial(approved=True)
    if fault=='erase':d.blocks[258]=bytes(p.RAW_BLOCK)
    d.fault=fault
    with pytest.raises((ValueError,TimeoutError)):m.write_journal(0,b'a'*2048)
    count=len(d.events)
    with pytest.raises(ValueError):m.erase_block(258)
    assert len(d.events)==count
    assert sum(e[0]=='program' for e in d.events)==programs


def test_journal_only_recovery_checks_every_other_block(media):
    m,d,_=media
    d.blocks[258]=bytes(p.RAW_BLOCK)  # torn trial write, retained original is erased
    m.inspect(journal_trial_recovery=True);m.authorize_journal_trial(approved=True)
    m.erase_block(258)
    d.blocks[100]=bytes(p.RAW_BLOCK)
    with pytest.raises(ValueError):m.inspect(journal_trial_recovery=True)
    with pytest.raises(ValueError):m.authorize_journal_trial(approved=True)


def test_physical_engine_requires_the_exact_session_permit(media,monkeypatch,tmp_path):
    m,d,_=media
    monkeypatch.setattr(p.model,'verify_routes_reader',lambda *a:None)
    after=b'a'*2048+b'\xff'*(p.RAW_BLOCK-2048)
    tx=Transaction([Change(2048,p.ERASED,after,'stage-images')],m.backup_digest)
    with pytest.raises(ValueError):Engine(m,tx)
    m.inspect();token=m.authorize(tx,uboot=tmp_path/'uboot',approved=True)
    with pytest.raises(ValueError):Engine(m,tx,research_authorization=object())
    engine=Engine(m,tx,research_authorization=token)
    engine.prepare();engine.run()
    assert m.read_block(2048)==after
    count=len(d.events)
    engine.run()
    assert len(d.events)==count


def test_resume_accepts_only_journal_bound_progress(media,monkeypatch,tmp_path):
    m,d,_=media
    monkeypatch.setattr(p.model,'verify_routes_reader',lambda *a:None)
    after=b'a'*2048+b'\xff'*(p.RAW_BLOCK-2048)
    tx=Transaction([Change(2048,p.ERASED,after,'stage-images')],m.backup_digest)
    m.inspect();permit=m.authorize(tx,uboot=tmp_path/'uboot',approved=True)
    engine=Engine(m,tx,research_authorization=permit);engine.prepare()
    engine._save(0,True)
    d.blocks[2048]=bytes(p.RAW_BLOCK)  # partial write is allowed only at pending index
    m.inspect(transaction=tx,resume=True)
    permit=m.authorize(tx,uboot=tmp_path/'uboot',approved=True)
    Engine(m,tx,research_authorization=permit).run()
    assert m.read_block(2048)==after
    d.blocks[42]=bytes(p.RAW_BLOCK)
    with pytest.raises(ValueError):m.inspect(transaction=tx,resume=True)


def test_failed_durable_event_prevents_erase(media):
    m,d,_=media
    m.inspect();m.authorize_journal_trial(approved=True)
    def fail(_):raise OSError('disk full')
    m.event=fail
    with pytest.raises(OSError):m.write_journal(0,b'a'*2048)
    assert d.events==[]
    with pytest.raises(ValueError):m.erase_block(258)


def test_torn_journal_peer_does_not_prevent_resume(media,monkeypatch,tmp_path):
    m,d,_=media
    monkeypatch.setattr(p.model,'verify_routes_reader',lambda *a:None)
    after=b'a'*2048+b'\xff'*(p.RAW_BLOCK-2048)
    tx=Transaction([Change(2048,p.ERASED,after,'stage-images')],m.backup_digest)
    m.inspect();permit=m.authorize(tx,uboot=tmp_path/'uboot',approved=True)
    engine=Engine(m,tx,research_authorization=permit);engine.prepare()
    d.blocks[258]=bytes(p.RAW_BLOCK)
    m.inspect(transaction=tx,resume=True)
    permit=m.authorize(tx,uboot=tmp_path/'uboot',approved=True)
    Engine(m,tx,research_authorization=permit).run()
    assert m.read_block(2048)==after


def test_restore_uses_separate_initial_snapshot_and_retains_routes(backup,monkeypatch,tmp_path):
    import shutil
    path,digest=backup
    initial=tmp_path/'initial.raw';shutil.copyfile(path,initial)
    changed=b'a'*2048+b'\xff'*(p.RAW_BLOCK-2048)
    with initial.open('r+b') as f:
        for block in (256,2048,0,240):
            f.seek(block*p.RAW_BLOCK);f.write(changed)
    initial_digest=p.model.file_hash(initial)
    monkeypatch.setattr(p.model,'verify_routes_reader',lambda *a:None)
    d=Device();d.blocks={b:changed for b in (256,2048,0,240)}
    m=p.PhysicalMedia(d,path,digest,initial=initial,initial_digest=initial_digest,event=lambda _:None)
    try:
        tx=Transaction([Change(b,changed,p.ERASED,phase) for b,phase in
                        ((256,'disable-boot'),(2048,'restore-data'),(0,'restore-rom'),(240,'restore-cleanup'))],
                       digest,mode='restore')
        m.inspect();permit=m.authorize(tx,uboot=tmp_path/'uboot',approved=True)
        e=Engine(m,tx,research_authorization=permit);e.prepare();e.run()
        assert all(m.read_block(b)==p.ERASED for b in (256,2048,0,240))
        m.inspect(transaction=tx,resume=True)
        assert m._checked
    finally:m.close()


def test_retained_physical_trial_resumes_lost_ack_without_reprogramming(backup,monkeypatch,tmp_path):
    import prime_phase6_install_trial as trial
    monkeypatch.setattr(trial.model,'private_output',lambda path:path)
    path,digest=backup
    after=b'a'*2048+b'\xff'*(p.RAW_BLOCK-2048)
    tx=Transaction([Change(2048,p.ERASED,after,'stage-images')],digest)
    paths={'backup':path,'uboot':tmp_path/'uboot'}
    monkeypatch.setattr(trial,'checked_plan',lambda *_:(tx,set(),paths,digest))
    monkeypatch.setattr(p.model,'verify_routes_reader',lambda *a:None)
    d=Device()
    monkeypatch.setattr(trial,'Phase6SDP',lambda:d)
    original=d.program_pages
    def lose_ack(block,count):
        original(block,count)
        if block==2048:raise TimeoutError('lost target acknowledgement')
    d.program_pages=lose_ack
    session=tmp_path/'session'
    with pytest.raises(TimeoutError):trial.run({},session,priority='lefony',approved=True)
    d.program_pages=original
    result=trial.run({},session,priority='lefony',approved=True,resume=True)
    assert result['state']=='physical-nand-verified' and not result['boot_confirmed']
    assert len([e for e in d.events if e[0]=='program' and e[1]==2048])==1
    assert p.model.read_block(session/'verified-nand.raw',2048)==after
    count=len(d.events)
    trial.run({},session,priority='lefony',approved=True,resume=True)
    assert len(d.events)==count
    with pytest.raises(ValueError):trial.run({},session,priority='hp',approved=True,resume=True)
    assert len(d.events)==count


def test_trial_authorization_and_signed_plan_precede_usb(monkeypatch,tmp_path):
    import prime_phase6_install_trial as trial
    def forbidden():raise AssertionError('opened USB before validation')
    monkeypatch.setattr(trial,'Phase6SDP',forbidden)
    with pytest.raises(ValueError):trial.run({},tmp_path/'session',priority='lefony')
    with pytest.raises(ValueError):trial.run({},tmp_path/'session',priority='lefony',approved=True)


def test_final_snapshot_rejects_unplanned_bytes(media,tmp_path):
    import prime_phase6_install_trial as trial
    m,d,_=media
    after=b'a'*2048+b'\xff'*(p.RAW_BLOCK-2048)
    tx=Transaction([Change(2048,p.ERASED,after,'stage-images')],m.backup_digest)
    d.blocks[2048]=after
    d.blocks[42]=bytes(p.RAW_BLOCK)
    output=tmp_path/'verified.raw'
    with pytest.raises(ValueError,match='block 42'):
        trial.snapshot_verified(m,tx,output)
    assert not output.exists()
    assert output.with_suffix('.partial').exists()


def test_boot_repair_retains_old_snapshot_and_resumes_lost_program_ack(backup,monkeypatch,tmp_path):
    import shutil
    from prime_phase6_install_trial import inspected_engine
    path,digest=backup;initial=tmp_path/'repair-before.raw';shutil.copyfile(path,initial)
    monkeypatch.setattr(p.model,'verify_routes_reader',lambda *a:None)
    before=b'a'*2048+b'\xff'*(p.RAW_BLOCK-2048)
    after=b'b'*2048+b'\xff'*(p.RAW_BLOCK-2048)
    old=Transaction([Change(240,p.ERASED,before,'stage-recovery')],digest)
    d=Device();d.blocks[240]=old.changes[0].after
    with p.model.NativeBCH() as native:
        for slot,b in enumerate((258,259)):
            page=journal_page(old,2+slot,1,False)
            data,aux=p.model.ECC.swap_marker(page,b'\xff'*10)
            d.blocks[b]=p.model.ECC.encode(data,aux,native)+b'\xff'*(p.RAW_BLOCK-2112)
    with initial.open('r+b') as f:
        for b,raw in d.blocks.items():f.seek(b*p.RAW_BLOCK);f.write(raw)
    m=p.PhysicalMedia(d,path,digest,initial=initial,initial_digest=p.model.file_hash(initial),event=lambda _:None)
    repair=Transaction([Change(240,d.blocks[240],after,'stage-recovery')],digest,mode='repair-boot')
    program=d.program_pages
    def lost_ack(b,n):
        program(b,n)
        if b==240:raise TimeoutError('target programmed, acknowledgement lost')
    try:
        d.program_pages=lost_ack
        with pytest.raises(TimeoutError):inspected_engine(m,repair,tmp_path/'uboot').run()
        d.program_pages=program
        inspected_engine(m,repair,tmp_path/'uboot',resume=True).run()
        assert d.read_block(240)==repair.changes[0].after
        assert sum(e[0]=='program' and e[1]==240 for e in d.events)==1
        assert all(e[1] in (240,258,259) for e in d.events)
    finally:m.close()


def test_pristine_initialization_recovers_torn_journals_but_not_changed_data(media,monkeypatch,tmp_path):
    from prime_phase6_install_trial import inspected_engine
    m,d,_=media
    monkeypatch.setattr(p.model,'verify_routes_reader',lambda *a:None)
    after=b'a'*2048+b'\xff'*(p.RAW_BLOCK-2048)
    tx=Transaction([Change(2048,p.ERASED,after,'stage-images')],m.backup_digest)
    d.blocks[258]=bytes(p.RAW_BLOCK);d.blocks[259]=bytes(p.RAW_BLOCK)
    inspected_engine(m,tx,tmp_path/'uboot',resume=True).run()
    assert d.read_block(2048)==after
    d.blocks[258]=bytes(p.RAW_BLOCK);d.blocks[259]=bytes(p.RAW_BLOCK)
    count=len(d.events)
    with pytest.raises(ValueError):inspected_engine(m,tx,tmp_path/'uboot',resume=True)
    assert len(d.events)==count


def test_retained_restore_resumes_interrupted_final_journal_cleanup(backup,monkeypatch,tmp_path):
    import shutil
    import prime_phase6_restore as restore
    path,digest=backup;initial=tmp_path/'initial.raw';shutil.copyfile(path,initial)
    changed=b'a'*2048+b'\xff'*(p.RAW_BLOCK-2048)
    with initial.open('r+b') as f:f.seek(2048*p.RAW_BLOCK);f.write(changed)
    tx=Transaction([Change(2048,changed,p.ERASED,'restore-data')],digest,mode='restore')
    monkeypatch.setattr(restore.model,'private_output',lambda p:p)
    monkeypatch.setattr(restore.model,'build_restore_plan',lambda *a:(tx,set()))
    monkeypatch.setattr(restore.model,'verify_routes',lambda *a:None)
    monkeypatch.setattr(p.model,'verify_routes_reader',lambda *a:None)
    uboot=tmp_path/'uboot';uboot.write_bytes(b'test')
    d=Device();d.blocks[2048]=changed
    monkeypatch.setattr(restore,'Phase6SDP',lambda:d)
    original=d.erase
    def lose_ack(block,**kw):
        original(block,**kw)
        if block==259 and d.read_block(2048)==p.ERASED and d.read_block(258)==p.ERASED:
            raise TimeoutError('final cleanup ACK lost')
    d.erase=lose_ack
    output=tmp_path/'restore'
    with pytest.raises(TimeoutError):restore.run(initial,path,digest,uboot,output,approved=True)
    d.erase=original;count=len(d.events)
    result=restore.run(initial,path,digest,uboot,output,approved=True,resume=True)
    assert result['state']=='restore-verified' and not result['boot_confirmed']
    assert len(d.events)==count  # all target bytes already present: no replay
    assert p.model.file_hash(output/'verified-restore.raw')==digest
