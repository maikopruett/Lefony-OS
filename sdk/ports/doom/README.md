# Doom port qualification inputs

This directory pins the program/data and contains the public-API platform
adapter for the SDK 1.0 proving app. The published 0.2.3 package passes E1M1
gameplay, save/reload, cold saved-state restoration and clean quit in the ARM
emulator using normal keys and public APIs. The port is not release qualified;
see the current evidence and limits below.

- Engine: [doomgeneric](https://github.com/ozkl/doomgeneric/tree/dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284),
  revision `dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284`.
- Game data: [Freedoom 0.13.0](https://github.com/freedoom/freedoom/releases/tag/v0.13.0),
  Phase 1, the unmodified `freedoom1.wad` in the official release archive.
  The selected workload starts at E1M1 and must exercise gameplay, menus,
  held keys/combinations, saving/loading and OS-owned Home/exit.
- Resolution: 320 × 200 RGB565 pixels centered on the 320 × 240 panel, copied
  through public presentation. Physical rendering/performance are unqualified.

The older 0.2.2 app could take several minutes to start on physical NAND. Its adapter
clears the display before loading, so this wait looks like a black screen;
Home still returns to Lefony. The published 0.2.3 update presents a loading
message and uses the updated foreground runtime. Matching firmware caches
verified snapshot content and completes cached reads without filesystem work.
See [startup measurements and qualification](../../../docs/DOOM-STARTUP-PERFORMANCE.md).
With firmware `1.0.0+1790281237`, two physical launches reached the first game
frame in 15.114–15.229 seconds. Both OS and app updates are published.

A September 24 read-only USB observation recorded 86,843,392 bytes of NAND
reads over a 175.9-second portion of a physical launch, with no new read
failures or page programs; the user subsequently confirmed gameplay appeared.
That window is not a complete launch-time measurement. Reads spent 21.5 seconds
inside the NAND read operation. The snapshot reader verifies an entire roughly
128 KiB chunk whenever the requested chunk changes, including revisits, while
the libc interface submits reads of at most 2 KiB through the foreground
scheduler. Doom's random WAD access therefore incurs repeated verification and
many file-service round trips. The remaining time is not separately profiled.
The new cache retains the authenticated bytes themselves, rather than
skipping verification on later reads from NAND. Its first-frame measurements
do not include package signature verification before foreground entry.

[source.json](source.json) records the exact engine files and the 80 portable
translation units selected from its upstream Makefile, excluding the X11
platform adapter. [assets.json](assets.json) records the release archive, WAD,
license and credit hashes. The measured WAD is **28,795,076 bytes**, making
streaming storage a concrete requirement. It cannot become an embedded ABI 1
resource or fit the legacy private byte store.

## Maintainer reproduction

From the OS checkout:

```sh
.venv/bin/python scripts/fetch_sdk_doom.py
.venv/bin/python scripts/build_sdk_newlib.py
.venv/bin/python scripts/probe_sdk_doom.py
```

The fetch command preserves an existing modified checkout or asset and fails
instead of replacing it. `--offline` verifies already acquired inputs without
network access. `--directory PATH` selects an input cache; pass its
`doomgeneric` subdirectory as `probe_sdk_doom.py --source PATH` when using a
nondefault location. Builds and downloaded WAD/source files stay under ignored
`build/` by default. The compile probe produces a relocatable ARM engine object
and a report of remaining symbols, without successful dummy platform hooks.
It also emits `doom-source.lfsrc` using [source format 2](../../PROJECTS.md),
preserving all pinned C/header files, the hashed engine license and an explicit
80-unit `project.json`. This validates the real tree against source-exchange
limits; it is an architecture-input bundle, not a runnable app package.

The current core compiles with the pinned GCC 16.2.0/newlib headers: 274,047
bytes of code/constants, 59,995 initialized-data bytes and 243,608 BSS bytes
before dead-code elimination. These are engine-object sizes, not a complete
linked application's memory footprint. This remains a separate compile-only
probe. The normal zone allocation is 6 MiB, plus screen and other allocations.

## Local ARM integration and validation status

[platform.c](platform.c) uses ordinary main/newlib, public foreground timing and
pixels, authenticated named files and the API 4 held-key stream. The current
0.2.1 recipe requires API 12 and capability mask 8252, including explicit writer
cancellation. Earlier 0.1.x packages retain their original requirements and
behavior. No game-specific firmware service is
used. The [preparation script](../../../scripts/prepare_sdk_doom.py) verifies
the pinned sources, preserves their notices and records each checked change:
allocation errors, visible fatal messages, checked save transactions,
configuration I/O, and successful Quit outside the SDL-only compilation guard.
The 0.2.1 recipe also restores the recursive-error guard: an error inside an
engine exit callback exits with failure, preserving the first displayed error
and running the registered output discard instead of re-entering cleanup.

Prepare a new local project after fetching the pinned inputs:

```sh
.venv/bin/python scripts/prepare_sdk_doom.py --project build/my-doom-project
```

The generated project builds through the ordinary SDK. Its WAD is separate
app-private data; source packaging does not embed it. Public file exchange now
has a complete WAD import, cancelled replacement and cold-export ARM/USB-model
journey. With the installed app closed and no pending upgrade, use:

```sh
lefony-sdk files import doom-proof freedoom1.wad ./freedoom1.wad
lefony-sdk files list doom-proof .savegame
lefony-sdk files export doom-proof .savegame/doomsav0.dsg ./doomsav0.dsg
```

Use `--replace` explicitly when replacing an existing destination. See
[file exchange](../../FILE-EXCHANGE.md) for quotas, cancellation and uncertain
commit outcomes. Physical transfer qualification remains separate.

Named saves use `.savegame/doomsav0.dsg` through `.savegame/doomsav5.dsg`.
The 0.2.0 recipe enables upstream portable configuration loading and saving,
which were disabled by `ORIGCODE` in the earlier port. It also fixes the missing
directory separator in configuration filenames. `default.cfg` and
`doomgenericdoom.cfg` each accept at most 64 KiB. Only an absent file selects
first-run defaults; other read errors stop with a visible message. Ordinary
Quit saves settings; OS-owned Home can force exit without doing so.
The 0.2.1 loader preserves Doomgeneric's four virtual action keys in saved
configuration. Earlier configuration-enabled builds wrote those keys outside
the DOS scan-code range and then loaded them as zero, disabling Fire and Use.
Existing files containing the original virtual key values need no conversion.

[output.c](output.c) stages direct replacements using the public API 12 abort
operation. Replacing a same-sized save needs no additional logical quota, though
physical transaction headroom is still required. Processing failures discard
the staged writer, leaving gameplay available for another save attempt. A final
commit failure is reported as unconfirmed: the prior or complete new file may
have survived. Configuration failures produce a visible fatal message. These
are per-file transactions; the two configuration files are not an atomic pair.

Controls: arrows move/turn, XNT fires, Space uses, Shift runs, Alpha strafes,
Back/Menu opens the game menu and OK confirms. Num opens save, Symb opens load,
Plot/View request quick save/load and Toolbox requests quit. Movement,
turn/fire, menu, named/quick save/load, overwrite cancellation and clean quit
have selected normal-input evidence; the complete control map still needs
workload coverage. Home remains OS-owned. Sound and
multiplayer are omitted from this workload.

The earlier gameplay image (`aa3b6e7f976001189a482b96d43d47329049d19d8b455439a5f8ede5762e2405`)
has 315,758 code bytes and 430,904 static-data bytes, with a reserved 64 KiB
stack and 8,380,416-byte heap. Observed newlib maximum sbrk extent is 6,643,712
bytes. Later package-bound profiling observed 1,568 stack bytes in that
workload; this is not a worst-case stack measurement. General live-allocation
peaks remain unmeasured. Exact candidate measurements belong in the SDK ledger.

The maintainer test `vm/test-sdk-doom-gameplay.py` in the OS checkout reads actual
game state with GDB while normal keys drive movement, firing, menus, saving,
loading and quit. A cold launch restores the recorded position, angle and
ammunition, and leaves the 61,342-byte save unchanged. The final report is
`build/sdk-doom/gameplay-scheduled/report.json` in the maintainer checkout.
Debug pauses are excluded from timing qualification.

The earlier 120-second install timeout was reproduced and reconciled: the old
package/data root remained intact. Firmware now advances runnable storage
verification without a 10 ms idle delay between 2 KiB steps, retaining normal
input dispatch and UI timers. Both target builds and input/scheduling regressions
pass. No integrity checks or USB deadlines were relaxed.

The new `vm/test-sdk-doom-storage.py`, `vm/test-sdk-doom-errors.py` and
`vm/test-sdk-doom-resources.py` workloads exercise full-quota replacements,
settings restoration, failed writes and retry, oversized configuration input,
missing game data and allocator exhaustion. Their current results belong in the
OS checkout's `docs/NATIVE-APP-SDK-1.0-PROGRESS.md`; adding a harness alone does
not qualify its cases. `vm/test-sdk-doom-interruption.py` now covers normal Home
after a staged save prefix and during pre-commit verification, unchanged public
save/configuration exports, cold loading and retry. The maintainer observer
requires matching firmware symbols; it uses normal KPP input and no game or
storage function calls. Debugger-controlled stages do not establish physical
input timing or power-loss behavior.

`vm/test-sdk-doom-reset.py` exercises abrupt process stops at a save prefix,
reference verification, and immediately before/after the root's commit rename.
Use a previously installed synthetic `game` workspace with matching Doom code,
saved settings and a saved game:

```sh
.venv/bin/python vm/test-sdk-doom-reset.py \
  --seed-project build/my-doom-project --output build/my-doom-reset \
  --firmware dist/my-vm.elf --firmware-debug dist/my-vm-debug.elf
```

The harness verifies matching executable/debug segments, reads back the existing
signed installation and guards against host install/import/repair requests.
It kills only its own QEMU process while a hardware breakpoint holds the CPU,
then cold-boots that same synthetic media without reinstalling. Public exports
and exact serialized/restored player state distinguish old-save recovery before
commit from new-save recovery after commit. Each recovery retries a save; a final
cold run checks that retry and exports the entire pinned WAD. Reports and sources
identify the tested candidate; the script's existence alone is not a pass.

These selected cuts lose guest volatile state between completed modeled NAND
operations. They do not model torn physical programming or host power loss.
Broader reset/resource/control coverage and physical evidence remain separate
requirements; current results are in the SDK ledger.

`vm/test-sdk-doom-upgrade-reset.py` tests interrupted signed package updates
using the same prepared seed. It creates three local manifest-version fixtures;
these do not change the public Doom release or engine code:

```sh
.venv/bin/python vm/test-sdk-doom-upgrade-reset.py \
  --seed-project build/my-doom-project --output build/my-doom-upgrade-reset \
  --firmware dist/my-vm.elf --firmware-debug dist/my-vm-debug.elf
```

The cuts cover a partial USB upload, a partial package write, and both sides
of the root rename. Cold boots first authenticate and read back the existing
installation without reinstalling. Pre-commit cases retry the update. The
post-commit case inspects the retained package/data pair, explicitly rolls back
through the public data API, checks rejection of the retired version, and retries
with a higher version. Ordinary Doom Quit accepts a pending schema-zero update;
forced Home exit keeps its rollback pair available.

The final harness compares the saved game, both configuration files, file
listings, private-data digest and twelve restored player fields. Each case ends
with another cold load and a complete public WAD export checked against its pin.
Only explicit install and rollback phases permit corresponding host mutations;
no firmware, provisioning, key-management or raw-NAND command is allowed.
Use `--cases upload package-write before-rename after-rename` to select cuts.
Reports bind results to exact source/binary hashes. A completed pass, recorded
in the SDK ledger, is required before claiming the selected upgrade coverage.
These process-stop cases retain the same modeled-NAND and physical limitations
as the save-reset tests above.

`vm/test-sdk-doom-quickslots.py` uses normal Plot/View/Back input to exercise
quick-save slot selection, overwrite confirmation, cancellation and quick load.
It chooses an unused slot and preserves all existing named saves and both
configuration files. Three sessions check the serialized/restored state,
committed generations, final cold recovery and complete public WAD readback:

```sh
.venv/bin/python vm/test-sdk-doom-quickslots.py \
  --seed-project build/my-doom-project --output build/my-doom-quickslots \
  --firmware dist/my-vm.elf --firmware-debug dist/my-vm-debug.elf
```

The quick-slot choice lasts only for the running game. After a cold launch,
View reports that no quick-save slot has been selected; use Symb to load a named
save, and Plot to select a quick-save slot for that session. Saved files persist
independently of this menu selection. Consult the SDK ledger for the qualified
candidate and limits; these debugger-observed cases do not measure input timing.

## Distribution boundary

The engine's original GPL notices remain authoritative. Freedoom's exact
`COPYING.txt`, `CREDITS.txt` and `CREDITS-MUSIC.txt` accompany its game data.
The project describes the assets under a permissive BSD license; preserve the
copyright, conditions and disclaimer when distributing them.
[Freedoom licensing and attribution](https://freedoom.github.io/about.html).

The copyright holder approved an MIT alternative for the twelve original
conventional runtime/interface/linker files and startup-argument template listed
in the [license review](../../../docs/NATIVE-APP-LINKED-LICENSE-REVIEW.md). The
prepared project includes that scope, full MIT text, engine GPL text and
[component notices](THIRD_PARTY_NOTICES.md). The original grant changed notices
without changing the then-tested executable; later functional changes produce
separately identified candidates.

The grant does not relicense firmware, unrelated SDK helpers, newlib, GCC or
assets. The map excludes executable OpenBSD math helper sections from this
Doom image; those sources and notices remain in the SDK. Complete the actual
linked-input/corresponding-source audit, source/binary bundle checks and release
qualification before distributing a final artifact.

## Ready-to-play store candidate

Prepare the bundled local 0.2.3 project with:

```sh
.venv/bin/python scripts/prepare_sdk_doom.py --project build/doom-bundled --bundle-data
```

This opt-in recipe includes the pinned Freedoom WAD and exact license/credits
using the SDK's companion-data publication format. The executable stays within
ABI 1 limits; game data is automatically installed as named files. The earlier
manual-import instructions describe qualification projects without this flag.
See [publishing](../../PUBLISHING.md#bundled-installation-data-source-sdk-candidate).
