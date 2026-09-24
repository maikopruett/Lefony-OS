# Forms and Tables

An experimental public-API reference for layout, focus, text/caret/selection,
toggles, disabled buttons, a six-row result table and nested confirmation dialogs.
The expression field uses the bounded scalar parser. Start with `2+3*4`, press
OK to evaluate, then use Up/Down to move between controls. Shift+Left/Right selects
text; typing replaces the selection. Operator keys insert the parser's ASCII
spelling. Unsupported operations produce visible errors.

The table retains expression text and results rounded to three decimal places.
Its explicit app schema supports six rows within the existing private 64 KiB
byte store. Changes are staged and saved on normal app exit. Unknown saved
schemas stay read-only. This does not demonstrate data-only durable checkpoints.

Back returns from dialogs/table when optional navigation service 9 is available;
at the form it exits the app. On older firmware use the on-screen Back/Cancel
buttons; base ABI input supports numeric editing only. Home and power remain
OS-owned. Non-ASCII field characters use a visible `?` glyph fallback, and the
scalar parser rejects unsupported grammar. This is not a full math editor.

Run `lefony-sdk test --workspace forms-test` from a fresh generated project.
The replay explicitly clears this app's synthetic table first, then tests
keypad/touch navigation, normal Back, focus restoration, multi-contact capture
cancellation, row deletion and Shift-selection editing. Screenshots are in
`build/tests/forms-tables/`. Inspect them as well as the automated assertions.
Emulator checks do not establish physical interaction feel or durability.
