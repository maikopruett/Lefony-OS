# SPDX-License-Identifier: GPL-3.0-or-later
"""Native app build tools. Never flashes hardware or implicitly publishes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from lfapp import PackageError, elf_segments, manifest, pack, unpack
from sdk_environment import SDK

RUNTIME = SDK.parent / 'runtime'
QEMU_NAME = 'qemu-system-arm.exe' if os.name == 'nt' else 'qemu-system-arm'
DEFAULT_QEMU = RUNTIME / QEMU_NAME if RUNTIME.exists() else SDK.parent / 'build/qemu-prime-g2' / QEMU_NAME
DEFAULT_FIRMWARE = RUNTIME / 'firmware.elf' if RUNTIME.exists() else SDK.parent / 'dist/lefony-os-prime-g2-vm-native.elf'
TRUST = sorted((SDK / 'trust').glob('*.pem'))



def build(project, profile='release'):
    from build import build as compile_app
    return compile_app(project, SDK, profile)


def package(project, profile='release'):
    metadata, image = build(project, profile)
    destination = project / "build" / f"{metadata['id']}-{metadata['version']}.lfapp"
    destination.write_bytes(pack(metadata, image.read_bytes()))
    unpack(destination.read_bytes())
    return destination


def management_transport(args, physical):
    if args.emulator_usb is not None:
        from emulator_usb import ManagementUSB
        return ManagementUSB(args.emulator_usb, physical)
    return physical()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor")
    doctor.add_argument('--https-origin', help='explicit read-only HEAD check of an HTTPS origin; no account or device access')
    doctor.add_argument('--https-ca-file', type=Path, help='explicit CA file for that check, replacing system trust')
    keys = sub.add_parser('keys', help='manage developer public keys with approval on the calculator')
    keys.add_argument('--emulator-usb', type=Path, help='exclusive already-enumerated QEMU USB socket; no physical device access')
    key_commands = keys.add_subparsers(dest='key_operation', required=True)
    generate = key_commands.add_parser('generate', help='create a new independent app identity locally; no USB access')
    generate.add_argument('--private-key', type=Path, required=True)
    generate.add_argument('--public-key', type=Path, required=True)
    key_commands.add_parser('status');key_commands.add_parser('list')
    enroll = key_commands.add_parser('enroll');enroll.add_argument('--public-key',type=Path,required=True);enroll.add_argument('--label',required=True)
    revoke = key_commands.add_parser('revoke');revoke.add_argument('fingerprint')
    remove = key_commands.add_parser('remove');remove.add_argument('fingerprint')
    damaged = key_commands.add_parser('backup-damaged');damaged.add_argument('backup',type=Path);damaged.add_argument('--replace',action='store_true')
    repair = key_commands.add_parser('repair');repair.add_argument('--public-key',type=Path,required=True);repair.add_argument('--label',required=True)
    repair.add_argument('--backup',type=Path,required=True,help='new destination for the verified damaged registry before calculator approval')
    partial = key_commands.add_parser('backup-unreadable',help='save readable registry fragments and mark missing regions')
    partial.add_argument('backup',type=Path);partial.add_argument('--replace',action='store_true')
    repair_partial = key_commands.add_parser('repair-unreadable',help='back up readable fragments, then request approval to rebuild trust with one key')
    repair_partial.add_argument('--public-key',type=Path,required=True);repair_partial.add_argument('--label',required=True)
    repair_partial.add_argument('--backup',type=Path,required=True,help='new destination for a verified partial backup; unreadable bytes cannot be recovered')
    key_cancel = key_commands.add_parser('cancel');key_cancel.add_argument('sequence',type=int);key_cancel.add_argument('--nonce',required=True)
    install = sub.add_parser('install', help='install an explicitly signed app over USB and verify readback')
    install.add_argument('package',type=Path);install.add_argument('--public-key',type=Path,action='append',required=True)
    install.add_argument('--recover-signer',action='store_true',help='recover one app from a revoked key with approval on the calculator')
    install.add_argument('--emulator-usb', type=Path, help='exclusive already-enumerated QEMU USB socket; no physical device access')
    signing = sub.add_parser('sign', help='sign an unsigned app locally with an explicit private key; no USB or store access')
    signing.add_argument('package', type=Path)
    signing.add_argument('--private-key', type=Path, required=True)
    signing.add_argument('--output', type=Path, required=True, help='new destination for the verified signed package')
    account_commands = []
    login = sub.add_parser('login', help='authorize a scoped store session through GitHub in your browser')
    login.add_argument('--no-browser', action='store_true', help='print the sign-in URL without opening a browser')
    login.add_argument('--label', default='Lefony SDK', help='session name shown in website SDK access')
    account_commands.append(login)
    for command in ('logout', 'whoami'):
        account_commands.append(sub.add_parser(command, help='manage the active SDK store session'))
    apps = sub.add_parser('apps', help='list every owned store app and its release history')
    operations = apps.add_subparsers(dest='app_operation', required=True)
    account_commands.append(operations.add_parser('list'))
    show = operations.add_parser('show'); show.add_argument('app_id'); account_commands.append(show)
    withdraw = operations.add_parser('withdraw', help='withdraw every store version; does not uninstall existing devices')
    withdraw.add_argument('app_id')
    modes = withdraw.add_mutually_exclusive_group()
    modes.add_argument('--dry-run', action='store_true', help='review the withdrawal without changing the store')
    modes.add_argument('--resume', metavar='OPERATION_ID', help='retry the saved withdrawal')
    modes.add_argument('--status', metavar='OPERATION_ID', help='read the saved withdrawal receipt')
    account_commands.append(withdraw)
    project_command = sub.add_parser('project', help='link local source to an owned store app')
    operations = project_command.add_subparsers(dest='project_operation', required=True)
    link = operations.add_parser('link'); link.add_argument('app_id'); account_commands.append(link)
    operations.add_parser('unlink', help='remove only the local store link; works offline')
    account_commands.append(operations.add_parser('list', help='show local project locations for the active account'))
    listing_command = sub.add_parser('listing', help='review and merge store listing changes into this project')
    operations = listing_command.add_subparsers(dest='listing_operation', required=True)
    pull = operations.add_parser('pull', help='merge text and images using the saved store baseline')
    pull.add_argument('--dry-run', action='store_true', help='save a local review without changing project files')
    pull.add_argument('--plan', metavar='PLAN_ID', help='apply the exact saved review after rechecking both sides')
    pull.add_argument('--take-local', action='append', default=[], choices=['name','short_description','description','release_notes','repository_url','icon','screenshots'])
    pull.add_argument('--take-remote', action='append', default=[], choices=['name','short_description','description','release_notes','repository_url','icon','screenshots'])
    account_commands.append(pull)
    recover = operations.add_parser('recover', help='roll back an interrupted local pull; works offline')
    recover.add_argument('plan_id')
    push = operations.add_parser('push', help='update listing text/images without rebuilding or publishing a release')
    modes = push.add_mutually_exclusive_group()
    modes.add_argument('--dry-run', action='store_true', help='show listing differences without changing the store')
    modes.add_argument('--resume', metavar='OPERATION_ID', help='retry the exact saved listing request')
    modes.add_argument('--status', metavar='OPERATION_ID', help='read the saved listing receipt')
    account_commands.append(push)
    for command in account_commands:
        command.add_argument('--store-origin', default='https://lefony.com', help='explicit HTTPS store origin; credentials are isolated by origin')
        command.add_argument('--store-ca-file', type=Path, help='explicit CA bundle for a development store')
    companion = sub.add_parser('companion',help='explicit app-scoped USB/HTTPS connection; no firmware operations')
    companion.add_argument('--app-id',required=True)
    companion.add_argument('--signer',required=True,help='expected 64-digit signer ID from the signed package')
    companion.add_argument('--package-hash',help='optional exact LFAPP1 inner payload SHA-256')
    companion.add_argument('--allow-origin',action='append',required=True,help='exact granted HTTPS origin; repeat to add another')
    companion.add_argument('--method',action='append',choices=['GET','HEAD','POST','PUT','PATCH','DELETE'],default=None)
    companion.add_argument('--upload-limit',type=int,default=8*1024*1024)
    companion.add_argument('--response-limit',type=int,default=8*1024*1024)
    companion.add_argument('--timeout-ms',type=int,default=120000)
    companion.add_argument('--ca-file',type=Path,help='explicit host CA bundle, including controlled local TLS fixtures')
    companion.add_argument('--label',default='Lefony SDK companion')
    companion.add_argument('--emulator-usb',type=Path,help='exclusive already-enumerated QEMU USB socket; uses only the emulator, never physical USB discovery')
    new = sub.add_parser("new")
    new.add_argument("directory", type=Path)
    new.add_argument('--template', choices=['basic', 'counter', 'form', 'graph', 'pocket-lab', 'forms-tables', 'graph-explorer', 'reference-cards', 'c-main', 'notebook', 'link-gallery', 'ui-gallery'], default='basic')
    lock = sub.add_parser('lock', help='inspect or explicitly update the pinned SDK identity')
    lock.add_argument('--update', action='store_true')
    work = sub.add_parser('workspace', help='manage synthetic emulator data; export includes app data')
    work.add_argument('operation', choices=['info', 'reset', 'clone', 'export', 'restore'])
    work.add_argument('name')
    work.add_argument('target', nargs='?')
    debug = sub.add_parser('debug', help='pause a VM with matching symbols and a private local GDB socket')
    debug.add_argument('--qemu', type=Path, default=DEFAULT_QEMU)
    debug.add_argument('--firmware', type=Path, default=DEFAULT_FIRMWARE)
    debug.add_argument('--headless', action='store_true')
    debugger = sub.add_parser('debugger', help='open the current project debug script with the SDK ARM GDB')
    debugger.add_argument('--batch', action='store_true', help='run the script and commands, then exit')
    debugger.add_argument('--execute', action='append', default=[], help='GDB command after the generated script; repeat as needed')
    diagnose = sub.add_parser('symbolize', help='resolve a fault PC using matching local symbols')
    diagnose.add_argument('package', type=Path)
    diagnose.add_argument('pc', type=lambda value: int(value, 0))
    preview = sub.add_parser('preview', help='rebuild actual ARM source and inspect a synthetic preview')
    preview.add_argument('--qemu', type=Path, default=DEFAULT_QEMU)
    preview.add_argument('--firmware', type=Path, default=DEFAULT_FIRMWARE)
    preview.add_argument('--scenario', type=Path, help='project-relative normal-input replay')
    preview.add_argument('--fixture-dir', type=Path, help='initial named-file/directory fixtures; saved edits are retained until reset')
    preview_data = preview.add_mutually_exclusive_group()
    preview_data.add_argument('--reset-data',action='store_true',help='start fresh or reseed fixtures on the next successful preview')
    preview_data.add_argument('--fresh-data',action='store_true',help='use disposable data on every run and leave saved preview data untouched')
    preview.add_argument('--once', action='store_true', help='build and capture once instead of watching saves')
    preview.add_argument('--no-inspect', action='store_true', help='capture an app without layout instrumentation')
    publish = sub.add_parser('publish', help='snapshot, ARM-test and publish the exact project submission')
    publication_mode = publish.add_mutually_exclusive_group()
    publication_mode.add_argument('--dry-run', action='store_true', help='prepare locally without authentication or upload')
    publication_mode.add_argument('--resume', metavar='ATTEMPT_ID', help='upload or resume a saved exact-byte attempt without rebuilding')
    publication_mode.add_argument('--status', metavar='ATTEMPT_ID', help='query the saved upload or publication receipt')
    publication_mode.add_argument('--cancel', metavar='ATTEMPT_ID', help='cancel staging; does not withdraw an accepted release')
    publish.add_argument('--store-origin', default='https://lefony.com', help='explicit HTTPS store origin; credentials are isolated by origin')
    publish.add_argument('--store-ca-file', type=Path, help='explicit CA bundle for a development store')
    publish.add_argument('--qemu', type=Path, default=DEFAULT_QEMU)
    publish.add_argument('--firmware', type=Path, default=DEFAULT_FIRMWARE)
    for name in ("build", "package", "run", "test", "source"):
        child = sub.add_parser(name)
        if name == 'source':
            child.add_argument('--format', type=int, choices=[0, 1, 2], default=0)
        if name != 'source':
            child.add_argument('--profile', choices=['debug', 'release'], default='release')
        if name in ("run", "test"):
            child.add_argument('--measure-resources', action='store_true', help='observe stack use in matching VM firmware; changes initial unused stack bytes')
            child.add_argument("--qemu", type=Path, default=DEFAULT_QEMU)
            child.add_argument("--firmware", type=Path, default=DEFAULT_FIRMWARE)
            child.add_argument("--headless", action="store_true")
            if name == 'test':
                child.add_argument('--suite', default='all', help='all, startup, or a project-relative replay JSON path')
            child.add_argument('--workspace', help='persistent synthetic workspace name; omission uses disposable preview')
    launch = sub.add_parser("launch")
    launch.add_argument("package", type=Path)
    launch.add_argument("--public-key", type=Path, action="append", default=TRUST)
    launch.add_argument("--headless", action="store_true")
    launch.add_argument("--test", action="store_true")
    launch.add_argument("--qemu", type=Path, default=DEFAULT_QEMU)
    launch.add_argument("--firmware", type=Path, default=DEFAULT_FIRMWARE)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("package", type=Path)
    inspect.add_argument("--public-key", type=Path, action="append", default=TRUST)
    files = sub.add_parser('files', help='explicit app-private file import/export over USB')
    files.add_argument('--emulator-usb',type=Path,help='exclusive already-enumerated QEMU USB socket; no physical device access')
    commands = files.add_subparsers(dest='file_operation', required=True)
    commands.add_parser('status')
    cancel = commands.add_parser('cancel');cancel.add_argument('sequence', type=int)
    for operation in ('info','list','import','export'):
        command = commands.add_parser(operation);command.add_argument('app_id')
        if operation=='list':command.add_argument('directory', nargs='?', default='')
        if operation in ('import','export'):
            command.add_argument('path', help='app-relative file path')
            command.add_argument('local', type=Path, help='local source for import or destination for export')
            command.add_argument('--replace', action='store_true', help='explicitly replace an existing destination')
    data = sub.add_parser('data', help='explicit private-data backup/restore and retained-pair rollback over USB')
    data.add_argument('--emulator-usb',type=Path,help='exclusive already-enumerated QEMU USB socket; no physical device access')
    commands = data.add_subparsers(dest='data_operation', required=True)
    for operation in ('info','export','restore','rollback'):
        command = commands.add_parser(operation);command.add_argument('app_id')
        if operation in ('export','restore'): command.add_argument('backup',type=Path)
        if operation=='export': command.add_argument('--replace',action='store_true',help='replace an existing local backup')
    archive = sub.add_parser('archive', help='signed whole-app backup and restore over USB')
    archive.add_argument('--emulator-usb',type=Path,help='exclusive already-enumerated QEMU USB socket; no physical device access')
    commands = archive.add_subparsers(dest='archive_operation', required=True)
    commands.add_parser('status')
    cancel = commands.add_parser('cancel');cancel.add_argument('sequence',type=int);cancel.add_argument('--nonce',required=True)
    info = commands.add_parser('info');info.add_argument('app_id')
    info.add_argument('--include-unreadable',action='store_true',help='inspect surviving archive repair identity when installed code is unreadable')
    for operation in ('export','restore'):
        command=commands.add_parser(operation)
        if operation=='export':command.add_argument('app_id')
        else:
            modes=command.add_mutually_exclusive_group()
            modes.add_argument('--allow-recovery-pair',action='store_true',help='request calculator approval for a fresh restore across developer signers')
            modes.add_argument('--repair-code',action='store_true',help='replace an unreadable installed app from an archive proving its exact original signed code')
        command.add_argument('archive',type=Path)
        command.add_argument('--replace',action='store_true',help='explicitly replace the destination file or installed app')
        command.add_argument('--public-key',type=Path,action='append',default=TRUST,help='trusted signing public key; repeat for each archive signer')
    args = parser.parse_args()
    try:
        if args.command == 'sign':
            from signing import sign_file
            print(json.dumps(sign_file(args.package, args.private_key, args.output), indent=2));return 0
        if args.command == 'archive':
            from archive_device import Client as ArchiveClient, ArchiveUSB, prepare
            from device import Client
            from usb_files import transfer_interrupts
            with transfer_interrupts() as cancelled:
                if args.archive_operation=='restore':
                    # Keep the validated descriptor open and authenticate every
                    # package before enumerating or opening a USB device.
                    with prepare(args.archive,args.public_key,cancelled=cancelled) as source:
                        cancelled()
                        with management_transport(args, ArchiveUSB) as transport:
                            result=ArchiveClient(Client(transport)).restore_prepared(source,replace=args.replace,
                                allow_recovery_pair=args.allow_recovery_pair,repair_code=args.repair_code,cancelled=cancelled,
                                notify=lambda info:print(json.dumps(info,indent=2),file=sys.stderr))
                else:
                    if args.archive_operation=='export' and not args.public_key:
                        raise ValueError('Provide trusted --public-key files to verify the exported archive')
                    with management_transport(args, ArchiveUSB) as transport:
                        client=ArchiveClient(Client(transport))
                        if args.archive_operation=='status':result=client.status();cancelled()
                        elif args.archive_operation=='cancel':result=client.cancel(args.sequence,args.nonce)
                        elif args.archive_operation=='info':result=client.info(args.app_id,include_unreadable=args.include_unreadable);cancelled()
                        else:result=client.export(args.app_id,args.archive,args.public_key,replace=args.replace,cancelled=cancelled)
            print(json.dumps({k:v.hex() if isinstance(v,bytes) else v for k,v in result.items()},indent=2));return 0
        if args.command == 'keys':
            if args.key_operation == 'generate':
                from signing import keygen
                if args.emulator_usb is not None:
                    raise ValueError('Key generation is local; omit --emulator-usb')
                print(json.dumps(keygen(args.private_key, args.public_key), indent=2));return 0
            from keys_device import Client, KeyUSB
            with management_transport(args, KeyUSB) as transport:
                client=Client(transport)
                if args.key_operation=='status':result=client.status()
                elif args.key_operation=='list':result=client.keys()
                elif args.key_operation=='cancel':result=client.cancel(args.sequence,args.nonce)
                elif args.key_operation=='backup-damaged':result=client.backup_damaged(args.backup,replace=args.replace)
                elif args.key_operation=='repair':result=client.repair(args.public_key,args.label,args.backup,notify=lambda text:print(text,file=sys.stderr,flush=True))
                elif args.key_operation=='backup-unreadable':result=client.backup_unreadable(args.backup,replace=args.replace)
                elif args.key_operation=='repair-unreadable':result=client.repair_unreadable(args.public_key,args.label,args.backup,notify=lambda text:print(text,file=sys.stderr,flush=True))
                else:
                    options={'public_key':args.public_key,'label':args.label} if args.key_operation=='enroll' else {'fingerprint':args.fingerprint}
                    client.begin(args.key_operation,notify=lambda text:print(text,file=sys.stderr,flush=True),**options)
                    result=client.wait()
                print(json.dumps(result,indent=2))
                return 0 if result.get('state') not in ('failed','denied','expired','cancelled') else 1
        if args.command == 'install':
            from device import Client
            from keys_device import InstallUSB, RecoveryUSB, Client as KeyClient
            from signing import MAX_PACKAGE, verify
            if not args.package.is_file():raise ValueError('Select a regular signed package file')
            data_spec = data_parts = None
            if args.package.suffix == '.lfbundle':
                if args.recover_signer:raise ValueError('Signer recovery requires a standalone package; bundled data is not a recovery operation')
                from bundled_data import load_bundle
                content, app, data_spec, data_parts = load_bundle(args.package, args.public_key)
            else:
                with args.package.open('rb') as source:content=source.read(MAX_PACKAGE+1)
            if not 468<=len(content)<=MAX_PACKAGE:raise ValueError('Invalid signed package size')
            verify(content, args.public_key)  # Reject untrusted bytes before opening any USB transport.
            class BundleUSB(InstallUSB):
                READ_REQUESTS = InstallUSB.READ_REQUESTS + (0x70, 0x72)
                WRITE_REQUESTS = InstallUSB.WRITE_REQUESTS + (0x71, 0x72, 0x73, 0x74, 0x75)
            with management_transport(args, RecoveryUSB if args.recover_signer else BundleUSB if data_spec else InstallUSB) as transport:
                if args.recover_signer:
                    result=KeyClient(transport).recover_install(content,args.public_key,notify=lambda text:print(text,file=sys.stderr,flush=True))
                else:
                    client = Client(transport)
                    if data_spec:
                        from bundled_data import install as install_data
                        existing = any(row['id'] == app['id'] for row in client.catalog())
                        if existing:install_data(client, app['id'], data_spec, data_parts)
                    result=client.install(content,args.public_key)
                    if data_spec and not existing:install_data(client, app['id'], data_spec, data_parts)
                    if data_spec:result = {**result, 'bundled_data': 'verified'}
            print(json.dumps(result,indent=2));return 0
        if args.command == 'listing':
            from store_listing_sync import pull, recover
            if args.listing_operation == 'recover':
                result = recover(args.project, args.plan_id)
            elif args.listing_operation == 'push':
                from store_accounts import configured, authenticated
                from store_mutations import push
                client, credentials = configured(args)
                result = push(args.project, client, authenticated(client, credentials)['account'], dry_run=args.dry_run,
                              operation_id=args.status or args.resume, operation='status' if args.status else 'resume')
            else:
                if args.dry_run and args.plan:
                    raise ValueError('Use --dry-run to create a review, or --plan to apply it.')
                from store_accounts import configured, authenticated
                client, credentials = configured(args)
                account = authenticated(client, credentials)['account']
                result = pull(args.project, client, account, dry_run=args.dry_run, plan_id=args.plan,
                              take_local=args.take_local, take_remote=args.take_remote)
            print(json.dumps(result, indent=2))
            return 1 if result['state'] == 'conflicts' else 0
        if args.command == 'project' and args.project_operation == 'unlink':
            from store_projects import unlink
            print(json.dumps(unlink(args.project), indent=2))
            return 0
        if args.command in ('login', 'logout', 'whoami', 'apps', 'project'):
            from store_accounts import configured, login, logout, authenticated
            client, credentials = configured(args)
            if args.command == 'login':
                login(client, credentials, label=args.label, open_browser=not args.no_browser)
                return 0
            if args.command == 'logout':
                result = logout(client, credentials)
            else:
                result = authenticated(client, credentials)
                if args.command == 'apps':
                    if args.app_operation == 'withdraw':
                        from store_mutations import withdraw
                        result = withdraw(client, result['account'], args.app_id, dry_run=args.dry_run,
                                          operation_id=args.status or args.resume, operation='status' if args.status else 'resume')
                    else:
                        result = {'apps': client.apps()} if args.app_operation == 'list' else client.app(args.app_id)
                elif args.command == 'project':
                    from store_projects import link, projects
                    result = link(args.project, client, result['account'], args.app_id) if args.project_operation == 'link' else {
                        'projects': projects(client.origin, result['account']['id'])}
            print(json.dumps(result, indent=2))
            return 0
        if args.command == 'companion':
            from companion import run_cli
            args.method=args.method or ['GET','HEAD']
            return run_cli(args)
        if args.command == 'publish':
            if args.dry_run:
                from store_snapshot import prepare
                result = prepare(args.project, SDK, args.qemu, args.firmware)
            else:
                from store_accounts import configured, authenticated
                from store_publish import publish
                client, credentials = configured(args)
                account = authenticated(client, credentials)['account']
                result = publish(args.project, SDK, args.qemu, args.firmware, client, account,
                                 attempt_id=args.resume or args.status or args.cancel,
                                 operation='status' if args.status else 'cancel' if args.cancel else 'resume')
            print(json.dumps(result, indent=2))
            return 0
        if args.command == 'preview':
            from preview import once, watch
            options = dict(scenario=args.scenario, fixture_dir=args.fixture_dir, inspect=not args.no_inspect,
                           reset_data=args.reset_data,fresh_data=args.fresh_data)
            if args.once:
                result = once(args.project, args.qemu, args.firmware, **options)
                print(json.dumps(result, indent=2))
                return 0 if result['status'] == 'ready' else 1
            watch(args.project.resolve(), args.qemu, args.firmware, **options)
            return 0
        if args.command == 'data':
            from device import Client
            from data_device import DataClient, read_backup
            from usb_files import LibUSB, transfer_interrupts
            prepared = None
            if args.data_operation=='restore':
                prepared = read_backup(args.backup)
                if prepared[0]['app']!=args.app_id:
                    raise ValueError('Backup belongs to a different app; no USB connection was opened')
            with transfer_interrupts() as cancelled, management_transport(args, LibUSB) as transport:
                data = DataClient(Client(transport))
                if args.data_operation=='info': result=data.info(args.app_id);cancelled()
                elif args.data_operation=='export': result=data.export(args.app_id,args.backup,replace=args.replace,cancelled=cancelled)
                elif args.data_operation=='restore': result=data._restore(args.app_id,prepared,cancelled=cancelled)
                else: result=data.rollback(args.app_id,cancelled=cancelled)
                print(json.dumps(result,indent=2))
                return 0
        elif args.command == 'files':
            from device import Client
            from files_device import FileClient
            from usb_files import LibUSB, transfer_interrupts
            with transfer_interrupts() as cancelled, management_transport(args, LibUSB) as transport:
                files = FileClient(Client(transport))
                if args.file_operation=='status':result=files.status();result['digest']=result['digest'].hex();cancelled()
                elif args.file_operation=='cancel':
                    state=files.status()
                    if not 0<args.sequence<=0xffffffff or state['sequence']!=args.sequence:
                        raise ValueError('Select the active file exchange sequence from files status')
                    state=files._wait(sequence=args.sequence)
                    if state['state'] not in (2,3):
                        raise ValueError('The file exchange has already finished')
                    files.client.write(0x75,argument=args.sequence);result={'cancellation_requested':args.sequence}
                elif args.file_operation=='info':result=files.info(args.app_id);cancelled()
                elif args.file_operation=='list':result=files.list(args.app_id,args.directory);cancelled()
                elif args.file_operation=='import':result=files.import_file(args.app_id,args.path,args.local,replace=args.replace,cancelled=cancelled)
                else:result=files.export_file(args.app_id,args.path,args.local,replace=args.replace,cancelled=cancelled)
                print(json.dumps(result,indent=2))
                return 0
        elif args.command == "doctor":
            import platform
            import importlib.util
            from build import contract
            spec = contract(SDK)
            if args.https_ca_file is not None and args.https_origin is None:
                raise ValueError('--https-ca-file requires --https-origin')
            network = {'status': 'not_checked'}
            if args.https_origin is not None:
                from https_diagnostics import probe
                network = probe(args.https_origin, args.https_ca_file)
            from usb_files import load_library, USBError
            try:
                load_library()  # Load only; no enumeration or device access.
                usb_library = True
            except USBError:
                usb_library = False
            compiler = shutil.which("arm-none-eabi-g++")
            version = subprocess.check_output([compiler, "-dumpfullversion"], text=True, encoding='utf-8', timeout=10).strip() if compiler else "missing"
            print(json.dumps({'sdk': spec['sdk'], "compiler": version, "required_compiler": spec['compiler'], "abi": 1,
                              'objcopy': bool(shutil.which('arm-none-eabi-objcopy')),
                              'qemu': DEFAULT_QEMU.is_file(), 'vm_firmware': DEFAULT_FIRMWARE.is_file(),
                              'pillow': importlib.util.find_spec('PIL') is not None,
                              'gdb': bool(shutil.which('arm-none-eabi-gdb')),
                              'libusb': usb_library,
                              'https': network,
                              'host': {'system': platform.system(), 'machine': platform.machine(),
                                       'qualification': 'not_checked'},
                              'physical_install': {'sdk_supported': True, 'device': 'not_checked',
                                  'requires': ['signed ABI 1 package', 'compatible firmware', 'ready app storage'],
                                  'usb_protocols': spec['usb_protocols'], 'hardware_qualification': 'pending'},
                              "source_bundles": True, 'publication': 'developer-local',
                              "store_configuration": "not_checked"}, indent=2))
            return 0 if network['status'] != 'failed' and version == spec['compiler'] and shutil.which('arm-none-eabi-objcopy') and DEFAULT_QEMU.is_file() and DEFAULT_FIRMWARE.is_file() else 1
        if args.command == 'lock':
            from build import project_lock, write_json
            project = args.project.resolve()
            path = project / 'sdk.lock.json'
            if args.update:
                write_json(path, project_lock(project, SDK))
            print(path.read_text(encoding='utf-8'))
            return 0
        if args.command == 'workspace':
            from workspace import manage, restore
            if args.operation in ('clone', 'export', 'restore') and not args.target:
                raise ValueError('this workspace operation requires a target')
            operation = restore(args.project.resolve(), args.name, args.target) if args.operation == 'restore' else manage(
                args.project.resolve(), args.operation, args.name, args.target)
            print(json.dumps(operation, indent=2))
            return 0
        if args.command == 'symbolize':
            from diagnostics import symbolize
            print(json.dumps(symbolize(args.project.resolve(), args.package.resolve(), args.pc), indent=2))
            return 0
        if args.command == 'debugger':
            gdb = shutil.which('arm-none-eabi-gdb')
            script = args.project.resolve() / 'build/debug.gdb'
            if not gdb or not script.is_file():
                raise ValueError('ARM GDB and build/debug.gdb are required; start lefony-sdk debug first')
            command = [gdb, '-nx', '-x', str(script)]
            if args.batch:
                command.append('--batch')
            for value in args.execute:
                command += ['-ex', value]
            return subprocess.run(command).returncode
        if args.command == 'debug':
            from runner import exercise
            path = package(args.project.resolve(), 'debug')
            exercise(path, args.qemu.resolve(), args.firmware.resolve(), headless=args.headless,
                     interactive=True, debug_project=args.project.resolve())
            return 0
        if args.command == "new":
            target = args.directory.resolve()
            if target.exists():
                raise ValueError("new project directory must not already exist")
            if args.template == 'basic':
                shutil.copytree(SDK / 'templates/basic', target)
            else:
                shutil.copytree(SDK / 'examples' / args.template, target,
                                ignore=shutil.ignore_patterns('build', 'sdk.lock.json', 'compile_commands.json', '.lefony', '__pycache__'))
                for filename in ('AGENTS.md', 'CMakeLists.txt'):
                    if not (target / filename).exists():
                        shutil.copyfile(SDK / 'templates/basic' / filename, target / filename)
            if not (target / 'store').exists():
                shutil.copytree(SDK / 'templates/basic/store', target / 'store')
            (target / ".gitignore").write_text("/build/\n/compile_commands.json\n/.lefony/\n", encoding="utf-8", newline="\n")
            from build import lock_value, write_json
            metadata = manifest(json.loads((target / 'app.json').read_text(encoding='utf-8')))
            # Scaffolding must work offline without an installed optional sysroot.
            # The foreground profile pins its library on the first actual build.
            from project import load as project_configuration
            from runtime import selected as foreground_runtime
            if not foreground_runtime(project_configuration(target)):
                write_json(target / 'sdk.lock.json', lock_value(SDK, metadata['abi'], metadata.get('schema', 0)))
            print(target)
        elif args.command == "launch":
            from runner import run
            return run(args.package.resolve(), args.qemu.resolve(), args.firmware.resolve(), args.headless or args.test, args.test, args.public_key)
        elif args.command == "inspect":
            from signing import MAGIC, verify
            content = args.package.read_bytes()
            signed = content.startswith(MAGIC)
            metadata, image = verify(content, args.public_key) if signed else unpack(content)
            _, segments = elf_segments(image)
            print(json.dumps({**metadata, 'report_schema': 1, 'signature': 'verified' if signed else 'unsigned',
                              'signer_id': content[24:56].hex() if signed else None,
                              'payload_sha256': content[56:88].hex() if signed else None,
                              'package_sha256': hashlib.sha256(content).hexdigest(), 'download_bytes': len(content),
                              'resources': {'code_bytes': sum(m for _, _, m, p in segments if p == 5),
                                            'static_data_bytes': sum(m for _, _, m, p in segments if p == 6)},
                              'allocated_flash_bytes': None, 'device_compatibility': 'not_checked',
                              'package_schema': metadata.get('schema', 0),
                              'required_capabilities': metadata.get('required_capabilities', 0),
                              'optional_capabilities': metadata.get('optional_capabilities', 0),
                              'minimum_api': metadata.get('minimum_api', 0)}, indent=2))
        elif args.command == "source":
            from source import collect
            data = collect(args.project.resolve(), args.format)
            destination = args.project.resolve() / "build/app.lfsrc"
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(data)
            print(destination)
        elif args.command == "build":
            print(build(args.project.resolve(), args.profile)[1])
        else:
            path = package(args.project.resolve(), args.profile)
            print(path, flush=True)
            if args.command in ("run", "test"):
                from contextlib import nullcontext
                from workspace import opened
                context = opened(args.project.resolve(), args.workspace) if args.workspace else nullcontext((None, None))
                with context as (directory, _):
                    if args.command == 'test' and args.suite != 'startup':
                        from replay import test_project
                        return test_project(args.project.resolve(), path, args.qemu.resolve(), args.firmware.resolve(), args.suite, directory, measure_resources=args.measure_resources)
                    from runner import run
                    return run(path, args.qemu.resolve(), args.firmware.resolve(),
                               args.headless or args.command == "test", args.command == "test", workspace=directory, measure_resources=args.measure_resources)
        return 0
    except KeyboardInterrupt:
        print('lefony-sdk: cancelled', file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, ImportError, zipfile.BadZipFile, PackageError, subprocess.SubprocessError) as exc:
        print(f"lefony-sdk: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    from sdk_environment import configure_output
    configure_output()
    raise SystemExit(main())
