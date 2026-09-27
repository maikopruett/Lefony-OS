# SPDX-License-Identifier: GPL-3.0-or-later
"""Companion action/approval tests; fake media only, never enumerate USB."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import prime_dual_service as s


@pytest.fixture
def service(tmp_path,monkeypatch):
    c={'state':tmp_path,'bundle':{'backup':str(tmp_path/'original.raw'),'backup_sha256':'ab'*32,
       'source_profile':'lefony-menu1'},'binary':'binary','imx':'imx'}
    calls=[];tx=SimpleNamespace(id=b't'*32,changes=[1,2])
    monkeypatch.setattr(s,'load',lambda _:c)
    monkeypatch.setattr(s,'checked_plan',lambda *a:(tx,set(),{},b'b'*32))
    monkeypatch.setattr(s,'enter',lambda *a,**kw:calls.append('enter'))
    monkeypatch.setattr(s,'Phase6SDP',lambda:SimpleNamespace(close=lambda:None))
    monkeypatch.setattr(s,'capture',lambda *a,**kw:{'sha256':'cd'*32})
    monkeypatch.setattr(s,'candidate_release',lambda _:1)
    monkeypatch.setattr(s,'install',lambda *a,**kw:calls.append(('install',kw['resume'])) or {'verified':True})
    return c,calls


def review():return s.dispatch('config','review',{'action':'install','priority':'hp'})


def test_choices_approval_use_and_boot_completion_are_separate(service):
    c,calls=service;r=review()
    assert r['state']=='review' and r['priority']=='hp' and calls==['enter']
    assert 'approvalHash' not in r and 'bundle' not in r
    result=s.dispatch('config','run',{'session':r['id'],'approval':r['approval']})
    assert result['state']=='verified' and result['confirmed']==[]
    assert calls==['enter','enter',('install',False)]
    with pytest.raises(ValueError):s.dispatch('config','run',{'session':r['id'],'approval':r['approval']})
    confirm=s.dispatch('config','confirm',{'session':r['id'],'os':'hp'})
    assert confirm['state']=='verified' and confirm['confirmed']==['hp']
    assert s.dispatch('config','current',{})['id']==r['id']


def test_expired_review_stops_before_recovery(service,monkeypatch):
    _,calls=service;r=review();count=len(calls)
    monkeypatch.setattr(s.time,'time',lambda:r['approvalExpires']+1)
    with pytest.raises(ValueError,match='expired'):
        s.dispatch('config','run',{'session':r['id'],'approval':r['approval']})
    assert len(calls)==count


def test_disconnect_retains_same_transaction_and_never_retries(service,monkeypatch):
    c,calls=service;r=review()
    def fail(*a,**kw):
        (c['state']/r['id']/'operation').mkdir();calls.append('failed-write');raise TimeoutError('disconnect')
    monkeypatch.setattr(s,'install',fail)
    with pytest.raises(TimeoutError):s.dispatch('config','run',{'session':r['id'],'approval':r['approval']})
    assert calls.count('failed-write')==1
    assert s.dispatch('config','current',{})['state']=='reconnect'
    monkeypatch.setattr(s,'install',lambda *a,**kw:calls.append(('resume',kw['resume'])) or {})
    assert s.dispatch('config','resume',{'session':r['id']})['state']=='verified'
    assert calls[-1]==('resume',True)


@pytest.mark.parametrize('action,payload',[
    ('review',{'action':'install','priority':'hp','path':'/tmp/untrusted'}),
    ('review',{'action':'erase','priority':'hp'}),('run',{'session':'../escape','approval':'x'}),
    ('confirm',{'session':'a'*32,'os':'hp','verified':True}),('current',{'path':'x'}),
])
def test_browser_cannot_supply_paths_or_unreviewed_operations(service,action,payload):
    _,calls=service
    with pytest.raises(ValueError):s.dispatch('config',action,payload)
    assert not calls


def test_space_check_precedes_reset(service,monkeypatch):
    _,calls=service
    monkeypatch.setattr(s.shutil,'disk_usage',lambda _:SimpleNamespace(free=0))
    with pytest.raises(ValueError,match='space'):review()
    assert not calls


@pytest.mark.parametrize('approved,expected',[(False,'recovery-required'),(True,'reconnect')])
def test_restart_reports_abandoned_work_without_replaying_it(service,approved,expected):
    c,calls=service;r=review();p=c['state']/r['id']/'state.json'
    state=json.loads(p.read_text());state.update(state='working' if approved else 'preparing',approvalUsed=approved)
    p.write_text(json.dumps(state));count=len(calls)
    assert s.dispatch('config','current',{})['state']==expected
    assert len(calls)==count
