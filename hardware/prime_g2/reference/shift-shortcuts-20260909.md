# Prime Shift shortcut corrections — 2026-09-09

Candidate: `260909-045344-c50bbc` (0.1.0-dev), recovery capsule SHA-256
`0ab9a920aa7abeb8a927969d3618a8e1ddf981e06bb4f9010ae46d791eeef030`.
Not flashed or physically keyboard-qualified during this change. U-Boot unchanged.

## Corrected mappings

Printed legends were checked visually against HP's English Prime Quick Start
Guide, keyboard illustration on page 3:
https://ftp.hp.com/pub/calculators/Prime/Documentation/Calculator/EN/Quick_Start_Guide_EN_2017_11_20_1.pdf

| Key | Lefony behavior |
| --- | --- |
| Shift + Enter | Submit the expression, including Lefony's existing exact/approximate results; not a new approximate-only evaluation mode |
| Shift + Space | Underscore instead of minus |
| Shift + 4 | Open Matrices and Vectors in the math toolbox |
| Shift + 5 | Insert a properly editable matrix |
| Shift + 6 | Open calculus functions rather than insert only a summation |
| Shift + 9 | Insert an editable two-column row vector |
| Shift + math-template key | Open Units |
| Plain math-template key | Open the math toolbox |
| Shift + 7 | Explain that the List catalog is not available in this build |

The List catalog is compiled out (`LIST_ARE_DEFINED`); this patch does not add
list support. Other HP-specific catalogs and applications are not made fully
HP-compatible by these corrections. For example, existing Chars/Base shortcuts
still use the generic toolbox and Notes/Program use Code.

The durable patch is `ports/lefony-prime-g2/patches/prime-g2-shift-shortcuts.patch`,
applied after the original keyboard patch by the native build script.
Category requests are consumed in `didBecomeFirstResponder`, not
`viewWillAppear`: opening a submenu in the latter reenters modal appearance and
can register scrolling-text timers twice. Unsupported-list handling explicitly
redraws and updates the modifier/backlight state.

## Qualification

- Physical-target binary and emulator-target ELF built successfully. A full
  rebuild after the new translation was required to eliminate stale label IDs
  seen in incremental-build screenshots.
- 114 targeted keyboard, battery/clock, USB diagnostic, identity, history, and
  installer unit tests passed.
- `vm/test-prime-shift-events.py` compiles the prepared C++ decoder and actual
  layout table: 20 text mappings and 9 semantic shortcuts passed, with plain
  math and Alpha preservation.
- `vm/test-prime-shift-ui.py --elf .../prime_g2_vm/epsilon.elf` exercised eight UI
  workflows and captured them in `build/lefony-keyboard-qualification/`.
  Inspected categories, List warning, templates, evaluation, and ordinary
  toolbox restoration. This uses the emulator-target KPP driver on the EVK
  machine, **not** the physical GPIO scanner. KPP injection does not currently
  drive the physical-target firmware's GPIO keyboard path.
- Packaged physical-target candidate booted through the emulated NAND chain;
  main timer and elapsed-clock USB checks passed. This does not establish
  physical key scanning, hardware timing fidelity, or physical NAND boot.
- Physical-target battery fault-injection test passed: stopped GPT sampling,
  unplugged-full icon stability, and a complete simulated two-day sleep gap.

Physical acceptance still requires installing this build and trying the printed
Shift combinations on the calculator, including in apps other than Calculation.
