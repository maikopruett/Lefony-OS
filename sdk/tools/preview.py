# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual ARM preview, read-only GDB layout capture and a source-save watch loop."""
import base64
from contextlib import ExitStack
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from build import digest,exclusive,write_json,project_lock
from sdk_environment import SDK
from replay import Controls,load
from runner import exercise
from preview_data import fixtures,fixture_identity,Checkpoints,compose,PUBLIC

HEADER=struct.Struct('<6I')
NODE=struct.Struct('<2I8i2I32s96s')
KINDS=('unknown','label','button','list row','text field','progress','custom','choice','slider','dialog','scrollbar','menu','menu item')


def decode_layout(data):
    if len(data) not in (11288,11292):raise ValueError('Unexpected layout frame size')
    magic,schema,size,sequence,count,overflow=HEADER.unpack_from(data)
    if magic!=0x4955464c or (schema,size) not in ((1,11288),(2,11292)) or size!=len(data) or sequence&1 or not sequence or count>64:
        raise ValueError('Layout frame is absent or drawing is incomplete')
    ready=struct.unpack_from('<I',data,11288)[0] if schema==2 else 1
    if ready not in (0,1):raise ValueError('Invalid layout input readiness')
    nodes=[]
    for index in range(count):
        values=NODE.unpack_from(data,HEADER.size+NODE.size*index)
        identifier,kind=values[:2];bounds=values[2:6];clip=values[6:10];state,line=values[10:12]
        name,file=(value.split(b'\0',1)[0].decode('utf-8',errors='replace') for value in values[12:])
        x,y,w,h=bounds;cx,cy,cw,ch=clip
        nodes.append({'id':identifier,'kind':KINDS[kind] if kind<len(KINDS) else 'unknown','bounds':bounds,
            'clip':clip,'state':state,'line':line,'name':name,'file':file,
            'clipped':w>0 and h>0 and (x<cx or y<cy or x+w>cx+cw or y+h>cy+ch)})
    return {'schema':schema,'sequence':sequence,'input_ready':bool(ready),'overflow':overflow,'nodes':nodes}


def inspect_layout(normal,elf,output,*,name='layout'):
    from gdb_transport import gdb_quote, remote_command
    from local_transport import qemu_path
    gdb=shutil.which('arm-none-eabi-gdb')
    if not gdb:raise ValueError('Layout inspection requires arm-none-eabi-gdb; run doctor')
    folder=normal.channel.session_directory
    if name not in ('layout','initial-layout'):raise ValueError('Invalid layout capture phase')
    endpoint=folder/'layout-gdb';dump=folder/(name+'.bin')
    address='unix:'+qemu_path(endpoint)+',server=on,wait=off'
    if not getattr(normal,'layout_gdb_started',False):
        normal.execute('human-monitor-command',{'command-line':'gdbserver '+json.dumps(address,ensure_ascii=False)})
        normal.layout_gdb_started=True
    # GDB commands are fixed except quoted tool-generated local paths.
    # A completed frame is a nonzero even sequence. Schema 2 also distinguishes
    # an interactive screen from a loading screen that cannot handle input.
    # Watch the sequence, which inspectionEnd updates after readiness is set.
    # The subprocess deadline also bounds a missing inspectionEnd call.
    script=folder/(name+'.gdb')
    script.write_text('set pagination off\nset confirm off\nfile '+gdb_quote(elf.resolve())+'\n'+
        remote_command(endpoint)+'\n'+
        'set $layout_waiting = lefony_ui_debug.sequence == 0 || (lefony_ui_debug.sequence & 1)\n'+
        'if sizeof(lefony_ui_debug) == 11292\n'+
        'set $layout_waiting = $layout_waiting || lefony_ui_debug.inputReady == 0\n'+
        'end\n'+
        'if $layout_waiting\n'+
        'watch -location lefony_ui_debug.sequence\n'+
        'if sizeof(lefony_ui_debug) == 11292\n'+
        'condition $bpnum lefony_ui_debug.sequence != 0 && (lefony_ui_debug.sequence & 1) == 0 && lefony_ui_debug.inputReady == 1\n'+
        'else\n'+
        'condition $bpnum lefony_ui_debug.sequence != 0 && (lefony_ui_debug.sequence & 1) == 0\n'+
        'end\n'+
        'continue\n'+
        'delete $bpnum\n'+
        'end\n'+
        # GDB dump's filename parser does not support quotes. Use the private
        # session as cwd and a fixed basename, including on Windows with spaces.
        'dump binary memory '+name+'.bin &lefony_ui_debug ((char*)&lefony_ui_debug)+sizeof(lefony_ui_debug)\n'+
        'detach\nquit\n', encoding='utf-8', newline='\n')
    log=output/(name+'-gdb.log')
    try:
        result=subprocess.run([gdb,'-q','-nx','-batch','-x',str(script)],cwd=folder,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    except subprocess.TimeoutExpired as error:
        # TimeoutExpired may retain bytes even with text=True. Keep the last
        # debugger position so a missing inspectionEnd is diagnosable.
        parts=[part.decode('utf-8',errors='replace') if isinstance(part,bytes) else part or ''
               for part in (error.stdout,error.stderr)]
        log.write_text(''.join(parts),encoding='utf-8',newline='\n')
        raise ValueError(f'Layout inspection did not reach an input-ready completed frame within 30 seconds; see {log.name}') from error
    log.write_text(result.stdout+result.stderr,encoding='utf-8',newline='\n')
    if result.returncode or not dump.exists():raise ValueError(f'No layout records: build with debug profile and call inspectionBegin/End; see {log.name}')
    data=dump.read_bytes()
    (output/(name+'.bin')).write_bytes(data)
    value=decode_layout(data);write_json(output/(name+'.json'),value);return value


def source_state(project,fixture_dir=None):
    files=[]
    for name in ('app.json','project.json','assets.json','sdk.lock.json'):
        path=project/name
        if path.exists():files.append(path)
    for name in ('src','assets','tests'):
        folder=project/name
        if folder.exists():files.extend(path for path in folder.rglob('*') if path.is_file())
    state={str(path.relative_to(project)):digest(path) for path in sorted(files)}
    if fixture_dir:
        state['fixtures']=fixture_identity(fixture_dir)
    return hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest()


def render(output,state):
    image=output/'frame.png';layout=state.get('layout',{})
    picture='';rows=[]
    if image.exists():
        picture='<div class="screen"><img width="640" height="480" alt="Actual ARM emulator frame" src="data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode()+'"><svg viewBox="0 0 320 240">'
        for node in layout.get('nodes',[]):
            x,y,w,h=node['bounds'];color='#fb7185' if node['clipped'] else '#38bdf8'
            picture+=f'<rect x="{x}" y="{y}" width="{max(0,w)}" height="{max(0,h)}" stroke="{color}"><title>'+html.escape(f"{node['id']} {node['name']} — {node['file']}:{node['line']}")+'</title></rect>'
        picture+='</svg></div>'
    for node in layout.get('nodes',[]):
        rows.append('<tr>'+''.join('<td>'+html.escape(str(value))+'</td>' for value in
            (node['id'],node['kind'],node['name'],node['bounds'],node['clip'],node['state'],f"{node['file']}:{node['line']}"))+ '</tr>')
    stale=state['status']!='ready'
    failure=(state.get('emulator_failure') or {}).get('directory','')
    details=''
    if isinstance(failure,str) and re.fullmatch(r'failure-[a-zA-Z0-9_-]{1,64}',failure):
        folder=output/'emulator'/failure
        if (folder/'failure.json').is_file():
            details='<p>Emulator failure: '+', '.join('<a href="emulator/'+failure+'/'+name+'">'+label+'</a>'
                for name,label in (('failure.json','details'),('stderr.log','host log'),('uart.log','guest log')))+'.</p>'
    page='''<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="3"><title>Lefony ARM preview</title>
<style>body{background:#101923;color:#e2e8f0;font:15px system-ui;margin:24px}h1{font-size:24px}.status{padding:12px;background:STATUSCOLOR;border-radius:8px} .screen{position:relative;width:640px;height:480px;margin-top:20px}.screen img{image-rendering:pixelated}.screen svg{position:absolute;inset:0;width:100%;height:100%}rect{fill:transparent;stroke-width:.5}rect:hover{fill:#38bdf830}table{border-collapse:collapse;margin-top:24px}td,th{padding:8px;border-bottom:1px solid #334155;text-align:left}pre{white-space:pre-wrap}a{color:#7dd3fc}</style>
<h1>Lefony ARM preview</h1><p class="status">STATUS</p><p>FRAMEINFO</p>PICTURE
<p>Blue: widget bounds. Pink: clipped bounds. Hover a box for its source location.</p>
<table><thead><tr><th>ID</th><th>Kind</th><th>Label</th><th>Bounds</th><th>Clip</th><th>State flags</th><th>Source</th></tr></thead><tbody>ROWS</tbody></table><pre>ERROR</pre>DETAILS'''
    frame_info='Last successful frame; '+state.get('data_policy','') if image.exists() else 'No successful frame yet.'
    for key,value in {'STATUSCOLOR':'#783b21' if stale else '#14532d','STATUS':html.escape('STALE — '+state['status'] if stale else 'Ready — actual ARM package'),
                      'FRAMEINFO':html.escape(frame_info),'PICTURE':picture,'ROWS':''.join(rows),'ERROR':html.escape(state.get('error','')),'DETAILS':details}.items():page=page.replace(key,value)
    temporary=output/'index.html.tmp';temporary.write_text(page,encoding='utf-8',newline='\n');temporary.replace(output/'index.html')


def once(project,qemu,firmware,*,scenario=None,fixture_dir=None,inspect=True,reset_data=False,fresh_data=False):
    from PIL import Image
    from lfapp import unpack
    from archive_device import Client as ArchiveClient
    project=project.resolve();output=project/'build/preview';output.mkdir(parents=True,exist_ok=True)
    with exclusive(output/'.lock'),ExitStack() as resources:
        previous={}
        try:previous=json.loads((output/'status.json').read_text(encoding='utf-8'))
        except (ValueError,OSError):pass
        policy='Fresh synthetic data; outputs discarded' if fresh_data else 'Committed preview files and private data retained'
        state={**previous,'status':'building','error':'','data_policy':policy}
        # Retain the last frame/checkpoint, but never attribute an earlier
        # emulator exit to this attempt's build or validation failure.
        state.pop('emulator_failure',None)
        write_json(output/'status.json',state);render(output,state)
        started=time.monotonic()
        try:
            if reset_data and fresh_data:raise ValueError('Choose either --reset-data or --fresh-data')
            checkpoints=None;receipt=None;saved=None
            if not fresh_data:
                checkpoints=Checkpoints(project);resources.enter_context(exclusive(checkpoints.directory/'.lock'))
                try:receipt=checkpoints.read()
                except ValueError:
                    if not reset_data:raise
                saved=None if reset_data else receipt
            seed_identity=fixture_identity(fixture_dir)
            if saved:
                if fixture_dir is not None and seed_identity!=saved['fixture_sha256']:
                    raise ValueError('Preview fixtures changed; use --reset-data to reseed without overwriting saved edits')
                seed_identity=saved['fixture_sha256']
            if not (project/'sdk.lock.json').exists():write_json(project/'sdk.lock.json',project_lock(project,SDK))
            initial=source_state(project,fixture_dir)
            if scenario and (scenario.is_absolute() or '..' in scenario.parts):raise ValueError('Scenario must be a project-relative replay path')
            replay=load(project/scenario) if scenario else {'schema':1,'name':'preview','steps':[]}
            with (output/'build.log').open('wb') as log:
                from sdk_environment import cli_command
                build=subprocess.run([*cli_command(),'--project',str(project),
                    'package','--profile','debug'],stdout=log,stderr=subprocess.STDOUT,timeout=240)
            if build.returncode:raise ValueError((output/'build.log').read_text(encoding='utf-8',errors='replace')[-16000:])
            value=json.loads((project/'app.json').read_text(encoding='utf-8'))
            artifact=project/'build'/f"{value['id']}-{value['version']}.lfapp"
            built=time.monotonic();metadata,_=unpack(artifact.read_bytes())
            from diagnostics import matching_symbols
            symbols=matching_symbols(project,artifact)
            package_hash=digest(artifact)
            records=[]
            with tempfile.TemporaryDirectory(prefix='lefony-preview-result-') as temp:
                captured=Path(temp);layout={}
                shutil.copyfile(artifact,captured/'app.lfapp')
                shutil.copyfile(symbols,captured/'app-debug.elf')
                seed=None;keys=[];prepared=None
                if checkpoints or fixture_dir is not None:
                    seed=captured/'seed.lfarchive'
                    signed,prepared=compose(artifact,seed,saved=checkpoints.path(saved) if saved else None,
                        saved_hash=saved['archive'] if saved else None,fixture_dir=fixture_dir if not saved else None)
                    (captured/'app.lfapp').write_bytes(signed);keys=[PUBLIC]
                    current=prepared.snapshots[0]
                    # A normal fresh install already has this exact empty
                    # state. Pending pairs and retained version/schema state
                    # still require the full restore, even without file bytes.
                    if (len(prepared.snapshots)==1 and not current.private.size and not current.entries and
                        current.data_schema==metadata.get('data_schema',0) and
                        prepared.high_version==tuple(map(int,metadata['version'].split('.')))):
                        seed=None
                def prepare(client):
                    if seed:ArchiveClient(client).restore(seed,[PUBLIC],replace=True)
                def controls(channel):
                    nonlocal layout
                    from replay import control_session
                    with control_session(Controls(channel,captured)) as normal:
                        # APP OPEN acknowledges launch before an ordinary main
                        # has necessarily drawn. Do not send input into startup.
                        if inspect:inspect_layout(normal,captured/'app-debug.elf',output,name='initial-layout')
                        normal.run(replay,records)
                        if int(channel.command('APP DIAG 9').split()[1]):raise ValueError('Preview app faulted; saved data was preserved')
                        if metadata.get('required_capabilities',0)&16 and int(channel.command('APP DIAG 15').split()[1]):
                            exit_code=int(channel.command('APP DIAG 21').split()[1])
                            if exit_code:raise ValueError(f'Preview program exited with status {exit_code}; saved data was preserved')
                        if inspect:layout=inspect_layout(normal,captured/'app-debug.elf',output)
                        normal.execute('screendump',{'filename':str(captured/'frame.ppm')})
                        if checkpoints:
                            # Capture the visible UI first. Normal Home discards
                            # unsaved edits and closes streams before the signed
                            # archive reads committed data through real USB.
                            normal.key('home');channel.app_client.wait()
                            ArchiveClient(channel.app_client).export(metadata['id'],captured/'saved.lfarchive',[PUBLIC])
                if checkpoints or fixture_dir is not None:
                    from workspace import opened
                    with opened(captured/'media','preview') as (media,_):
                        run=exercise(captured/'app.lfapp',qemu,firmware,controls=controls,prepare_workspace=prepare,workspace=media,public_keys=keys,diagnostics_dir=output/'emulator')
                else:run=exercise(captured/'app.lfapp',qemu,firmware,controls=controls,diagnostics_dir=output/'emulator')
                if run['result']!=1 or not run['os_responsive']:raise ValueError('Preview app faulted; inspect run.json')
                if initial!=source_state(project,fixture_dir):raise ValueError('Source or fixtures changed during preview; rebuilding on next save')
                with Image.open(captured/'frame.ppm') as frame:frame.save(output/'frame.next.png')
                if checkpoints:state['checkpoint']=checkpoints.commit(captured/'saved.lfarchive',seed_identity,receipt)
                (output/'frame.next.png').replace(output/'frame.png')
            state={'schema':1,'status':'ready','source_sha256':initial,'package_sha256':package_hash,
                'firmware_sha256':digest(firmware),'qemu_sha256':digest(qemu),'layout':layout,'runtime':run,'steps':records,
                'checkpoint':state.get('checkpoint') if checkpoints else None,'reset_data':reset_data,'fresh_data':fresh_data,
                'data_policy':state['data_policy'],'timings':{'build_seconds':built-started,'total_seconds':time.monotonic()-started},'error':''}
        except KeyboardInterrupt:
            state.update(status='cancelled',error='Preview interrupted; the checkpoint receipt records the last saved data.',
                elapsed_seconds=time.monotonic()-started)
            write_json(output/'status.json',state);render(output,state)
            raise
        except (OSError,ValueError,RuntimeError,AssertionError,subprocess.SubprocessError) as error:
            state.update(status='failed',error=str(error),elapsed_seconds=time.monotonic()-started)
            if hasattr(error,'emulator_failure'):state['emulator_failure']=error.emulator_failure
        write_json(output/'status.json',state);render(output,state);return state


def watch(project,qemu,firmware,*,scenario=None,fixture_dir=None,inspect=True,reset_data=False,fresh_data=False):
    previous=None
    while True:
        try:current=source_state(project,fixture_dir)
        except (OSError,ValueError):current=None
        if current!=previous or previous is None:
            result=once(project,qemu,firmware,scenario=scenario,fixture_dir=fixture_dir,inspect=inspect,reset_data=reset_data,fresh_data=fresh_data)
            print(json.dumps({'status':result['status'],'preview':str(project/'build/preview/index.html'),'error':result.get('error','')}),flush=True)
            # A source change during the run must trigger a subsequent rebuild.
            previous=current
            if result['status']=='ready':reset_data=False
        time.sleep(.5)
