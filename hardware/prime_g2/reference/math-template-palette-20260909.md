# Lefony math-template palette

Touch selection is added by the later `260909-054139-118cf4` build; see
`coordinate-touch-20260909.md`. Earlier qualifications below predate touch support.

## Grid-only revision

Build `260909-051510-4fb065` removes the title, selected-template label, and
footer instructions. The popup is now only a bordered 266×146 grid; controls
and insertion behavior are unchanged. Capsule SHA-256:
`736a1f474cd16dc7ae192be5662e79d08836a91d0cd8cee5333ed9e6b38c888d`.
Both targets built; 119 targeted unit tests, emulator preview/boundary/cancel
checks, visual inspection, and physical-target emulated NAND timer/elapsed
checks passed. Not flashed. Screenshot: `build/lefony-template-qualification/palette-grid.png`.

## Original implementation and qualification

Build candidate: `260909-050619-3e0610`.
Recovery capsule SHA-256:
`667559333ed719db6028ac12a969eceaaa231c8353c35f91bbbea1fd7f90270a`.

The plain math-template key (the key with Units above it) opens a white,
Lefony-green 4×4 palette in editors using the shared math-toolbox provider.
Arrow keys select, Enter inserts into the original input, and Esc or the
template key closes without inserting. The selected template name appears
below the grid. Touch hit-testing is not implemented.

Templates: fraction, power, square, square root, nth root, absolute value,
logarithm with base, exponential, derivative, integral, sum, product, matrix,
row vector, parentheses, reciprocal. These use existing Lefony input/layout
primitives. They are not a port of HP's firmware, and HP-only templates are
not offered. Shift+the same key still opens Units; ordinary Toolbox is separate.
Python, RPN, and Sequence override the shared toolbox provider and retain their
existing app-specific behavior for now.

## Editor fix discovered during qualification

`LayoutField::handleEventWithText` built special cursor-based layouts without
reloading their size and drawing. The normal key-event path reloaded later,
but insertion from a popup bypassed that path. The palette's Power test caught
an unchanged screen despite insertion. The Prime-only patch now refreshes
cursor-built templates after insertion, including powers, squares, roots, and
matrices. Parsed expression insertion already reloads and returns early.

The physical x²-key report is not conclusively explained by this bug: the
preceding candidate already displayed `3² = 9` from the key in the emulator.
No physical key testing or firmware flashing was performed for this change.

## Reproduction

- `vm/test-prime-template-palette.py --elf <prime_g2_vm epsilon.elf>` injects
  modeled KPP keys, captures all 16 template insertions, and checks cancellation,
  bounds, and isolation from Toolbox and Shift+Units. Inspect the screenshots
  in `build/lefony-template-qualification/`; image differences alone do not
  establish mathematical correctness.
- `vm/test-prime-shift-events.py --source <prepared tree>` compiles the actual
  event table/decoder and checks plain x² plus the prior Shift corrections.
- `tests/test_prime_math_template_palette.py` covers the template inventory,
  routing, navigation guards, and popup redraw patch structure.
- Physical-target capsule regression tools: `vm/test-prime-main-timer.py
  --elapsed` and `vm/test-prime-battery-usb.py`, with
  `PRIME_G2_CURRENT_CAPSULE` pointing to the candidate.

The palette UI test uses the emulator-target KPP driver on the EVK machine,
not the physical GPIO keyboard scanner. NAND boot and peripheral tests are
separate emulator checks, not physical acceptance. U-Boot is unchanged.

Qualification completed: 118 targeted unit tests and the compiled decoder test
passed; all 16 UI insertion checks passed, including popup x² on `3` producing
`3² = 9`. Visually inspected the palette, power, logarithm, integral, matrix,
and square-result captures. The physical-target capsule's emulated NAND-boot
timer/elapsed checks and battery fault-injection tests also passed. The latter
covered stopped-GPT sampling, unplugged-full icon stability, and a complete
two-day sleep gap. Candidate remains physically unverified and not flashed.
