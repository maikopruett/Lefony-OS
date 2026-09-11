#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate only public app trust roots from an explicit JSON array of PEM paths."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sdk/tools'))
from signing import firmware_header

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('key_list', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    keys = json.loads(args.key_list.read_text())
    if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
        parser.error('key list must be a JSON array of public PEM file paths')
    firmware_header([args.key_list.resolve().parent / key for key in keys], args.output)
