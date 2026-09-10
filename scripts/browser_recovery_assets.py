#!/usr/bin/env python3
"""Fetch and verify the pinned public recovery environment, without USB access.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

from prepare_browser_recovery_release import RECOVERY_ASSETS, bootstrap_ranges, read_assets

PIN_PATH = Path(__file__).resolve().parents[1] / 'ports/lefony-prime-g2/browser-recovery.json'
ASSETS = (*RECOVERY_ASSETS, 'recoveryUpstream', 'recoveryNotices')


def read_pin():
    pin = json.loads(PIN_PATH.read_text())
    if (pin.get('schema') != 1 or pin.get('repository') != 'maikopruett/Lefony-OS' or
            not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,127}', pin.get('tag', '')) or
            set(pin.get('assets', {})) != set(ASSETS)):
        raise ValueError('Invalid public recovery pin')
    names = set()
    for asset in pin['assets'].values():
        path = asset.get('path', '')
        if (not re.fullmatch(r'artifacts/[A-Za-z0-9][A-Za-z0-9._-]*', path) or
                path in names or type(asset.get('bytes')) is not int or
                not 0 < asset['bytes'] <= 128 * 1024 * 1024 or
                not re.fullmatch(r'[a-f0-9]{64}', asset.get('sha256', ''))):
            raise ValueError('Invalid pinned recovery artifact')
        names.add(path)
    return pin


def verified_assets(directory):
    pin = read_pin()
    files = read_assets(pin, directory, ASSETS, flat=True)
    bootstrap_ranges(files)
    return pin['assets'], files


def download(directory):
    pin = read_pin()
    directory.mkdir(parents=True, exist_ok=False)
    # Explicit names only. Never download private captures, old firmware or keys.
    command = ['gh', 'release', 'download', pin['tag'], '--repo', pin['repository'],
               '--dir', str(directory)]
    for asset in pin['assets'].values():
        command.extend(['--pattern', asset['path'].removeprefix('artifacts/')])
    subprocess.run(command, check=True, timeout=300)
    verified_assets(directory)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    download(args.output)
    print('Pinned public recovery assets verified. No calculator accessed.')
