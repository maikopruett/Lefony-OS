# Functions touch controls and graph gestures

The native Prime Functions app supports tapping its tabs, function cells,
footer buttons, graph toolbar, bottom banner, menu rows, and interval controls.
The on-screen plot OK button is removed; the bottom banner and physical OK key
still open curve options.
One finger drags the graph in both axes; two fingers zoom uniformly about their
midpoint while also allowing that midpoint to move. The range stays under the
fingers. Lifting either finger rebases to a one-finger pan without a jump.

## Implementation

- `scripts/prepare_prime_functions_touch.py`, called by the existing touch
  preparation script, adds hit testing against the visible view hierarchy.
  Targets use clipped screen rectangles, so keyboard focus is no longer needed
  to reach buttons, tabs, or tables. Modal views exclude covered content.
- Buttons and tabs activate on release inside their original target. A drag,
  second finger, keyboard action, or cancellation cannot become a tap. Tables
  explicitly focus a touched cell even if that cell was already selected.
- The Goodix reader reads two eight-byte contact records before acknowledging
  the report. This follows the contact layout in the upstream
  [Linux Goodix driver](https://github.com/torvalds/linux/blob/master/drivers/input/touchscreen/goodix.c).
  Contact IDs are normalized across record reordering. Joining and departing
  fingers are distinguished from an unexpected replacement. Three or more
  contacts, duplicate IDs, bad coordinates, and failed I2C transactions cancel
  until all fingers lift. Release retains the last valid coordinates.
- Multitouch is opt-in for graph responders. Existing menus, calculator
  history, and other controls cancel when a second finger joins.
- `prime_graph_gesture.h` computes centroid movement and scale. It ignores
  sub-threshold tap motion and avoids unstable division for coincident fingers.
  `prime_graph_touch_impl.h` applies changes using the graph's pixel scale and
  existing bounded range pan/zoom methods. Manual gestures disable Auto through
  those methods; toolbar Auto restores the normal computed range.
- Graph touch returns keyboard focus to the plot. The Navigate screen also
  supports gestures, and shared graph views update their touch owner as screens
  appear and disappear. No inertial scrolling or text caret placement is added.

## Verification

Both `prime_g2` and `prime_g2_vm` firmware targets compiled. Preparation was
repeated on a freshly built checkout to check idempotence. Thirty-two targeted
unit tests passed across touch, display settings, keyboard navigation, settings
identity, and frame presentation. The new compiled test executes the production
tracker and gesture geometry, including reordered IDs, one/two-finger
transitions, outward/inward pinches, coincident contacts, and invalid streams.

The emulator test uses `TOUCH FRAME` to publish complete contact reports into
the modeled Goodix registers, then runs the actual firmware reader, event
dispatch, and UI. It checks range values, not just screenshot differences:

```sh
PRIME_G2_CURRENT_CAPSULE=build/lefony-functions-touch/lefony-functions-touch.zImage \
  python3 vm/test-prime-coordinate-touch.py \
  --elf dist/lefony-os-functions-touch-vm.elf --functions
```

Verified: add/edit function, Functions/Graph/Table tabs, Plot graph and Display
values footers, all four graph toolbar buttons, curve options, interval Confirm,
function options, pan direction/distance, pinch scale and midpoint anchoring,
finger transitions, third-finger rejection, toolbar-crossing cancellation,
keyboard cancellation, and returning keyboard focus to the plot. Display guards
passed with zero timeouts. Captures and logs are under
`build/lefony-touch-qualification/` and `build/functions-touch-*.log`.

The existing launcher/toolbox/palette and display-settings UI regression passed,
including LCD refresh trial rollback and confirmation. The calculation-history
regression also passed with `--calculation-history`, covering expression and
answer recall, exact/approximate selection, draft preservation, scrolling,
and cancellation.

Two broader existing checks have unrelated stale expectations: the display
emulator contract expects `CLK_IPG_HIGH` in the unchanged timer source, and the
peripheral-model check expects `PRIME_NAND_MARK_OFFSET 2038` in the unchanged
NAND implementation. Neither timer nor NAND behavior was modified here.

The local QEMU r70 runtime directory had been configured against the r69 source
checkout. Qualification rebuilt with `PRIME_G2_QEMU_SOURCE_DIR` pointing to that
actual configured source so the new Goodix frame ingress was compiled.

## Candidate

- Physical firmware build ID: `260909-150107-cbbd3b`.
- Native binary: `dist/lefony-os-functions-touch-native.bin`.
- Recovery capsule: `build/lefony-functions-touch/lefony-functions-touch.zImage`.
- Capsule SHA-256: `4413144a3d226f6a2b1e60f68e5243cbf959d28c9e9c40b211f3167ad51fdfd4`.
- History entry: `20260909T150140944725Z-recovery-capsule-4413144a3d22`.

Docker was unavailable, so the capsule was assembled with the installed ARM
compiler using the same loader, linker script, payload offset, zImage end field,
magic, size checks, and manifest as `build_prime_g2_nand_capsule.sh`.
The candidate has not been flashed. Physical pinch responsiveness and touch
acceptance remain to be tested on the calculator; history remains unverified.
