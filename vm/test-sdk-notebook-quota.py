#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real Notebook replacement, failed growth, retry and shrinking at the app quota."""
import argparse
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from cli import package
from files_device import FileClient
from preview import inspect_layout
from replay import Controls
from runner import exercise
from workspace import opened
from sdk_notebook_probe import wait_notebook
LIMIT=32*1024*1024
ORIGINAL=b'LFNOTE3\nL\n0 0 07\n2+3*4\n'
OLD_EXPORT=b'Last complete export\n'+b'X'*200


def observe_storage(normal,firmware,folder,elapsed,records):
    # Read-only progress evidence for the intentionally large 32 MiB workload.
    # Keep integrity verification enabled; do not substitute a smaller quota.
    symbols=firmware.with_name(firmware.stem+'-debug.elf').resolve()
    assert symbols.is_file(),symbols
    # Reuse the layout inspector's server: QEMU does not replace an already
    # listening GDB endpoint when another name is requested.
    endpoint=Path(normal.channel.socket.getpeername()).parent/'layout-gdb'
    normal.execute('human-monitor-command',{'command-line':'gdbserver unix:'+str(endpoint)+',server=on,wait=off'})
    owner="'PrimeG2::AppManagement::(anonymous namespace)::"
    expressions=[owner+"sFiles'.m_phase",owner+"sVolume'.m_state"]
    expressions.extend(owner+"sVolume'.m_documents."+name for name in
        ('m_phase','m_referenceCursor','m_referenceCount','m_cursor'))
    script=folder/'storage-progress.gdb'
    script.write_text('set pagination off\nset confirm off\nfile '+json.dumps(str(symbols))+'\ntarget remote '+str(endpoint)+'\n'+
        ''.join('print '+expression+'\n' for expression in expressions)+'detach\nquit\n')
    result=subprocess.run([shutil.which('arm-none-eabi-gdb'),'-q','-nx','-batch','-x',str(script)],capture_output=True,text=True,timeout=30)
    name='storage-progress-'+str(len(records))+'.log';(folder/name).write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stderr
    records.append({'action':'storage-progress','elapsed_seconds':elapsed,'log':name})
    print('Storage progress:',folder.name,elapsed,result.stdout,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('firmware','previous-notebook','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--modes',nargs='+',choices=('baseline','current'),default=['baseline','current'])
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True)
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm'
    report={'schema':1,'status':'running','physical':'not_tested','sdk_sha256':identity(ROOT/'sdk'),
        'firmware_sha256':digest(args.firmware),'qemu_sha256':digest(qemu),'cases':[]}
    write_json(out/'report.json',report)
    try:
        with tempfile.TemporaryDirectory(prefix='notebook-quota-') as temp:
            directory=Path(temp);helper=directory/'helper';helper.mkdir()
            fixture=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](helper)
            for mode,source in [('baseline',args.previous_notebook),('current',ROOT/'sdk/examples/notebook')]:
                if mode not in args.modes:continue
                project=directory/mode;shutil.copytree(source,project,ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json'))
                artifact=package(project,'debug');retained=out/mode;retained.mkdir()
                for name in ('app-debug.elf','build.json',artifact.name):shutil.copyfile(project/'build'/name,retained/name)
                for phase in ('install','full','cold'):
                    folder=retained/phase;folder.mkdir();records=[];observed={}
                    def controls(channel):
                        normal=Controls(channel,folder)
                        def key(name,count=1):
                            for _ in range(count):normal.key(name)
                        def tap(x,y):normal.run({'steps':[{'touch':[[1,x,y]]},{'touch':[]}]},records)
                        def ready():
                            wait_notebook(normal,records,timeout=120,observe=lambda elapsed:observe_storage(normal,args.firmware,folder,elapsed,records))
                        def snapshot(name,title=None,field=None,message=None):
                            ready();normal.run({'steps':[{'capture':name}]},records)
                            details=folder/name;details.mkdir();layout=inspect_layout(normal,retained/'app-debug.elf',details)
                            nodes={node['id']:node for node in layout['nodes']}
                            if title:assert nodes[50]['name']==title,(name,nodes[50])
                            if field is not None:assert nodes[10]['name']==field,(name,nodes[10])
                            if message:assert nodes[62]['name'].startswith(message),(name,nodes[62])
                        try:
                            ready()
                            if phase=='full':
                                snapshot('full','Notebook');key('ok');tap(260,20);key('seven',5);tap(50,205)
                                if mode=='baseline':snapshot('replacement-rejected','Edit expression','77777','Save failed')
                                else:
                                    snapshot('replacement-saved','Notebook',message='Saved')
                                    key('ok');tap(260,20);key('seven',6);tap(50,205)
                                    snapshot('growth-rejected','Edit expression','777777','Save unconfirmed')
                                    key('left');key('backspace');key('ok');snapshot('retry-saved','Notebook',message='Saved')
                                    key('ok');tap(260,20);key('seven');tap(50,205)
                                    snapshot('shrunk','Notebook',message='Saved');tap(260,205);snapshot('exported','Notebook',message='Export ready')
                            elif phase=='cold':snapshot('cold','Notebook')
                            normal.key('home');channel.wait_for_storage();files=FileClient(channel.app_client)
                            if phase!='install':
                                expected=ORIGINAL if mode=='baseline' else b'LFNOTE3\nL\n0 0 07\n7\n'
                                exported=OLD_EXPORT if mode=='baseline' else b'# Notebook DEG AUTO 7 / x=1\n7 = 7\n'
                                for name,data in [('notebook.txt',expected),('export.txt',exported)]:
                                    files.export_file('notebook',name,folder/name);assert (folder/name).read_bytes()==data
                                observed['space']=files.info('notebook')
                                assert observed['space']['quota_bytes']==LIMIT
                                expected_usage=LIMIT-len(ORIGINAL)-len(OLD_EXPORT)+len(expected)+len(exported)
                                assert observed['space']['quota_committed_bytes']==expected_usage
                                assert 'notebook.tmp' not in {e['path'] for e in files.list('notebook')['entries']}
                        finally:
                            write_json(folder/'records.json',records);normal.close()
                    with opened(project,'quota') as (workspace,_):
                        if phase=='full':
                            filler=directory/'filler';filler.write_bytes(bytes(LIMIT-len(ORIGINAL)-len(OLD_EXPORT)))
                            for name,data in [('notebook.txt',ORIGINAL),('export.txt',OLD_EXPORT),('filler',None)]:
                                path=directory/name
                                if data is not None:path.write_bytes(data)
                                subprocess.run([fixture,'put-file',workspace/'nand.overlay','notebook',name,path],check=True,stdout=subprocess.DEVNULL,timeout=90)
                        result=exercise(artifact,qemu,args.firmware,workspace=workspace,controls=controls)
                    assert result['result']==1 and result['os_responsive'],result
                    report['cases'].append({'mode':mode,'phase':phase,'runtime':result,'records':records,**observed})
                    write_json(out/'report.json',report);print('PASS:',mode,phase,flush=True)
        assert report['sdk_sha256']==identity(ROOT/'sdk'),'SDK changed during qualification'
        report.update(status='passed',sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),ROOT/'sdk/examples/notebook/src/main.cpp',
            ROOT/'sdk/examples/notebook/src/document.h',ROOT/'sdk/include/lefony/file_writer.h')})
        write_json(out/'report.json',report)
    except Exception as exc:
        report.update(status='failed',error=str(exc));write_json(out/'report.json',report);raise


if __name__=='__main__':main()
