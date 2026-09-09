# Calculation history touch support

The calculation editor now routes coordinate touches to its sibling history
table even while the editable input has keyboard focus. This was the missing
path: the app normally delivers touch only along the focused responder's
ancestor chain.

Behavior:

- Drag vertically through previous calculations, with bounded offsets.
- Tap a submitted expression (left) to insert its original input.
- Tap an answer (right) to insert that answer into the bottom editor.
- When exact and approximate answers are both visible, their actual view
  positions determine which representation is inserted.
- Insertion uses the existing keyboard recall path, preserving the current
  draft and inserting at the cursor. Nothing is submitted automatically.
- A drag, cancelled contact, or release on a different row/representation
  cannot recall an answer. Blank space can start scrolling but cannot recall.

The hit test reads the visible row before changing selection. Selecting a
history row first can expand exact/approximate layouts, scroll the viewport,
and recycle cells, invalidating the original touch coordinates. The text is
copied before deselection or focus changes. The touch path does not synthesize
Enter or mutate the calculation store.

Durable integration: `scripts/prepare_prime_touch.py` and
`ports/lefony-prime-g2/apps/prime_calculation_touch_impl.h`. Existing generic
menu/launcher touch behavior and frame-boundary presentation remain unchanged.

Emulator qualification uses `vm/test-prime-coordinate-touch.py
--calculation-history` with a Prime VM ELF and the current capsule supplied via
`PRIME_G2_CURRENT_CAPSULE`. It injects modeled Goodix contacts and physical KPP
key events, not direct controller calls. Physical touch feel still needs user
validation after installing the candidate. No U-Boot or NAND changes are made
by these tests.

## Qualified candidate

- Firmware build: `260909-064215-e0bd3c`.
- Capsule SHA-256: `91404f7b60c9387c5d78e7f11cd3044b0b11837ef4881904fe7adbe01842bb28`.
- Installer history: `20260909T065048444383Z-recovery-capsule-91404f7b60c9`.
- Full native/VM rebuilds, 131 targeted tests, calculation-history gesture
  qualification, and the existing touch/display-settings UI regression passed.
- Verified recall examples: older `101` becomes editable `101+2 = 103`;
  original `100+1` becomes `100+1+3 = 104`; exact `√(2)` is inserted into
  a draft and squared to evaluate `9+√(2)^2 = 11`. The decimal representation
  is independently recalled at full stored precision.
- Empty and bottom-aligned single-row history, keyboard-focused history,
  cancelled taps, and scrolling beyond both boundaries are covered.
- Not flashed. Installer status remains `unverified` pending physical testing.
