# Full installer and software recovery candidate

The website's local protocol 2 candidate explicitly installs the bootloader,
OS and device tree. `scripts/package_lefony_release.py --full-install`
requires `--recovery-dir` and emits the `boot-os-dtb` development contract.
Without that flag, recovery packages retain the existing OS-only contract.
The companion's provisioning and A/B requirements are unchanged.

During physical preparation, the original RAM-only recovery handoff disconnected
USB without reaching ROM mode. Rear RESET returned the original installation.
Two independent reads of the existing OS matched SHA-256
`bc51443e27728aeb377c2d18ddc6ae1938b0e556497ac2935c1d638307689f86`.
These are OS-only captures, not whole-NAND or application backups.

`Watchdog::rebootToROMRecovery` incorrectly kept WCR bit 4 high while describing
it as WDA. The corrected sequence keeps WDA (bit 5) high and clears SRS
(bit 4), matching the internal-reset branch of the
[Linux i.MX watchdog driver](https://github.com/torvalds/linux/blob/master/drivers/watchdog/imx2_wdt.c).
The ROM override registers and NAND layout do not change.

The physical candidate capsule SHA-256 is
`34990e3a67931a969b319a6a6e4e183865c2699b7b2c9730502191ff89c2de55`.
Physical and emulator target compilation passed. The ROM recovery model test
uses the exact corrected WCR value `0x24` and passes its positive/negative
controls, reset-retention and SDP transfer checks with synthetic NAND untouched.
The release/recovery/USB host tests pass (42 tests), and `make check-public`
passes. Model success does not establish physical reset or cold-boot behavior.

The physical native writer installed that capsule and reported complete
byte-for-byte verification (2,105,488 bytes, CRC32 193453922). The calculator
then reappeared as native Lefony. The local build reports version `1.0.0+0`;
it is a diagnostic candidate, not a versioned release.

A subsequent RAM-verified request using the corrected recovery code again
disconnected USB without exposing a ROM or recovery endpoint within 35 seconds.
The bit correction is therefore insufficient to qualify physical software
recovery. A physical RESET is required before further host commands can run.
No full-NAND erase or bootloader write was performed. The original OS capture
and installation receipts remain private under ignored build output.

Website validation passed 624 host tests (one skipped), all 69 mocked browser
tests, four companion tests, build and lint; desktop/mobile review screenshots
were inspected. Initial concurrent host tests timed out; a bounded two-worker
run passed. The first browser-only run had a permission-prompt timeout; the
complete browser suite subsequently passed. No full-NAND erase or full browser
installation has been physically qualified, and these changes are unpublished.

The comprehensive emulator smoke command initially failed its protocol case
without an assertion diagnostic. That case passed with shell tracing, followed
by a successful complete smoke rerun (USB stall, direct ELF, boot and protocol).
The initial intermittent failure remains recorded rather than treated as a
proven regression or erased from the qualification history.

## Follow-up: physical reset-state capture

After the user restored native USB with rear RESET, a read-only diagnostic
was added at GET `0x4E`, value 1, index 0, length 64. Its `LDR1`/version 1
response contains fixed SRC, clock, watchdog and USB/display registers. The
existing value-0 capability response and CRC-gated OUT handoff are preserved.
There is no arbitrary register interface or write operation in this diagnostic.

The captured native state has SRC SCR `0xa0480538`, GPR9/GPR10 zero, CCM CCDR
`0x00020000`, CCGR3 `0xffffffff`, WDOG1 WCR `0x30`, WRSR `1` and WMCR zero.
The ordinary post-install software reset succeeds with the watchdog disabled.
The shared-reset candidate therefore uses the same immediate WCR-zero reset
for normal boot and ROM entry; it no longer arms a half-second watchdog as
part of the recovery request. This is a diagnostic change, not a qualified fix.

Candidate SHA-256
`e1bf420be6a48eb1646e15463f9792f12effaae585acc3ff8418e375b299faed`
was installed with full native byte verification and rebooted into Lefony.
The subsequent CRC-verified RAM handoff again lost USB without exposing SDP
within 60 seconds. UUU enumeration and the native IOHID reader independently
found no ROM device. This rules out newly enabling WDE as a sufficient
explanation; the remaining hardware failure is unresolved. NAND bootloader
and full-device contents have not been erased. The installed diagnostic build
still reports `1.0.0+0`; it is not a published release.

The new `vm/test-native-rom-handoff.py --elf <candidate.elf>` exercises the
compiled physical firmware through USB enumeration, diagnostic read, RAM
staging and the real request handler, then requires ROM identity `15a2:0080`
and retained override values. It passes for this physical ELF in the model.
This is stronger code-path coverage than directly writing watchdog registers
through QTest, but still does not reproduce the physical failure. The model's
ECC-write counter resets during handoff, so the test reports those counters
without claiming they establish absence of NAND writes across reset.

Both target builds and 43 focused host tests pass, as does the public-tree
check. The compiled USB handoff test also passes for the VM ELF, and the final
comprehensive smoke run passes all four cases. Physical progress requires
restoring USB after the failed handoff.

## Watchdog timeout and physical control, 2026-09-25

The NXP i.MX6ULL Reference Manual, Rev. 1 (11/2017), section 8.4.7,
Table 8-6 specifies that `PERSIST_OVERRIDE_SBMR1` is valid only after a
watchdog **timeout** reset. Immediate SRS reset is a different cause.
Sections 59.7.1–59.7.3 define active-low SRS/WDA, WT, WDE and WRSR.
The manual's SRC_SBMR2 definition (51.7.5) exposes `DIR_BT_DIS` at bit 3:
the physical value `0x02000001` has this bit clear, ruling out that fuse
as the reason for override rejection. No fuses were modified.

The CRC-gated OUT `0x4F` diagnostic saves, writes, reads and restores only
GPR9/GPR10; GET `0x4E`, value 2 returns its fixed `LDR2` report. On the
calculator it read back `0x20`/`0x10000000`, then restored both to zero.
The reset snapshot remained unchanged. Capsule SHA-256:
`48a45695864146684508d8e70cd3310aa703e72a77a41f20c9344e8c12cd2d3d`.

Recovery now programs a two-second timeout with WDA/SRS inactive, services
it once, masks interrupts and spins awake without feeding it again. Capsule
`b3ec52dabd6e7915d4dfbd05c034dd7bac54c052f933d6602e21af6dd87e9579`
installed with full native readback verification but again produced a black
screen and no USB endpoint for 60 seconds. This is not a qualified fix.
The user restored native USB using rear RESET.

A separate CRC-gated OUT `0x5E` control requires zero GPR9/GPR10 and uses
exactly the same timeout routine without changing the boot source. With
capsule `590175d7d3f3cdc4003a21e0a8ae9bcd80e0f7fb593bf602571bbb6a0fb405f5`,
it returned to native Lefony USB in 25.9 seconds. WRSR changed from software
reset (`1`) to timeout (`2`), proving the timeout/reset path works physically.
The remaining failure is associated with the ROM recovery path. Private
installation receipts and control observations are retained under `build/`.

QEMU r72 fixes three false assumptions: SRS cannot activate the ROM override,
WT=0 is a half-second timer rather than an immediate reset, and write-once
WCR fields retain their own bits rather than reading WICR. Firmware built
for the VM previously failed the real timeout handoff because the model
cleared its already-enabled WDE bit. It passes with r72. Both compiled
physical and VM firmware pass the normal-source timeout control; the ROM
suite now includes an immediate-SRS negative control. The RAM-only stub and
other ROM-entry fixtures use real timeouts. QEMU still does not establish
physical reset-domain or electrical parity.

Validation at this point: both firmware builds, r72 QEMU build, 55 focused
host tests, ROM recovery tests and comprehensive smoke pass. The optional
`vm/test-prime-g2-nand-rom-boot.py` could not run because its private exact
NAND fixture is absent. No full-NAND erase or bootloader write has occurred.

The next candidate stops LCDIF through `Display::shutdown` (matching U-Boot's
reset preparation) and detaches the native USB gadget through its owning driver
before the timeout. Both stop waits are bounded. Capsule SHA-256:
`2b25950dd8c08f19765b7009e7d9f142191043c49ab4030a4de49384c107cc97`.
Both targets build, compiled physical/VM ROM handoff tests pass in r72, and
all four comprehensive smoke cases pass. The focused host set now passes
65 tests. ROM SDP DDR availability and self-refresh controls also pass.
These results do not establish physical ROM entry.

The quiesced candidate also installed with full native readback verification,
rebooted normally, then lost USB on the CRC-verified recovery request. Neither
UUU nor the macOS USB inventory found a ROM endpoint within 60 seconds.
Stopping the display/gadget is therefore insufficient. A cable-only reconnect
was requested to distinguish ROM USB re-enumeration from an execution hang;
that physical check has not yet been confirmed. The calculator is currently
unreachable over USB at the end of that attempt, with NAND bootloader and
application data preserved.

## PHY shutdown control and remaining physical failure

Native USB subsequently returned with WRSR `0x10` (power-on/reset status).
The user's exact cable/reset action was not confirmed, so this observation
does not establish the result of the cable-only test.

The next candidate adds `USBDiagnostics::shutdownForROM`, following the
power-down portion of Linux's `mxs_phy_shutdown`: clear wake/automatic-power
bits, power down the PHY blocks, and gate the PHY clock. Shared PLLs and
supplies remain under their existing owners. Candidate capsule SHA-256:
`2267d64e705b3738e68af49fdc191d5aabd8764c3ba6d139b4d713c2b5ac2f3b`
(2,105,520 bytes). It installed with native byte-for-byte verification.

The normal-source control using this exact preparation returned to native
USB in about 29.5 seconds. A subsequent read recorded WRSR `2`, confirming
a watchdog timeout. The first read attempted during USB enumeration could
not open the device; a later read-only retry succeeded. The ROM recovery
request then disconnected native USB and exposed no recognized endpoint
through the full 60-second observation. PHY shutdown is therefore also
insufficient; software ROM entry remains unresolved. No whole-NAND erase
or bootloader write has been performed.

Both target builds pass. The real compiled physical and VM firmware each
pass ROM-entry and normal-source control tests in r72, including assertions
that LCDIF and USB RUN are clear, PHY PWD is all ones, and PHY automatic
power/wake bits are clear before reset. All four comprehensive smoke cases,
65 focused host tests and the public-tree check pass after this change.
The full host suite passed 1,980 tests with two skips before the final PHY
shutdown addition; it was not rerun in full after that addition. The optional
exact-NAND fixture test remains unavailable as described above.

These controls establish that the physical reset mechanism works and that
the override registers accept the requested values before reset. They do
not establish where ROM execution stops, whether it selects UART, or whether
USB enumeration fails inside ROM. An emulator pass cannot resolve those
alternatives. Full blank-device website installation remains unqualified.

Reproduction commands for the open model (no private NAND required):

```sh
./vm/build-prime-g2-qemu.sh
./scripts/build_prime_g2_rom_recovery_stub.sh
.venv/bin/python vm/test-prime-g2-rom-recovery.py
.venv/bin/python vm/test-native-rom-handoff.py --elf dist/lefony-os-prime-g2-native.elf
.venv/bin/python vm/test-native-rom-handoff.py --elf dist/lefony-os-prime-g2-vm-native.elf
.venv/bin/python vm/test-native-rom-handoff.py --elf dist/lefony-os-prime-g2-vm-native.elf --reset-control
.venv/bin/python vm/test-prime-g2-ddr-usb.py
./vm/test-native-comprehensive.sh smoke
```

## Read-only ROM investigation and correction of the timeout claim

After the user reported Lefony running again, native USB responded and WRSR
read `0x10`. The exact cable/reset action was still unconfirmed. No further
physical SDP request was issued during the following investigation.

GET `0x5F` now provides fixed 64-byte packets from the first 92 KiB of boot
ROM. It cannot read arbitrary addresses. `System::readBootROM` temporarily
maps a privileged read-only, non-cacheable, execute-never alias with interrupts
masked, then removes it and restores the interrupt state. The null guard
remains unmapped. Tests use synthetic ROM bytes, with no vendor ROM fixture.

The initial diagnostic used the manual's 96 KiB ROM window. On this device,
reading at offset `0x17000` caused a synchronous external abort; the diagnostic
USB handler remained available. The host's initial capture was incomplete.
The already-tested normal-source timeout control restored ordinary operation
without a manual reset. Two subsequent captures limited to 92 KiB were
byte-identical, SHA-256
`1727a0f46dbde555b583e9a138ae359389974b7be4369ffd4a252a8730f7e59b`.
This matches the i.MX6ULL ROM fingerprint documented by the
[USB armory project](https://github.com/usbarmory/usbarmory/wiki/Internal-Boot-ROM-%28Mk-II%29).
Captures and disassembly stay private in ignored build output.

The ROM's override-selection code checks the SRC watchdog source bit
`SRC_SRSR[4]`, GPR10's override-enable bit, and the disable fuse. It does not
check the timeout-versus-SRS distinction in WDOG WRSR. This **supersedes the
r72 timeout-only model claim above**: the manual's timeout wording did not
justify asserting that an immediate watchdog SRS could not select recovery
on this ROM. r73 removes that invented restriction while retaining the real
WCR write-once and half-second timer fixes. A WDOG3-only source (bit 7)
is insufficient; the model and tests now reflect that distinction. The
negative boot-source control uses the known NAND value `0x893`, rather than
assuming reserved value `0x21` differs from reserved value `0x20`.

The production-source handoff still uses the physically tested timeout
sequence. Static inspection of the ROM establishes its selection condition,
not the execution point at which the physical recovery attempt failed.
It does not qualify SDP entry or blank-NAND installation.

The bounded diagnostic capsule is
`357491e5c550e7cdf1e561f2b6bb3390b40339694301d55e5e472ef3af1e7562`
(2,105,520 bytes). The native installer reports full byte verification before
its ordinary reboot. Both firmware targets build and pass the synthetic ROM
read test, including out-of-range request rejection, stall recovery and MMU
mapping restoration. The focused host set passes 55 tests. Full-suite results
recorded above precede this diagnostic addition.

The bounded diagnostic also passes on the physical calculator: its first and
last readable packets match the independent capture, offset `0x17000` is
rejected with a USB stall, and a valid read immediately afterward succeeds.
Native reset diagnostics still respond. The r73 ROM suite, compiled physical
ROM handoff, compiled VM normal-source control and all four comprehensive
smoke cases pass. The calculator remains in Lefony; the root cause of failed
physical SDP entry is not established.
