# Fast development USB: first physical bring-up gate

## Development installer bootstrap: 260909-022548-762b29

Physical test after the user installed this bootstrap: C0/4E returned
`{version:1, flags:1, capacity:8388608}`. The installer preflight passed,
uploaded all 2,103,184 bytes of SHA-256
`899167de2a0f65b10f61a202b26e07d2361d1f4ffc99139badc4c8f7ff153928`,
and passed device CRC verification. The handoff OUT request returned without
an error, but native USB disappeared and no ROM/recovery endpoint appeared
within 30 seconds. UUU and IOUSB checks confirmed no calculator endpoint.
The installer stopped before invoking the NAND writer; NAND/U-Boot untouched.
This narrows the current blocker to the native reset/recovery transition,
not full-image transport. Screen/power behavior still needs user observation.

Installer `[U] Update` selects the single-slot development workflow for an
unsigned recovery capsule; signed `.lfu` packages retain the existing A/B
workflow. Explicit UPDATE confirmation warns that mtd1 is overwritten without
A/B rollback and USB power must remain connected.

The development workflow preflights and snapshots the image, qualified
U-Boot baseline and Linux recovery assets before resetting anything. It
queries native C0/4E capabilities (`LDV1`, version 1, flag 1, capacity), uploads
the snapshot to RAM and checks CRC, then sends 40/4E with the same CRC in
wIndex:wValue. Firmware accepts only a Ready image and matching CRC and calls
the recovery routine only after successful status completion. A replacement
SETUP, bus reset or failed status descriptor cancels the pending handoff.
This is an unsigned local development protocol, not signature authentication.

The host waits at most 30 seconds for ROM/recovery enumeration. Failure stops
before any NAND write. On detection it runs the existing mtd1-only Linux
writer, compares the existing U-Boot against history, and checks image
readback on device and with host SHA-256. Boot/reset trouble after successful
verification is a warning, not a false failed-write report. The already
running firmware predates this command and needs one recovery installation.

70 host tests pass. Emulator test `/tmp/lfusb-_kqny89m` covers capabilities,
staging and cancellation before the handoff status ACK, as well as USB
enumeration and reconnect. **Physical native-to-ROM transition and end-to-end
persistent USB installation remain unqualified.** The command currently uses
the existing watchdog recovery routine; its prior physical failures are not
fixed merely by exposing a new USB command. Keep the original U-Boot.

## Physical full-image upload passed (2026-09-09 UTC)

Running build `260909-020239-0154b3` accepted a complete 2,103,184-byte
capsule over native CAFE:5052 USB. Device status returned Ready (2), equal
declared/received lengths, and Ion CRC32 `1e572733`. Uploaded artifact SHA-256:
`13d5cd66055b095e6b1370afb18a9c680cfb0b19e052a5b5e026f401b912e9a1`.
An explicit abort afterward returned Idle with length/received/CRC all zero.
No NAND write, reboot, recovery transition or U-Boot change was performed.
This qualifies full-image RAM reception, **not persistent USB updating**.

Candidate `260909-021750-309d07` adds bounded upload polling (at most 200
iterations with 10us delays per platform poll), to reduce UI-event-interval
latency between control-transfer phases. Physical throughput improvement is
not yet measured. Emulator enumeration, deferred address handling, 64 KiB
staging/CRC, abort and reconnect pass (`/tmp/lfusb-3msemlxj`).

Installer `[T] USB RAM test` uploads the selected recovery capsule with
progress, checks device CRC, then clears staging. It needs neither UUU nor
administrator access, and does not install or execute the uploaded image.
The CLI `prime_g2_usb_diag.py --stage IMAGE` displays progress on stderr and
leaves successful staging ready in RAM. Both reject malformed headers before
transfer and attempt to abort interrupted/rejected transfers without blindly
retrying a possibly consumed chunk. A disconnect may prevent cleanup; the
next BEGIN restarts at offset zero.

Persistent updating remains a separate gate: the current signed A/B path
requires a provisioned layout, while the working original U-Boot uses a
single development kernel slot. Reusing that slot must retain the verified
Linux NAND writer and readback checks, and needs a proven native-to-writer
handoff. Do not silently label RAM staging an installation or change U-Boot
to bypass this gate.

## Address-service timing candidate: 260909-020239-0154b3

IMG_1294.HEIC shows the preceding 127751 build completing all eight observed
status transfers (PH=5, DONE=8), with SET_ADDRESS(45) and ADDR=5A000000.
Configuration is still absent and the host has reset eight times. This proves
progress past the prior active-status stall, not successful enumeration.

The next hypothesis is delayed address application: Linux handles completion
in interrupt context, while Lefony normally services USB in its UI polling
loop. SET_ADDRESS now polls specifically for its status-IN completion directly
after queuing it, at most 2,000 iterations with a requested 10-us delay. It
uses the same checked completion handler and never applies an address without
a completion. Reset/new SETUP interrupts the wait; timeout falls back to normal
polling without forcing a reset or address. Real elapsed time depends on the
physical delay calibration; this is a bounded iteration count, not a hard
real-time 20-ms guarantee.

The diagnostics page adds WAIT (iterations in the last fast wait) and FAST
(successful status completions serviced there). All 15 rows fit on one screen.
This is a timing candidate requiring another physical snapshot, not a confirmed
diagnosis of the remaining failure. U-Boot and recovery remain unchanged.

## SET_ADDRESS fix: 260909-015559-127751

The user's photo IMG_1293.HEIC shows build 04973c receiving SET_ADDRESS(23):
REQ=00050017, RAW0=00170500, ADDR=2E000000, PH=4,
IN-TD=00008080, DONE=0. The address had already changed while the zero-length
status IN was still active. Prinux Linux applies the address in
`isr_setup_status_complete`, not when parsing SET_ADDRESS.

Lefony now validates the request, stores a pending address, and writes
DEVICEADDR only after a successful status-IN descriptor completion. Pending
state is canceled on replacement SETUP, bus reset, stall, shutdown, and fresh
initialization. Address zero is valid and is not used as the empty sentinel.
The full-page snapshot remains available. No U-Boot/recovery change is made.

The emulator regression withholds the status IN and checks that the old
address stays active, then acknowledges it and checks the new address. This
test fails against the archived previous 04973c image. It also exercises
replacement-SETUP cancellation and address zero. The socket host model needs
a polling interval before consuming the replacement request's response;
it does not automatically retire the old descriptor on SETUP delivery.
Physical macOS enumeration still needs confirmation with this candidate.

## Current candidate: 260909-015029-04973c

Settings → About → USB status now opens a single full-page diagnostic snapshot,
replacing the cycling pages described in the historical sections below.
OK/EXE captures a new snapshot; Back/Left closes it. The view stays frozen
between refreshes for phone photographs, while the USB event loop continues.
The page includes Build ID, flags/error, last request/phase/length, full
setup/completion/reset counts, CMD/STS/MODE/PORT, SETUP/PRIME/FLUSH/COMPLETE,
device address, endpoint-list address, both transfer descriptor tokens, and
the two raw words of the last captured SETUP packet. All numbers are hex.

The previous physical reading was F:0000002F E:00, R:00000000 P:3,
N:0008 C:0000 B:0008. This shows repeated attempts without completed control
transfers; the all-zero decoded request is suspicious, not proof of a cause.

This candidate cleans initialized queue-head memory to RAM before exposing
it to USB DMA. SETUP capture acknowledges EP0 and uses the USBCMD bit-13
setup tripwire, invalidates the queue-head cache before copying, retries up to
16 times if the controller replaces the packet, and reports error 0E on
exhaustion. It leaves NAND, U-Boot, and the paused recovery implementation
unchanged. Physical enumeration remains unverified.

Validation covers compilation, source/geometry contracts (all page text fits
320×222), and emulated physical-target enumeration, staging/CRC, abort,
reconnection and trace observation. The actual Settings page still needs
physical visual confirmation; the emulator input harness cannot navigate
this physical target's GPIO keyboard. A passing transfer test does not model
all physical cache/DMA races or demonstrate tripwire race injection coverage.

The immediate goal is host-driven OS revisions without manually entering ROM
recovery for every build. Production A/B migration is not a prerequisite for
qualifying native USB transport. It remains a prerequisite for claiming safe
automatic rollback. Do not change the working original Prinux U-Boot merely
to test USB enumeration or RAM staging.

The current physical blocker is native enumeration. The running calculator
has not exposed CAFE:5052 to macOS in the current sessions. The existing
protocol can stage a capsule in RAM with a length/CRC check; staging does not
execute it or program NAND. The signed update path still depends on recovery
handoff, which is not physically working. We have not bypassed that gate.

## Build 260909-013421-ec4c93

- Repeated Ion USB enable/DFU calls preserve an active USB controller, its
  address, endpoint transactions, and update staging instead of resetting it.
- The first USB failure step is retained until a fresh initialization.
- Settings → About → USB status displays `F:xxxxxxxx E:xx` even when USB
  cannot enumerate. Select that row and press OK to refresh; this is read-only.
- The recovery implementation and U-Boot are unchanged.

Flags are hexadecimal: 01 clock, 02 PHY, 04 controller, 08 bus reset observed,
10 configured, 20 high speed, 80000000 error. For example, F:00000007 E:00
means initialization reached a running controller but no bus reset has been
observed; it does not prove that a cable is attached. E identifies the first
failed step from `usb_diagnostics.cpp`: 01 PLL lock; 02–05 PHY reset/gating;
06 controller reset; 07 device mode; later steps are endpoint/transfer faults.
The configured flag is revoked on disconnect; bus-reset is historical.

After installation, boot normally with the cable connected, open USB status,
press OK and record both fields along with whether the installer detects
native Lefony. Do not use the recovery option for this test.

The test `vm/test-prime-dev-usb.py` runs this physical-target capsule in QEMU:
enumeration, 64 KiB RAM staging and CRC, abort, disconnect and re-enumeration.
It neither executes uploaded code nor writes NAND, and is not physical USB
qualification. Physical enumeration and a matching host transfer must pass
before implementing the next execution/handoff stage.

## Enumeration trace: build 260909-014109-7549d5

Physical observation on the preceding build was `F:0000002F E:00`: clocks,
PHY, controller, historical bus reset and high speed, but not configured.
macOS did not retain a native Lefony device. This narrows the investigation
to enumeration; it does not establish which control transaction failed.

USB status now cycles three read-only pages on OK/EXE/Right:

1. `F:xxxxxxxx E:xx`: the original flags and first error.
2. `R:xxxxxxxx P:x`: the last SETUP request (request type, request code,
   then 16-bit value, all hexadecimal) and last transfer phase.
3. `N:xxxx C:xxxx B:xxxx`: setup count, status-completion count, and bus-reset
   count (low 16 bits, hexadecimal). These are lifetime counts since USB init.

For example `R:80060100` is GET_DESCRIPTOR(Device). Phases: 0 no request,
1 setup copied, 2 IN data queued, 3 OUT status queued (IN data completed),
4 IN status queued, 5 status completion observed, 6 stall requested,
7 descriptor transfer error, 8 OUT data queued. An error flag still takes
precedence over a completion count; those counters are observations, not a
claim of successful enumeration.

The last request and phase survive host bus resets so repeated enumeration
attempts cannot erase the diagnostic evidence. B changing therefore matters
when interpreting a historical P value. Fresh USB initialization clears all
trace fields. The read-only vendor request C0/4D returns eight little-endian
32-bit words: magic 0x4c465554, schema 1, request, phase, setup count,
completion count, reset count, and last requested length. Reading this trace
does not replace the last request or increment its counters.

Send all three on-screen pages after the failed enumeration attempt. No
recovery change, NAND write capability, or new bootloader is introduced.
