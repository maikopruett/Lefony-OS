# Coordinate touch, launcher selection, and menu scrolling

Candidate `260909-054139-118cf4`, capsule SHA-256
`12e6614c125fcd3b4a095b292dd1b528f4146bc7cb25de2092972d976a42f82c`.
Not flashed or physically touch-qualified during this change. U-Boot unchanged.

Subsequent user observation: coordinate touch works perfectly on the calculator,
but scrolling has visible tearing. The separate
[frame-presentation change](frame-presentation-20260909.md) addresses scanout
ownership without changing the now-confirmed touch mapping.

Subsequent [Functions touch support](functions-touch-20260909.md) adds visible
buttons/tabs and two-finger graph gestures. The single-contact scope and
multitouch rejection below describe this earlier candidate.

## Cause and change

The old Prime touch backend converted broad screen regions and gestures into
keyboard arrows, Enter, Back, or Apps. Widgets did not receive coordinates, so
the launcher could not identify the tapped icon. The parser also interpreted
the coordinate bytes of a zero-contact release as a point; those bytes are
not a current finger position and can cause false swipes.

The new backend emits a dedicated non-keyboard Touch event with Down, Move,
Up, and Cancel phases. It retains the last valid single-contact position for
release, ignores duplicate stationary reports, tracks contact ID, and latches
drag state after 10 pixels of movement. Dragging back to the starting point
does not turn the gesture back into a tap. Malformed coordinates, multiple
contacts, changed contact IDs, and I2C failures cancel/quarantine the gesture
until all contacts lift.

Escher captures touch to the responder that accepted Down. Release clears
capture before calling an activation that could destroy the current app.
Keyboard use, modal changes, and app exits cancel capture, preventing stale
release events from acting on a different screen. Unhandled touches do not
turn into keyboard presses or click through a modal.

Shared SelectableTableView widgets hit-test visible cell rectangles using
their actual content origin, including margins and scroll offset. A tap
highlights its target and activates only if released on the same cell without
dragging. Normal controller Enter handling still applies validation and
exam-mode restrictions. The launcher rejects unpopulated last-row cells.
Dragging moves the scroll offset with bounds clamping, without activation.

Scrolling revealed two additional integration issues: transparent launcher
cells needed full viewport dirtying to remove old pixels, and animated menu
highlights needed to be stopped before recycling cells. Re-highlighting an
already highlighted menu cell could register the shared animation timer again.
The touch path avoids redundant highlighting and clears highlights before
recycling. No general timer behavior was changed.

The grid-only math palette also supports direct tap-to-insert, with the same
drag/cancel protections. Its arrow/Enter/Esc controls remain available.

## Scope and limitations

This covers the launcher, menus/lists built on SelectableTableView (including
the shared math toolbox and Settings tables), and the math-template palette.
It is not universal touch support for every widget: graph gestures, text-caret
placement/selection, custom buttons, tabs, pinch zoom, and kinetic/inertial
scrolling remain separate work. Scrolls stop when the finger stops.
The old global top/bottom/side tap shortcuts are deliberately removed; physical
Esc and Apps keys remain available. Sensor calibration/orientation and physical
scroll smoothness still require testing on the calculator.

## Build and verification

`scripts/prepare_prime_touch.py <prepared source>` performs checked, idempotent
integration into a prepared checkout. The native build script runs it after
copying the Prime port. It never resets the checkout. The driver and reusable
widget helpers live under `ports/lefony-prime-g2`.

- `tests/test_prime_coordinate_touch.py` compiles and runs the actual contact
  tracker, including stale/invalid release coordinates, jitter, latched drags,
  multi-touch/ID-change rejection, and I2C cancellation.
- `vm/test-prime-coordinate-touch.py --elf <prime_g2_vm epsilon.elf>` uses the
  modeled Goodix I2C reports and emulator-target KPP input. It asserts app
  identity after tapping different icons and after scrolling, repeatedly
  recycles toolbox rows, inserts a template by touch, checks `3² = 9` through
  the calculation result API, and tests cancellation with Esc.
- Captures are in `build/lefony-touch-qualification/`. The initial USB-power
  modal must be dismissed before testing the launcher; merely inspecting the
  underlying app ID does not establish which view is visible.
- Physical-target emulated NAND boot, main/elapsed timer, and battery fault
  tests are separate from the emulator-target UI checks. Neither substitutes
  for physical touchscreen acceptance.

Final qualification passed: both firmware targets built, 123 targeted unit
tests passed, the complete coordinate-touch UI test passed (including repeated
menu scrolling and exact result `9`), and the physical-target emulated NAND
timer/elapsed and battery fault-injection tests passed. The battery tests
covered stopped-GPT sampling, stable unplugged-full display, and a complete
two-day elapsed-time gap. Only this passing candidate was added to history.
