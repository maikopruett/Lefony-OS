#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Manage signed native apps without invoking the firmware update protocol."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from device import Client
from prime_g2_usb_diag import LibUSB

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('status');sub.add_parser('list');sub.add_parser('cancel-upload')
    install=sub.add_parser('install');install.add_argument('package',type=Path)
    install.add_argument('--public-key',type=Path,action='append',default=[])
    remove=sub.add_parser('remove');remove.add_argument('id')
    migrate=sub.add_parser('migrate-storage');migrate.add_argument('--backup',type=Path,required=True)
    migrate.add_argument('--retire-stock-filesystem',action='store_true',required=True)
    args=parser.parse_args()
    transport=LibUSB()
    try:
        client=Client(transport)
        if args.command=='status':result=client.status()
        elif args.command=='cancel-upload':client.cancel_upload();result={'cancelled':True}
        else:
            client.connect()
            if args.command=='list':result=client.catalog()
            elif args.command=='remove':client.remove(args.id);result={'removed':args.id}
            elif args.command=='install':result=client.install(args.package.read_bytes(),args.public_key or [ROOT/'ports/lefony-prime-g2/app-signing.pub'])
            else:result=client.backup_and_migrate(args.backup,retire_stock_filesystem=args.retire_stock_filesystem)
        print(json.dumps(result,indent=2))
    finally:transport.close()

if __name__=='__main__':main()
