# SPDX-License-Identifier: GPL-3.0-or-later
"""Project/target-library packaging correspondence without hardware access."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'sdk/tools'))
import native_desktop_project as project
import package_native_desktop_sources as sources


def sha(data):return hashlib.sha256(data).hexdigest()


def put(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);return path


def archive(path,files):
    with tarfile.open(path,'w:gz') as tar:
        for name,data in files.items():
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;tar.addfile(info,io.BytesIO(data))
    return path


@pytest.fixture
def newlib(tmp_path):
    root=tmp_path/'repo';sdk=root/'sdk';candidate=tmp_path/'newlib'
    source=b'original newlib source';header=b'adjusted descriptor';license=b'original terms'
    spec={'profile':'foreground-newlib-1','version':'1','source_sha256':sha(source),'target':'ARM fixture',
          'heap_bytes':8380416,'configure_options':['fixture'],'source_adjustments':{'stdio-descriptor-32-v1':{'after_sha256':sha(header)}}}
    put(sdk/'contracts/newlib.json',json.dumps(spec).encode());put(sdk/'contract.json',b'{"compiler":"16.2.0"}')
    put(root/'scripts/build_sdk_newlib.py',b'# fixture reproduction recipe\n')
    put(candidate/'newlib-1.tar.gz',source);put(candidate/'COPYING.NEWLIB',license)
    put(candidate/'install/arm-none-eabi/include/sys/reent.h',header)
    libs={}
    for name in ('libc.a','libm.a'):
        data=('ARM archive '+name).encode();put(candidate/'install/arm-none-eabi/lib'/name,data);libs[name]={'sha256':sha(data),'bytes':len(data)}
    report={k:spec[k] for k in ('version','source_sha256','target','configure_options','source_adjustments')}
    report.update(compiler='16.2.0',headers={'sys/reent.h':sha(header)},libraries=libs,license_sha256=sha(license))
    put(candidate/'candidate.json',json.dumps(report).encode())
    return sdk,candidate


def test_newlib_sources_and_copy_bind_actual_selected_files(newlib,tmp_path):
    sdk,candidate=newlib;record=project.newlib_record(sdk,candidate)
    component=project.collect_newlib(sdk,candidate,tmp_path/'materials')
    project.verify_newlib_materials(sdk,tmp_path/'materials',{'components':[component]},record)
    stage=tmp_path/'stage'
    for name in record['files']:put(stage/name,(candidate/name).read_bytes())
    project.verify_newlib_copy(stage,record)
    assert not record['runtime_qualified'] and len(record['files'])==6


@pytest.mark.parametrize('change',['modified','missing','extra','symlink'])
def test_newlib_bundle_changes_rejected(newlib,tmp_path,change):
    sdk,candidate=newlib;record=project.newlib_record(sdk,candidate);stage=tmp_path/'stage'
    for name in record['files']:put(stage/name,(candidate/name).read_bytes())
    p=stage/'install/arm-none-eabi/lib/libc.a'
    if change=='modified':p.write_bytes(b'changed')
    elif change=='missing':p.unlink()
    elif change=='extra':put(stage/'extra',b'x')
    else:p.unlink();p.symlink_to(candidate/'install/arm-none-eabi/lib/libc.a')
    with pytest.raises(ValueError):project.verify_newlib_copy(stage,record)


@pytest.mark.parametrize('change',['recipe','source','notice','different_sysroot'])
def test_newlib_source_changes_rejected(newlib,tmp_path,change):
    sdk,candidate=newlib;record=project.newlib_record(sdk,candidate)
    materials=tmp_path/'materials';component=project.collect_newlib(sdk,candidate,materials)
    if change=='different_sysroot':record['candidate_sha256']='1'*64
    else:
        name={'recipe':'recipe/scripts/build_sdk_newlib.py','source':'sources/newlib-1.tar.gz','notice':'notices/COPYING.NEWLIB'}[change]
        (materials/'arm-none-eabi-newlib'/name).write_bytes(b'changed')
    with pytest.raises(ValueError):project.verify_newlib_materials(sdk,materials,{'components':[component]},record)


@pytest.fixture
def inputs(tmp_path):
    firmware=put(tmp_path/'firmware.elf',b'VM ELF');qemu=put(tmp_path/'qemu.exe',b'Windows QEMU')
    log=put(tmp_path/'build.log',b'original successful build log')
    prepared={'prepared-firmware/main.cpp':b'firmware source'}
    manifest={'schema':1,'firmware_sha256':sha(firmware.read_bytes()),'qemu_input_sha256':sha(qemu.read_bytes()),'archives':{},'evidence':{}}
    for name,files in [('lefony',{'lefony/sdk/tools/cli.py':b'CLI'}),('qemu-prime',{'qemu/main.c':b'QEMU'}),('prepared-firmware',prepared)]:
        p=archive(tmp_path/(name+'.tar.gz'),files);manifest['archives'][name]={'file':p.name,'sha256':sources.digest(p),'bytes':p.stat().st_size}
    report={'status':'passed','exit_code':0,'byte_identical':True,'expected_firmware':{'elf':manifest['firmware_sha256']},
            'rebuilt_firmware':{'elf':manifest['firmware_sha256']},'archive_sha256':manifest['archives']['prepared-firmware']['sha256'],
            'build_log_sha256':sources.digest(log),'command':['make','PLATFORM=prime_g2_vm'],
            'files':{n:{'bytes':len(data),'mode':0o644,'sha256':sha(data)} for n,data in prepared.items()}}
    rp=put(tmp_path/'rebuild.json',json.dumps(report).encode())
    for name,p in [('firmware-rebuild',rp),('firmware-build-log',log)]:manifest['evidence'][name]={'file':p.name,'sha256':sources.digest(p),'bytes':p.stat().st_size}
    path=put(tmp_path/'project.json',json.dumps(manifest).encode())
    materials=tmp_path/'materials';candidate={'status':'passed','qemu_sha256':manifest['qemu_input_sha256'],'source_sha256':manifest['archives']['qemu-prime']['sha256']}
    name='windows-qemu/inputs/qemu/candidate.json';cp=put(materials/name,json.dumps(candidate).encode())
    source_name='windows-qemu/inputs/qemu/source.tar.gz'
    sp=put(materials/source_name,(tmp_path/'qemu-prime.tar.gz').read_bytes())
    sm={'platform':'windows-AMD64','components':[{'component':'windows-qemu','files':{name:sources.digest(cp),source_name:sources.digest(sp)}}]}
    return path,firmware,qemu,materials,sm,manifest,report


def test_project_evidence_retained_and_matches_selected_binaries(inputs,tmp_path):
    path,fw,qemu,materials,sm,manifest,_=inputs
    result=project.verify_project(path,fw,qemu,materials,sm)
    assert result['retained_byte_identical_rebuild'] and not result['firmware_rebuilt_this_run']
    assert result['firmware_source_files']==1 and not result['native_windows_qualified']
    (materials/'manifest.json').write_text(json.dumps({'components':[]}))
    out=tmp_path/'output';sources.package(materials,out,('lefony-qemu',),project_sources=path)
    with tarfile.open(out/'lefony-sdk-source-lefony-qemu.tar.gz') as tar:
        archived=json.load(tar.extractfile('manifest.json'))
        for item in archived['evidence'].values():assert sha(tar.extractfile(item['file']).read())==item['sha256']


def test_project_assembly_checks_native_inputs_and_preserves_evidence(inputs,tmp_path,monkeypatch):
    import collect_native_windows_sources as native
    path,fw,qemu,materials,sm,manifest,_=inputs
    (materials/'manifest.json').write_text(json.dumps(sm))
    shutil.copyfile(path.parent/'qemu-prime.tar.gz',materials/'windows-qemu/inputs/qemu/source.tar.gz')
    checked=[]
    monkeypatch.setattr(native,'verify_materials',lambda folder,record: checked.append((folder,record)))
    output=tmp_path/'assembled'
    result=project.assemble_project_sources(output,path.parent/'lefony.tar.gz',path.parent/'prepared-firmware.tar.gz',
        path.parent/'rebuild.json',path.parent/'build.log',fw,qemu,materials)
    assert checked==[(materials,sm)]
    assert result==project.verify_project(output/'project-sources.json',fw,qemu,materials,sm)
    assert json.loads((output/'verification.json').read_text())==result
    with pytest.raises(FileExistsError):
        project.assemble_project_sources(output,path.parent/'lefony.tar.gz',path.parent/'prepared-firmware.tar.gz',
            path.parent/'rebuild.json',path.parent/'build.log',fw,qemu,materials)


@pytest.mark.parametrize('change',['firmware','qemu','report','log','wrong_target','missing_evidence','source_inventory'])
def test_project_mismatches_rejected(inputs,change):
    path,fw,qemu,materials,sm,manifest,report=inputs
    if change=='firmware':fw.write_bytes(b'changed')
    elif change=='qemu':qemu.write_bytes(b'changed')
    elif change=='log':(path.parent/'build.log').write_bytes(b'changed')
    elif change=='missing_evidence':manifest.pop('evidence')
    else:
        if change=='report':report['rebuilt_firmware']['elf']='1'*64
        elif change=='wrong_target':report['command']=['make','PLATFORM=prime_g2']
        else:report['files']['prepared-firmware/main.cpp']['sha256']='1'*64
        rp=path.parent/'rebuild.json';rp.write_text(json.dumps(report));manifest['evidence']['firmware-rebuild'].update(sha256=sources.digest(rp),bytes=rp.stat().st_size)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):project.verify_project(path,fw,qemu,materials,sm)


@pytest.mark.parametrize('kind',['changed','missing','extra_required'])
def test_public_sources_bind_sdk_and_host_recipe_bytes(tmp_path,kind):
    sdk=tmp_path/'sdk';recipes=tmp_path/'scripts'
    put(sdk/'tools/cli.py',b'CLI');put(recipes/'package.py',b'packager')
    path=archive(tmp_path/'public.tar.gz',{'lefony/sdk/tools/cli.py':b'CLI','lefony/scripts/package.py':b'packager'})
    assert project.verify_public_sources(path,sdk,recipes)['checked_files']==2
    if kind=='changed':put(sdk/'tools/cli.py',b'changed')
    elif kind=='missing':archive(path,{'lefony/sdk/tools/cli.py':b'CLI'})
    else:put(recipes/'new.py',b'new recipe')
    with pytest.raises(ValueError):project.verify_public_sources(path,sdk,recipes)


@pytest.fixture
def linux_inputs(inputs):
    path,fw,qemu,materials,sm,manifest,report=inputs
    source=materials/'qemu-prime/source.tar.gz'
    put(source,(path.parent/'qemu-prime.tar.gz').read_bytes())
    candidate={'platform':'Linux','architecture':'x86_64','status':'passed',
               'qemu_sha256':manifest['qemu_input_sha256'],
               'source_sha256':manifest['archives']['qemu-prime']['sha256']}
    put(materials/'qemu-prime/candidate.json',json.dumps(candidate).encode())
    put(materials/'qemu-prime/notices/COPYING',b'original QEMU terms')
    component={'component':'qemu-prime','inputs':[
        {'file':'qemu-prime/'+n,'sha256':sources.digest(materials/'qemu-prime'/n)}
        for n in ('source.tar.gz','candidate.json')], 'installed_notices':[
        {'file':'qemu-prime/notices/COPYING','sha256':sources.digest(materials/'qemu-prime/notices/COPYING')}]}
    sm={'platform':'linux-x86_64','components':[component]}
    return path,fw,qemu,materials,sm,manifest,report


def test_linux_project_assembly_binds_qemu_and_vm_without_windows_catalog(linux_inputs,tmp_path):
    path,fw,qemu,materials,sm,manifest,_=linux_inputs
    (materials/'manifest.json').write_text(json.dumps(sm))
    out=tmp_path/'linux-project'
    result=project.assemble_project_sources(out,path.parent/'lefony.tar.gz',path.parent/'prepared-firmware.tar.gz',
        path.parent/'rebuild.json',path.parent/'build.log',fw,qemu,materials)
    assert result['source_platform']=='linux-x86_64' and not result['native_host_qualified']
    assert result['firmware_source_files']==1 and result['retained_byte_identical_rebuild']
    assert result==project.verify_project(out/'project-sources.json',fw,qemu,materials,sm)


@pytest.mark.parametrize('change',['candidate','source','notice','duplicate-input','duplicate-component',
                                  'wrong-host','failed-build','wrong-source-record','wrong-qemu-record','unsupported-platform'])
def test_linux_project_rejects_changed_or_unrelated_qemu_materials(linux_inputs,change):
    path,fw,qemu,materials,sm,manifest,_=linux_inputs
    component=sm['components'][0]
    if change in ('candidate','source','notice'):
        name={'candidate':'candidate.json','source':'source.tar.gz','notice':'notices/COPYING'}[change]
        (materials/'qemu-prime'/name).write_bytes(b'changed')
    elif change=='duplicate-input':component['inputs'].append(component['inputs'][0])
    elif change=='duplicate-component':sm['components'].append(component)
    elif change=='unsupported-platform':sm['platform']='linux-aarch64'
    else:
        cp=materials/'qemu-prime/candidate.json';record=json.loads(cp.read_text())
        if change=='wrong-host':record['architecture']='aarch64'
        elif change=='failed-build':record['status']='failed'
        elif change=='wrong-source-record':record['source_sha256']='1'*64
        else:record['qemu_sha256']='1'*64
        cp.write_text(json.dumps(record))
        next(i for i in component['inputs'] if i['file'].endswith('candidate.json'))['sha256']=sources.digest(cp)
    with pytest.raises(ValueError):project.verify_project(path,fw,qemu,materials,sm)


@pytest.mark.parametrize('platform',['linux-x86_64','windows-AMD64'])
@pytest.mark.parametrize('change',[None,'firmware','qemu','input','audit-output','provider','audit-schema'])
def test_final_project_bytes_bind_after_host_relocation(tmp_path,platform,change):
    linux=platform=='linux-x86_64';fw=b'VM ELF';original=b'QEMU input'
    output=b'QEMU after library-path relocation' if linux else original
    bundle=tmp_path/'bundle'
    fp=put(bundle/'_internal/runtime/firmware.elf',fw)
    qp=put(bundle/('_internal/runtime/qemu-system-arm'+('' if linux else '.exe')),output)
    record={'source_platform':platform,'firmware_sha256':sha(fw),'qemu_input_sha256':sha(original)}
    entry={'component':'qemu-prime','input_sha256':sha(original),'bundled_sha256':sha(output)}
    audit={'schema':1,'platform':'linux-x86_64','files':{'runtime/qemu-system-arm':entry}}
    if change=='firmware':fp.write_bytes(b'changed VM')
    elif change=='qemu':qp.write_bytes(b'changed QEMU')
    elif change=='input':record['qemu_input_sha256']='1'*64
    elif change=='audit-output':entry['bundled_sha256']='1'*64
    elif change=='provider':entry['component']='unrelated'
    elif change=='audit-schema':audit['schema']=2
    put(bundle/'linux-native-source-inputs.json',json.dumps(audit).encode())
    if change and (linux or change in ('firmware','qemu','input')):
        with pytest.raises(ValueError):project.verify_bundled_project(bundle,record)
    else:
        result=project.verify_bundled_project(bundle,record)
        assert result['qemu_input_sha256']==sha(original) and result['qemu_bundled_sha256']==sha(output)
        assert ('linux_source_audit_sha256' in result)==linux


@pytest.fixture
def macos_inputs(linux_inputs):
    path,fw,qemu,materials,sm,manifest,report=linux_inputs
    sm['platform']='darwin-arm64'
    cp=materials/'qemu-prime/candidate.json';record=json.loads(cp.read_text())
    record.update(platform='Darwin',architecture='arm64');cp.write_text(json.dumps(record))
    next(i for i in sm['components'][0]['inputs'] if i['file'].endswith('candidate.json'))['sha256']=sources.digest(cp)
    return path,fw,qemu,materials,sm,manifest,report


def test_macos_project_binds_selected_source_and_vm_rebuild(macos_inputs):
    path,fw,qemu,materials,sm,_,_=macos_inputs
    result=project.verify_project(path,fw,qemu,materials,sm)
    assert result['source_platform']=='darwin-arm64'
    assert result['retained_byte_identical_rebuild'] and not result['native_host_qualified']
    cp=materials/'qemu-prime/candidate.json';record=json.loads(cp.read_text())
    record['architecture']='x86_64';cp.write_text(json.dumps(record))
    next(i for i in sm['components'][0]['inputs'] if i['file'].endswith('candidate.json'))['sha256']=sources.digest(cp)
    with pytest.raises(ValueError,match='different host'):
        project.verify_project(path,fw,qemu,materials,sm)


@pytest.mark.parametrize('change',[None,'missing','duplicate','conflict','data','changed-input','changed-output'])
def test_macos_qemu_freeze_binds_actual_input_and_relocated_output(tmp_path,change):
    original=put(tmp_path/'qemu',b'original QEMU');bundle=tmp_path/'bundle'
    output=put(bundle/'_internal/runtime/qemu-system-arm',b'relocated signed QEMU')
    firmware=put(bundle/'_internal/runtime/firmware.elf',b'VM')
    entries=[('runtime/qemu-system-arm',str(original),'BINARY')]
    expected=sources.digest(original)
    if change=='missing':entries=[]
    elif change=='duplicate':entries*=2
    elif change=='conflict':entries.append(('runtime/qemu-system-arm',str(put(tmp_path/'other',b'other QEMU')),'BINARY'))
    elif change=='data':entries[0]=(*entries[0][:2],'DATA')
    elif change=='changed-input':original.write_bytes(b'other QEMU')
    toc=put(tmp_path/'Analysis-00.toc',repr(('analysis',[entries], [('runtime/qemu-system-arm',str(original),'DATA')])).encode())
    if change in ('missing','conflict','data','changed-input'):
        with pytest.raises(ValueError):project.record_macos_qemu(toc,bundle,expected)
        return
    audit=project.record_macos_qemu(toc,bundle,expected)
    put(bundle/'macos-qemu-source-inputs.json',json.dumps(audit).encode())
    record={'source_platform':'darwin-arm64','firmware_sha256':sources.digest(firmware),'qemu_input_sha256':expected}
    if change=='changed-output':
        output.write_bytes(b'different signed output')
        with pytest.raises(ValueError):project.verify_bundled_project(bundle,record)
    else:
        result=project.verify_bundled_project(bundle,record)
        assert result['qemu_bundled_sha256']==sources.digest(output)
        assert result['macos_source_audit_sha256']==sources.digest(bundle/'macos-qemu-source-inputs.json')
