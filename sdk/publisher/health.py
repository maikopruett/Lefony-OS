#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only deployment check. API credentials are never printed or put in argv."""
import argparse
import json
import os
import urllib.parse
import urllib.request
from worker import NoRedirect

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store',required=True)
    args=parser.parse_args()
    url=urllib.parse.urlsplit(args.store)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
        parser.error('store must be an HTTPS origin')
    token=os.environ.get('LEFONY_STORE_BUILDER_TOKEN','')
    if len(token)<32: parser.error('Set the private LEFONY_STORE_BUILDER_TOKEN environment variable')
    request=urllib.request.Request(args.store.rstrip('/')+'/api/store/build/health',headers={'Authorization':'Bearer '+token,'User-Agent':'Lefony-Validator/1'})
    opener=urllib.request.build_opener(NoRedirect())
    with opener.open(request,timeout=30) as response: data=response.read(8193)
    if len(data)>8192: raise ValueError('Health response too large')
    print(json.dumps(json.loads(data),indent=2))
