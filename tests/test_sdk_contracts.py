# SPDX-License-Identifier: GPL-3.0-or-later
import base64
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import types
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
import lfapp
import source
from test_native_app_package import image
from test_native_app_device import META, PoolTransport
from signing import sign
from device import Client, DeviceError
CORPUS = json.loads((ROOT / 'sdk/contracts/manifest-v1.json').read_text())['cases']
EXT = {**META, 'schema': 1, 'minimum_api': 1, 'required_capabilities': 3, 'optional_capabilities': 4, 'data_schema': 1}


def test_named_files_require_matching_api_and_feature_without_changing_legacy():
    metadata = {**EXT, 'minimum_api': 2, 'required_capabilities': 8, 'optional_capabilities': 0}
    assert lfapp.compatible(metadata)
    for api, features in ((1, 15), (2, 7)):
        with pytest.raises(lfapp.PackageError):
            lfapp.compatible(metadata, api=api, features=features)
    assert lfapp.compatible(META, api=1, features=7)


def test_live_sync_requires_matching_api_and_feature():
    metadata = {**EXT, 'minimum_api': 5, 'required_capabilities': 88, 'optional_capabilities': 0}
    assert lfapp.compatible(metadata)
    for api, features in ((4, 127), (5, 63)):
        with pytest.raises(lfapp.PackageError):
            lfapp.compatible(metadata, api=api, features=features)
    assert lfapp.compatible(META, api=4, features=63)


def test_file_catalog_requires_matching_api_and_feature():
    metadata = {**EXT, 'minimum_api': 6, 'required_capabilities': 152, 'optional_capabilities': 0}
    assert lfapp.compatible(metadata)
    for api, features in ((5, 255), (6, 127)):
        with pytest.raises(lfapp.PackageError):
            lfapp.compatible(metadata, api=api, features=features)
    assert lfapp.compatible(META, api=5, features=127)


def test_file_quota_requires_matching_api_and_feature():
    metadata = {**EXT, 'minimum_api': 7, 'required_capabilities': 280, 'optional_capabilities': 0}
    assert lfapp.compatible(metadata)
    for api, features in ((6, 511), (7, 255)):
        with pytest.raises(lfapp.PackageError):
            lfapp.compatible(metadata, api=api, features=features)
    assert lfapp.compatible(META, api=6, features=255)


def test_foreground_requires_matching_api_and_explicit_capability():
    metadata = {**EXT, 'minimum_api': 3, 'required_capabilities': 16, 'optional_capabilities': 0}
    assert lfapp.compatible(metadata)
    for api, features in ((2, 31), (3, 15)):
        with pytest.raises(lfapp.PackageError):
            lfapp.compatible(metadata, api=api, features=features)
    for profile in (1, 2):
        assert lfapp.compatible(META, api=profile, features=7)


def test_private_checkpoint_requires_matching_api_and_feature():
    metadata = {**EXT, 'minimum_api': 8, 'required_capabilities': 536, 'optional_capabilities': 0}
    assert lfapp.compatible(metadata)
    for api, features in ((7, 1023), (8, 511)):
        with pytest.raises(lfapp.PackageError):
            lfapp.compatible(metadata, api=api, features=features)
    assert lfapp.compatible(META, api=7, features=511)


def test_typography_requires_current_api_and_explicit_feature():
    metadata = {**EXT, 'minimum_api': 9, 'required_capabilities': 1024, 'optional_capabilities': 0}
    assert lfapp.compatible(metadata)
    for api, features in ((8, 2047), (9, 1023)):
        with pytest.raises(lfapp.PackageError):
            lfapp.compatible(metadata, api=api, features=features)


def test_system_requires_matching_api_and_explicit_feature():
    metadata = {**EXT, 'minimum_api': 10, 'required_capabilities': 2048, 'optional_capabilities': 0}
    assert lfapp.compatible(metadata)
    for api, features in ((9, 4095), (10, 2047)):
        with pytest.raises(lfapp.PackageError):
            lfapp.compatible(metadata, api=api, features=features)


def test_channel_requires_matching_api_and_explicit_feature():
    metadata = {**EXT, 'minimum_api': 11, 'required_capabilities': 4096, 'optional_capabilities': 0}
    assert lfapp.compatible(metadata)
    for api, features in ((10, 8191), (11, 4095)):
        with pytest.raises(lfapp.PackageError):
            lfapp.compatible(metadata, api=api, features=features)
    assert lfapp.compatible(META, api=10, features=4095)


def test_writer_abort_requires_matching_api_and_explicit_feature():
    metadata = {**EXT, 'minimum_api': 12, 'required_capabilities': 8200, 'optional_capabilities': 0}
    assert lfapp.compatible(metadata)
    for api, features in ((11, 16383), (12, 8191)):
        with pytest.raises(lfapp.PackageError):
            lfapp.compatible(metadata, api=api, features=features)
    assert lfapp.compatible(META, api=11, features=8191)


@pytest.mark.parametrize('case', CORPUS, ids=lambda c: c['case'])
def test_manifest_package_corpus(case):
    text = case['manifest'].encode()
    body = text + image()
    package = lfapp.HEADER.pack(lfapp.MAGIC, case['header_schema'], len(text), len(image()), case['abi'],
                                hashlib.sha256(body).digest(), bytes(8)) + body
    if not case['valid']:
        with pytest.raises(lfapp.PackageError): lfapp.unpack(package)
    else:
        metadata, _ = lfapp.unpack(package)
        assert lfapp.pack(metadata, image()) == package
        if case['supported']: assert lfapp.compatible(metadata, api=1, features=7)
        else:
            with pytest.raises(lfapp.PackageError): lfapp.compatible(metadata, api=1, features=7)


def test_firmware_parser_corpus_truncations_and_nonascii_under_sanitizers(tmp_path):
    compiler = shutil.which('clang++') or shutil.which('g++')
    assert compiler, 'a host C++ compiler is required'
    rows = []
    for c in CORPUS:
        literal = json.dumps(c['manifest'], ensure_ascii=True)
        rows.append('{'+f"{literal},{len(c['manifest'].encode())},{c['header_schema']},{c['abi']},{int(c['valid'])},{int(c['supported'])}"+'}')
    cpp = tmp_path / 'manifest.cpp'
    cpp.write_text('''#include "native_app_manifest.h"
#include <cassert>
#include <cstdio>
#include <string>
using namespace PrimeG2::NativeAppManifest;
static_assert(APIRevision==12 && Features==16383 && PackageSchemas==3,"current contract constants");
struct Case { const char *text;size_t bytes;uint32_t schema,abi;bool valid,compatible; };
Case cases[]={'''+','.join(rows)+'''};
int main(){
 for(unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
  auto &c=cases[i];Manifest m;m.abi=99;
  bool valid=parse(reinterpret_cast<const uint8_t *>(c.text),c.bytes,c.schema,c.abi,&m);
  if(valid!=c.valid) { fprintf(stderr,"case %u parsing\\n",i);return 1; }
  assert(valid || m.abi==99);
  if(valid) {
   assert(supported(m,1,7)==c.compatible); // Preserve the original reader corpus.
   assert(supported(m)==(m.minimumAPI<=APIRevision && !(m.required&~Features)));
   for(size_t n=0;n<c.bytes;n++) assert(!parse(reinterpret_cast<const uint8_t *>(c.text),n,c.schema,c.abi,&m));
   for(size_t n=0;n<c.bytes;n++) { std::string bad(c.text);bad[n]=char(255);
    assert(!parse(reinterpret_cast<const uint8_t *>(bad.data()),bad.size(),c.schema,c.abi,&m)); }
  }
 }
}
''')
    exe = tmp_path / 'manifest'
    subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-I', str(ROOT / 'ports/lefony-prime-g2/ion/src/prime_g2'), str(cpp), '-o', str(exe)], check=True)
    subprocess.run([exe], check=True, timeout=30)


def test_preserved_schema_zero_reader_refuses_explicit_new_schema():
    # This is the exact pre-maturity reader in the checked revision, not a model.
    old = types.ModuleType('old_lfapp')
    exec(subprocess.check_output(['git', 'show', '91701e213d74918226b3692f570079c2c13d9000:sdk/tools/lfapp.py'], cwd=ROOT), old.__dict__)
    legacy = lfapp.pack(META, image())
    assert old.unpack(legacy) == lfapp.unpack(legacy)
    with pytest.raises(old.PackageError): old.unpack(lfapp.pack(EXT, image()))


class ExtendedTransport(PoolTransport):
    flags = 22
    api = 1
    features = 7
    schemas = 3
    profile = 2
    def read(self, request, value=0, index=0, length=0):
        if request == 0x6e:
            self.cap_reads = getattr(self, 'cap_reads', 0) + 1
            return struct.pack('<12I', 0x4341464c, 48, 1, 0, 1, self.api, self.features, self.schemas, self.profile, 2101664, 65536, 0)
        data = bytearray(super().read(request, value, index, length))
        if request == 0x60: struct.pack_into('<I', data, 60, self.flags)
        return bytes(data)


@pytest.mark.parametrize('field,value', [('flags', 6), ('api', 0), ('api', 1), ('features', 1), ('schemas', 1), ('profile', 1)])
def test_requirements_fail_before_any_upload(field, value, tmp_path):
    t = ExtendedTransport();setattr(t, field, value)
    m = {**EXT, 'minimum_api': 2} if field == 'api' and value == 1 else EXT
    signed = sign(lfapp.pack(m, image()), ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem')
    with pytest.raises(DeviceError): Client(t).install(signed, [ROOT / 'tests/fixtures/prime_g2_emulator_update_public.pem'])
    assert t.calls == []
    if field == 'flags': assert not getattr(t, 'cap_reads', 0)


def test_extended_install_readback_and_unknown_optional():
    t = ExtendedTransport()
    m = {**EXT, 'optional_capabilities': 0xfffffffc}
    signed = sign(lfapp.pack(m, image()), ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem')
    assert Client(t).install(signed, [ROOT / 'tests/fixtures/prime_g2_emulator_update_public.pem'])['id'] == 'sample'
    assert t.cap_reads == 1 and t.calls.count(0x65) == 1


def descriptor(data, binary=False):
    return {'encoding': 'base64' if binary else 'utf8', 'content': base64.b64encode(data).decode() if binary else data.decode(),
            'sha256': hashlib.sha256(data).hexdigest()}


def bundle():
    return {'format': 'lefony-source-1', 'manifest': EXT, 'files': {'src/main.cpp': descriptor(b'// hello\n'),
        'assets/picture.bin': descriptor(bytes(range(256)), True), 'tests/startup.json': descriptor(b'{"schema":1}'),
        'sdk.lock.json': descriptor(b'{"schema":1}'), 'notices/license.txt': descriptor('© author'.encode())}}


def test_source_one_roundtrip_keeps_inputs_and_ignores_generated_files(tmp_path):
    value = bundle();encoded = source.encode(value)
    target = tmp_path / 'source';source.extract(encoded, target)
    assert source.collect(target, 1) == encoded
    (target / 'build').mkdir();(target / 'build/private.pem').write_text('private')
    assert source.collect(target, 1) == encoded
    with pytest.raises(lfapp.PackageError, match='format 1'): source.collect(target)
    assert (target / 'assets/picture.bin').read_bytes() == bytes(range(256))


@pytest.mark.parametrize('kind', ['hash', 'encoding', 'padding', 'source-binary', 'case-file', 'case-directory', 'reserved', 'hook', 'size', 'surrogate', 'descriptor'])
def test_source_one_rejects_unsafe_or_inconsistent_files(kind):
    b = bundle();f = b['files']
    if kind == 'hash': f['assets/picture.bin']['sha256'] = '0'*64
    elif kind == 'encoding': f['assets/picture.bin']['encoding'] = 'gzip'
    elif kind == 'padding': f['assets/picture.bin']['content'] += '='
    elif kind == 'source-binary': f['src/main.cpp'] = descriptor(b'x', True)
    elif kind == 'case-file': f['src/Main.cpp'] = descriptor(b'x')
    elif kind == 'case-directory': f.update({'src/X/a.h': descriptor(b'x'), 'src/x/b.h': descriptor(b'x')})
    elif kind == 'reserved': f['src/CON.cpp'] = descriptor(b'x')
    elif kind == 'hook': f['postinstall.sh'] = descriptor(b'x')
    elif kind == 'size': f['assets/picture.bin'] = descriptor(bytes(65537), True)
    elif kind == 'surrogate': f['src/main.cpp']['content'] = '\ud800'
    else: f['src/main.cpp']['extra'] = 1
    with pytest.raises(ValueError): source.encode(b)


def test_source_root_symlinks_and_duplicate_json_rejected(tmp_path):
    target = tmp_path / 'source';source.extract(source.encode(bundle()), target)
    (target / 'tests/startup.json').unlink();(target / 'tests').rmdir();(target / 'tests').symlink_to(target / 'assets', target_is_directory=True)
    with pytest.raises(lfapp.PackageError): source.collect(target, 1)
    data = source.encode(bundle()).replace(b'"format":"lefony-source-1"', b'"format":"lefony-source-1","format":"lefony-source-1"')
    with pytest.raises(lfapp.PackageError, match='duplicate'): source.decode(data)
