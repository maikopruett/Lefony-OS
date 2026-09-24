#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated GNOME Keyring fixture for opt-in SDK qualification.

Run in a disposable Linux test environment. The new, empty session directory
holds a private D-Bus socket and temporary encrypted keyring, never an existing
desktop collection. A bounded file control channel permits audit/lock/unlock/
restart/shutdown operations without writing passwords or session tokens to it.
This is a test fixture, not an application credential backend.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import time


def write_json(path, value):
    temporary = path.with_suffix('.partial')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--isolated-test-service', action='store_true', required=True)
    args = parser.parse_args()
    session = args.session.resolve(strict=True)
    assert not args.session.is_symlink() and session.is_dir() and not any(session.iterdir()), 'Use a new empty session directory'
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    session.chmod(0o700)
    data = session/'data'; runtime = session/'runtime'; config = session/'config'
    for path in (data, runtime, config): path.mkdir(mode=0o700)
    # GNOME otherwise consults a legacy ~/.gnome2/keyrings directory when this
    # XDG keyring directory is absent. Never select a real desktop alias/file.
    (data/'keyrings').mkdir(mode=0o700)
    environment = {**os.environ, 'XDG_DATA_HOME': str(data), 'XDG_RUNTIME_DIR': str(runtime),
                   'XDG_CONFIG_HOME': str(config), 'DBUS_SESSION_BUS_ADDRESS': 'unix:path='+str(session/'bus'),
                   'DISPLAY': '', 'WAYLAND_DISPLAY': ''}
    os.environ.update({key: environment[key] for key in ('XDG_DATA_HOME','XDG_RUNTIME_DIR','XDG_CONFIG_HOME','DBUS_SESSION_BUS_ADDRESS','DISPLAY','WAYLAND_DISPLAY')})
    import secretstorage
    password = secrets.token_urlsafe(32)
    nonce = secrets.token_hex(32)
    processes, logs, actions = [], [], []
    report = {'schema': 1, 'status': 'starting', 'fixture': 'isolated-GNOME-Keyring',
              'nonempty_keyring_password': True, 'actions': actions}
    def stop(process):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait()
    def start(command, name, stdin=None):
        log = (output/name).open('wb'); logs.append(log)
        process = subprocess.Popen(command, env=environment, stdin=stdin, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process)
        return process
    def collection():
        return secretstorage.get_default_collection(secretstorage.dbus_init())
    def wait_owner(expected):
        deadline = time.monotonic()+15
        while time.monotonic() < deadline:
            result = subprocess.run(['dbus-send','--session','--print-reply','--dest=org.freedesktop.DBus',
                '/org/freedesktop/DBus','org.freedesktop.DBus.NameHasOwner','string:org.freedesktop.secrets'],
                env=environment, capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and ('boolean true' in result.stdout) == expected: return
            time.sleep(.1)
        raise RuntimeError('Secret Service ownership did not reach its expected state')
    def keyring_start():
        daemon = start(['gnome-keyring-daemon','--foreground','--components=secrets',
                        '--control-directory='+str(runtime/'keyring'),'--unlock'],
                       'keyring-'+str(len(processes))+'.log', subprocess.PIPE)
        daemon.stdin.write(password.encode()); daemon.stdin.close()
        wait_owner(True)
        assert daemon.poll() is None and not collection().is_locked()
        return daemon
    def unlock():
        # GNOME-specific fixture control, never used by the SDK backend.
        # The ordinary --unlock invocation starts another daemon; it does not
        # unlock the already-owned service. Use its encrypted master-password
        # method on this fixture's existing private bus instead.
        # https://gitlab.gnome.org/GNOME/gnome-keyring/-/blob/46.1/daemon/dbus/org.gnome.keyring.InternalUnsupportedGuiltRiddenInterface.xml
        from secretstorage.util import DBusAddressWrapper, format_secret, open_session
        connection = secretstorage.dbus_init()
        exchange = open_session(connection); assert exchange.encrypted
        service = DBusAddressWrapper('/org/freedesktop/secrets',
            'org.gnome.keyring.InternalUnsupportedGuiltRiddenInterface', connection)
        service.call('UnlockWithMasterPassword', 'o(oayays)', collection().collection_path,
                     format_secret(exchange, password.encode(), 'text/plain'))
        assert not collection().is_locked()
    def alarm(signum, frame):
        raise TimeoutError('Credential fixture operation exceeded its deadline')
    def terminate(signum, frame):
        raise KeyboardInterrupt('Credential fixture terminated')
    signal.signal(signal.SIGALRM, alarm)
    signal.signal(signal.SIGTERM, terminate)
    try:
        signal.alarm(30)
        bus = start(['dbus-daemon','--session','--nofork','--nopidfile',
                     '--address='+environment['DBUS_SESSION_BUS_ADDRESS']], 'bus.log')
        deadline = time.monotonic()+10
        while not (session/'bus').exists():
            assert bus.poll() is None and time.monotonic() < deadline
            time.sleep(.05)
        daemon = keyring_start()
        report['versions'] = {name: subprocess.check_output([name,'--version'],env=environment,text=True,timeout=5).splitlines()[0]
                              for name in ('dbus-daemon','gnome-keyring-daemon')}
        report['status'] = 'running'
        write_json(session/'ready.json', {'schema':1,'isolated_test_service':True,'nonce':nonce,
                   'bus_address':environment['DBUS_SESSION_BUS_ADDRESS'],'versions':report['versions']})
        write_json(output/'report.json', report)
        signal.alarm(0)
        deadline = time.monotonic()+1800
        while time.monotonic() < deadline:
            assert bus.poll() is None and daemon.poll() is None
            request_path = session/'command.json'
            if not request_path.exists(): time.sleep(.05); continue
            assert request_path.stat().st_size <= 4096
            request = json.loads(request_path.read_text()); request_path.unlink()
            assert request.get('nonce') == nonce and isinstance(request.get('id'),str) and len(request['id']) == 32
            assert all(c in '0123456789abcdef' for c in request['id'])
            operation = request.get('operation'); result = {'schema':1,'id':request['id'],'operation':operation}
            try:
                signal.alarm(20)
                if operation == 'lock':
                    collection().lock(); assert collection().is_locked()
                    result['locked'] = True
                elif operation == 'unlock':
                    unlock(); result['locked'] = False
                elif operation == 'restart':
                    stop(daemon); wait_owner(False); daemon = keyring_start()
                    result['restarted'] = True
                elif operation == 'audit':
                    service = request.get('service'); assert isinstance(service,str) and service.startswith('Lefony SDK: https://')
                    items = list(collection().search_items({'service':service,'username':'active'}))
                    assert len(items) <= 1
                    result['items'] = len(items)
                    if items:
                        secret = items[0].get_secret(); record = json.loads(secret)
                        token = record['token'].encode()
                        result['token_sha256'] = hashlib.sha256(token).hexdigest()
                        result['account'] = record['account']
                        for path in data.rglob('*'):
                            if path.is_file(): assert token not in path.read_bytes() and secret not in path.read_bytes()
                        result['plaintext_token_on_disk'] = False
                    result['files'] = [{'file':str(path.relative_to(data)),'bytes':path.stat().st_size,
                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'mode':oct(path.stat().st_mode&0o777)}
                        for path in sorted(data.rglob('*')) if path.is_file()]
                    assert all(record['mode']=='0o600' for record in result['files'])
                elif operation == 'shutdown':
                    assert not list(collection().get_all_items()), 'Temporary credentials remain'
                    result['credentials_removed'] = True
                else: raise ValueError('Unknown fixture operation')
                result['status'] = 'passed'
            except Exception as error:
                result.update(status='failed',error=type(error).__name__)
            finally:
                signal.alarm(0)
            actions.append({key:value for key,value in result.items() if key != 'id'})
            write_json(session/(request['id']+'.json'), result)
            write_json(output/'report.json',report)
            if operation == 'shutdown' and result['status']=='passed':
                report.update(status='passed',credentials_removed=True); break
        else: raise TimeoutError('Isolated credential fixture exceeded its lifetime')
    except BaseException as error:
        report.update(status='failed',error=type(error).__name__); raise
    finally:
        signal.alarm(0)
        for process in reversed(processes): stop(process)
        for log in logs: log.close()
        for path in (data,runtime,config): shutil.rmtree(path)
        report['owned_processes_stopped'] = all(process.poll() is not None for process in processes)
        report['temporary_keyring_directories_removed'] = True
        write_json(output/'report.json',report)


if __name__ == '__main__': main()
