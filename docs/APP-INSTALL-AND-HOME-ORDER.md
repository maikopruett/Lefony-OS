# App installation feedback and Home ordering

The HP Prime G2 development candidate `1.0.0+1790287024` adds a white on-device
installation screen and long-press app ordering. Its physical and emulator
builds use the existing release key, app trust roots and storage layout.

## Using the changes

App package, data and icon transfers show a green progress bar on white.
Authenticated app names appear once the package has been verified. The package
phase distinguishes installing from updating an existing app. Completion shows
briefly, then returns to the previous screen, including while USB stays attached.
Cancelled uploads dismiss the screen; failures briefly show that installation
stopped. OS installation and physical trust/restore approval retain priority.

Progress describes the current transfer phase. The existing protocol does not
announce the total size or number of files in an installation bundle; each data
file and icon has its own progress. A phase reaches 100% only after the storage
operation succeeds, and readback does not move its bar backward.

On the Apps screen, hold an icon for about a second, drag it to its new position,
and release. The icon follows the finger and other apps move to make room.
Holding near the top or bottom scrolls to other rows. Short swipes still scroll,
and ordinary taps still launch. Dropping an icon never launches it. Additional
contacts, keyboard navigation or leaving the screen cancel the preview.

Both built-in and installed apps can be reordered. Ordering uses stable built-in
names and installed app IDs, so package updates and catalog slot changes keep
an app's position. New apps append to the current order; removed apps disappear.
The hardware Home, CAS and Apps shortcuts retain their existing destinations.

## Persistence and isolation

The Home order is an OS-owned `home-order` file at the root of the existing app
filesystem. It is separate from app namespaces, developer keys and the catalog;
there is no new USB request or app API. The versioned `LFHO` payload contains
bounded, null-terminated IDs and is wrapped with a length and SHA-256 digest.
Missing or invalid preference data falls back to the default order.

One save is queued on drop, never on every pointer movement. AppManagement
serializes the save with app, key and archive operations. The existing bounded
writer writes a temporary file, closes it, verifies every byte, then atomically
renames it. The previous cached order remains authoritative if saving fails.
This supports physical NAND persistence without changing the separate,
still-RAM-only physical built-in calculator records.

## Candidate identities

| Target | SHA-256 |
| --- | --- |
| Physical `prime_g2` binary | `4d4a37d8ccef92424772acf0eeea74144fa72618d0585a01f2d669b0b6d4fb7e` |
| Emulator `prime_g2_vm` ELF | `00630899614c6979f6a91fe736517b90ce5bdb759108807fc9d732f154d9f0a3` |

Builds used `LEFONY_RELEASE_VERSION=1.0.0+1790287024`, the checked-in
`release-signing.pub` and `app-trust-roots.json`, `make firmware-vm`, then
`make firmware`. The source distribution contains the audited public working
tree and the prepared physical source, with the base revision distinguished
from the exact distributed source snapshot.

## Validation

- Host progress tests: monotonic phase progress, verified completion, failure,
  cancellation, clock wrap and automatic dismissal.
- Host ordering tests: stable identities, insertion/removal, malformed records
  and bounded moves. Storage tests inject interrupted and torn NAND writes at
  48 replacement points; each recovery retains the old or complete new order.
- `vm/test-app-install-progress.py`: real guest USB package install/update,
  exact readback, file import/readback, icon install, cancellation, failed
  signature and disconnect, with screen captures and automatic dismissal.
- `vm/test-home-app-order.py`: real Goodix input and normal UI timers, built-in
  and installed app dragging, correct launch identity, multitouch cancellation,
  ordinary scrolling, edge scrolling and persistence across a cold NAND boot.
- Repeated Home preparation accepts the already prepared physical checkout.

Evidence is retained locally under the ignored release build directory.
These checks validate the model and code paths. No physical calculator was
flashed for this change. Physical long-press feel, frame pacing, flash endurance
and real power-loss behavior require separate hardware acceptance.

## Source integration recheck — September 24, 2026

Before merging the accumulated `sdk-1.0` source into `main`, both targets and
the custom QEMU were rebuilt with `make firmware`, `make firmware-vm` and
`make emulator`. This recheck used the existing local release signing identity
and did not flash a calculator.

`make test` passed 1,973 host tests, with two expected private DTB/DTS fixture
skips. `make check-public` passed, as did README local-link checks. The staged
whitespace check passed outside the byte-preserved OpenBSD math vendor sources.

| Rebuilt target | SHA-256 |
| --- | --- |
| Physical `prime_g2` binary | `44bb0eafeca631220c9773d574f9a82f0376da08ad1b13bc6d4ef2f806e96b6b` |
| Emulator `prime_g2_vm` ELF | `5b575fcb64e4b716c9c1dda0fcab2a3c99c2c8aa62a439187af0af56aeb28651` |

The following integration commands passed with the rebuilt emulator:

```sh
./vm/test-native-comprehensive.sh smoke
.venv/bin/python vm/test-prime-coordinate-touch.py --elf dist/lefony-os-prime-g2-vm-native.elf --functions
.venv/bin/python vm/test-prime-coordinate-touch.py --elf dist/lefony-os-prime-g2-vm-native.elf --calculation-history
.venv/bin/python vm/test-app-install-progress.py --output build/publish-validation/app-install-progress
.venv/bin/python vm/test-home-app-order.py --output build/publish-validation/home-order
```

The initial smoke run exhausted its ten-second startup wait while rebuilding
boot media and its Docker image, before guest startup. After those prerequisites
finished, the full rerun passed USB protocol stall, direct ELF, U-Boot smoke and
protocol checks. Installation/update progress and Home drag/order captures were
also inspected. Logs and synthetic emulator captures remain under ignored
`build/publish-validation/` and `build/prime-g2-native-suite-*` directories.
These results do not extend physical qualification beyond the limits above.

## Touch selection feedback — local follow-up

The Apps grid now starts without a highlighted app label. Directional-pad
navigation (including modified arrows) and keypad app shortcuts show the
selection. Touching the grid hides it immediately and keeps it hidden while
scrolling, after release and after gesture cancellation. The next directional
key restores the retained selection, including at the edge of the grid, and
brings it back into view if a touch scroll moved it offscreen.

This changes Home's visual feedback only. Logical selection, tap activation,
long-press reordering and other apps' table highlights retain their existing
behavior. The checked preparation scripts apply it to both built-in and
installed app cells; no generated source edit is required.

The expanded `vm/test-home-app-order.py` captures selection feedback through
normal KPP and Goodix input before continuing the existing drag, tap, scroll,
installed-app and cold-persistence journey. An initial candidate failed the
clipped-arrow screenshot check: changing the visual mode without consuming
that event did not redraw. The controller now handles that boundary event
after preserving normal table navigation and row wrapping.

Evidence for this local follow-up is retained under ignored
`build/home-touch-selection-20260925/`. No calculator has been flashed and
physical touch/keyboard acceptance remains separate.

Both `prime_g2_vm` and physical `prime_g2` builds passed with
`LEFONY_APP_PUBLIC_KEYS=ports/lefony-prime-g2/app-trust-roots.json`; the physical
build also used `LEFONY_UPDATE_PUBLIC_KEY=ports/lefony-prime-g2/release-signing.pub`.
The existing trust roots and prior local launch optimization are retained.

| Follow-up target | SHA-256 |
| --- | --- |
| Physical `prime_g2` binary | `04c4dc5289b2c6bc5cc0a33a244e659775e4011a81329b97d9fe2b8484f75416` |
| Emulator `prime_g2_vm` ELF | `a8bc6ec71237ec926c35a31fed80459345b8ffe4b54b1d0a638b73230200434f` |

The expanded `vm/test-home-app-order.py` passed all ten checks, including the
new label-pixel comparisons, with captures visually inspected. Eighteen focused
host tests passed (`test_home_order.py`, `test_prime_coordinate_touch.py` and
`test_prime_g2_keyboard_navigation.py`). Two repeated runs of
`prepare_prime_app_menu.py` left the prepared Home sources byte-identical.
`vm/test-prime-coordinate-touch.py --elf dist/lefony-os-prime-g2-vm-native.elf
--calculation-history` passed the separate history touch/keyboard regression.
`vm/test-native-comprehensive.sh smoke` passed all four selected cases.
`make check-public` and `git diff --check` also passed.
