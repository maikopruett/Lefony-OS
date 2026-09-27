#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify a reviewed source profile and installed snapshot without hardware I/O.

Exercise every modeled erase/program/half-page/journal boundary for the exact
source-to-dual plan, rollback, and optionally a retained bootstream repair.
Inputs are private immutable files; all writes occur in copy-on-write memory.
This does not establish physical power-loss behavior or release readiness.
"""
import argparse
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prime_dual_installer import atomic_json, checked_plan
from prime_dual_boot_contract import require
import prime_dual_migration as model
import prime_phase6_boot_repair as repair

faults = importlib.import_module('test-prime-dual-migration-faults')


def checked_repair(path):
    review = json.loads(path.read_text())
    require(review['purpose'] == 'phase6-boot-marker-repair', 'unsupported repair review')
    for field in ('current', 'backup', 'uboot', 'public_key'):
        require(model.file_hash(review[field]).hex() == review[field + '_sha256'],
                'repair input changed')
    tx, original = repair.plan(review['current'], review['backup'],
        bytes.fromhex(review['backup_sha256']), review['uboot'],
        review['public_key'], review['install_review'])
    require(tx.id.hex() == review['transaction'] and
            original.hex() == review['original_transaction'] and
            [c.identity() for c in tx.changes] == review['changes'], 'repair plan changed')
    return review, tx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'installed', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--repair-review', type=Path)
    args = parser.parse_args()
    out = model.private_output(args.output)
    require(not out.exists(), 'output must be new')
    bundle = json.loads(args.bundle.read_text())
    tx, bad, paths, digest = checked_plan(bundle, 'lefony')
    installed_hash = model.file_hash(args.installed)
    with model.NativeBCH() as native:
        model.verify_routes(args.installed, paths['uboot'], bad, native)
    restore, restore_bad = model.build_restore_plan(args.installed, paths['backup'], digest)
    retained = checked_repair(args.repair_review) if args.repair_review else None
    out.mkdir(parents=True)
    results = []

    def run(name, source, backup, transaction, inventory, uboot, replace=False):
        if replace:
            result = faults.qualify_restore_journal_replacement(
                source, backup, transaction, inventory, uboot)
            atomic_json(out / (name + '-journal-replacement.json'), result)
        result = faults.qualify(source, backup, transaction, inventory, uboot)
        result['transaction'] = transaction.id.hex()
        atomic_json(out / (name + '.json'), result)
        results.append(result)

    run('install', paths['backup'], paths['backup'], tx, bad, paths['uboot'])
    run('restore', args.installed, paths['backup'], restore, restore_bad,
        paths['uboot'], replace=True)
    if retained:
        review, transaction = retained
        run('repair', Path(review['current']), Path(review['backup']), transaction,
            model.factory_inventory(review['backup']), Path(review['uboot']), replace=True)
    require(model.file_hash(args.installed) == installed_hash, 'installed fixture changed')
    # Revalidate signed inputs and retained repair after all copy-on-write trials.
    repeated, _, _, _ = checked_plan(bundle, 'lefony')
    require(repeated.id == tx.id, 'source inputs changed during qualification')
    if args.repair_review:
        require(checked_repair(args.repair_review)[1].id == retained[1].id,
                'repair inputs changed during qualification')
    atomic_json(out / 'qualification.json', {
        'result': 'PASS', 'source_profile': bundle.get('source_profile', 'stock-hp'),
        'installed_sha256': installed_hash.hex(), 'results': results,
        'bundle_sha256': model.file_hash(args.bundle).hex(),
        'physical_qualification': False,
        'scope': 'copy-on-write physical-codeword fault model; no hardware access',
        'limits': ['Electrical interrupted erase/program is not modeled',
                   'ARM boot and physical acceptance are separate checks'],
    })
    print('PASS reviewed install, exact rollback and requested repair interruption boundaries', flush=True)


if __name__ == '__main__':
    main()
