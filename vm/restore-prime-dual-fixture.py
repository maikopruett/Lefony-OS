#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Restore a disposable shared-layout fixture to its exact retained stock backup."""
import argparse
from pathlib import Path
from prime_dual_migration import restore_stock

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('current','backup','uboot','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--backup-sha256',required=True)
    p.add_argument('--resume',action='store_true')
    a=p.parse_args()
    print(restore_stock(a.current,a.backup,a.uboot,bytes.fromhex(a.backup_sha256),a.output,resume=a.resume))
