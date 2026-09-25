#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise contract negotiation in the actual guest loader and modeled USB."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, write_json
from cli import package
from device import Client, DeviceError
from lfapp import API_REVISION, HEADER, MAGIC, pack, unpack
from runner import exercise
from signing import openssl, sign
from workspace import opened


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-firmware', type=Path)
    parser.add_argument('--api3-firmware', type=Path, help='Earlier API 3 VM ELF for input-stream rejection')
    parser.add_argument('--api4-firmware', type=Path, help='Earlier API 4 VM ELF for live-sync rejection')
    parser.add_argument('--api5-firmware', type=Path, help='Earlier API 5 VM ELF for file catalog rejection')
    parser.add_argument('--api6-firmware', type=Path, help='Earlier API 6 VM ELF for file quota rejection')
    parser.add_argument('--api7-firmware', type=Path, help='Earlier API 7 VM ELF for checkpoint rejection')
    parser.add_argument('--firmware', type=Path, default=ROOT / 'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/sdk-contracts')
    args = parser.parse_args()
    firmware = args.firmware.resolve()
    qemu = ROOT / 'build/qemu-prime-g2/qemu-system-arm'
    output = args.output.resolve();output.mkdir(parents=True, exist_ok=True)
    results = []
    skipped = []
    with tempfile.TemporaryDirectory(prefix='lefony-contract-') as folder:
        project = Path(folder)
        shutil.copytree(ROOT / 'sdk/templates/basic', project, dirs_exist_ok=True)
        metadata = json.loads((project / 'app.json').read_text())
        metadata.update(schema=1, minimum_api=1, required_capabilities=3, optional_capabilities=0xfffffffc, data_schema=1)
        (project / 'app.json').write_text(json.dumps(metadata))
        app = package(project)
        _, image = unpack(app.read_bytes())
        result = exercise(app, qemu, firmware)
        assert result['result'] == 1
        results.append({'case':'new-loader-schema-one','result':result})
        if args.old_firmware:
            try: exercise(app, qemu, args.old_firmware.resolve())
            except RuntimeError as exc: assert 'guest rejected app' in str(exc)
            else: raise AssertionError('old reader accepted schema 1')
            results.append({'case':'old-loader-refuses-schema-one','firmware_sha256':digest(args.old_firmware),'passed':True})
        else:
            skipped.append({'case':'old-loader-refuses-schema-one',
                            'reason':'requires --old-firmware with a pre-schema-1 VM ELF'})
        if args.api3_firmware:
            for name,requirements in [('api-four',{'minimum_api':4,'required_capabilities':0}),
                                      ('input-feature',{'minimum_api':3,'required_capabilities':32})]:
                bad=project/(name+'.lfapp')
                bad.write_bytes(pack({**metadata,**requirements,'optional_capabilities':0},image))
                try:exercise(bad,qemu,args.api3_firmware.resolve())
                except RuntimeError as exc:assert 'guest rejected app' in str(exc)
                else:raise AssertionError('API 3 reader accepted '+name)
                results.append({'case':'api3-loader-refuses-'+name,'passed':True,
                                'firmware_sha256':digest(args.api3_firmware)})
        if args.api4_firmware:
            for name,requirements in [('api-five',{'minimum_api':5,'required_capabilities':0}),
                                      ('sync-feature',{'minimum_api':4,'required_capabilities':64})]:
                bad=project/(name+'.lfapp')
                bad.write_bytes(pack({**metadata,**requirements,'optional_capabilities':0},image))
                try:exercise(bad,qemu,args.api4_firmware.resolve())
                except RuntimeError as exc:assert 'guest rejected app' in str(exc)
                else:raise AssertionError('API 4 reader accepted '+name)
                results.append({'case':'api4-loader-refuses-'+name,'passed':True,
                                'firmware_sha256':digest(args.api4_firmware)})
        if args.api5_firmware:
            for name,requirements in [('api-six',{'minimum_api':6,'required_capabilities':0}),
                                      ('catalog-feature',{'minimum_api':5,'required_capabilities':128})]:
                bad=project/(name+'.lfapp')
                bad.write_bytes(pack({**metadata,**requirements,'optional_capabilities':0},image))
                try:exercise(bad,qemu,args.api5_firmware.resolve())
                except RuntimeError as exc:assert 'guest rejected app' in str(exc)
                else:raise AssertionError('API 5 reader accepted '+name)
                results.append({'case':'api5-loader-refuses-'+name,'passed':True,
                                'firmware_sha256':digest(args.api5_firmware)})
        if args.api6_firmware:
            for name,requirements in [('api-seven',{'minimum_api':7,'required_capabilities':0}),
                                      ('quota-feature',{'minimum_api':6,'required_capabilities':256})]:
                bad=project/(name+'.lfapp')
                bad.write_bytes(pack({**metadata,**requirements,'optional_capabilities':0},image))
                try:exercise(bad,qemu,args.api6_firmware.resolve())
                except RuntimeError as exc:assert 'guest rejected app' in str(exc)
                else:raise AssertionError('API 5 reader accepted '+name)
                results.append({'case':'api6-loader-refuses-'+name,'passed':True,
                                'firmware_sha256':digest(args.api6_firmware)})
        if args.api7_firmware:
            for name,requirements in [('api-eight',{'minimum_api':8,'required_capabilities':0}),
                                      ('checkpoint-feature',{'minimum_api':7,'required_capabilities':512})]:
                bad=project/(name+'.lfapp')
                bad.write_bytes(pack({**metadata,**requirements,'optional_capabilities':0},image))
                try:exercise(bad,qemu,args.api7_firmware.resolve())
                except RuntimeError as exc:assert 'guest rejected app' in str(exc)
                else:raise AssertionError('API 7 reader accepted '+name)
                results.append({'case':'api7-loader-refuses-'+name,'passed':True,
                                'firmware_sha256':digest(args.api7_firmware)})
        for name, changed in [('future-api', {'minimum_api':API_REVISION+1}), ('unknown-required', {'required_capabilities':0x80000000,'optional_capabilities':0})]:
            bad = project / (name+'.lfapp');bad.write_bytes(pack({**metadata, **changed}, image))
            try: exercise(bad, qemu, firmware)
            except RuntimeError as exc: assert 'guest rejected app' in str(exc)
            else: raise AssertionError(name+' executed')
            results.append({'case':name,'passed':True})
        raw = app.read_bytes();text = raw[64:64+HEADER.unpack_from(raw)[2]]
        for name, badtext in [('duplicate',text.replace(b'"abi":1',b'"abi":1,"abi":1')),
                              ('header-mismatch',text.replace(b'"schema":1',b'"schema":0'))]:
            body = badtext+image
            bad = project / (name+'.lfapp')
            bad.write_bytes(HEADER.pack(MAGIC,1,len(badtext),len(image),1,hashlib.sha256(body).digest(),bytes(8))+body)
            # Deliberately bypass the host parser only, so malformed bytes reach
            # the real protected loader. The guest validation is never bypassed.
            with patch('runner.unpack', return_value=(metadata,image)):
                try: exercise(bad,qemu,firmware)
                except RuntimeError as exc: assert 'guest rejected app' in str(exc)
                else: raise AssertionError(name+' executed')
            results.append({'case':'loader-'+name,'passed':True})
        # Feed invalid signed bytes to the real loader, bypassing only host
        # preflight. The launch optimization must retain every trust/ELF check.
        private = ROOT / 'tests/fixtures/prime_g2_emulator_update_private.pem'
        public = ROOT / 'tests/fixtures/prime_g2_emulator_update_public.pem'
        signed = sign(raw, private)
        for name in ('signature', 'payload', 'signer', 'envelope-abi', 'elf-entry'):
            invalid = bytearray(signed)
            if name == 'signature': invalid[96] ^= 1
            elif name == 'payload': invalid[-1] ^= 1
            elif name == 'signer': invalid[24] ^= 1
            elif name == 'envelope-abi':
                # A correctly signed envelope declaring ABI 0 around ABI 1.
                invalid[16:20] = bytes(4)
                invalid[96:352] = openssl('dgst', '-sha256', '-sign', private, data=invalid[:96])
            else:
                offset = 352 + 64 + len(text) + 24
                invalid[offset:offset+4] = (0x10201000).to_bytes(4, 'little')
                invalid[352+24:352+56] = hashlib.sha256(invalid[352+64:]).digest()
                invalid[56:88] = hashlib.sha256(invalid[352:]).digest()
                invalid[96:352] = openssl('dgst', '-sha256', '-sign', private, data=invalid[:96])
            bad = project / ('signed-' + name + '.lfapp');bad.write_bytes(invalid)
            with patch('signing.verify', return_value=(metadata, image)):
                try: exercise(bad, qemu, firmware, public_keys=[public])
                except RuntimeError as exc: assert 'guest rejected app' in str(exc)
                else: raise AssertionError('signed ' + name + ' executed')
            results.append({'case':'signed-loader-' + name,'passed':True})
        with opened(project, 'installed') as (workspace, _):
            result = exercise(app, qemu, firmware, workspace=workspace)
            assert result['result'] == 1
            original = json.loads((workspace / 'workspace.json').read_text())['package_sha256']
            results.append({'case':'negotiated-signed-install-readback','result':result})
            # A malicious host can ignore negotiation. Firmware must reject it
            # before begin()/commit, preserving the previously installed app.
            bad = project / 'incompatible-update.lfapp'
            bad.write_bytes(pack({**metadata,'version':'999.0.0','minimum_api':API_REVISION+1},image))
            with patch.object(Client, 'require_compatible', lambda *a, **k: None):
                try: exercise(bad,qemu,firmware,workspace=workspace)
                except DeviceError as exc: assert 'error 3' in str(exc)
                else: raise AssertionError('firmware installed unsupported requirements')
            assert json.loads((workspace / 'workspace.json').read_text())['package_sha256'] == original
            # Cold mount + idempotent install includes exact signed-byte readback.
            result = exercise(app,qemu,firmware,workspace=workspace)
            assert result['result'] == 1
            results.append({'case':'device-rejection-keeps-old-app-after-cold-boot','result':result})
    write_json(output / 'report.json', {'schema':1,'validation':'developer-local','firmware_sha256':digest(firmware),
                                      'qemu_sha256':digest(qemu),'status':'passed','cases':results,'skipped':skipped})
    print('PASS: schema 1 loader/USB, unsupported preflight, malicious host rejection and unchanged committed app',flush=True)
    if skipped: print('SKIP: old-loader refusal requires --old-firmware',flush=True)
    else: print('PASS: old loader refuses schema 1',flush=True)


if __name__ == '__main__':main()
