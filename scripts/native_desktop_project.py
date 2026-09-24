# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind desktop firmware, QEMU and target-library bytes to retained sources."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

from package_native_desktop_sources import digest, project_inputs
from windows_python_sources import source_file, relative as safe_relative

ROOT = Path(__file__).resolve().parents[1]


def newlib_record(sdk, candidate):
    import sys
    sys.path.insert(0,str(sdk/'tools'))
    from runtime import bundle_files
    selected = bundle_files(sdk,candidate)
    files = {}
    for name, path in selected.items():
        if source_file(candidate,name).resolve()!=path.resolve():
            raise ValueError('Newlib input escaped the selected candidate')
        files[name] = digest(path)
    recipes = {'scripts/build_sdk_newlib.py':digest(sdk.parent/'scripts/build_sdk_newlib.py'),
               'sdk/contracts/newlib.json':digest(sdk/'contracts/newlib.json'),
               'sdk/contract.json':digest(sdk/'contract.json')}
    report = json.loads((candidate/'candidate.json').read_text(encoding='utf-8'))
    return {'schema':1,'version':report['version'],'files':files,
            'candidate_sha256':files['candidate.json'],'source_sha256':report['source_sha256'],
            'reproduction_recipe':recipes,'runtime_qualified':False}


def verify_newlib_copy(destination, record):
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    if actual != record['files'].keys() or any(p.is_symlink() for p in destination.rglob('*')):
        raise ValueError('Bundled newlib file set differs from selected input')
    for name, sha in record['files'].items():
        if digest(source_file(destination,name))!=sha:
            raise ValueError('Bundled newlib input changed: '+name)


def collect_newlib(sdk, candidate, materials):
    record = newlib_record(sdk,candidate); name = 'arm-none-eabi-newlib'
    folder = materials/name;folder.mkdir(parents=True,exist_ok=False)
    selections = {'candidate.json':candidate/'candidate.json',
                  'notices/COPYING.NEWLIB':candidate/'COPYING.NEWLIB',
                  'sources/newlib-'+record['version']+'.tar.gz':candidate/('newlib-'+record['version']+'.tar.gz')}
    selections.update({'recipe/'+n:sdk.parent/n for n in record['reproduction_recipe']})
    files = {}
    for relative, source in selections.items():
        path = folder/relative;path.parent.mkdir(parents=True,exist_ok=True)
        expected = digest(source);shutil.copyfile(source,path)
        if digest(path)!=expected:raise ValueError('Newlib source changed during copying')
        files[name+'/'+relative] = expected
    return {'component':name,'version':record['version'],'inputs':[{'file':n,'sha256':h} for n,h in files.items()],
            'files':files,'bundle':record,'runtime_qualified':False}


def verify_newlib_materials(sdk, materials, manifest, record=None):
    entries = [c for c in manifest['components'] if c['component']=='arm-none-eabi-newlib']
    if len(entries)!=1:raise ValueError('Require one matching newlib source component')
    component = entries[0];name = component['component'];folder = source_file(materials,name)
    bundle = component['bundle']
    if record is not None and bundle!=record:raise ValueError('Newlib sources differ from selected sysroot')
    spec = json.loads((sdk/'contracts/newlib.json').read_text(encoding='utf-8'))
    if component['version']!=spec['version'] or bundle['source_sha256']!=spec['source_sha256']:
        raise ValueError('Newlib sources differ from SDK contract')
    files = component['files'];actual = {p.relative_to(materials).as_posix() for p in folder.rglob('*') if p.is_file()}
    if actual!=files.keys() or any(p.is_symlink() for p in folder.rglob('*')):
        raise ValueError('Newlib source material file set differs')
    for path, sha in files.items():
        if not path.startswith(name+'/') or digest(source_file(materials,path))!=sha:
            raise ValueError('Newlib source material changed')
    if set(bundle['reproduction_recipe'])!={'scripts/build_sdk_newlib.py','sdk/contracts/newlib.json','sdk/contract.json'}:
        raise ValueError('Incomplete newlib reproduction recipe')
    expected = {name+'/candidate.json':bundle['candidate_sha256'],
                name+'/notices/COPYING.NEWLIB':bundle['files']['COPYING.NEWLIB'],
                name+'/sources/newlib-'+spec['version']+'.tar.gz':spec['source_sha256']}
    expected.update({name+'/recipe/'+n:digest(sdk.parent/n) for n in bundle['reproduction_recipe']})
    if (expected!=files or len(component['inputs'])!=len(files)
            or {i['file']:i['sha256'] for i in component['inputs']}!=files):
        raise ValueError('Newlib source input inventory differs')
    return bundle


def qemu_sources(materials, source_manifest):
    """Read a checked QEMU build record in its host collector's native format."""
    platform = source_manifest.get('platform')
    if platform in ('linux-x86_64', 'darwin-arm64'):
        name, folder = 'qemu-prime', 'qemu-prime'
    elif platform == 'windows-AMD64':
        name, folder = 'windows-qemu', 'windows-qemu/inputs/qemu'
    else:
        raise ValueError('Unsupported desktop project source platform')
    components = [c for c in source_manifest['components'] if c['component']==name]
    if len(components)!=1:raise ValueError('Require one verified '+name+' source component')
    component = components[0]
    if platform in ('linux-x86_64', 'darwin-arm64'):
        records = component['inputs'] + component.get('installed_notices', [])
        files = {item['file']:item['sha256'] for item in records}
        if len(files)!=len(records):raise ValueError('Duplicate QEMU source input')
        for path, sha in files.items():
            if not path.startswith(name+'/') or digest(source_file(materials,path))!=sha:
                raise ValueError('QEMU source input changed')
    else:
        files = component['files']
    candidate = source_file(materials,folder+'/candidate.json')
    source = source_file(materials,folder+'/source.tar.gz')
    for path in (candidate,source):
        expected = files.get(path.relative_to(materials).as_posix())
        if not expected or digest(path)!=expected:raise ValueError('QEMU build/source record changed')
    if candidate.stat().st_size>1024**2:raise ValueError('QEMU build record exceeds bound')
    q = json.loads(candidate.read_text(encoding='utf-8'))
    if platform == 'linux-x86_64' and (q.get('platform'),q.get('architecture'))!=('Linux','x86_64'):
        raise ValueError('QEMU build record is for a different host')
    if platform == 'darwin-arm64' and (q.get('platform'),q.get('architecture'))!=('Darwin','arm64'):
        raise ValueError('QEMU build record is for a different host')
    if q.get('status')!='passed' or q.get('source_sha256')!=digest(source):
        raise ValueError('QEMU sources differ from the successful build')
    return q, source


def verify_project(manifest_path, firmware, qemu, materials, source_manifest):
    manifest, inputs = project_inputs(manifest_path)
    paths = {name:path for path,name in inputs}
    if digest(firmware)!=manifest['firmware_sha256'] or digest(qemu)!=manifest['qemu_input_sha256']:
        raise ValueError('Project source binary identities differ from selected firmware/QEMU')
    q, _ = qemu_sources(materials,source_manifest)
    if (q.get('qemu_sha256')!=manifest['qemu_input_sha256']
            or q.get('source_sha256')!=manifest['archives']['qemu-prime']['sha256']):
        raise ValueError('Project QEMU source differs from the selected build')
    evidence = manifest.get('evidence',{})
    if set(evidence)!={'firmware-rebuild','firmware-build-log'}:
        raise ValueError('Require retained firmware rebuild report and build log')
    report_path = paths[evidence['firmware-rebuild']['file']]
    if report_path.stat().st_size>8*1024**2:raise ValueError('Firmware rebuild record exceeds bound')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if (report.get('status')!='passed' or report.get('exit_code')!=0 or report.get('byte_identical') is not True
            or report.get('expected_firmware')!=report.get('rebuilt_firmware')
            or report.get('rebuilt_firmware',{}).get('elf')!=manifest['firmware_sha256']
            or report.get('archive_sha256')!=manifest['archives']['prepared-firmware']['sha256']
            or report.get('build_log_sha256')!=evidence['firmware-build-log']['sha256']
            or 'PLATFORM=prime_g2_vm' not in report.get('command',[])):
        raise ValueError('Firmware source/rebuild evidence does not match the selected VM image')
    source = paths[manifest['archives']['prepared-firmware']['file']]
    records = report.get('files',{});seen = set();total = 0
    with tarfile.open(source) as archive:
        for member in archive:
            safe_relative(member.name)
            total += member.size
            if (len(seen)>=30000 or total>512*1024**2 or not member.isfile()
                    or member.name in seen or member.name not in records):
                raise ValueError('Prepared firmware archive differs from rebuild inventory')
            entry = records[member.name]
            if (member.size!=entry['bytes'] or member.mode!=entry['mode']
                    or hashlib.file_digest(archive.extractfile(member),'sha256').hexdigest()!=entry['sha256']):
                raise ValueError('Prepared firmware source member changed')
            seen.add(member.name)
    if not seen or seen!=records.keys():raise ValueError('Prepared firmware source inventory is incomplete')
    return {'schema':1,'project_manifest_sha256':digest(manifest_path),'firmware_sha256':manifest['firmware_sha256'],
            'qemu_input_sha256':manifest['qemu_input_sha256'],'archives':manifest['archives'],'evidence':evidence,
            'firmware_source_files':len(seen),'retained_byte_identical_rebuild':True,
            'firmware_rebuilt_this_run':False,'physical_qualified':False,'native_windows_qualified':False,
            'native_host_qualified':False,'source_platform':source_manifest['platform']}


def verify_public_sources(archive_path, sdk_tree, recipe_root):
    """Bind the SDK data being frozen and available host recipes to public source."""
    expected = {}
    for path in sdk_tree.rglob('*'):
        relative = path.relative_to(sdk_tree)
        if relative.parts[0] in ('runtime','trust') or not path.is_file():continue
        if path.is_symlink():raise ValueError('Linked SDK project source input')
        expected['lefony/sdk/'+relative.as_posix()] = digest(path)
    for path in recipe_root.rglob('*'):
        relative = path.relative_to(recipe_root)
        if '__pycache__' in relative.parts or path.suffix not in ('.py','.json','.patch','.txt'):continue
        if not path.is_file() or path.is_symlink():raise ValueError('Invalid host recipe source input')
        expected['lefony/scripts/'+relative.as_posix()] = digest(path)
    seen = set();matched = set();total = 0
    with tarfile.open(archive_path) as archive:
        for member in archive:
            safe_relative(member.name)
            total += member.size
            if not member.isfile() or member.name in seen or len(seen)>=30000 or total>512*1024**2:
                raise ValueError('Invalid public project source archive')
            seen.add(member.name)
            if member.name in expected:
                if hashlib.file_digest(archive.extractfile(member),'sha256').hexdigest()!=expected[member.name]:
                    raise ValueError('Public project source differs from packaging input: '+member.name)
                matched.add(member.name)
    if not expected or matched!=expected.keys():raise ValueError('Public project sources omit SDK/host inputs')
    return {'checked_files':len(matched),'archive_sha256':digest(archive_path)}


def record_macos_qemu(toc, bundle, expected):
    """Bind PyInstaller's actual QEMU input to its relocated, signed output."""
    if toc.stat().st_size > 8*1024**2:
        raise ValueError('macOS freeze input table exceeds bound')
    inputs = []
    def visit(value):
        if not isinstance(value, (tuple, list)):
            return
        if (len(value) == 3 and all(isinstance(item, str) for item in value)
                and value[0] == 'runtime/qemu-system-arm' and value[2] == 'BINARY'):
            inputs.append(Path(value[1]))
        else:
            for item in value:
                visit(item)
    visit(ast.literal_eval(toc.read_text(encoding='utf-8')))
    # Analysis retains both the caller's input table and the normalized final
    # table. Repeated identical entries are expected; every occurrence must
    # identify the selected binary.
    if not inputs or any(digest(path) != expected for path in inputs):
        raise ValueError('macOS QEMU freeze input differs from selected build')
    return {'schema':1, 'platform':'darwin-arm64', 'files':{
        'runtime/qemu-system-arm':{'component':'qemu-prime',
            'input_sha256':expected,
            'bundled_sha256':digest(bundle/'_internal/runtime/qemu-system-arm')}}}


def verify_bundled_project(bundle, record):
    """Bind final files, preserving Linux's audited library-path relocation."""
    firmware = digest(bundle/'_internal/runtime/firmware.elf')
    linux = record['source_platform']=='linux-x86_64'
    macos = record['source_platform']=='darwin-arm64'
    qemu = digest(bundle/('_internal/runtime/qemu-system-arm'+('' if linux or macos else '.exe')))
    if firmware!=record['firmware_sha256']:
        raise ValueError('Bundled firmware differs from project source inputs')
    result = {'firmware_sha256':firmware,'qemu_input_sha256':record['qemu_input_sha256'],
              'qemu_bundled_sha256':qemu}
    if linux or macos:
        host = 'linux' if linux else 'macos'
        path = bundle/('linux-native-source-inputs.json' if linux else 'macos-qemu-source-inputs.json')
        if path.stat().st_size>8*1024**2:raise ValueError('Host QEMU source audit exceeds bound')
        audit = json.loads(path.read_text(encoding='utf-8'))
        entry = audit.get('files',{}).get('runtime/qemu-system-arm',{})
        if (audit.get('schema')!=1 or audit.get('platform')!=record['source_platform'] or entry.get('component')!='qemu-prime'
                or entry.get('input_sha256')!=record['qemu_input_sha256']
                or entry.get('bundled_sha256')!=qemu):
            raise ValueError('Bundled QEMU differs from its audited source input')
        result[host+'_source_audit_sha256'] = digest(path)
    elif qemu!=record['qemu_input_sha256']:
        raise ValueError('Bundled QEMU differs from project source inputs')
    return result


def assemble_project_sources(output, public_source, prepared_source, rebuild_report,
                             build_log, firmware, qemu, materials):
    """Create a project manifest from verified host QEMU and retained VM inputs."""
    source_manifest = json.loads((materials/'manifest.json').read_text(encoding='utf-8'))
    if source_manifest.get('platform') == 'windows-AMD64':
        import collect_native_windows_sources as native
        native.verify_materials(materials,source_manifest)
    _, qemu_source = qemu_sources(materials,source_manifest)
    output.mkdir(parents=True,exist_ok=False)
    manifest = {'schema':1,'firmware_sha256':digest(firmware),'qemu_input_sha256':digest(qemu),
                'archives':{},'evidence':{},'physical_qualified':False,'complete_distribution_qualified':False}
    for group, entries in (
        ('archives',{'lefony':public_source,'qemu-prime':qemu_source,'prepared-firmware':prepared_source}),
        ('evidence',{'firmware-rebuild':rebuild_report,'firmware-build-log':build_log})):
        for name, source in entries.items():
            if not source.is_file() or source.is_symlink():raise ValueError('Missing or linked project source input')
            target = output/(name+('.tar.gz' if group=='archives' else '.json' if name=='firmware-rebuild' else '.log'))
            expected = digest(source);shutil.copyfile(source,target)
            if digest(target)!=expected:raise ValueError('Project source changed during copying')
            manifest[group][name] = {'file':target.name,'sha256':expected,'bytes':target.stat().st_size}
    path = output/'project-sources.json';path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    record = verify_project(path,firmware,qemu,materials,source_manifest)
    (output/'verification.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return record


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('output','public-source','prepared-source','rebuild-report','build-log','firmware','qemu','source-materials'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    result = assemble_project_sources(args.output,args.public_source,args.prepared_source,args.rebuild_report,
                                      args.build_log,args.firmware,args.qemu,args.source_materials)
    print(json.dumps({'project_manifest_sha256':result['project_manifest_sha256'],
                      'firmware_source_files':result['firmware_source_files'],'native_windows_qualified':False}))
