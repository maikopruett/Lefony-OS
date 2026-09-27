#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Export/check the public installer contract; contains no private inputs."""
import argparse
import json
from pathlib import Path
from prime_dual_installer import contract

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', type=Path, help='verify the website copy without changing it')
    args = parser.parse_args()
    exported = json.dumps(contract(), indent=2) + '\n'
    if args.check:
        if args.check.read_text() != exported:
            parser.error('Website installer contract differs; export it again before building.')
        print('PASS exact public installer contract parity')
    else:
        print(exported, end='')
