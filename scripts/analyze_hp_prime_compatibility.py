#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reproduce V15751 research using private images; never patch or flash them.

Unicorn executes selected authentic instruction ranges with synthetic RAM and
explicitly intercepted device calls. This is not a full HP boot or confinement
qualification. Reports (including disassembly) must stay in ignored build/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

BASE = 0x80000000
ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    "HPPrime_OS.img": (19483788, "80ba573472b3731bdbb0165bf13390579863ca1d3f5c003dfb21c17dd4871461"),
    "HPPrime.img": (8192864, "25d3d2d27e45fc3ce7dc8c4a111b31f8aefc14c4b21e8d8ee4b32251e31c1b82"),
    "bootloader.img": (358316, "9bfe04ec74eed51b606001caa3e5c0f701acd70eeb7d622f5a25616efdc0436e"),
}
# Addresses describe this exact image pair, not an installable patch profile.
PROFILES = {
    "HPPrime.img": {
        "bounds": (0x802B1AB8, 0x802B1AD2),
        "stores": (0x802B1ACA, 0x802B1AD0),
        "copy": (0x804716E4, 0x8047172A),
        "format": 0x8047181C, "init": 0x804716A6,
        "query": 0x804E2FE4, "erase": 0x804E3004,
        "raw_erase": 0x803A1946, "raw_write": 0x803A1700,
        "raw_mark": 0x803A190A, "diagnostic": 0x803A23D4,
        "mark_callback": 0x802B192E,
        "state_literal": 0x802B193A, "geometry_literal": 0x802B1952,
        "prefix": (0x803A1FD2, 0x803A1FD6, 0x80289934, 0x804788D4, 0x803A16A4),
        "placement": (0x803A277C, 0x803A2790),
        "ranges": [(0x802B18E6, 0x802B1AE4), (0x804716E4, 0x8047172A),
                   (0x8047181C, 0x8047186A), (0x803A190A, 0x803A19D8),
                   (0x803A1DAC, 0x803A1DC6), (0x803A1FD2, 0x803A20F2),
                   (0x803A23D4, 0x803A23F2), (0x803A255C, 0x803A2680),
                   (0x803A2680, 0x803A2880), (0x80415AE0, 0x80415B1C),
                   (0x802B0B7E, 0x802B0BA2), (0x802B0B30, 0x802B0B7E),
                   (0x802B31BE, 0x802B31CC), (0x8039DFBC, 0x8039E026),
                   (0x802F5580, 0x802F5720), (0x80525DF8, 0x80526070),
                   (0x804E931E, 0x804E935E)],
    },
    "bootloader.img": {
        "bounds": (0x80007CCC, 0x80007D00),
        "stores": (0x80007CF0, 0x80007CFE),
        "copy": (0x800060E0, 0x80006126),
        "format": 0x80006218, "init": 0x800060A2,
        "query": 0x8000A074, "erase": 0x8000A094,
        "raw_erase": 0x8001416A, "raw_write": 0x80013F24,
        "raw_mark": 0x8001412E, "diagnostic": 0x80014744,
        "mark_callback": 0x80007A40,
        "state_literal": 0x80007A72, "geometry_literal": 0x80007A88,
        "prefix": (0x80014628, 0x8001462E, 0x80011C18, 0x8001F770, 0x80013EC8),
        "placement": (0x80014B9C, 0x80014BA6),
        "ranges": [(0x800079BA, 0x80007BA8), (0x80007BDC, 0x80007D10),
                   (0x800060E0, 0x80006126), (0x80006218, 0x80006266),
                   (0x800145D0, 0x80014624), (0x80014628, 0x80014758),
                   (0x80014758, 0x800147C0), (0x8001490C, 0x80014A3A),
                   (0x80014A40, 0x80014FD8), (0x80031688, 0x800318D0)],
    },
}


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def verify_input(name, data):
    require(name in INPUTS, "unknown input component")
    size, digest = INPUTS[name]
    require(len(data) == size and hashlib.sha256(data).hexdigest() == digest,
            f"{name}: requires the exact original V15751 input; no partial matches")


def private_output(path):
    path = path.resolve()
    require(path.is_relative_to((ROOT / "build").resolve()),
            "private reports must be written beneath this checkout's ignored build/")
    return path


def stock_bounds(block_bytes, total_blocks):
    require(block_bytes > 0 and total_blocks > 0, "invalid geometry")
    return ((48 * 1024 * 1024 + block_bytes - 1) // block_bytes + 8,
            total_blocks - 1)


def instructions(data, start, stop, arm=False):
    import capstone as cs
    md = cs.Cs(cs.CS_ARCH_ARM, cs.CS_MODE_ARM if arm else cs.CS_MODE_THUMB)
    md.detail = True
    return list(md.disasm(data[start-BASE:stop-BASE], start))


def literal(data, address):
    import capstone.arm as arm
    i = instructions(data, address, address+4)[0]
    require(i.mnemonic.startswith("ldr") and len(i.operands) == 2 and
            i.operands[1].type == arm.ARM_OP_MEM and
            i.operands[1].mem.base == arm.ARM_REG_PC, "expected PC-relative literal")
    offset = ((address + 4) & ~3) + i.operands[1].mem.disp - BASE
    return struct.unpack_from("<I", data, offset)[0]


class Machine:
    """A bounded instruction harness, with no physical I/O or MMIO mapping."""
    def __init__(self, data):
        import unicorn as uc
        from unicorn import arm_const as reg
        self.reg = reg
        self.u = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_THUMB)
        self.u.mem_map(BASE, 0x4000000)
        self.u.mem_write(BASE, data)
        self.set("SP", 0x83FF0000)
        self.set("LR", 0x83FE0001)
        self.hooks = {}
        self.count = 0
        self.u.hook_add(uc.UC_HOOK_CODE, self._hook)

    def get(self, r):
        return self.u.reg_read(getattr(self.reg, "UC_ARM_REG_" + r))

    def set(self, r, value):
        self.u.reg_write(getattr(self.reg, "UC_ARM_REG_" + r), value)

    def put(self, address, value, size=4):
        self.u.mem_write(address, value.to_bytes(size, "little"))

    def read(self, address):
        return int.from_bytes(self.u.mem_read(address, 4), "little")

    def _hook(self, _u, address, _size, _user):
        self.count += 1
        if address in self.hooks:
            self.hooks[address](self)
            self.set("PC", self.get("LR"))

    def run(self, start, stop=0x83FE0000):
        self.u.emu_start(start | 1, stop, timeout=5_000_000, count=300_000)
        require(self.get("PC") == stop,
                f"instruction budget/timeout: stopped at {self.get('PC'):#x}, wanted {stop:#x}")


def audit_bounds(name, data, profile):
    results = []
    for block_bytes, total in [(131072, 4096), (262144, 2048), (196608, 3000)]:
        m = Machine(data)
        dev, geo = 0x82000000, 0x82010000
        if name == "HPPrime.img":
            m.set("R4", dev)
            m.set("R5", geo)
        else:
            geo, dev = literal(data, 0x80007CCC), literal(data, 0x80007CEC)
        m.put(geo+8, block_bytes, 8)
        m.put(geo+0x18, total)
        m.set("R1", 0)
        m.run(*profile["bounds"])
        actual = (m.read(dev+0x14), m.read(dev+0x18))
        require(actual == stock_bounds(block_bytes, total), "bounds differ from formula")
        m.set("R4", dev)
        m.run(*profile["copy"])
        require((m.read(dev+0xF4), m.read(dev+0xF8)) == actual, "internal bounds differ")
        results.append({"block_bytes": block_bytes, "total_blocks": total,
                        "bounds": actual, "instructions": m.count})
    return results


def audit_format(data, p, end, bad=()):
    m = Machine(data)
    dev = 0x82000000
    m.set("R0", dev)
    m.put(dev+0xF4, 392)
    m.put(dev+0xF8, end)
    checked, erased = [], []
    m.hooks[p["init"]] = lambda vm: vm.set("R0", 1)
    def query(vm):
        block = vm.get("R1")
        checked.append(block)
        vm.put(vm.get("R2"), 9 if block in bad else 0, 1)
    def erase(vm):
        erased.append(vm.get("R1"))
        vm.set("R0", 1)
    m.hooks[p["query"]], m.hooks[p["erase"]] = query, erase
    m.run(p["format"])
    expected = list(range(392, end+1))
    require(checked == expected, "format query escapes inclusive bounds")
    require(erased == [b for b in expected if b not in bad], "format erase range differs")
    return {"start": 392, "end": end, "queries": len(checked), "erases": len(erased),
            "bad_blocks": list(bad), "instructions": m.count,
            "intercepts": ["initialization returns success", "block-state query", "erase"]}


def audit_diagnostic(data, p):
    m = Machine(data)
    erased = []
    def erase(vm):
        erased.append(vm.get("R0"))
        vm.set("R0", 0)
    m.hooks[p["raw_erase"]] = erase
    m.run(p["diagnostic"])
    require(erased == [0, 1, 2, 3], "diagnostic erase changed")
    return {"erased_blocks": erased, "intercepts": ["raw erase succeeds"]}


def audit_badblock(name, data, p, table_block):
    m = Machine(data)
    header, table = 0x82020000, 0x82030000
    state, geo = literal(data, p["state_literal"]), literal(data, p["geometry_literal"])
    m.put(state, header)
    if name == "HPPrime.img":
        m.put(state+4, table)
    else:
        m.put(literal(data, 0x80007A58), table)
    m.put(header+0x78, table_block*64)
    m.put(geo+0x14, 64)
    m.put(geo+0x2C, 2048)
    m.set("R1", 500)
    events = []
    for label, address in [("mark", p["raw_mark"]), ("erase", p["raw_erase"]),
                           ("program", p["raw_write"])]:
        def hook(vm, label=label):
            events.append([label, vm.get("R0")])
            vm.set("R0", 0)
        m.hooks[address] = hook
    m.run(p["mark_callback"])
    require([e[1] for e in events if e[0] == "erase"] == list(range(table_block, table_block+4)),
            "bad-block metadata erase copies differ")
    require([e[1] for e in events if e[0] == "program"] ==
            [b*64+page for b in range(table_block, table_block+4) for page in (0, 4)],
            "bad-block metadata program pages differ")
    require(m.read(table+0x804) == 1 and m.read(table+0x808) == 500,
            "native bad-block table append differs")
    return {"synthetic_table_first_block": table_block, "events": events,
            "intercepts": ["raw mark/program/erase succeed"],
            "warning": "header and table placement are synthetic, not measured NAND locations"}


def audit_reset(data):
    results = []
    for mode in range(5):
        m = Machine(data)
        calls = []
        for target in (0x802B076C, 0x802F5580, 0x802B0B7E):
            def hook(vm, target=target):
                calls.append({"target": hex(target), "r1": vm.get("R1")})
                vm.set("R0", 0)
            m.hooks[target] = hook
        m.set("R0", mode)
        m.run(0x80415AE0)
        expected = [0x802B076C, 0x802F5580, 0x802F5580, 0x802B0B7E]
        require([c["target"] for c in calls] == ([hex(expected[mode])] if mode < 4 else []),
                "reset dispatch differs")
        require(mode not in (1, 2) or calls[0]["r1"] == mode-1, "factory reset argument differs")
        results.append({"mode": mode, "calls": calls, "result": m.get("R0")})
    return results


def audit_prefix(data, p):
    """Execute updater's raw erase helper, including its whole-chip bad scan."""
    start, geo_literal, allocate, initialize, query = p["prefix"]
    m = Machine(data)
    table, progress = 0x82030000, 0x82050000
    m.put(literal(data, geo_literal)+0x18, 4096)
    m.set("R0", 384)
    m.set("R1", progress | 1)
    scanned, erased = [], []
    m.hooks[allocate] = lambda vm: vm.set("R0", table)
    m.hooks[initialize] = lambda vm: vm.set("R0", table)
    m.hooks[progress] = lambda vm: vm.set("R0", 0)
    def check(vm):
        block = vm.get("R0")
        scanned.append(block)
        vm.set("R0", int(block == 7))
    def erase(vm):
        erased.append(vm.get("R0"))
        vm.set("R0", 0)
    m.hooks[query], m.hooks[p["raw_erase"]] = check, erase
    m.run(start)
    require(scanned == list(range(4, 4096)), "raw prefix helper's bad-block scan changed")
    require(erased == [b for b in range(384) if b != 7], "raw prefix erase changed")
    return {"requested_blocks": 384, "scanned_bounds": [4, 4095],
            "erase_bounds": [0, 383], "erase_count": len(erased), "skipped_bad_block": 7,
            "intercepts": ["allocator", "empty table constructor", "progress callback",
                           "raw bad-block query", "raw erase succeeds"],
            "warning": "helper execution with synthetic caller arguments, not a full update"}


def audit_placement(name, data, p):
    m = Machine(data)
    geo = 0x82010000 if name == "HPPrime.img" else literal(data, p["placement"][0])
    m.put(geo+0x14, 64)
    m.set("R4", geo)
    m.set("R5", 0x82040000)
    m.run(*p["placement"])
    require(m.get("R0") == 768, "nominal first image placement changed")
    return {"first_component_page": 768, "page_bytes": 2048,
            "byte_offset": 1572864, "pages_per_block": 64,
            "warning": "nominal start before bad-block skipping; not a readback of installed HP"}


def audit_image(name, data):
    from prepare_hp_prime_stock_fixture import parse_ivt
    p = PROFILES[name]
    ivt = parse_ivt(data, name)
    boot_data = struct.unpack_from("<III", data, ivt["boot_data"]-BASE)
    entry_target = struct.unpack_from("<I", data, 0x2020)[0]
    evidence = []
    for a, b in p["ranges"] + [(0x80002000, 0x80002020), (entry_target, entry_target+0xA0)]:
        decoded = instructions(data, a, b, a == 0x80002000 or a == entry_target)
        evidence.append({"start": hex(a), "stop": hex(b),
                         "sha256": hashlib.sha256(data[a-BASE:b-BASE]).hexdigest(),
                         "instructions": [f"{i.address:#010x} {i.mnemonic} {i.op_str}" for i in decoded]})
    stores = [instructions(data, a, a+2)[0] for a in p["stores"]]
    require(all(i.mnemonic == "str" for i in stores), "expected 16-bit parameter stores")
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "ivt": ivt, "boot_data": boot_data, "arm_reset_target": hex(entry_target),
            "parameter_stores": [{"address": hex(a), "expected_bytes": data[a-BASE:a-BASE+2].hex()}
                                 for a in p["stores"]],
            "bounds_cases": audit_bounds(name, data, p),
            "format_cases": [audit_format(data, p, end, bad)
                             for end, bad in [(4095, ()), (2047, (400, 2047)), (391, ())]],
            "diagnostic": audit_diagnostic(data, p),
            "badblock_cases": [audit_badblock(name, data, p, b) for b in (4, 16)],
            "raw_prefix_erase": audit_prefix(data, p),
            "image_placement": audit_placement(name, data, p),
            "reset_dispatch": audit_reset(data) if name == "HPPrime.img" else None,
            "private_disassembly": evidence}


def writer_references(data, p):
    """Discovery index, not a reachability claim: code and data are interleaved."""
    import capstone as cs
    targets = {p[k]: k for k in ("raw_erase", "raw_write", "raw_mark", "mark_callback")}
    found = {name: {"entry": hex(address), "direct_candidates": [], "pointer_candidates": []}
             for address, name in targets.items()}
    for mode_name, mode in (("thumb", cs.CS_MODE_THUMB), ("arm", cs.CS_MODE_ARM)):
        md = cs.Cs(cs.CS_ARCH_ARM, mode)
        md.skipdata = True
        for address, _, mnemonic, operands in md.disasm_lite(data, BASE):
            if mnemonic not in ("bl", "blx", "b", "b.w"):
                continue
            match = re.fullmatch(r"#(0x[0-9a-f]+)", operands)
            if match and int(match[1], 16) in targets:
                found[targets[int(match[1], 16)]]["direct_candidates"].append(
                    {"address": hex(address), "mode": mode_name})
    for address, name in targets.items():
        needle = struct.pack("<I", address | 1)
        offset = data.find(needle)
        while offset >= 0:
            found[name]["pointer_candidates"].append(hex(BASE+offset))
            offset = data.find(needle, offset+1)
    return {"coverage": "linear ARM/Thumb scan and Thumb pointer search; false positives and indirect gaps possible",
            "writers": found}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--container", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        out = private_output(args.output_dir)
        paths = {n: args.container if n == "HPPrime_OS.img" else args.fixture_dir / n
                 for n in INPUTS}
        inputs = {n: path.read_bytes() for n, path in paths.items()}
        for name, data in inputs.items():
            verify_input(name, data)
        import capstone
        import unicorn
        report = {"format": "lefony-hp-v15751-phase2-research-v1",
                  "analyzer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "qualification": "research-only; no supported physical dual-boot path",
                  "physical_io": False, "image_mutation": False,
                  "dependencies": {"capstone": capstone.__version__, "unicorn": unicorn.__version__},
                  "limitations": ["synthetic RAM and selected function entry states",
                                  "device callbacks intercepted; no actual NAND writes",
                                  "not a complete call graph or proof of all indirect writers",
                                  "no authentic cold/reset boot or U-Boot handoff qualification"],
                  "inputs": {n: {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
                             for n, b in inputs.items()},
                  "images": {n: audit_image(n, inputs[n]) for n in PROFILES}}
        for name, p in PROFILES.items():
            report["images"][name]["writer_reference_candidates"] = writer_references(inputs[name], p)
        for name, original in inputs.items():
            require(paths[name].read_bytes() == original, "source changed during audit")
        out.mkdir(parents=True, exist_ok=True)
        (out / "compatibility.json").write_text(json.dumps(report, indent=2) + "\n")
        print("V15751 instruction checks passed; private report:", out / "compatibility.json")
    except (AuditError, OSError, ImportError) as exc:
        parser.exit(1, f"audit refused: {exc}\n")


if __name__ == "__main__":
    main()
