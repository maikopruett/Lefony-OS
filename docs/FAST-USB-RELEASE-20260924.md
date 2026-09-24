# Fast USB development release — September 24, 2026

OS candidate: [1.0.0+1790267071](https://github.com/maikopruett/Lefony-OS/releases/tag/build-20260924-1790267071).
This is a published, build-tested development candidate for HP Prime G2.
No physical calculator was flashed or used for throughput qualification.

## Behavior

LFB1 negotiates high-speed bulk endpoints without probing legacy devices with
unknown vendor requests. Chained DMA receives complete payloads into bounded
RAM before installation. Terminal SDK and browser clients use this transport
for app packages, bundled files, export/readback, and native OS capsules.
The browser Linux-recovery path queues four existing 64 KiB frames. The ROM
protocol itself is unchanged. Older firmware uses the legacy transfer path
for its first update; the new transport becomes available after booting this
release. USB staging does not eliminate NAND writes, hashing or readback time.

Explicit commit, signatures, file digests, cancellation and existing installer
safety boundaries remain in place. A failed bulk write is never automatically
replayed through the legacy path. Full-speed USB falls back to the old protocol.
See [the protocol and ownership rules](USB-BULK-PROTOCOL.md) and
[implementation plan](FAST-USB-TRANSFER-PLAN.md).

The 32 MiB staging region at `0x8B000000` is reserved through linker symbols,
not an ELF load segment. This preserves compatibility with the existing U-Boot
native loader. It does not add 32 MiB to the firmware download. The separate
48 MiB image region, app staging, boot handoff and framebuffer remain intact.

## Candidate identity and verification

| Artifact | SHA-256 |
| --- | --- |
| Physical native firmware | `bf8968c8b9525cb23dbef4dc2a8d610a989f2e5edec903791b2e57aefc975db4` |
| VM ELF | `4cf513bfa4116fd6662f169d1cbed94811a1e2c387b20a4c107c8668b90906e5` |
| Signed LFU1 capsule | `b6659c586b52fbd95920ef907c60323d227086227056cb6f495dbf9e52d6c67b` |
| OS corresponding sources | `700c6d13f19707b5a80a5fa6423b409505bf801e1742ec98f6891d40d41bd135` |

The release uses the existing release identity. Its base commit is
`91701e213d74918226b3692f570079c2c13d9000`; the archive contains the exact public
working tree and prepared physical sources used for the candidate. No unrelated
working changes were committed as part of this publication.

Verification commands and outcomes:

- `make test`: 1,941 passed; two optional private hardware-reference tests skipped.
- Physical and VM target builds with the existing release/app trust inputs passed.
- A clean rebuild from the archived prepared VM sources produced byte-identical
  ELF and binary outputs.
- `vm/native-suite.py --suite smoke`: USB stall, direct ELF, normal U-Boot boot
  and protocol checks passed using QEMU patchset r71.
- `vm/test-native-bulk.py`: legacy/chained CRC, 512-byte packet accumulation,
  early apply rejection, cancellation/stale token, short transfer and size bounds
  passed. QEMU models both high-speed packet progression and chained descriptors.
- Full Doom 0.2.2 bundled Freedoom installation and repeat verification passed.
  The full 28,795,076-byte WAD is included by the previously published app update.
- The frozen macOS SDK passed Notebook replay, signed app install/package
  readback, and byte-identical 256 KiB file import/export across four bulk sessions.
- Browser recovery validation checked all eight files, LFU1 signature, baseline,
  RAM layout and exit plan. All 16 published OS assets were downloaded and hashed;
  live website release discovery selected this version and verified its signature.
- `make check-public` and `git diff --check` passed before publication.

Detailed logs and hash inventories are retained locally under the ignored
`build/fast-usb-20260924/final/`. These are emulator/host results, not physical
USB bandwidth, electrical behavior, NAND endurance or power-loss qualification.

## Remaining hardware qualification

Measure RAM upload/download throughput on a physical G2, then measure file
installation and readback separately. Exercise disconnect, reset and power loss
at the documented boundaries on a recoverable test device. Verify cache/DMA
coherency and sustained writes under real NAND latency. The 35–45 MB/s RAM goal
is an engineering target; no claim is made that this release reaches it.

## Completed SDK and website rollout

[Developer downloads](https://lefony.com/#developers) and the public terminal
installer serve the refreshed macOS ARM64 and Linux x86-64 SDKs. The existing
SDK contract remains `0.2.0-dev`; SDK 1.0 and physical qualification are not
claimed. Existing September 16 installations can upgrade to a separate
September 24 directory; old SDK folders are retained.

| Artifact | SHA-256 |
| --- | --- |
| macOS SDK | `09cf5e726b99f799218b0a51ce3d4e412d6f91f966dbcfc22c64db596d7aac12` |
| Linux SDK | `ac791ebc5d35afca9bee42707ef3963c6e284767071d53c7311809605a47aa2f` |
| SDK source kit | `9f37980f5ab179a1b0fa2693b7b2b9d10a7ef8acaac0344fff60065c4ce64c8d` |

Both frozen SDKs passed Notebook replay and four actual bulk sessions: signed
app installation, package readback, named-file import and named-file export.
Every archived member was checked (1,936 macOS files; 5,518 Linux files). The
public macOS installer completed successfully and all 1,936 installed files
matched. Linux executables were tested under CPU emulation, not on a native
Linux host. Platform-independent Linux corresponding-source verification and
archiving ran on the macOS host using the unchanged source-packaging tool.

All seven new remote objects passed full R2 readback. All nine configured
downloads and the source kit passed complete public HTTPS checksum checks.
The live JS/CSS match the sealed fast-USB website client. Final Worker version:
`fd30c9f4-8659-460b-ac2c-3a7fb74fc9ba`. Website validation: 579 tests passed, one skipped, 67 browser
journeys passed, and build/lint/sealed Worker checks passed.

The final bucket inventory has 59 objects and 5,955,199,384 bytes,
within the reviewed 6 GiB operational release allowance. Historical objects are
retained; managed app quotas and signing identities remain unchanged.
