#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""One-shot queue consumer. Requires an operator-provisioned, digest-pinned image."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from lfapp import unpack
from source import MAX_SOURCE, decode
from signing import sign, public_der

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError('Build API redirects are forbidden')


def sandbox(image, source, timeout=180):
    if not re.fullmatch(r'(?:[A-Za-z0-9./:_-]+@sha256:|sha256:)[0-9a-f]{64}', image):
        raise ValueError('Builder image must be pinned by its immutable sha256 digest')
    name = 'lefony-build-' + uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix='lf-build-') as folder:
        output = Path(folder)/'output'
        errors = Path(folder)/'errors'
        data = Path(folder)/'source'
        data.write_bytes(source)
        # No host mount, credentials, network, privilege, or writable image.
        command = ['docker','run','--rm','--pull=never','--name',name,'--network=none',
          '--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=64',
          '--memory=1g','--memory-swap=1g','--cpus=2','--user=65534:65534',
          '--tmpfs=/tmp:rw,nosuid,nodev,size=128m','--ipc=none','-i',image]
        try:
            with data.open('rb') as inp, output.open('wb') as out, errors.open('wb') as err:
                process = subprocess.Popen(command, stdin=inp, stdout=out, stderr=err)
                end = time.monotonic()+timeout
                while process.poll() is None:
                    if time.monotonic()>end or output.stat().st_size>2900000 or errors.stat().st_size>1048576:
                        process.kill(); process.wait(timeout=5)
                        raise ValueError('Validation exceeded time or output limits')
                    time.sleep(.1)
                if process.returncode or output.stat().st_size>2900000 or errors.stat().st_size>1048576:
                    raise ValueError('Isolated validator failed')
            return json.loads(output.read_bytes())
        finally:
            subprocess.run(['docker','rm','--force',name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', required=True, help='HTTPS origin of the store')
    parser.add_argument('--image', required=True, help='Preloaded image@sha256:digest or immutable local sha256:image-id')
    parser.add_argument('--signing-key', required=True, type=Path, help='Independent app private key; never mounted in the validator')
    parser.add_argument('--qualification', required=True, type=Path, help='Passed report from qualify.py for this exact image')
    args = parser.parse_args()
    qualification = json.loads(args.qualification.read_text())
    cases = qualification.get('cases', [])
    if not isinstance(cases, list) or {case.get('case') for case in cases if isinstance(case, dict) and case.get('passed') is True} != {'return','compile-error','hang','privileged-memory','malformed-source'}:
        parser.error('Qualification report does not contain all required passing checks')
    if qualification.get('schema') != 1 or qualification.get('qualified') is not True or qualification.get('image') != args.image:
        parser.error('Qualify this exact immutable validator image before consuming jobs')
    public_der(args.signing_key, private=True)
    url = urllib.parse.urlsplit(args.store)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
        parser.error('--store must be an HTTPS origin')
    token = os.environ.get('LEFONY_STORE_BUILDER_TOKEN','')
    if len(token)<32:
        parser.error('Set LEFONY_STORE_BUILDER_TOKEN privately')
    # Environment belongs only to this host orchestrator. No env is passed into Docker.
    opener = urllib.request.build_opener(NoRedirect())
    def api(path, method='GET', body=None, lease=None):
        headers = {'Authorization':'Bearer '+token, 'Content-Type':'application/json', 'User-Agent':'Lefony-Validator/1'}
        if lease: headers['X-Lefony-Lease']=lease
        request = urllib.request.Request(args.store.rstrip('/')+'/api/store'+path, method=method,
            headers=headers, data=None if body is None else json.dumps(body).encode())
        with opener.open(request, timeout=30) as response:
            value = response.read(2900001)
        if len(value)>2900000: raise ValueError('Build API response too large')
        return value
    job = json.loads(api('/build/claim','POST'))['job']
    if job is None:
        print('No queued apps.'); return
    if not re.fullmatch(r'[0-9a-f-]{36}',job['id']) or not re.fullmatch(r'[0-9a-f]{64}',job['lease']):
        raise ValueError('Invalid build job')
    source = api('/build/'+job['id']+'/source',lease=job['lease'])
    if len(source)>MAX_SOURCE or hashlib.sha256(source).hexdigest()!=job['source_hash']:
        raise ValueError('Source download digest mismatch')
    metadata = decode(source)['manifest']
    try:
        result = sandbox(args.image,source)
        if result.get('source_hash')!=job['source_hash'] or type(result.get('passed')) is not bool:
            raise ValueError('Validator result does not match the source')
        if result['passed']:
            package = base64.b64decode(result['package'],validate=True)
            actual, _ = unpack(package)
            if actual!=metadata: raise ValueError('Artifact does not match source identity')
            report = json.loads(result['report'])
            if report.get('package_sha256')!=hashlib.sha256(package).hexdigest() or report.get('reproducible') is not True or report.get('os_responsive') is not True:
                raise ValueError('Invalid validation evidence')
            signed = sign(package, args.signing_key)
            result['package'] = base64.b64encode(signed).decode()
            report['unsigned_package_sha256'] = report.pop('package_sha256')
            report['package_sha256'] = hashlib.sha256(signed).hexdigest()
            report['signed_package_format'] = 1
            result['report'] = json.dumps(report, separators=(',', ':'))
    except Exception as error:
        # Do not expose raw container logs, host paths or environment in public reports.
        print(type(error).__name__ + ': validation failed',file=sys.stderr)
        result = {'source_hash':job['source_hash'],'passed':False,'report':'Automatic native build or emulator validation failed. Run lefony-sdk build and test locally.'}
    reply = json.loads(api('/build/'+job['id']+'/complete','POST',result,job['lease']))
    print(json.dumps({'id':job['id'],'state':reply['state']}))


if __name__ == '__main__':
    main()
