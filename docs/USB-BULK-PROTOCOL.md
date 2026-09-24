# Native bulk transfers (LFB1)

This additive transport moves native OS capsules, signed app packages and app
files over USB high-speed bulk endpoints. Existing EP0 operations, storage
formats, signatures, quotas and explicit commit boundaries are unchanged.
Older hosts still work. Updated hosts select legacy transfers when the standard
configuration descriptor does not advertise the LFB1 endpoints at high speed.
They must never fall back after starting a bulk transfer.

Interface 0 remains vendor class `ff/4d/47`. Configuration 1 now advertises
endpoint `01` OUT and `81` IN (bulk, 512 bytes at high speed; 64 at full speed).
LFB1 requires high speed. EP0 retains 64-byte packets and its 512-byte control
buffer. The i.MX6UL device-streaming erratum workaround remains enabled.

## Staging and ownership

The linker reserves 32 MiB at `0x8b000000` for privileged, non-executable USB
file staging. This is separate from the image heap/stack, native-app staging,
boot handoff, framebuffer and the existing 8 MiB OS recovery buffer. It is
reserved by linker symbols without an ELF load segment, so existing bootelf
loaders remain compatible; it adds no bytes to downloads. App package transfers use the existing
bounded package buffer. Hosts cannot supply physical or virtual addresses.

The controller follows a prebuilt chain of 16 KiB dTDs. Software cleans the
source/descriptor caches before priming, invalidates DMA writeback before
inspection and bounds descriptor inspection and endpoint flushing. EP0 cache
maintenance must not write back a stale bulk queue-head overlay. Reset,
disconnect, short packets, descriptor errors and stalled reception cancel the
uncommitted transfer. Buffers cannot be reused if flushing fails.

App files enter the existing file session in bounded 2 KiB steps, retaining
SHA-256, generation/schema checks, quota checks and atomic root commit. Receipt
in RAM is not a saved file. The host must issue the existing file COMMIT only
after application completes. Downloads stage authenticated reads before bulk
IN; the host still checks the returned digest. Foreground app launch is blocked
while bulk DMA owns an app buffer.

## Control records

All records are little-endian uint32 values. Vendor IN `58` returns 64 bytes:

| Word | Meaning |
| --- | --- |
| 0–1 | Magic `3142464c`, version 1 |
| 2 | State: idle 0, transferring 1, received 2, applying/preparing 3, ready 4, failed 5 |
| 3–5 | Monotonic bulk sequence, target, exact byte length |
| 6–8 | USB bytes transferred, bytes applied/prepared, error |
| 9–13 | Capacity 33554432, host chunk 262144, OUT endpoint 1, IN endpoint 1, high-speed flag 1 |
| 14–15 | Reserved zero |

Vendor OUT `59` begins a transfer with six words: magic, version, target,
length, existing file-session sequence (otherwise zero), reserved zero.

| Target | Existing operation that must be prepared first |
| --- | --- |
| 1 | OS capsule upload: EP0 `44`, exact length and offset zero |
| 2 | App package upload: EP0 `63`, exact length and offset zero |
| 3 | Named-file import: EP0 `71`, writable import at offset zero |
| 4 | Named-file export: EP0 `71`, readable export at offset zero |
| 5 | Package readback: EP0 `6a`, completed exact package snapshot |

Upload targets receive the complete payload before OUT `5a` requests application.
Its argument is the bulk sequence in `wIndex:wValue`; application starts only
after successful status acknowledgement. Existing capsule finish/CRC, app
install/signature and file commit/digest commands remain necessary afterward.
Download targets prepare their data and enter transferring state automatically;
the host waits for that state before bulk IN and verifies ready afterward.

OUT `5b` cancels the matching bulk sequence. It never commits. Failures are
reported without replay. A 30-second no-progress limit bounds abandoned RAM
reception; hosts bound installation/preparation separately and permit explicit
cancellation before commit. Sequence rollover requires a device restart.

## Performance and qualification

The SDK uses 256 KiB libusb transfers. The browser queues up to four 256 KiB
transfers. Browser recovery Linux retains its existing protocol and 64 KiB
frames with up to four queued writes. The immutable ROM downloader is unchanged.
An update from older native firmware necessarily uses its old transport once.

`vm/test-native-bulk.py` exercises DMA chaining, legacy transfers, packet
accumulation, exact CRC, cancellation, stale tokens, early apply, short packets
and capacity bounds. Host tests cover digest rejection and preservation of
committed data. Emulator timing is not physical bandwidth qualification.

The engineering target is 35–45 MB/s to RAM, below USB 2.0's 480 Mbit/s signaling
rate; actual Prime USB, hashing and flash throughput still require measurement.
See the [implementation plan](FAST-USB-TRANSFER-PLAN.md).

The September 24 physical Doom trial exposed a host timeout: the published SDK
cancelled a still-progressing 28,795,076-byte import after ten minutes, at
28,545,792 bytes, before commit. The source SDK now allows file application up
to 30 minutes, bounded by a two-minute no-progress watchdog. Tests cover slow
progress beyond ten minutes, stalls, the absolute limit, and unchanged commit
boundaries. This host correction is not included in the earlier frozen SDK
archives. The website source uses the same bounds and reports actual device-side
application progress separately from USB receipt. Raw device evidence remains
in ignored `build/physical-doom-20260924/`.

The authorized physical retry committed Doom 0.2.2's WAD with the expected
SHA-256. The whole RAM-staging interval was 1.058 seconds (about 27.2 MB/s),
followed by 605.176 seconds of file application and 94.325 seconds to finish
and confirm the commit. Including preflight, the successful WAD retry took
735.079 seconds. These are one calculator's measured host intervals, not flash
hardware limits, an old/new end-to-end comparison, or a cold-start/gameplay test.
The bulk/source SDK checks passed 42 tests. No firmware was replaced in this
trial, and no physical throughput qualification is inferred for OS updates.

DMA layouts and endpoint fields were checked against the upstream Linux
[ChipIdea definitions](https://github.com/torvalds/linux/blob/master/drivers/usb/chipidea/udc.h)
and [device driver](https://github.com/torvalds/linux/blob/master/drivers/usb/chipidea/udc.c).
