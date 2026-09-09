#!/usr/bin/env python3
"""Prepend 1 KiB of zeros so the i.MX NAND ROM finds the IVT at 0x400.

USB SDP wants the IVT at offset 0. Every Prinux / Raymii u-boot-dtb.imx is
built that way. The NAND boot ROM discards the first 1 KiB and looks at
0x400. NXP's kobs-ng -x is supposed to add this pad; the 2019 mfgtool
binary on the Prime G2 aborts instead of writing. Do the pad here.

Usage:
  pad_uboot.py u-boot-dtb-nandboot.imx u-boot-dtb-nandboot-pad.imx
  pad_uboot.py u-boot-dtb-nandboot.imx          # writes <name>-pad.imx
"""
from __future__ import annotations

import sys
from pathlib import Path

IVT = bytes.fromhex("d1002040")
PAD = b"\x00" * 1024


def pad(src: Path, dst: Path) -> None:
    data = src.read_bytes()
    if data[:4] != IVT:
        raise SystemExit(f"{src}: no IVT at offset 0 (got {data[:4].hex()})")
    if data[0x400:0x404] == IVT:
        raise SystemExit(f"{src}: already looks padded (IVT at 0x400)")
    out = PAD + data
    dst.write_bytes(out)
    print(f"wrote {dst} ({len(out)} bytes)")
    print(f"  0x000 {out[0:4].hex()}  (should be zeros)")
    print(f"  0x400 {out[0x400:0x404].hex()}  (should be d1002040)")


def main(argv: list[str]) -> None:
    if len(argv) not in (2, 3):
        raise SystemExit(__doc__)
    src = Path(argv[1])
    dst = Path(argv[2]) if len(argv) == 3 else src.with_name(src.stem + "-pad.imx")
    pad(src, dst)


if __name__ == "__main__":
    main(sys.argv)
