# Doom startup performance — September 24, 2026

The published Doom 0.2.2 app could spend several minutes displaying a black
screen before gameplay. A user confirmed that the game eventually appeared.
A read-only physical observation recorded 86,843,392 NAND-read bytes during
175.9 seconds of that launch, with 21.5 seconds inside NAND reads, no new read
failures and no page programs. This was only part of the launch, not its total
duration or a complete CPU profile.

## Local deployment

Firmware `1.0.0+1790281237` and Doom 0.2.3 address two sources of repeated work:

- A privileged 64-slot cache holds roughly 8 MiB of verified snapshot content.
  A chunk becomes readable only after its complete SHA-256 matches the verified
  file index. Hits return those same RAM bytes. Misses still read and verify in
  bounded 2 KiB steps. Incomplete fills cannot be evicted, and close/failure
  discards the reader's entries. Separate opens cannot reuse another reader's
  content. Root, signature, quota and mutation verification remain unchanged.
- Cached reads and snapshot seek/stat operations can complete entirely in RAM.
  The existing submit/token/poll protocol is unchanged. The newlib adapter polls
  once before yielding; pending operations still yield to input and storage.
  The OS continues to preempt CPU work. There is no busy wait or NAND access
  inside the immediate-completion path.

Doom also presents a loading message before engine initialization. The local
recipe builds 0.2.3. The OS and app-store releases are now published; existing
SDK binary downloads are separate artifacts.

## Measurement interface

Vendor IN request `0x57`, with zero value/index and length 64, returns sixteen
little-endian words: magic `0x5452464c`, schema 1, size 64, flags, foreground
start milliseconds, current milliseconds, first pixel milliseconds, elapsed
milliseconds to first pixels, pixel-frame count, surface-frame count, heap
setup milliseconds, last fault, exit status and three reserved zero words.
Flags are loaded (1), foreground (2), public foreground (4) and exited (8).
Timing resets on unload/new launch. This is read-only: no launch, input,
memory access, counter reset or storage mutation is provided. Malformed queries
and OUT requests are rejected. It measures foreground entry to the first public
pixel presentation, excluding package loading and signature verification.

```sh
.venv/bin/python scripts/prime_g2_app_runtime.py
```

## Validation

Both firmware targets compile with the existing production trust roots. The
physical image retains about 10 MiB of OS heap after adding the cache. Nineteen
focused host tests pass, including sanitizer-backed corruption, eviction,
incomplete fills, owner isolation, replacement, media failure, close/reopen and
one-shot completion tests. Existing storage/session/archive tests also pass.

The signed 0.2.3 package starts in **2,184 ms and 2,468 ms** on two cold
synthetic emulator boots with matching firmware. The normal-input gameplay
harness passes movement, firing, menus, save/reload, cold saved-state recovery
and clean exit. A separate suite exercises the updated C runtime. Emulator
timings are not physical performance claims.

Reproduction uses `vm/test-sdk-doom-startup.py` with `--seed-project`,
`--package`, `--firmware`, `--public-key` and a new `--output` directory. It
clones synthetic media, queries the normal read-only USB timing record and
captures frames without debugger pauses. Use `vm/test-sdk-doom-gameplay.py`
for the separate gameplay/save workload. Host coverage is in
`tests/test_app_read_cache.py` and `tests/test_app_runtime_report.py`.

Private evidence and backups remain under ignored
`build/doom-startup-fix-20260924/`. Physical power-loss durability and endurance
are not established by these checks.

## Physical installation

The authorized local Prime G2 update completed full native-writer byte readback
verification in 4.81 seconds and rebooted to `1.0.0+1790281237`. The user confirmed
the Home screen. Doom 0.2.3 installed with exact signed-package readback. A
double-read firmware backup and verified package/private/named-file backups
preceded installation. All four named files (28,821,980 bytes total) and the
empty private-data snapshot matched after upgrade; the retained previous app
pair remains available. Publication followed separately, as recorded below.

- Signed firmware payload SHA-256:
  `90a691204799cd5d99199198e9f95aefd5ac76f3106f69fde355a8d494c449a8`.
- Signed Doom package SHA-256:
  `9a72ea4a3e76d44b3dab8714448d1a3d034c1176fe6ff40d25e8f7df9c65a927`.

The first physical launch reached the first game frame in **15,229 ms**, with
784 ms of heap preparation and no app fault. The user confirmed that the game
appeared quickly. The read-only interval from Home through that frame recorded
22,284,288 NAND-read bytes, 5.515 seconds in NAND reads, zero read failures and
zero NAND programs. A later read-only snapshot recorded another launch at
**15,114 ms**, with 137 pixel frames and no fault. The byte interval includes
package loading, while the
15,229 ms timer starts at foreground entry. These are two observed launches,
not a cold-power-cycle distribution. Startup is substantially faster than the prior
minutes-long wait, but does not meet a literal near-instant launch target.

Final checks used `make firmware`, `make firmware-vm`,
`vm/test-native-comprehensive.sh smoke`, `vm/test-native-bulk.py`,
`vm/test-sdk-c.py`, `vm/test-sdk-doom-gameplay.py`,
`vm/test-sdk-doom-startup.py`, the focused host tests above, and
`make check-public`. The normal-input gameplay and save tests were emulator
tests; physical acceptance here covers successful launch and continued pixel
presentation, not a full manual gameplay/save matrix.


## Public OS release

Firmware `1.0.0+1790281237` is published as the
[development release](https://github.com/maikopruett/Lefony-OS/releases/tag/build-20260924-1790281237).
All 16 public assets passed independent length/hash readback. The signed
capsule and firmware match the locally installed artifacts exactly. Pinned
browser recovery signature, baseline, RAM layout and exit-plan checks pass.
The complete host suite passed 1,959 tests with two expected private-fixture
skips. The release includes the audited working-tree and prepared firmware
sources; the tag identifies their base commit. No Git branch was advanced.

Doom 0.2.3 is also [published in the app store](https://lefony.com/#apps/doom-proof).
The public signed package matches the locally installed bytes exactly. Source
rebuild, bundled-data gameplay replay and full public bundle/source/data
verification pass; see the [app release record](DOOM-STORE-RELEASE.md).
