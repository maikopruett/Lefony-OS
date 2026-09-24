# Fast USB installation plan

Scope: native app packages and bundled data, terminal SDK, browser installer,
and native OS installation/update. Preserve the existing signed commit,
backup, geometry, cancellation and readback boundaries.

1. Add a versioned, capability-negotiated bulk transport. Retain EP0 commands
   for control and all legacy clients. Use chained ChipIdea DMA descriptors
   and a bounded, kernel-only RAM staging area; never accept host addresses.
2. Receive payloads before filesystem installation. Feed staged app files
   through the existing authenticated file session and atomic commit path.
   Keep received bytes distinct from installed/verified bytes.
3. Add bounded large host transfers in the SDK and browser, and use the same
   transport for native OS capsules. Never fall back or replay a write after
   a bulk transfer has started. Preserve legacy fallback on old firmware.
4. Test descriptor chaining in QEMU, interruption/reset/cancellation, malformed
   sessions, digest rejection, commit ambiguity, and old/new host compatibility.
   Build physical and VM targets and run the applicable host/emulator suites.
5. Publish the tested OS development candidate, refreshed SDK artifacts and
   corresponding sources, and the website installer. Verify public bytes and
   signatures and document remaining physical qualification.

The first update from older firmware still uses its existing transport. The
immutable i.MX ROM downloader cannot acquire a new protocol; first installation
must retain its supported recovery stages. Existing Linux recovery bulk paths
must be assessed separately from native firmware transfers.

USB 2.0 high-speed signaling is 480 Mbit/s. Useful transfer rate is lower; a
35–45 MB/s RAM-transfer goal is an engineering target, not a measured Prime
result. Flash writes, hashing and readback have separate ceilings. Emulator
timings establish regressions and protocol behavior, not physical USB speed.

Implementation and release evidence: ignored `build/fast-usb-20260924/`.
No physical flash is part of this publication task.

## Implementation checkpoint

Firmware, terminal SDK and browser now implement upload and readback with LFB1.
The QEMU model supports chained descriptors and partial bulk packets (r71).
Full bundled Doom installation and repeat verification passed in the emulator.
Protocol details and memory ownership are in [USB-BULK-PROTOCOL.md](USB-BULK-PROTOCOL.md).
Release publication follows candidate build, source correspondence and public
artifact verification; it does not qualify physical throughput.
