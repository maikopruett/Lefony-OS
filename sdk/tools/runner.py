# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the actual LFAPP container through the Prime VM's guest loader."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from lfapp import unpack
from local_transport import connect, qemu_path, session_directory, socket_path
from emulator_failure import Capture, file_identity, record as record_failure


class Channel:
    def __init__(self, path, process, timeout=30):
        self.path = socket_path(path)
        self.session_directory = self.path.parent
        self.socket = connect(self.path, timeout=timeout, process=process)
        self.file = self.socket.makefile("rwb", buffering=0)
        self.last_command = None

    def command(self, command):
        # Record the operation only, never text, byte payloads or coordinates.
        self.last_command=' '.join(word for word in command.split()[:2] if word.isascii() and word.isalpha() and word.isupper())[:64]
        self.socket.sendall((command+"\n").encode())
        value = self.file.readline(4096)
        if not value.endswith(b"\n"):
            raise RuntimeError("emulator control response was incomplete")
        return value.decode().strip()

    def close(self):
        self.file.close()
        self.socket.close()


def exercise(package, qemu, firmware, *, headless=True, event=0, first=0, second=0, capture=None, interactive=False, events=None, controls=None, public_keys=(), workspace=None, debug_project=None, debug_timeout=3600, prepare_workspace=None, measure_resources=False, diagnostics_dir=None):
    from signing import MAGIC, verify
    content = package.read_bytes()
    metadata, _ = verify(content, public_keys) if content.startswith(MAGIC) else unpack(content)
    foreground = bool(metadata.get('required_capabilities', 0) & 16)
    if foreground and workspace is None:
        # Entry requires the ordinary foreground loader. Disposable previews
        # therefore use a signed installation into private synthetic media too.
        from workspace import opened
        with tempfile.TemporaryDirectory(prefix='lefony-preview-') as directory:
            with opened(Path(directory), 'preview') as (media, _):
                report = exercise(package, qemu, firmware, headless=headless, event=event,
                    first=first, second=second, capture=capture, interactive=interactive,
                    events=events, controls=controls, public_keys=public_keys, workspace=media,
                    debug_project=debug_project, debug_timeout=debug_timeout, prepare_workspace=prepare_workspace,
                    measure_resources=measure_resources, diagnostics_dir=diagnostics_dir)
                report['persistence'] = 'disposable-installed-preview'
                return report
    if not qemu.is_file() or not firmware.is_file():
        raise ValueError("VM firmware and custom QEMU are required; pass --firmware and --qemu")
    with session_directory() as folder:
        folder = Path(folder)
        payload = folder / "app.lfapp"
        shutil.copyfile(package, payload)
        if workspace:
            from signing import sign
            from sdk_environment import SDK as sdk
            private = sdk.parent / 'tests/fixtures/prime_g2_emulator_update_private.pem'
            public = sdk.parent / 'tests/fixtures/prime_g2_emulator_update_public.pem'
            if not content.startswith(MAGIC):
                payload.write_bytes(sign(content, private))
                # Only the package signed above needs the emulator fixture
                # key. Adding it again for an already signed package makes
                # strict verification reject the duplicated signing identity.
                public_keys = [public]
        uart = folder / "uart"
        control = folder / "control"
        qmp = folder / "qmp"
        qtest = folder / "qtest"
        browser_panel = interactive and not headless and not debug_project
        command = [str(qemu), "-machine", "mcimx6ul-evk", "-m", "256M",
                   "-global", "imx6ul-lcdif.prime-g2-panel=on", "-display", "none" if headless or browser_panel else ("cocoa" if sys.platform == "darwin" else "sdl"),
                   "-monitor", "none", "-serial", f"file:{uart}", "-serial", "null",
                   "-chardev", f"socket,id=appcontrol,path={qemu_path(control)},server=on,wait=off", "-serial", "chardev:appcontrol",
                   "-qtest", f"unix:{qemu_path(qtest)},server=on,wait=off", "-qtest-log", os.devnull,
                   "-qmp", f"unix:{qemu_path(qmp)},server=on,wait=off", "-kernel", str(firmware), "-no-reboot",
                   "-device", f"loader,file={qemu_path(payload)},addr=0x86000000,force-raw=on"]
        if workspace:
            command += ['-global', f'prime-g2-gpmi-bch.stock-overlay={workspace / "nand.overlay"}',
                        '-chardev', f'socket,id=usbhost,path={qemu_path(folder / "usb")},server=on,wait=off',
                        '-global', 'prime-g2-usbotg-device.chardev=usbhost']
        if debug_project:
            command += ['-chardev', f'socket,path={qemu_path(folder / "gdb")},server=on,wait=off,id=appdebug', '-gdb', 'chardev:appdebug']
        from build import identity
        from sdk_environment import SDK
        identities={'sdk_sha256':identity(SDK),'package_sha256':hashlib.sha256(payload.read_bytes()).hexdigest(),
                    'firmware_sha256':file_identity(firmware),'qemu_sha256':file_identity(qemu)}
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        captured = Capture(process)
        channel = monitor = host = None
        failure = None;phase = 'boot';exit_at_failure = None
        try:
            end = time.monotonic()+30
            while not uart.exists() or "entering calculator runtime" not in uart.read_text(encoding="utf-8", errors="replace"):
                if process.poll() is not None or time.monotonic()>end:
                    raise RuntimeError("VM failed to boot: " + (uart.read_text(encoding="utf-8", errors="replace")[-1500:] if uart.exists() else "no UART"))
                time.sleep(.05)
            phase = 'control-handshake';channel = Channel(control, process)
            if channel.command("PING") != "PONG":
                raise RuntimeError("VM control handshake failed")
            profile_target = None
            if measure_resources:
                from resource_profile import arm
                profile_target = arm(channel, content)
            if workspace:
                phase = 'workspace-install'
                from emulator_usb import PrimeUSBHost, ManagementUSB
                from device import Client
                from keys_device import InstallUSB
                from usb_files import LibUSB as FileUSB
                from build import write_json
                host = PrimeUSBHost(folder / 'usb')
                host.connect_and_enumerate()
                class Transport(ManagementUSB):
                    def __init__(self):
                        # Borrow the already enumerated model connection. Reuse
                        # the bounded app/file bulk protocol instead of sending
                        # large bundled files through individual EP0 packets.
                        self.host = host
                        self.read_requests = InstallUSB.READ_REQUESTS + FileUSB.READ_REQUESTS
                        self.write_requests = InstallUSB.WRITE_REQUESTS + FileUSB.WRITE_REQUESTS
                    def read(self, request, value=0, index=0, length=64):
                        return host.control_in(0xc0, request, value, index, length)
                    def write(self, request, data=b'', value=0, index=0):
                        host.control_out(0x40, request, value, index, data)
                    def reset(self):
                        # Synthetic USB bus reset for disconnect/recovery tests.
                        host.connect_and_enumerate()
                client = Client(Transport())
                if client.status()['state'] != 2:
                    raise RuntimeError('VM app storage did not become ready; use matching workspace-capable firmware')
                entry = client.install(payload.read_bytes(), public_keys)
                channel.installed_slot = entry['slot']
                channel.wait_for_storage = client.wait
                channel.app_client = client
                # Packet-level integration tests may schedule phases separately.
                # This host exists only on the synthetic workspace USB socket.
                channel.usb_host = host
                write_json(workspace / 'workspace.json', {'schema': 1, 'kind': 'synthetic-prime-g2',
                           'app': metadata['id'], 'version': metadata['version'],
                           'package_sha256': hashlib.sha256(payload.read_bytes()).hexdigest()})
                # Dismiss the OS USB sheet through the normal Back key.
                from replay import Controls, control_session
                with control_session(Controls(channel, folder)) as input_device:
                    input_device.key('back')
                if prepare_workspace is not None:
                    prepare_workspace(client)
                if not debug_project and channel.command(f"APP OPEN {entry['slot']}") != 'OK':
                    raise RuntimeError('installed app launch failed')
            else:
                phase = 'app-load'
                reply = channel.command(f"APP LOAD {payload.stat().st_size}")
                if reply != "OK":
                    raise RuntimeError(f"guest rejected app: {reply}")
                channel.preview_size = payload.stat().st_size
            phase = 'app-execution';callbacks = []
            result = 1
            if debug_project:
                from diagnostics import gdb_script
                from replay import Controls
                debug_controls = Controls(channel, folder)
                try:
                    debug_controls.execute('stop')
                finally:
                    # CPU is deliberately stopped: do not send a Goodix command.
                    debug_controls.qtest.close();debug_controls.qmp.close()
                script = gdb_script(debug_project, package, folder / 'gdb')
                print(f'VM paused after loading matching symbols. From this project in another terminal run:\n'
                      f'  lefony-sdk debugger\nProject: {debug_project}\nDebug script: {script}\n'
                      'Debug pauses are excluded from deadline qualification. Ctrl-C ends this session.', flush=True)
                channel.socket.settimeout(debug_timeout)
                # Install/load before attaching, but defer the one-shot main
                # until GDB can set its breakpoint. Otherwise it can already
                # have returned when the developer opens the generated script.
                if workspace and channel.command(f"APP OPEN {entry['slot']}") != 'OK':
                    raise RuntimeError('installed debug app launch failed')
            for e, a, b in ([] if workspace else (events or [(event, first, second)])):
                reply = channel.command(f"APP EVENT {e} {a} {b}")
                if not reply.startswith("RESULT "):
                    raise RuntimeError(f"unexpected app result: {reply}")
                result = int(reply.split()[1])
                callbacks.append({"event": e, "first": a, "second": b, "result": result})
                if result != 1:
                    break
            if channel.command("PING") != "PONG":
                raise RuntimeError("OS did not regain control after callback")
            if not workspace and (interactive or controls is not None) and result == 1:
                if channel.command("APP LAUNCH") != "OK":
                    raise RuntimeError("VM firmware does not support the SDK launcher")
            if workspace or interactive or controls is not None:
                channel.native_state = channel.command('STATE').split(' home_row=')[0]
            if controls is not None and result == 1:
                controls(channel)
            diagnostics = [channel.command(f"APP DIAG {i}") for i in range(12)]
            program = None
            if foreground:
                exited = int(channel.command('APP DIAG 15').split()[1]) != 0
                status = int(channel.command('APP DIAG 21').split()[1])
                if status >= 2**31: status -= 2**32
                program = {'exited': exited, 'exit_status': status if exited else None}
            if diagnostics[6].startswith('VALUE '):
                last = int(diagnostics[6].split()[1])
                if last >= 2**31:
                    last -= 2**32
                if last < 0:
                    result = last
            if diagnostics[9].startswith('VALUE '):
                crash = int(diagnostics[9].split()[1])
                if crash >= 2**31:
                    crash -= 2**32
                if crash < 0:
                    result = crash
            if capture:
                phase = 'frame-capture'
                monitor = Channel(qmp, process)
                json.loads(monitor.file.readline())
                def qmp_command(name, arguments=None):
                    monitor.file.write((json.dumps({"execute": name, "arguments": arguments or {}})+"\n").encode())
                    while True:
                        response = json.loads(monitor.file.readline())
                        if "event" in response:
                            continue
                        if "error" in response:
                            raise RuntimeError(str(response))
                        return response
                qmp_command("qmp_capabilities")
                time.sleep(.1)
                qmp_command("screendump", {"filename": str(capture.resolve())})
                # QEMU serves one QMP client at a time. Release capture's
                # connection before workspace cleanup opens input controls.
                monitor.close()
                monitor = None
            if interactive and result == 1:
                if browser_panel:
                    phase = 'interactive-panel'
                    from emulator_ui import run_panel
                    run_panel(channel, folder, process, metadata.get('name', metadata['id']))
                else:
                    print("Native app is running. Close the emulator window or press Ctrl-C to stop.", flush=True)
                    try:
                        while process.poll() is None:
                            time.sleep(.2)
                    except KeyboardInterrupt:
                        pass
            if workspace and process.poll() is None:
                phase = 'workspace-close'
                from replay import Controls, control_session
                with control_session(Controls(channel, folder)) as input_device:
                    # Apps may own Back for menus or navigation. Home always
                    # leaves the foreground container and triggers normal close.
                    input_device.key('home')
                if channel.command('STATE').split(' home_row=')[0] == channel.native_state:
                    raise RuntimeError('SDK cleanup did not leave the native app container')
                client.wait()
            resources = None
            if profile_target:
                from resource_profile import snapshot
                resources = snapshot(channel, profile_target)
                if resources['faults']:
                    result = resources['failure_result']
            values = [int(d.split()[1]) if d.startswith('VALUE ') else None for d in diagnostics]
            fault = {'pc': values[10] or values[0], 'reason': result, 'event': values[11] if values[9] else values[3], 'address': None} if result != 1 else None
            if resources and resources['faults']:
                fault = {'pc': resources['fault_pc'], 'reason': result,
                         'event': resources['fault_event'], 'address': None}
            return {"schema": 1, 'validation': 'debug-session' if debug_project else 'developer-local', 'independently_verified': False,
                    "app": metadata["id"], "package_sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                    "firmware_sha256": hashlib.sha256(firmware.read_bytes()).hexdigest(),
                    "result": result, "callbacks": callbacks, "diagnostics": diagnostics,
                    'program': program,
                    'resources': resources,
                    'fault': fault,
                    'metrics': {'services': values[1], 'last_service': values[2], 'callback_ms': values[4], 'fill_pixels': values[5]},
                    'physical': 'not_tested', 'persistence': 'installed-workspace' if workspace else 'not_tested',
                    'workspace_cleanup': 'home-and-storage-drain' if workspace else None,
                    "os_responsive": channel.command('PING') == 'PONG', "target": "prime_g2_vm"}
        except (Exception, KeyboardInterrupt) as error:
            failure = error;exit_at_failure = process.poll()
            raise
        finally:
            cleanup_errors=[]
            for name,resource in (('usb',host),('control',channel),('monitor',monitor)):
                if resource:
                    try:resource.close()
                    except Exception as error:cleanup_errors.append({'resource':name,'error':type(error).__name__})
            outcome,stderr=captured.finish()
            if isinstance(failure, Exception):
                outcome['exit_at_failure']=exit_at_failure
                report,stderr,uart_data=record_failure(failure,outcome,stderr,uart,identities=identities,
                    command=getattr(channel,'last_command',None),phase=phase,directory=diagnostics_dir,cleanup_errors=cleanup_errors)
                print(uart_data[-2000:].decode('utf-8',errors='replace'),file=sys.stderr)
                if stderr:print(stderr[-2000:].decode('utf-8',errors='replace'),file=sys.stderr)
                print('Emulator outcome: '+json.dumps(outcome),file=sys.stderr)
                if report.get('directory'):print('Local emulator diagnostics: '+str(Path(diagnostics_dir)/report['directory']),file=sys.stderr)
            elif failure is None and cleanup_errors:
                raise RuntimeError('Emulator resources did not close cleanly: '+json.dumps(cleanup_errors))


def run(package, qemu, firmware, headless, testing, public_keys=(), workspace=None, measure_resources=False):
    from build import write_json
    try:
        report = exercise(package, qemu, firmware, headless=headless, capture=package.parent/"app.ppm", interactive=not testing, public_keys=public_keys, workspace=workspace, measure_resources=measure_resources,diagnostics_dir=package.parent/'emulator')
    except (Exception,KeyboardInterrupt) as error:
        report={'schema':1,'status':'cancelled' if isinstance(error,KeyboardInterrupt) else 'failed',
                'validation':'developer-local','physical':'not_tested','result':None,'os_responsive':False,
                'package_sha256':file_identity(package),'firmware_sha256':file_identity(firmware),'qemu_sha256':file_identity(qemu),
                'error':str(error),'emulator_failure':getattr(error,'emulator_failure',None)}
        try:write_json(package.parent/'run.json',report)
        except OSError as save_error:print('Could not replace failed run report: '+str(save_error),file=sys.stderr)
        raise
    (package.parent/"run.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))
    success = report["result"] == 1 and report['os_responsive']
    if report.get('program') and report['program']['exit_status'] not in (None, 0): success = False
    return 0 if success else 1
