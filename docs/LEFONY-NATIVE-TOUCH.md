# Prime G2 native touch contract

The native port uses the fitted Goodix controller at I2C2 address `0x14`.
Linux identified this unit as product `5688`, firmware `0200`; the board device
tree's `goodix,gt928` compatible is a driver binding and is not treated as the
silicon identity. Product bytes live at `0x8140`; a ready coordinate report at
`0x814e` carries contact count, tracking ID, little-endian X/Y, and size. The
driver acknowledges a report by clearing the ready byte. Reset is GPIO1_IO24,
IRQ is active-low GPIO1_IO25, and the reset/address-select sequence chooses
7-bit address `0x14`.

Native Upsilon has key events rather than a general pointer event type. Touch
therefore has an explicit navigation contract: a valid contact-down followed
by release preserves its raw start/end coordinates and duration, a movement
of 28 pixels or more becomes the dominant-axis D-pad direction, the top 24
pixels become Back, the bottom 24 pixels become Home, 32-pixel left/right edge
zones become Left/Right, and the remaining body becomes OK. Holds retain their
duration and activate their zone on release. Continuous drawing, multitouch,
and arbitrary widget pointer dispatch are not advertised.

Exactly one contact is accepted. Coordinates outside 320×240, more than one
contact, malformed readiness, or a report without a matching down/release
sequence cancels the gesture. The next valid down starts a fresh sequence.
The driver polls with bounded I2C operations, so a lost interrupt cannot strand
input. `test-native-touch.sh` covers coordinates, hold timing, cancellation,
missing and malformed controller behavior, lost IRQ, reset/re-detection, and
simultaneous KPP input against the QEMU I2C/GPIO model.

Physical axis calibration and orientation remain a hardware gate until
controlled corner taps are captured from the calculator. The driver rejects
unvalidated transforms instead of inventing one.
