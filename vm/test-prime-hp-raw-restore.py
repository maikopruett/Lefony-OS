#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run guarded raw restore transactions through actual ARM U-Boot in QEMU.

The default uses synthetic NAND without private inputs. Optional Phase 6 boot
fixtures exercise recovery routes and one image block on that synthetic source.
No attached calculator is used. This validates command behavior, not physical
flash endurance or power loss.
"""
import argparse
import importlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prime_phase6_transport import Phase6SDP
from prime_hp_raw_restore import Change, PrimeSDP, RAW_BLOCK, GEOMETRY, restore_blocks, restore_image, sha
r = importlib.import_module("test-prime-g2-rom-recovery")


def phase6_transaction(device, directory, candidate, uboot):
    """Optional private boot-stream fixture; all other NAND is synthetic.

    Exercises the real physical adapter and actual ARM NAND commands, including
    a lost target acknowledgement. This never boots the staged OS fixture.
    """
    from prime_dual_physical import PhysicalMedia, model, ERASED
    from prime_dual_boot_transaction import Change as DualChange, Transaction, Engine
    from prime_phase6_install_trial import snapshot_verified
    backup=directory/'synthetic-before.raw'
    with backup.open('wb') as f:
        for _ in range(128):f.write(ERASED*32)
    with backup.open('r+b') as f:
        for block in (0,7):
            f.seek(block*RAW_BLOCK);f.write(device.read_block(block))
    digest=model.file_hash(backup)
    changes=[]
    for block in (*range(240,256),3,2,1,0):
        before,after=model.read_block(backup,block),model.read_block(candidate,block)
        if before!=after:
            changes.append(DualChange(block,before,after,'stage-recovery' if block>=240 else 'redirect-rom'))
    # One image block suffices to exercise the physical ROM barrier.
    changes.append(DualChange(2048,ERASED,model.read_block(candidate,2048),'stage-images'))
    tx=Transaction(changes,digest)
    events=[]
    media=PhysicalMedia(device,backup,digest,event=events.append)
    program=device.program_pages
    try:
        media.inspect();permit=media.authorize(tx,uboot=uboot,approved=True)
        engine=Engine(media,tx,research_authorization=permit);engine.prepare()
        def lose_target_ack(block,count):
            program(block,count)
            if block==2048:raise TimeoutError('modeled lost acknowledgement after actual ARM program')
        device.program_pages=lose_target_ack
        try:engine.run()
        except TimeoutError:pass
        else:raise AssertionError('target acknowledgement was not interrupted')
        device.program_pages=program
        media.inspect(transaction=tx,resume=True)
        permit=media.authorize(tx,uboot=uboot,approved=True)
        Engine(media,tx,research_authorization=permit).run()
        assert sum(e.get('state')=='program-pending' and e.get('block')==2048 for e in events)==1
        current=directory/'synthetic-migrated.raw'
        current_digest=bytes.fromhex(snapshot_verified(media,tx,current))
    finally:
        device.program_pages=program;media.close()
    restore,_=model.build_restore_plan(current,backup,digest)
    media=PhysicalMedia(device,backup,digest,initial=current,initial_digest=current_digest,event=events.append)
    try:
        media.inspect();permit=media.authorize(restore,uboot=uboot,approved=True)
        for block in (258,259):media.erase_block(block)
        engine=Engine(media,restore,research_authorization=permit);engine.prepare();engine.run()
        # Verify all planned and preserved bytes before retiring the journals.
        snapshot_verified(media,restore,directory/'before-journal-cleanup.raw')
        for block in (258,259):media.erase_block(block)
        assert snapshot_verified(media,restore,directory/'synthetic-restored.raw')==digest.hex()
    finally:media.close()
    print('PASS actual ARM physical adapter: ROM barriers, lost-ACK resume without reprogramming, exact full restore',flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uboot", type=Path, default=ROOT / "build/lefony-uboot-hp-handoff/u-boot-dtb.bin")
    parser.add_argument('--phase6', action='store_true', help='also check isolated Phase 6 RAM hashing/page transport')
    parser.add_argument('--boot-candidate',type=Path,help='optional private candidate NAND for physical-adapter transaction tests')
    parser.add_argument('--boot-imx',type=Path,help='matching candidate NAND U-Boot IMX')
    parser.add_argument('--handoff-uboot',type=Path,help='optional dedicated RAM diagnostic binary to chain through bootm')
    parser.add_argument('--handoff-dtb',type=Path,help='matching bounded DTB for the RAM-only handoff')
    args = parser.parse_args()
    if bool(args.handoff_uboot)!=bool(args.handoff_dtb):
        parser.error('--handoff-uboot and --handoff-dtb must be paired')
    if bool(args.boot_candidate)!=bool(args.boot_imx) or args.boot_candidate and not args.phase6:
        parser.error('--boot-candidate and --boot-imx require --phase6 together')
    transport = Phase6SDP if args.phase6 else PrimeSDP
    with tempfile.TemporaryDirectory(prefix="hp-raw-model-", dir="/tmp") as temporary:
        p = Path(temporary)
        # Complete binary including DTB, explicit RAM entry, no implicit NAND ROM.
        binary = args.uboot.read_bytes()
        ident = b"\x7fELF" + bytes([1, 1, 1]) + bytes(9)
        header = struct.pack("<16sHHIIIIIHHHHHH", ident, 2, 40, 1, 0x87800000,
                             52, 0, 0x05000000, 52, 32, 1, 0, 0, 0)
        segment = struct.pack("<8I", 1, 0x1000, 0x87800000, 0x87800000,
                              len(binary), len(binary), 7, 0x1000)
        (p / "ram.elf").write_bytes((header + segment).ljust(0x1000, b"\0") + binary)
        marker = bytearray(b"\xff" * 2112); marker[2048] = 0
        # Block 0 models stock metadata occupying the conventional marker;
        # block 7 models a real factory-bad block that must never be erased.
        seeded = b"PG2RAW1\n" + b"".join(struct.pack("<B3xI", 1, page) + marker
                                        for page in (0, 7 * 64, 7 * 64 + 63))
        (p / "nand.overlay").write_bytes(seeded)
        command = [str(r.QEMU), "-machine", "hp-prime-g2", "-m", "256M",
                   "-global", "prime-g2-mmdc.preinitialized=on",
                   "-global", "cortex-a7-arm-cpu.cntfrq=8000000",
                   "-global", "prime-g2-gpmi-bch.physical-pages=on",
                   "-global", f"prime-g2-gpmi-bch.stock-overlay={p}/nand.overlay",
                   "-kernel", str(p / "ram.elf"), "-display", "none", "-monitor", "none",
                   "-serial", f"unix:{p}/serial,server=on,wait=off",
                   "-qtest", f"unix:{p}/qt,server=on,wait=off", "-qtest-log", "/dev/null",
                   "-qmp", f"unix:{p}/qmp,server=on,wait=off", "-S"]
        with (p / "stderr").open("wb") as err:
            process = subprocess.Popen(command, stdout=err, stderr=err)
            serial = q = mp = None
            transcript = bytearray()
            try:
                serial = r.connect_socket(p / "serial"); serial.settimeout(.2)
                q, mp = r.QTest(p / "qt"), r.QMP(p / "qmp")
                q.socket.settimeout(10); mp.socket.settimeout(10)

                def prompt(*, initial=False):
                    start, deadline = len(transcript), time.monotonic() + 35
                    interrupted=False
                    while time.monotonic() < deadline:
                        try: chunk = serial.recv(4096)
                        except socket.timeout: continue
                        if not chunk: break
                        transcript.extend(chunk)
                        # Dedicated Phase 6 RAM images enter SDP even without
                        # an SNVS token. This harness uses QTest RAM transfers
                        # and UART commands, so leave SDP through its existing
                        # Ctrl+C path. No physical firmware test hook is added.
                        if initial and args.phase6 and not interrupted and b'SDP: initialize...' in transcript[start:]:
                            serial.sendall(b'\x03');interrupted=True
                        if b"=> " in transcript[start:]: return
                    raise TimeoutError(transcript[-3000:].decode(errors="replace"))

                class ModelDevice(transport):
                    def __init__(self): pass
                    def _command(self, command, address, data=b"", read_count=0):
                        if command == 0x0404:
                            q.command(f"write {address:#x} {len(data)} 0x{data.hex()}")
                        elif command == 0x0b0b:
                            serial.sendall(f"source {address:x}\n".encode()); prompt()
                        else: raise ValueError("unsupported model transport command")
                    def read(self, address, count):
                        result = q.command(f"read {address:#x} {count}").split()[1]
                        return bytes.fromhex(result[2:])

                # Model a genuine defect separately from its recorded marker.
                q.command("writel 0x01806128 0x7")
                mp.execute("cont"); prompt(initial=True)
                d = ModelDevice()
                assert d.inventory() == (GEOMETRY, {0, 7}), d.inventory()
                # RAM BBT startup must not append flash BBT writes.
                assert (p / "nand.overlay").read_bytes() == seeded
                if args.phase6:
                    d.verify_protocol()
                    trial = bytes([0xa5])*2048 + bytes([255])*64
                    d.stage_bytes(trial)
                    d.erase(100)
                    assert d.hash_blocks(100,1) == [sha(bytes([255])*RAW_BLOCK)]
                    assert d.stage_digest(len(trial)).hex() == sha(trial)
                    d.program_pages(100,1)
                    assert d.read_page(100*64) == trial
                    assert d.hash_blocks(100,1) == [sha(trial + bytes([255])*(RAW_BLOCK-len(trial)))]
                    d.erase(100)
                    print('PASS actual ARM Phase 6 RAM digest, disjoint hash buffer and bounded page write/readback', flush=True)
                    if args.boot_candidate:
                        phase6_transaction(d,p,args.boot_candidate,args.boot_imx)
                factory = d.read_block(7)
                before = d.read_block(100)
                after = bytearray((i * 37 + 11) % 256 for i in range(RAW_BLOCK))
                after[2048] = after[2112 + 2048] = 255
                after = bytes(after)
                meta = d.read_block(0)
                journal = []
                restore_blocks(d, [Change(100, before, after),
                                   Change(0, meta, b"\xff" * RAW_BLOCK, sha(meta))],
                               {7}, journal.append, approved=True)
                assert d.read_block(7) == factory
                assert d.hash_blocks(100, 1) == [sha(after)]
                assert d.hash_blocks(0, 1) == [sha(b"\xff" * RAW_BLOCK)]
                restore_blocks(d, [Change(100, after, before)], {7}, journal.append, approved=True)
                assert d.read_block(100) == before and d.read_block(7) == factory
                # Raw controller operations on an injected defect must fail,
                # even though marker-only block 0 was explicitly scrubbed.
                q.command("writel 0x01806104 0x1c0")
                q.command("writel 0x01806100 0xd0")
                assert int(q.command("readl 0x0180610c").split()[1], 16) == 0xe1
                q.command("writel 0x01806100 0x80")
                q.command("writel 0x01806108 0xa5")
                q.command("writel 0x01806100 0x10")
                assert int(q.command("readl 0x0180610c").split()[1], 16) == 0xe1
                assert d.read_block(7) == factory
                expected = [sha(b"\xff" * RAW_BLOCK)] * 4096
                expected[7] = sha(factory)
                target = list(expected); target[100] = sha(after)
                captured = {}
                restore_image(d, target, lambda b: after if b == 100 else before,
                              {7}, journal.append,
                              lambda b, data: captured.update({b: data}),
                              expected_before=expected, approved=True)
                assert captured == {100: before}
                assert journal[-1]["state"] == "complete-device-verified"
                if args.handoff_uboot:
                    from prime_phase6_ram_handoff import handoff
                    # The diagnostic returns to SDP; this UART/QTest harness
                    # leaves SDP through Ctrl+C before reading its probe report.
                    class HandoffDevice(ModelDevice):
                        def _command(self,command,address,data=b'',read_count=0):
                            if command==0x0b0b:
                                serial.sendall(f'source {address:x}\n'.encode());prompt(initial=True)
                            else:super()._command(command,address,data,read_count)
                    handoff(HandoffDevice(),args.handoff_uboot.read_bytes(),args.handoff_dtb.read_bytes())
                    d.run('lfdualprobe layout')
                    assert struct.unpack('<4I',d.read(0x83e03000,16))==(0x4744464c,1,2,0xffffffff)
                    print('PASS RAM bootm handoff and diagnostic rejection of absent layout',flush=True)
                print(json.dumps({"result": "PASS", "uboot_sha256": sha(binary),
                                  "verified_transactions": sum(e["state"] == "verified" for e in journal),
                                  "complete_device_orchestration": True,
                                  "factory_bad_unchanged": True, "startup_flash_bbt_writes": False}))
            except Exception:
                print(transcript[-10000:].decode(errors="replace"), file=sys.stderr)
                raise
            finally:
                if serial: serial.close()
                if q: q.close()
                if mp: mp.close()
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)


if __name__ == "__main__":
    main()
