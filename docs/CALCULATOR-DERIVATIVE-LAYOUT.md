# Calculator derivative layout — September 25, 2026

The math-template palette now shows a centered `d/dx` fraction. Tapping it
inserts the same operator followed by parentheses containing an editable
placeholder. The cursor starts in that placeholder; the default variable is
`x`. For example, entering `x²+3x` gives the symbolic result `2x+3`.

The denominator's variable remains editable with the arrow keys, and the XNT
key follows a single-letter variable such as `t`. History and recalled input
use the same typeset layout. Existing evaluated derivatives show a vertical
evaluation bar and `x=…` annotation. Integral templates are unchanged.

The layout serializes to the existing three-argument `diff(expression,variable,
point)` syntax. Symbolic derivatives serialize the editable variable as both
the second and third arguments. No parser, differentiation rule, persistent
record name or storage schema changes. Plain-text input mode continues to use
the textual syntax; the new notation belongs to the two-dimensional editor.

Source is in the [palette](../ports/lefony-prime-g2/apps/prime_math_template_palette.h),
[semantic layout](../ports/lefony-prime-g2/poincare/src/derivative_layout.cpp) and
[checked preparation script](../scripts/prepare_prime_derivative.py). The build
installs these into the disposable upstream checkout on every build. The new
layout enum is appended to preserve existing layout identifiers.

## Qualification

Targets: physical `prime_g2` and emulator `prime_g2_vm`, HP Prime G2. Based on
repository revision `c45297de4ea5598af0cb408f77b074ba2b949dfd` with the local
derivative changes; upstream pin `f36520e0ed5faabbfea8a2b9f4e1309edc077927`.
Both clean target builds pass. Evidence is retained locally under ignored
`build/derivative-*` and `build/lefony-touch-qualification/derivative-*`.

| Candidate artifact | SHA-256 |
| --- | --- |
| Physical native BIN | `4d488f51792d06c578be53f622526827f2ea3579239debf6f6422d4d0c733fc2` |
| Physical native ELF | `35acf6007578938904674a18a302b57787919ce4710cd9a88c493d0c74cb36c2` |
| VM native BIN | `40b5f3d9a476a58a7d4f877019f860243f4c41a289ba7116d99d6bf66c5ccd2b` |
| VM native ELF | `1122cd0155bd8d4eb655560b7f8d3e9a23838c5bda4f7da69692eeb0e6abe11e` |

The focused emulator journey uses Goodix taps for palette selection/history
recall and normal KPP key events for polynomial entry, variable changes and
deletion. Additional expressions enter through the normal text-input event
path. It covers symbolic and evaluated results, alternate variables, nested
derivatives, composition, fractions and an integral regression. Captured frames
are inspected for editor/history layout and placeholder visibility.

The derivative and calculation-history journeys pass on the final VM ELF.
The four smoke-suite checks
(USB stalls, direct ELF boot, U-Boot boot/calculation and protocol) pass.
The 12 focused host tests for preparation, palette and touch pass, including
repeat-preparation byte identity and rejection of changed upstream context.
Public-tree and whitespace checks pass.

The full host suite completed with **1,982 passed, two expected private-fixture
skips and one pre-existing Settings fixture failure**:
`tests/test_prime_settings_identity.py::SettingsIdentityTests::test_preparation_is_idempotent_and_identity_is_embedded`
raises `ValueError: Unexpected contributors context in main_controller.h`.
The test fixture lacks the contributors declarations now required by
`prepare_prime_settings.py`. The same failure was reproduced using only
unmodified `HEAD` files in an isolated temporary directory; see local logs
`build/derivative-settings-failure.log` and
`build/derivative-baseline-settings.log`. During release preparation, the fixture
was updated to include the required contributors declarations and verify that
repeat preparation does not duplicate the contributor. All seven Settings
identity tests then passed; no Settings firmware behavior changed.

```sh
make firmware-vm
make firmware
make test
make check-public
.venv/bin/python vm/test-prime-coordinate-touch.py \
  --elf dist/lefony-os-prime-g2-vm-native.elf --derivative
.venv/bin/python vm/test-prime-coordinate-touch.py \
  --elf dist/lefony-os-prime-g2-vm-native.elf --calculation-history
./vm/test-native-comprehensive.sh smoke
```

No calculator was flashed during these checks. The subsequent
[versioned release](DERIVATIVE-RELEASE-20260925.md) is published and selected by
the website; its exact hashes and final passing host suite are recorded there.
Physical touchscreen feel and keypad/display acceptance remain unqualified.
