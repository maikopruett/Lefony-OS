#!/usr/bin/env python3
"""Patch a default-env string inside a u-boot-dtb.imx (NUL-terminated).

The replacement must fit in the original string (same or shorter). We
space-pad the tail so leftover characters cannot leak into the command while
preserving the packed environment's single NUL terminator.

Modes:
  nandboot  bootcmd_mfg=run bootcmd;
            USB is plugged on the bench; stock mfg path bootz's empty RAM.
  nandroot  bootcmd_mfg=bootz ${loadaddr} - ${fdt_addr};
            Boot a kernel/DTB loaded by SDP while mounting rootfs from NAND.
  normalreset  bootcmd_mfg=bmode normal; reset;
               Clear a retained SDP override before a watchdog reset.
  clearreset   bootcmd_mfg=mw.l 20d8040 0 2; reset;
               Directly clear both retained SRC boot registers, then reset.
  scrub     bootcmd_mfg=nand scrub -y 0 0x400000; reset;
            Clears the 4 MiB boot slot so Linux BBT cannot block kobs.

Usage:
  patch_uboot_env.py nandboot firmware/u-boot-dtb.imx firmware/u-boot-dtb-nandboot.imx
  patch_uboot_env.py scrub    boot/u-boot-dtb.imx     boot/u-boot-scrub.imx
"""
from __future__ import annotations

import sys
from pathlib import Path

KEY = b"bootcmd_mfg="
MODES = {
    "nandboot": b"bootcmd_mfg=run bootcmd;",
    "nandroot": b"bootcmd_mfg=bootz ${loadaddr} - ${fdt_addr};",
    "normalreset": b"bootcmd_mfg=bmode normal; reset;",
    "clearreset": b"bootcmd_mfg=mw.l 20d8040 0 2; reset;",
    "scrub": b"bootcmd_mfg=nand scrub -y 0 0x400000; reset;",
}


def patch(data: bytearray, new: bytes) -> None:
    i = data.find(KEY)
    if i < 0:
        raise SystemExit("bootcmd_mfg= not found")
    end = data.find(b"\x00", i)
    if end < 0:
        raise SystemExit("unterminated bootcmd_mfg")
    room = end - i
    if len(new) > room:
        raise SystemExit(f"replacement too long ({len(new)} > {room})")
    # CONFIG_EXTRA_ENV_SETTINGS is one packed sequence of NUL-terminated
    # key/value strings.  Adding a second NUL here terminates the *entire*
    # default environment, so every variable following bootcmd_mfg (including
    # panel, fdt_addr, bootargs, and bootcmd on the Prime) disappears at run
    # time.  Keep the original terminator in place and fill the unused value
    # bytes with shell whitespace instead.
    data[i : i + room] = new + b" " * (room - len(new))
    print(f"patched @{i}: {new!r}")


def main(argv: list[str]) -> None:
    if len(argv) != 4 or argv[1] not in MODES:
        raise SystemExit(__doc__)
    src, dst = Path(argv[2]), Path(argv[3])
    buf = bytearray(src.read_bytes())
    patch(buf, MODES[argv[1]])
    dst.write_bytes(buf)
    print(f"wrote {dst} ({len(buf)} bytes)")


if __name__ == "__main__":
    main(sys.argv)
