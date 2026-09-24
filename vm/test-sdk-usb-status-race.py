#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Schedule real EP0 completions and replacement SETUP between register reads.

GDB only pauses execution; all transfer bytes traverse the modeled USB endpoint.
No guest registers, application data or firmware memory are patched.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import digest, write_json
from cli import package
from files_device import FileClient, IMPORT, WRITABLE, COMPLETE, CANCELLED, STATUS
from replay import Controls
from runner import exercise
from signing import sign
from workspace import opened


class Debugger:
    def __init__(self, endpoint, firmware):
        self.process = subprocess.Popen(['arm-none-eabi-gdb', '--nx', '--quiet',
            '--interpreter=mi2', str(firmware)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.buffer = b''; self.transcript = bytearray(); self.token = 0
        self.command('-gdb-set pagination off')
        self.command('-target-select remote ' + str(endpoint), '^connected')

    def record(self, prefix):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                text = line.decode(errors='replace')
                if text.startswith(prefix): return text
                if re.match(r'\d+\^error', text): raise RuntimeError(text)
                continue
            readable, _, _ = select.select([self.process.stdout], [], [], .1)
            if readable:
                data = os.read(self.process.stdout.fileno(), 65536)
                if not data: raise RuntimeError('GDB exited: ' + self.transcript.decode(errors='replace'))
                self.buffer += data; self.transcript.extend(data)
        raise TimeoutError('GDB: waiting for ' + prefix)

    def command(self, command, expected='^done'):
        self.token += 1
        self.process.stdin.write(f'{self.token}{command}\n'.encode()); self.process.stdin.flush()
        return self.record(str(self.token) + expected)

    def pause_at(self, address, state_address, state=3):
        reply = self.command(f'-break-insert -t *0x{address:x}')
        number = re.search(r'number="(\d+)"', reply).group(1)
        # DataIn/DataOut/StatusIn/StatusOut are 1/2/3/4 in the production enum.
        self.command(f'-break-condition {number} *(unsigned int*)0x{state_address:x} == {state}')
        self.command('-exec-continue', '^running')
        stopped = self.record('*stopped')
        assert 'breakpoint-hit' in stopped, stopped

    def close(self):
        try:
            self.command('-target-detach')
        finally:
            self.process.terminate(); self.process.wait(timeout=10)


def poll_boundary(firmware):
    symbols = subprocess.check_output(['arm-none-eabi-nm', str(firmware)], text=True)
    function = next(line.split()[2] for line in symbols.splitlines()
                    if 'USBDiagnostics4pollEv' in line)
    state = next(int(line.split()[0], 16) for line in symbols.splitlines()
                 if line.split()[2].endswith('13sControlStateE'))
    assembly = subprocess.check_output(['arm-none-eabi-objdump', '-d',
        '--disassemble=' + function, str(firmware)], text=True)
    matches = re.findall(r'^\s*([0-9a-f]+):\s+[0-9a-f]+\s+ldr\s+\w+, \[\w+, #428\]', assembly, re.M)
    assert matches, 'Cannot locate the production EP0 SETUP status read'
    address = int(matches[0], 16)
    # The native USB activity timestamp now sits between these register reads.
    # Keep the breakpoint at SETUPSTAT, after the preceding COMPLETE read,
    # without assuming that bookkeeping fits in eight instructions.
    previous = assembly.split(matches[0] + ':', 1)[0].splitlines()[-24:]
    assert any(re.search(r'\bldr\s+\w+, \[\w+, #444\]', line) for line in previous), previous
    return address, state, assembly


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expect-before-fix', action='store_true', help='Record the selected known race on a retained baseline')
    reset = parser.add_mutually_exclusive_group()
    reset.add_argument('--commit-reset', action='store_true', help='Schedule file COMMIT status completion immediately before bus reset')
    reset.add_argument('--install-reset', action='store_true', help='Schedule package INSTALL status completion immediately before bus reset')
    reset.add_argument('--status-out', action='store_true', help='Schedule a read status OUT just before the next write SETUP')
    reset.add_argument('--data-out', action='store_true', help='Abandon an OUT data completion before a replacement write')
    reset.add_argument('--data-in', action='store_true', help='Abandon an IN data completion before a replacement read')
    args = parser.parse_args(); firmware = args.firmware.resolve(); output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    address, state_address, assembly = poll_boundary(firmware)
    (output / 'usb-poll.asm').write_text(assembly)
    cases = []
    with tempfile.TemporaryDirectory(prefix='lefony-usb-race-') as tmp:
        project = Path(tmp); (project / 'src').mkdir()
        (project / 'src/main.c').write_text('int main(void) { return 0; }\n')
        write_json(project / 'project.json', {'schema':2, 'runtime':'foreground-newlib-1', 'sources':['src/main.c']})
        write_json(project / 'app.json', {'abi':1, 'id':'usb-status-race', 'name':'USB Status Race',
            'version':'1.0.0', 'license':'CC-BY-NC-SA-4.0', 'schema':1, 'minimum_api':3,
            'required_capabilities':16, 'optional_capabilities':0, 'data_schema':0})
        artifact = package(project)
        if args.install_reset:
            metadata=json.loads((project/'app.json').read_text());metadata['version']='1.1.0';write_json(project/'app.json',metadata)
            replacement=sign(package(project).read_bytes(),ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem')
        def controls(channel):
            normal = Controls(channel, output); debugger = None
            try:
                deadline = time.monotonic() + 30
                while not int(channel.command('APP DIAG 15').split()[1]):
                    assert time.monotonic() < deadline; time.sleep(.02)
                normal.key('home'); client = channel.app_client; client.wait(); files = FileClient(client)
                endpoint = Path(channel.socket.getpeername()).parent / 'race-gdb'
                reply = normal.execute('human-monitor-command', {'command-line':'gdbserver unix:' + str(endpoint) + ',server=on,wait=off'})
                assert 'Waiting' in reply['return'], reply
                host = channel.usb_host
                for acknowledged in (False, True):
                    if args.data_out or args.data_in:
                        state=files._begin('usb-status-race', IMPORT, 'replaced-data', identity=files.info('usb-status-race'),
                            length=1, digest=hashlib.sha256(b'x').digest())
                        token=state['sequence'];assert state['state']==WRITABLE
                        reading=args.data_in
                        request_type,request,length=(0xc0,0x70,STATUS.size) if reading else (0x40,0x72,9)
                        host.setup_packet(request_type,request,length=length)
                        debugger=Debugger(endpoint,firmware);debugger.pause_at(address,state_address,state=1 if reading else 2)
                        before=host.command('STATUS')
                        if acknowledged:
                            if reading:assert len(host.in_packet(STATUS.size))==STATUS.size
                            else:host.out_packet(struct.pack('<2I',token,0)+b'y')
                        host.setup_packet(request_type,request,length=length)
                        debugger.close();(output/f'gdb-data-{acknowledged}.log').write_bytes(debugger.transcript);debugger=None
                        assert channel.command('PING')=='PONG'
                        assert channel.command('PING')=='PONG'
                        after=host.command('STATUS')
                        broken=acknowledged and args.expect_before_fix
                        premature_status=None
                        if reading:
                            # The replacement READ cannot accept status before
                            # its data has been consumed. A stale IN completion
                            # used to advance the new request into StatusOut.
                            premature_status=host.command('OUT -')
                            assert premature_status==('OK' if broken else 'NAK'),premature_status
                        command=f'IN {STATUS.size}' if reading else 'OUT '+(struct.pack('<2I',token,0)+b'x').hex()
                        response=host.command(command)
                        if reading:
                            assert response.startswith('DATA '),response
                            fresh=STATUS.unpack(bytes.fromhex(response[5:]));assert fresh[7]==0,fresh
                            if not broken:host.out_packet(b'')
                        elif broken:assert response=='NAK',response
                        else:
                            assert response=='OK',response
                            assert host.in_packet(0)==b''
                        observed=files._wait(sequence=token,operation=IMPORT)
                        assert observed['state']==WRITABLE and observed['offset']==int(not reading and not broken),observed
                        cases.append({'acknowledged':acknowledged,'before':before,'after':after,
                            'response':response,'premature_status':premature_status,
                            'observed':{k:v for k,v in observed.items() if k!='digest'}})
                        files._cancel(token);client.wait()
                        write_json(output/'progress.json',{'cases':cases});continue
                    if args.status_out:
                        state=files._begin('usb-status-race', IMPORT, 'status-out-write', identity=files.info('usb-status-race'),
                            length=1, digest=hashlib.sha256(b'x').digest())
                        token=state['sequence'];assert state['state']==WRITABLE
                        host.setup_packet(0xc0,0x70,length=STATUS.size)
                        assert len(host.in_packet(STATUS.size))==STATUS.size
                        debugger=Debugger(endpoint,firmware);debugger.pause_at(address,state_address,state=4)
                        before=host.command('STATUS')
                        if acknowledged:host.out_packet(b'')
                        host.setup_packet(0x40,0x72,length=9)
                        debugger.close();(output/f'gdb-status-out-{acknowledged}.log').write_bytes(debugger.transcript);debugger=None
                        # Let the next normal USB poll consume any old completion
                        # before sending this new transfer's payload. A stale OUT
                        # bit must not be interpreted as completion of new data.
                        assert channel.command('PING')=='PONG'
                        assert channel.command('PING')=='PONG'
                        after=host.command('STATUS')
                        payload=struct.pack('<2I',token,0)+b'x'
                        response=host.command('OUT '+payload.hex())
                        broken=acknowledged and args.expect_before_fix
                        if broken:assert response=='NAK',response
                        else:
                            assert response=='OK',response
                            assert host.in_packet(0)==b''
                        observed=files._wait(sequence=token,operation=IMPORT)
                        assert observed['state']==WRITABLE and observed['offset']==int(not broken),observed
                        cases.append({'acknowledged':acknowledged,'before':before,'after':after,
                            'response':response,'observed':{k:v for k,v in observed.items() if k!='digest'}})
                        files._cancel(token);client.wait()
                        write_json(output/'progress.json',{'cases':cases});continue
                    if args.install_reset:
                        original=client.catalog()[0];old_package=client.read_package(original['slot'],original['bytes'])
                        client.write(0x63,argument=len(replacement))
                        for offset in range(0,len(replacement),512):client.write(0x64,replacement[offset:offset+512],offset)
                        host.setup_packet(0x40,0x65)
                        debugger=Debugger(endpoint,firmware);debugger.pause_at(address,state_address)
                        before=host.command('STATUS')
                        if acknowledged:assert host.in_packet(0)==b''
                        assert host.command('RESET')=='OK';after=host.command('STATUS')
                        debugger.close();(output/f'gdb-install-{acknowledged}.log').write_bytes(debugger.transcript);debugger=None
                        assert channel.command('PING')=='PONG';client.transport.reset();status=client.wait()
                        assert status['state'] in (2,6),status
                        entries=client.catalog();assert len(entries)==1,entries
                        installed=entries[0];expected=replacement if acknowledged else old_package
                        assert installed['version']==('1.1.0' if acknowledged else '1.0.0'),installed
                        assert client.read_package(installed['slot'],installed['bytes'])==expected
                        cases.append({'acknowledged':acknowledged,'before':before,'after':after,'installed':installed,
                                      'package_sha256':hashlib.sha256(expected).hexdigest()})
                        write_json(output/'progress.json',{'cases':cases});continue
                    data = b'' if args.commit_reset else b'x'
                    state = files._begin('usb-status-race', IMPORT, 'commit-reset' if args.commit_reset else 'one-byte', identity=files.info('usb-status-race'),
                        length=len(data), digest=hashlib.sha256(data).digest())
                    token = state['sequence']; assert state['state'] == WRITABLE
                    if args.commit_reset:host.setup_packet(0x40, 0x74, value=token&65535, index=token>>16)
                    else:
                        host.setup_packet(0x40, 0x72, length=9)
                        host.out_packet(struct.pack('<2I', token, 0) + b'x')
                    debugger = Debugger(endpoint, firmware)
                    debugger.pause_at(address, state_address)
                    before = host.command('STATUS')
                    if acknowledged: assert host.in_packet(0) == b''
                    if args.commit_reset:assert host.command('RESET')=='OK'
                    else:host.setup_packet(0xc0, 0x70, length=STATUS.size)
                    after = host.command('STATUS')
                    debugger.close(); (output / f'gdb-{acknowledged}.log').write_bytes(debugger.transcript); debugger = None
                    # Wait until the guest has processed the injected SETUP.
                    # The model can expose the old descriptor until EP0 flush.
                    assert channel.command('PING') == 'PONG'
                    if args.commit_reset:
                        client.transport.reset();client.wait();normal.key('back')
                        deadline=time.monotonic()+120
                        while True:
                            observed=files.status()
                            if observed['state']!=1:break
                            assert time.monotonic()<deadline;time.sleep(.01)
                        committed=acknowledged and not args.expect_before_fix
                        cases.append({'acknowledged':acknowledged,'before':before,'after':after,
                            'observed':{k:v for k,v in observed.items() if k!='digest'}})
                        assert observed['state']==(COMPLETE if committed else CANCELLED),cases[-1]
                        assert observed['flags']==int(committed),cases[-1]
                        listing=files.list('usb-status-race')['entries']
                        assert listing==([{'path':'commit-reset','kind':'file','bytes':0}] if committed else []),listing
                        write_json(output/'progress.json',{'cases':cases});continue
                    first = STATUS.unpack(host.in_packet(STATUS.size)); host.out_packet(b'')
                    observed = files._wait(sequence=token, operation=IMPORT)
                    expected = int(acknowledged and not args.expect_before_fix)
                    cases.append({'acknowledged':acknowledged, 'before':before, 'after':after,
                        'first_state':first[3], 'first_offset':first[7], 'observed':{k:v for k,v in observed.items() if k!='digest'}})
                    write_json(output / 'progress.json', {'cases':cases})
                    assert observed['state'] == WRITABLE and observed['offset'] == expected, cases[-1]
                    files._cancel(token); client.wait()
                assert channel.command('PING') == 'PONG'
            finally:
                if debugger:
                    (output / 'gdb-failed.log').write_bytes(debugger.transcript); debugger.close()
                normal.close()
        with opened(project, 'race') as (workspace, _):
            result = exercise(artifact, ROOT / 'build/qemu-prime-g2/qemu-system-arm', firmware, workspace=workspace, controls=controls)
        assert result['result'] == 1 and result['os_responsive'], result
    write_json(output / 'report.json', {'schema':1, 'status':'baseline_failure_reproduced' if args.expect_before_fix else 'passed',
        'physical':'not_tested', 'firmware_sha256':digest(firmware), 'cases':cases,
        'commit_reset':args.commit_reset,'install_reset':args.install_reset,'status_out':args.status_out,
        'data_out':args.data_out,'data_in':args.data_in,
        'test_sha256':digest(Path(__file__)), 'qemu_sha256':digest(ROOT / 'build/qemu-prime-g2/qemu-system-arm')})
    print('PASS:', 'baseline race reproduced' if args.expect_before_fix else 'completed status retained; superseded transfer discarded', flush=True)


if __name__ == '__main__': main()
