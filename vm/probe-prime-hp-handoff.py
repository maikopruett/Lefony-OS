#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Observe the isolated U-Boot -> original HP RAM handoff, emulator only.

Completing this probe does not assert HP boot success. Private fixtures and
captures remain under build/. Optional stock NAND is read-only with a separate
model overlay; it is never passed to a host/device flashing command.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import socket
import struct
import shutil
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_hp_prime_compatibility import private_output, verify_input
from prime_hp_raw_restore import legacy_script, SCRIPT
from prime_usb_host import PrimeUSBHost
r = importlib.import_module('test-prime-g2-rom-recovery')


def main():
    probe_source = Path(__file__).read_bytes()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--uboot', type=Path, default=ROOT/'build/lefony-uboot-hp-handoff/u-boot-dtb.bin')
    parser.add_argument('--ddr-image', type=Path, help='replay the paired research IMX DCD in the model before RAM entry')
    parser.add_argument('--ram-loader', action='store_true', help='wrap the complete RAM U-Boot/DTB in ELF to bypass automatic NAND ROM loading')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stock-nand', type=Path)
    parser.add_argument('--physical-pages', action='store_true', help='NAND input is physical interleaved codewords')
    parser.add_argument('--menu', action='store_true', help='select HP using the shared boot menu')
    parser.add_argument('--sdp-launch', action='store_true', help='launch the RAM command through active U-Boot USB SDP, as on hardware')
    parser.add_argument('--overlay-from', type=Path, help='resume a private copy-on-write NAND overlay')
    parser.add_argument('--keys', default='', help='comma-separated physical key names after the first sample')
    parser.add_argument('--power-key', action='store_true', help='press/release modeled On key between samples')
    parser.add_argument('--power-off', action='store_true', help='press Shift+On after keys to save and suspend HP')
    parser.add_argument('--confinement', action='store_true', help='apply exact research-256 profile inside the RAM U-Boot loader')
    parser.add_argument('--trace-writes', action='store_true', help='observe all NAND program/erase attempts without blocking any')
    parser.add_argument('--actions', type=Path, help='bounded model key/swipe/wait sequence before calculation input')
    parser.add_argument('--gdb-script', type=Path, help='private emulator-only GDB experiment before input; bounded to 60 seconds')
    parser.add_argument('--gdb-stage', choices=('before-input','after-input'), default='before-input')
    parser.add_argument('--gdb-timeout', type=int, choices=range(10,601), default=60,
                        help='bounded experiment timeout, at most ten minutes')
    parser.add_argument('--seconds', type=int, choices=range(2, 61), default=20)
    args = parser.parse_args()
    data = args.image.read_bytes()
    verify_input(args.image.name, data)
    kind = 'os' if args.image.name == 'HPPrime.img' else 'updater'
    out = private_output(args.output)
    out.mkdir(parents=True, exist_ok=False)
    (out/'probe-source.py').write_bytes(probe_source)
    artifact_hashes = {name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in
                      [('uboot',args.uboot),('qemu',r.QEMU)]+([('ddr_image',args.ddr_image)] if args.ddr_image else [])}
    gdb_source = args.gdb_script.read_text() if args.gdb_script else None
    if args.menu and kind != 'os':
        parser.error('the menu experiment accepts only HPPrime.img')
    if args.overlay_from:
        if not args.stock_nand:
            parser.error('--overlay-from requires --stock-nand')
        shutil.copyfile(private_output(args.overlay_from), out/'nand.overlay')
    keymap = {m[0]:(int(m[1]),int(m[2])) for m in re.findall(r'PRIME_G2_KEY\(\s*(\w+),\s*\d+,\s*\w+,\s*(\d+),\s*(\d+)\)', (ROOT/'ports/lefony-prime-g2/ion/src/prime_g2/keymap.inc').read_text())}
    keys = args.keys.split(',') if args.keys else []
    actions = json.loads(args.actions.read_text()) if args.actions else []
    if not isinstance(actions, list) or len(actions) > 64:
        parser.error('actions must be a list of at most 64 operations')
    for action in actions:
        if not isinstance(action, dict) or len(action) != 1:
            parser.error('each action requires one key, swipe, or wait')
        if 'key' in action and action['key'] in keymap:
            continue
        if 'wait' in action and isinstance(action['wait'], (int,float)) and 0 <= action['wait'] <= 10:
            continue
        if 'swipe' in action and isinstance(action['swipe'],list) and len(action['swipe']) == 4 and all(
                type(v) is int and 0 <= v < (320 if i%2 == 0 else 240) for i,v in enumerate(action['swipe'])):
            continue
        parser.error('invalid model action')
    if any(k not in keymap for k in keys):
        parser.error('unknown physical key name')
    with tempfile.TemporaryDirectory(prefix='hp-handoff-', dir='/tmp') as temporary:
        p = Path(temporary)
        command = [str(r.QEMU), '-machine', 'hp-prime-g2', '-cpu', 'cortex-a7', '-m', '256M',
                   '-global', 'prime-g2-mmdc.preinitialized='+('off' if args.ddr_image else 'on'),
                   '-global', 'cortex-a7-arm-cpu.cntfrq=8000000',
                   '-global', 'imx6ul-lcdif.prime-g2-panel=on',
                   '-global', 'prime-g2-pf1550.external-power=on',
                   '-global', 'prime-g2-goodix-gt5688.drive-irq=off',
                   '-device', f'loader,file={args.image.resolve()},addr=0x84000000,force-raw=on',
                   '-device', f'loader,file={args.uboot.resolve()},addr=0x87800000,force-raw=on,cpu-num=0',
                   '-display', 'none', '-monitor', 'none', '-S', '-no-reboot',
                   '-no-shutdown',
                   '-serial', f'unix:{p}/serial,server=on,wait=off',
                   '-qmp', f'unix:{p}/qmp,server=on,wait=off',
                   '-qtest', f'unix:{p}/qt,server=on,wait=off', '-qtest-log', '/dev/null',
                   '-gdb', f'unix:{p}/gdb,server=on,wait=off',
                   '-chardev', f'socket,id=usb,path={p}/usb,server=on,wait=off',
                   '-global', 'prime-g2-usbotg-device.chardev=usb',
                   '-d', 'guest_errors,unimp,cpu_reset', '-D', str(out/'qemu.log')]
        if args.ram_loader:
            # QEMU otherwise runs its NAND ROM path when backing is present.
            # Wrap the unchanged complete U-Boot/DTB bytes in an ELF container
            # so -kernel selects an explicit RAM entry, with no code patches.
            binary = args.uboot.read_bytes()
            ident = b'\x7fELF'+bytes([1,1,1])+bytes(9)
            header = struct.pack('<16sHHIIIIIHHHHHH', ident,2,40,1,
                0x87800000,52,0,0x05000000,52,32,1,0,0,0)
            segment = struct.pack('<8I',1,0x1000,0x87800000,0x87800000,
                                  len(binary),len(binary),7,0x1000)
            ram_elf = out/'uboot-ram.elf'
            ram_elf.write_bytes((header+segment).ljust(0x1000,b'\0')+binary)
            index = command.index('-device', command.index('-device') + 1)
            command[index:index+2] = ['-kernel', str(ram_elf)]
        if args.physical_pages:
            command += ['-global', 'prime-g2-gpmi-bch.physical-pages=on']
        if args.trace_writes:
            command += ['-global', 'prime-g2-gpmi-bch.trace-writes=on']
        if args.stock_nand:
            command += ['-global', f'prime-g2-gpmi-bch.stock-nand={args.stock_nand.resolve()}',
                        '-global', f'prime-g2-gpmi-bch.stock-overlay={out}/nand.overlay']
        with (out/'stderr.log').open('wb') as err:
            proc = subprocess.Popen(command, stdout=err, stderr=err)
            serial = q = mp = usb = None
            transcript = bytearray()
            try:
                serial = r.connect_socket(p/'serial'); serial.settimeout(.2)
                q, mp = r.QTest(p/'qt'), r.QMP(p/'qmp')
                q.socket.settimeout(5); mp.socket.settimeout(5)
                def receive(needle, timeout=35):
                    start = len(transcript); deadline = time.monotonic()+timeout
                    while time.monotonic()<deadline:
                        try:
                            part = serial.recv(4096)
                        except socket.timeout:
                            continue
                        if not part:
                            break
                        transcript.extend(part)
                        if needle in transcript[start:]:
                            return bytes(transcript[start:])
                    raise TimeoutError(f'console missing {needle!r}')
                def cmd(text):
                    serial.sendall(text.encode()+b'\n')
                    return receive(b'=> ')
                if args.ddr_image:
                    imx = args.ddr_image.read_bytes()
                    header = struct.unpack_from('<8I', imx)
                    assert header[0] == 0x402000d1
                    binary = args.uboot.read_bytes()
                    entry = header[1]-header[5]
                    assert imx[entry:entry+len(binary)] == binary, 'DCD belongs to a different loader'
                    position = header[3]-header[5]
                    assert imx[position] == 0xd2
                    end = position+int.from_bytes(imx[position+1:position+3], 'big')
                    position += 4
                    while position < end:
                        tag, length, parameter = struct.unpack_from('>BHB', imx, position)
                        assert tag == 0xcc and parameter == 4 and length >= 12
                        assert (length-4) % 8 == 0 and position+length <= end
                        for at in range(position+4, position+length, 8):
                            address, value = struct.unpack_from('>II', imx, at)
                            q.writel(address, value)
                        position += length
                    assert position == end
                    # The model correctly rejects generic-loader writes while
                    # DDR is unavailable. Stage both payloads only after DCD,
                    # matching ROM initialization followed by USB upload.
                    for base, payload in ((0x87800000, binary), (0x84000000, data)):
                        for at in range(0, len(payload), 65536):
                            chunk = payload[at:at+65536]
                            q.command(f'write {base+at:#x} {len(chunk)} 0x{chunk.hex()}')
                mp.execute('cont'); receive(b'=> ')
                # Board startup writes its recovery marker at 80001000. Load
                # the authentic image after startup, as a real transfer would.
                cmd(f'cp.b 84000000 80000000 {len(data):x}')
                mp.execute('stop')
                mp.execute('human-monitor-command', {'command-line': f'pmemsave 0x80000000 {len(data):#x} "{out}/preloaded.bin"'})
                loaded = (out/'preloaded.bin').read_bytes()
                differences = [i for i, (a, b) in enumerate(zip(data, loaded)) if a != b]
                (out/'preload-check.json').write_text(json.dumps({'sha256': hashlib.sha256(loaded).hexdigest(), 'difference_count': len(differences), 'first_differences': differences[:32]}, indent=2)+'\n')
                assert loaded == data, 'CPU copy changed the original HP image'
                mp.execute('cont')
                assert b'unsupported component' in cmd('hpram unknown 1')
                assert b'unsupported component' in cmd(f'hpram {kind} 1')
                # Corrupt and restore only the isolated model's RAM copy.
                first = data[0]
                cmd(f'mw.b 80000000 {first ^ 1:02x} 1')
                assert b'verification failed' in cmd(f'hpram {kind} {len(data):x}')
                cmd(f'mw.b 80000000 {first:02x} 1')
                if args.ddr_image:
                    # A valid image must be refused before display shutdown
                    # when the inherited address window cannot serve HP.
                    original_map = q.readl(0x021b0040)
                    q.writel(0x021b0040, 0x47)
                    assert b'incompatible DDR map' in cmd(f'hpram {kind} {len(data):x}')
                    q.writel(0x021b0040, original_map)
                def capture_logical(name):
                    from PIL import Image
                    ctrl, size, framebuffer = (q.readl(a) for a in (0x021c8000,0x021c8030,0x021c8040))
                    if size != (240<<16)|320 or (ctrl>>8)&3 != 3:
                        return False
                    target = out/(name+'.bin')
                    mp.execute('human-monitor-command', {'command-line': f'pmemsave {framebuffer:#x} 0x4b000 "{target}"'})
                    Image.frombytes('RGB',(320,240),target.read_bytes(),'raw','BGRX').save(out/(name+'.png'))
                    return True
                def key(name):
                    row, col = keymap[name]
                    if row == 255:
                        q.writel(0x020cc0fc,1);time.sleep(1);q.writel(0x020cc0fc,0)
                    else:
                        q.writew(0x020b8008,(row<<8)|col|0x8000);time.sleep(.12)
                        q.writew(0x020b8008,(row<<8)|col)
                    time.sleep(.15)
                ilitek_path = None
                def swipe(coords):
                    nonlocal ilitek_path
                    # Inject reports through the selected controller, preserving guest I2C.
                    if ilitek_path is None:
                        pending = ['/machine']
                        for _ in range(512):
                            if not pending: break
                            parent = pending.pop()
                            for child in mp.execute('qom-list', {'path':parent})['return']:
                                if not child['type'].startswith('child<'): continue
                                path = parent+'/'+child['name']
                                if child['type'] == 'child<prime-g2-ilitek-ili2117>':
                                    ilitek_path = path; break
                                pending.append(path)
                            if ilitek_path: break
                        if ilitek_path is None: raise RuntimeError('modeled touch endpoint missing')
                    for name,value in zip(('host-x1','host-y1','host-x2','host-y2','host-ms'),(*coords,500)):
                        mp.execute('qom-set', {'path':ilitek_path,'property':name,'value':value})
                    time.sleep(1)
                def run_gdb():
                    script = p/'experiment.gdb'
                    script.write_text('set pagination off\nset confirm off\nset architecture arm\n'+
                                      ('file '+json.dumps(str(out/'uboot-ram.elf'))+'\n' if args.ram_loader else '')+
                                      'target remote '+str(p/'gdb')+'\n'+
                                      gdb_source+'\ndetach\nquit\n')
                    (out/'gdb-experiment.txt').write_text(gdb_source)
                    with (out/'gdb.log').open('w') as log:
                        result = subprocess.run(['arm-none-eabi-gdb','-q','-nx','-batch','-x',str(script)],
                                                stdout=log,stderr=subprocess.STDOUT,timeout=args.gdb_timeout)
                    result.check_returncode()
                    mp.execute('stop')
                def launch(text):
                    nonlocal usb
                    if not args.sdp_launch:
                        serial.sendall(text.encode()+b'\n')
                        return
                    # Fixture RAM preload, like the HP image above. Exercise
                    # the real SDP jump and active gadget at the handoff; this
                    # observation does not qualify the upload transport.
                    script = legacy_script(text)
                    q.command(f'write {SCRIPT:#x} {len(script)} 0x{script.hex()}')
                    serial.sendall(b'sdp 0\n')
                    usb = PrimeUSBHost(p/'usb')
                    usb.socket.settimeout(5)
                    device, _ = usb.connect_and_enumerate(controller_timeout=30)
                    assert struct.unpack_from('<HH', device, 8) == (0xcafe, 0x5053)
                    # f_sdp waits for the host's HID report descriptor request
                    # before it begins servicing the SDP state machine.
                    usb.control_in(0x81, 6, 0x2200, length=64)
                    r.sdp_command(usb, 0x0b0b, SCRIPT)
                    r.sdp_security(usb)
                if args.menu:
                    launch('lfhpboot'+(' research-256' if args.confinement else ''))
                    receive(b'HP RAM menu: screen=1 selected=1')
                    time.sleep(.2)
                    mp.execute('screendump', {'filename': str(out/'menu.ppm')})
                    key('ok')
                else:
                    launch(f'hpram {kind} {len(data):x}'+(' research-256' if args.confinement else ''))
                receive(b'original ARM entry')
                samples = []
                for index in range(2):
                    time.sleep(args.seconds/2)
                    mp.execute('stop')
                    samples.append({'elapsed_seconds': args.seconds*(index+1)/2,
                                    'cpu': mp.execute('human-monitor-command', {'command-line': 'info registers'})['return'],
                                    'nand_commands': q.readl(0x0180615c),
                                    'overlay_pages': q.readl(0x01806160),
                                    'ecc_writes': q.readl(0x01806170),
                                    'bch_registers': {hex(a): hex(q.readl(a)) for a in (0x01808000, 0x01808080, 0x01808090)},
                                    'diagnostic_mmio': {hex(a):hex(q.readl(a)) for a in (*range(0x020cc000,0x020cc060,4),0x00a02000,0x00a02004,*range(0x00a01200,0x00a01214,4),*range(0x021c8000,0x021c8050,0x10),0x020a0000,0x020a0004,0x020a8000,0x020a8004,*range(0x021c8050,0x021c80c0,0x10),*range(0x020e0104,0x020e0138,4),*range(0x020e0390,0x020e03c4,4),0x020c4018,0x020c4038)},
                                    'rtos': mp.execute('human-monitor-command', {'command-line': 'xp /32wx '+('0x807c3464' if kind=='os' else '0x8004b764')})['return'],
                                    'apbh': [q.readl(a) for a in (0x01804000,0x01804010,0x01804100,0x01804110,0x01804140)]})
                    if index == 0:
                        capture_logical('before-keys')
                        if args.gdb_script and args.gdb_stage == 'before-input': run_gdb()
                        mp.execute('cont')
                        for number,action in enumerate(actions):
                            if 'key' in action: key(action['key'])
                            elif 'swipe' in action: swipe(action['swipe'])
                            else: time.sleep(action['wait'])
                            mp.execute('stop'); capture_logical(f'action-{number:02d}')
                            (out/f'action-{number:02d}-input.json').write_text(json.dumps({hex(a):hex(q.readl(a)) for a in (*range(0x0209c000,0x0209c020,4),0x00a0110c,0x00a0120c,0x021a4008,0x021a400c)},indent=2)+'\n')
                            mp.execute('cont')
                        if args.gdb_script and args.gdb_stage == 'after-input':
                            mp.execute('stop'); run_gdb(); mp.execute('cont')
                        for name in keys:
                            key(name)
                        if keys:
                            time.sleep(.5)
                            mp.execute('stop'); capture_logical('after-keys'); mp.execute('cont')
                        if args.power_off:
                            row, col = keymap['shift']
                            q.writew(0x020b8008,(row<<8)|col|0x8000); time.sleep(.15)
                            key('onoff')
                            q.writew(0x020b8008,(row<<8)|col)
                        if args.power_key:
                            q.writel(0x020cc0fc, 1); time.sleep(.1); q.writel(0x020cc0fc, 0)
                mp.execute('human-monitor-command', {'command-line': f'pmemsave 0x80000000 0x1000000 "{out}/runtime.bin"'})
                mp.execute('screendump', {'filename': str(out/'screen.ppm')})
                from PIL import Image
                Image.open(out/'screen.ppm').save(out/'screen.png')
                if (out/'menu.ppm').exists():
                    Image.open(out/'menu.ppm').save(out/'menu.png')
                # Diagnostic LCDIF view, separate from panel electrical qualification.
                capture_logical('lcdif-logical')
                patch_report = None
                if args.confinement:
                    from prime_hp_confinement import patch_image, patches
                    _, patch_report = patch_image(args.image.name, data)
                    runtime = (out/'runtime.bin').read_bytes()
                    for patch in patches(args.image.name):
                        at = patch.address-0x80000000
                        assert runtime[at:at+len(patch.replacement)] == patch.replacement, 'runtime patch overwritten'
                report = {'image_sha256': hashlib.sha256(data).hexdigest(),
                          'uboot_sha256': artifact_hashes['uboot'],
                          'explicit_ram_loader': args.ram_loader,
                          'qemu_sha256': artifact_hashes['qemu'],
                          'probe_sha256': hashlib.sha256(probe_source).hexdigest(),
                          'command': command, 'samples': samples,
                          'nand_representation': ('physical codewords' if args.physical_pages else 'decoded capture') if args.stock_nand else 'synthetic erased',
                          'ddr': 'paired research DCD replayed through model MMIO' if args.ddr_image else 'model preinitialized; HP DCD not executed',
                          'ddr_image_sha256': artifact_hashes.get('ddr_image'),
                          'incompatible_ddr_rejected': bool(args.ddr_image),
                          'hp_instruction_patches': patch_report['patches'] if patch_report else [],
                          'confinement_profile': patch_report,
                          'trace_writes': args.trace_writes,
                          'power_key_between_samples': args.power_key,
                          'power_off_after_keys': args.power_off,
                          'keys_between_samples': keys,
                          'model_actions': actions,
                          'selected_through_menu': args.menu,
                          'launched_through_usb_sdp': args.sdp_launch,
                          'model_rejected_bch_layout': 'unsupported capture layout' in (out/'qemu.log').read_text(),
                          'negative_verification_checks': 'passed',
                          'gdb_experiment_sha256': hashlib.sha256(gdb_source.encode()).hexdigest() if gdb_source else None,
                          'qualification': 'verified transfer attempted; HP startup and retained data not asserted'}
                for name,path in [('uboot',args.uboot),('qemu',r.QEMU)]+([('ddr_image',args.ddr_image)] if args.ddr_image else []):
                    assert hashlib.sha256(path.read_bytes()).hexdigest()==artifact_hashes[name], 'test executable changed during run'
                (out/'observation.json').write_text(json.dumps(report, indent=2)+'\n')
                print('PASS image rejection and RAM transfer; HP startup is NOT qualified')
            finally:
                if mp and proc.poll() is None:
                    try:
                        mp.execute('stop')
                        (out/'final-registers.txt').write_text(mp.execute('human-monitor-command', {'command-line':'info registers'})['return'])
                    except (OSError, TimeoutError):
                        pass
                if serial:
                    # Preserve diagnostics emitted during failed USB actions.
                    deadline = time.monotonic()+1
                    while time.monotonic() < deadline:
                        try:
                            part = serial.recv(4096)
                        except socket.timeout:
                            break
                        if not part:
                            break
                        transcript.extend(part)
                (out/'serial.log').write_bytes(transcript)
                for connection in (usb, serial, q, mp):
                    if connection:
                        connection.close()
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill(); proc.wait(timeout=5)


if __name__ == '__main__':
    main()
