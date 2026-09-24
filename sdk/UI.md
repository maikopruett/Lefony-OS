# C/C++ UI and ARM preview candidate

The API 9 local candidate builds on the public drawing/input services. Screens,
layout and actions are C++ source owned by the project. The new
`lefony/ui_widgets.h` offers a configurable palette, measured labels, buttons,
two-line list rows, wrapping paragraphs, UTF-8 fields, choices, progress, sliders, menus and dialogs.
`Focus`, `Navigation`, `TextBuffer`, `TextFieldModel`, `SliderModel`, `ListModel` and `MenuModel` keep state
separate from painting. Slider drags, keyboard changes and cancellation use the
bounded model; committing a value and menu actions remain explicit app handlers.
No claim of complete localization, accessibility or stable 1.0 is made.

## Component gallery and states

```sh
lefony-sdk new ./my-gallery --template ui-gallery
lefony-sdk --project ./my-gallery preview --once --scenario tests/startup.json
```

The gallery demonstrates touch/keypad focus, pressed and disabled controls,
cancelled drags, a confirmation dialog, a scrolling action menu, four OS fonts,
long and empty text, wrapped help/warnings, a custom dark palette and empty/loading/ready states.
Loading is a three-second local demonstration; it makes no network requests.
Its app state is in memory. The Notebook example below supplies the durable
document workflow and error handling.

Pass each widget its original layout box and set the viewport in the `Widgets`
constructor. Clipping crops the original painting; it does not recenter text,
resize controls or change a progress/slider value. Focus hit bounds should use
the intersection with the viewport. Inspectors retain both the original bounds
and effective clip. Labels use the palette's muted color when disabled and its
error color for enabled invalid values. Buttons, choices and sliders expose
their pressed state; apps pass state flags from the corresponding input model.

## Menus and confirmation dialogs

`MenuModel<Capacity>` owns up to 32 actions (eight by default). Each action has a
unique nonzero ID, an enabled flag and an owned UTF-8 label of 1–95 bytes. Invalid
labels, duplicate IDs and full capacity fail without adding an item. Font support
is checked during painting. `layout(viewport, rowHeight)` uses `ListModel` bounds
and scrolling; the default row height is 30 pixels. Rows shorter than 14 pixels
have no label. Use a practical touch target for interactive menus.

```cpp
MenuModel<8> menu;
menu.layout({12,50,296,150});
menu.add(100,"Save");
menu.add(101,"Unavailable",false);
menu.add(102,"Close");
// During drawing:
ui.menu(60,menu,"No actions",LEFONY_UI_HERE);
// During input, route keys and the menu's captured touch gesture:
uint32_t action=menu.input(input);
if(action==100) saveDocument();
```

Up/Down wraps and skips disabled actions; OK returns the focused action ID.
Disabled actions cannot activate. Dragging, changed contacts and cancellation
follow the list rules below. Route the entire captured gesture to the menu,
including events outside its viewport, and call `cancel()` when navigating away.
The app owns Back, navigation and action handlers. An empty or entirely disabled
menu returns no action. `Widgets::menu` accepts empty/loading text explicitly;
the app owns asynchronous work and the transition to populated actions.

`DialogLayout` provides a two-button confirmation panel, title and action bounds.
Its default panel is `{12,60,296,126}`. `layout.open(focus,primaryId,cancelId)`
replaces background focus with the two actions and selects Cancel by default.
Pass `false` as the fourth argument to disable the primary action. Invalid
geometry, IDs or insufficient focus capacity leave the previous focus unchanged.
Use `Widgets::dialog` with the same layout, IDs, labels and state flags to paint.
The app pushes/pops its navigation state and restores prior focus after dismissal;
the model never invokes an action handler itself. Notebook and the gallery show
the complete flow.

## Touch editing in fields

Pass an optional `TextFieldModel` to `Widgets::field` to use the painted font
metrics and viewport for touch editing. A tap positions the caret; dragging
selects complete rendered cells. The viewport stays in place while the caret
is visible. Keyboard movement reveals it when needed. The model changes only
selection and scroll position; save and confirmation remain app actions.

```cpp
TextBuffer<128> text;
TextFieldModel field;
// During drawing, after configuring focus and palette:
ui.field(10, bounds, text, Enabled | Focused, LEFONY_UI_HERE, &field);
// Route Down inside the painted field and every event of its captured gesture:
if(input.event==3 && (field.captured() ||
    (input.touchPhase==0 && field.contains(input.contacts[0].x,input.contacts[0].y)))) {
  focus.select(10); // Also cancel any button capture.
  field.touch(text,input);
} else if(input.event==1) {
  field.cancel(text);
  // Handle the key using edit(text,input), expression editing or app actions.
}
```

Use one model per field and draw it before accepting touch. Disabled fields,
unsupported glyphs and empty clips cannot begin a gesture. Hit bounds follow
the effective drawing clip. A move into the left or right inset reveals one
additional cell; there is no timer-driven scroll while the finger stays still.
Leaving the field, adding/replacing a contact, malformed contact phases or
cancellation restores the original selection and viewport. Remaining events
cannot reactivate that gesture or a previously cancelled button capture.

Call `cancel(text)` before keyboard/programmatic edits, navigation, disabling or
layout changes. The model holds no text pointers. `TextBuffer::select(caret,
anchor)` accepts byte offsets at UTF-8 code-point boundaries and rejects invalid
offsets without changing either endpoint; `anchor()` exposes selection direction.
Touch hit testing uses the same base-plus-accent cells as painting. Keyboard
editing retains its existing Unicode-scalar behavior. Without an interaction
model, `Widgets::field` retains its earlier caret-following display behavior.

Notebook uses field touch to place/select text; OK or the Save button commits
the expression. UI Gallery keeps OK's select-all action and adds touch placement.
The maintainer harness `vm/test-sdk-text-field.py` checks normal Goodix/keypad
input, cancellation, long/accented fields, Home, saved bytes and cold reopening.
Its candidate-specific evidence is in the SDK implementation ledger.

## Lists and captured scrolling

`ListModel::layout(viewport, stride, gap)` enables pixel scrolling. `stride`
includes the trailing gap; the last row has no trailing gap in the content
extent. Layout dimensions and stride must be 1–32767, and gap must be smaller
than stride. Invalid layout leaves the model unchanged. A model without a
configured layout retains the earlier whole-row keyboard paging behavior.

```cpp
ListModel list;
const Box viewport{12,60,296,116};
list.layout(viewport,40,4);
list.count(document.count);
Widgets rows(palette,viewport);
for(unsigned i=list.first(); i<list.first()+list.visible(); i++) {
  auto flags=Enabled|(list.selected()==i?Selected:NoState)
    |(list.pressed()==i+1?Pressed:NoState);
  rows.row(100+i,list.row(i),titles[i],details[i],flags,LEFONY_UI_HERE);
}
```

Paint the original `row(i)` rectangle through a clipped `Widgets` instance;
use `intersect(list.row(i),viewport)` for focus bounds. Partially visible rows
retain their text positions and original borders. `visible()` includes partial
rows, and `row(i)` is empty for invisible entries. The allocation-free model
uses 64-bit content offsets so large virtual lists do not overflow row arithmetic.
Repeated identical layout/count calls preserve an active gesture.

Route an initial single-contact Down inside the viewport, then every event for
that captured gesture, to `list.touch(input)`. Its result is the tapped row
index plus one, or zero when no row should activate; opening a row remains an
app action. Gaps cannot activate a row. Vertical movement of at least six display
pixels starts a drag; the viewport tracks movement directly, without inertia.
Vertical capture continues outside the viewport and clamps at both content ends.
A drag release never becomes a tap, including over another control.

Horizontal departure, an initial predominantly horizontal movement, additional
or changed contacts, and Cancel stop capture while retaining the scroll position.
Call `cancel()` on keyboard input, navigation and focus/lifecycle changes; do not
send that gesture's remaining events to another control. A fresh Down can begin
another gesture. `select()` and `move()` reveal the selected row for keyboard
navigation; dragging keeps selection within the visible rows without snapping.

`Widgets::scrollbar(id,box,list,source)` paints a position indicator when the
content exceeds the viewport. It is not an interactive slider. The inspector
reports kind `scrollbar`, with Pressed while dragging. Physical scrolling feel
and timing still require qualification.

## Start a document project

```sh
lefony-sdk new ./my-notebook --template notebook
lefony-sdk --project ./my-notebook preview --once
lefony-sdk --project ./my-notebook preview --scenario tests/edit.json
```

Use `--firmware` and `--qemu` to select the matching local emulator firmware with
API 10 and the whole-app archive extension (USB hello flag 1024), and
custom QEMU. The default firmware in an older SDK download does not provide this
candidate. Dependencies must already be installed; preview performs no downloads.
`preview` watches source/configuration/assets/tests and rebuilds on saves;
`--once` captures one run. Open `build/preview/index.html` in a browser for the
actual 320 × 240 frame, bounds overlay and source table. It refreshes every three
seconds. `status.json` records exact package/firmware/QEMU hashes, timings and
errors; compiler diagnostics are retained in `build.log`.

Each preview installs the exact ARM package into fresh synthetic storage using
the normal signed USB installation and loader. A selected scenario traverses
normal keypad/Goodix input. Automatic preview never opens a physical USB device.
A failed build or run marks the last good image **STALE** and preserves it.
Changes during a run also invalidate its result; the watcher rebuilds the changed
source. Build/package locks retain their existing SDK pinning requirements.

The default retains committed named files, directories and private bytes between
successful previews. On the first run it starts empty, or seeds data from
`--fixture-dir ./fixtures`. Fixtures can contain nested files and empty directories:
up to 127 entries including directories, totaling at most 32 MiB. Paths follow
the [app file contract](FILES.md); symlinks and special files are rejected.
Scenario outputs never modify the fixture directory. Changing supplied fixtures
requires an explicit reset so a source save cannot overwrite edited app data.

```sh
lefony-sdk --project ./my-notebook preview --fixture-dir ./fixtures
lefony-sdk --project ./my-notebook preview --reset-data --fixture-dir ./fixtures
lefony-sdk --project ./my-notebook preview --once --fresh-data
```

`--reset-data` starts from the supplied fixtures, or empty data when omitted.
In watch mode it resets only the first successful run. `--fresh-data` discards
outputs and leaves saved preview data untouched; it cannot be combined with
reset. Failed builds, app faults/nonzero exits and source changes during a run
do not replace the saved checkpoint. Ctrl-C marks the preview stale. Capturing
the final frame precedes normal Home cleanup, so unsaved in-memory edits are
discarded and only committed data is exported.

Saved data lives in `.lefony/preview/`, outside `build/` and the source/publication
allowlist. An atomic `state.json` receipt selects a verified archive and retains
one previous checkpoint. Check that receipt after an interrupted local write;
it records whether checkpoint publication completed even if later frame or
status publication failed. These archives use only the public emulator fixture
key and are development data, not calculator trust grants.

Source edits at the same app version preserve saved data. A version increase
retains the previous compatible package/data pair and presents a real pending
upgrade through [API 8](DATA.md). Apps must migrate as needed and explicitly
accept the upgrade before a further version increase. A schema change requires
a version increase; downgrades require an explicit preview reset. Each run uses
normal installation/restore into fresh synthetic media, preserving the physical
installer's version and signing policy. Empty data needs no redundant restore.
Saved preview mode requires ABI 1; use `--fresh-data` for older experiments.

## Measuring preview time

The local September 13 candidate completed a populated Notebook preview in
**19.1 seconds**, including a **2.7-second build**, compared with **109.5 seconds**
in the recorded baseline. Both used 12 expressions, a 131,328-byte nested
attachment, signed installation, archive restore/export and a normal Goodix
scroll scenario. The resulting frames are pixel-identical. These are local
profiled measurements, not a latency guarantee or a supported-host benchmark.
Current local source-kit and macOS bundle previews have separate evidence in
the SDK ledger. Repeated supported-host measurements, clean-host release
qualification and physical USB remain open.

From the OS repository, reproduce the workload with an existing VM firmware
candidate and an unused output directory:

```sh
.venv/bin/python vm/profile-sdk-preview.py --firmware dist/lefony-os-prime-g2-preview-poll-v2-vm.elf --output build/my-preview-profile
```

The output includes `report.json`, `profile.bin`, readable `profile.txt`, the
external project and its real preview frame/layout. Timings distinguish build,
installation, archive transfer and status polling. The profiler records the
SDK, firmware and QEMU identities and rejects an SDK change during measurement.
It uses synthetic storage and the normal signed package path. Exact regression
evidence and remaining qualification belong in the
[implementation ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md).

## OS fonts and Unicode

Declare `minimum_api: 9` and capability `1024` in a schema-1 manifest. The C
`lefony/text.h` interface exposes service 15 using the 80-byte `LefonyTextRequest`.
C++ `measure` and `drawText` wrappers are in `lefony/typography.h`.

- Font IDs 0/1/2/3 select small/large/small italic/large italic. Current OS glyph
  cells measure 7 × 14 and 10 × 18 pixels. Measure returns the actual dimensions;
  callers should use those values rather than assuming another font size.
- One request accepts 0–256 UTF-8 bytes. Empty text may use a null pointer and
  measures zero width with the selected line height. Embedded NUL, C0/C1/DEL,
  malformed scalars and a leading U+0300–U+036F combining mark are invalid.
- The pinned OS glyph inventory is the supported set. No normalization or
  replacement occurs. For example, `Cafe\u0301` renders an acute accent over `e`;
  precomposed `é` is unavailable in the current font. Greek and supported math
  glyphs work. Unknown glyphs return `-5`, including emoji.
- Initialize a fresh request for each call: size 80, schema 1, operation 1
  (measure) or 2 (draw), font/text/textBytes. Outputs and reserved fields must be
  zero. Measure requires all coordinates, clipping and colors zero.
- Draw accepts RGB565 colors and x/y from -4096 through 4096. Its nonnegative
  clipping rectangle must fit the 320 × 240 surface. Partial glyphs are clipped;
  output flag 1 indicates that the measured text rectangle extends past the clip.
  No pointer is retained. The request and surface stay unchanged on failure.
- Success is 0; invalid memory/fields/text or undeclared capability is `-4`;
  missing font glyph is `-5`; older firmware returns `-3` for the service.
  The original ASCII service remains unchanged.

The widget field accepts the full `TextBuffer` capacity, including a 1023-byte
value in `TextBuffer<1024>`. It validates font support in requests of at most
256 bytes, keeping each base character and its combining marks in one request,
then draws the visible cells around the caret. A single cell exceeding that
request limit fails with `-4`; unsupported glyphs still fail with `-5`, including
outside the visible portion. The per-request limit does not truncate the field.
Other widget labels retain the text API's 256-byte request limit; long labels
within that limit are clipped to their layout bounds.

The widget field groups supported combining accents with their base for drawing
and horizontal scrolling. Caret editing still moves by Unicode scalar, not by
full grapheme cluster. Two-dimensional mathematical editing and arbitrary font
conversion remain separate work.

### Wrapping paragraphs

Use `Widgets::paragraph` when help, empty-state or recovery text needs multiple
lines. Existing `label` calls remain single-line and clipped. Paragraphs use
the same four fonts, palette and inspection `Label` kind, with no firmware or
wire-format change:

```cpp
auto text = ui.paragraph(53, {24,112,272,60},
    "The original file is unchanged. Export it before restoring a backup.",
    LEFONY_FONT_SMALL, LEFONY_UI_HERE);
if (text.error) { /* handle an unsupported font or invalid text */ }
if (text.clipped) { /* provide more space or a separate details screen */ }
```

The NUL-terminated input may contain up to 1,024 UTF-8 bytes. Plain ASCII spaces
separate words; leading and trailing spaces on each rendered line are omitted.
LF and CRLF force a line break and preserve empty lines, including a final empty
line after a trailing newline. Long words split between rendered cells, keeping
a base and its U+0300–U+036F combining marks together. This is a bounded fixed-font
layout, not full Unicode word breaking, bidirectional text or hyphenation.

The return value contains `lines`, required `height`, `clipped` and `error`.
Empty input needs zero lines/height. `clipped` reports insufficient box width or
height and viewport clipping. A box narrower than one glyph lays out one cell
per line and clips that glyph. The optional final `lineGap` argument is 0–32
pixels, default 2. x/y must be within -4096…4096 and width/height within 0…32767.
The layout uses the requested box; changing the viewport only crops its pixels.

All input before the terminating NUL, including invisible lines, is validated
before the paragraph changes pixels. Invalid UTF-8, controls other than LF/CRLF,
leading combining marks, excessive input or a single cell exceeding the 256-byte font request
return `-4`. Missing glyphs retain the typography service's `-5` result. Metrics
are usable when `error` is zero. The widget clears its box to the palette's paper
color and draws using normal, disabled or invalid text colors. It allocates no
heap memory. The caller retains ownership of the text throughout the call.

`ParagraphLayout` in `lefony/ui_paragraph.h` also exposes an allocation-free line
iterator for valid text and a positive column count. Each `ParagraphLine` gives
its source byte offset/length and rendered-cell count; font availability is
checked by the widget separately. It borrows its input without copying it.
Unlike the NUL-terminated widget interface, the iterator takes an explicit byte
count and rejects a NUL within those bytes.

Notebook uses this component for its empty and damaged-document instructions.
UI Gallery's Wrapped text action demonstrates word wrapping, long words,
explicit blank lines and disabled/invalid states. Qualification is recorded in
the [SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md).

## Layout inspection

Wrap a screen paint with `inspectionBegin()` and `inspectionEnd()`. Pass
`LEFONY_UI_HERE` to widget calls. `inspectNode` records custom-drawing regions.
Each node includes a stable ID, kind, requested bounds, effective clip, state,
short label and source location. State bits are enabled 1, focused 2, pressed 4,
selected 8 and invalid 16. The fixed frame holds 64 nodes and reports overflow.

Use `inspectionEnd(false)` for a loading screen that cannot yet handle input;
finish the subsequent interactive screen with ordinary `inspectionEnd()`.
Notebook marks its document-opening and save-status screens this way. Preview
waits for a completed, input-ready frame before replaying a scenario and before
its final capture, using a debugger watchpoint with a 30-second deadline. A
missing completion/readiness transition fails with retained debugger logs and
preserves the previous visible frame and committed preview data.

This is debug-layout schema 2 (11,292 bytes); schema 1 dumps remain readable but
cannot describe input readiness. It changes no firmware service or runtime ABI.
Rebuild the app with matching SDK headers to obtain readiness-aware preview.

Debug builds define `LEFONY_SDK_DEBUG=1`. The viewer reads the copied frame with
GDB through the emulator's private local socket, pausing without modifying guest
code or invoking guest functions. The viewer checks matching package symbols.
Incomplete frames are rejected after the bounded wait. Use `--no-inspect` for
apps without records; their replay scenarios must arrange their own startup wait.
Release compilation omits the inspection records and calls; ordinary source
symbols remain available in the separate debug ELF for diagnosis. Qualification
compares actual debug/release ARM frames and verifies the record symbol is absent
from the release image.

## Notebook behavior and current limits

[Notebook](examples/notebook/src/main.cpp) demonstrates list scrolling, expression
editing/validation, a custom plotted region, light/dark palettes, disabled/error
states and confirmation dialogs. Up/Down moves focus; OK activates; Back navigates
or asks before discarding edits. Home remains OS-owned and discards unsaved edits.

Notebook 0.6 uses the shared confirmation layout and shows pressed slider states,
in addition to the captured list scrolling and scrollbar added in 0.4. The
document format and data schema are unchanged. It requires API 12 writer
cancellation, API 10 system services, API 9 typography and API 8 data
control. Its
light palette follows the OS; the dark palette remains an app customization.
It holds up to 12 expressions of 95 ASCII bytes. Calculations use the bounded
app-linked scalar evaluator, with `x = 1` for the displayed result.
New documents copy the OS angle, display format and significant-digit settings.
Options selects degrees/radians/gradians, automatic/scientific/engineering
notation and 1–14 significant digits. Apply saves these values with the document;
Cancel or Back discards draft choices. OS defaults only changes those drafts.
Dragging the slider outside its bounds or adding a contact restores its starting
value. Left/Right changes the focused slider by one digit. These controls do not
change OS preferences. Invalid, unsupported, unbound and undefined expressions
have explicit error text; export never substitutes a fabricated numeric answer.

In the focused expression field, Shift+View copies the selection (or the whole
expression), Shift+OK cuts it and Shift+Menu pastes. Select all selects the entire
field; Shift+Left/Right extends a selection. Clipboard access uses the real OS
gesture grant. A failed copy leaves text untouched; rejected or oversized paste
is atomic. Common math glyphs normalize into the scalar grammar: π, ×, ÷, ·, −,
ᴇ, ℯ, √ and ². A pasted root must use parentheses, such as `√(2)`; line breaks,
tabs, unsupported Unicode and internal layout controls are rejected. This is
one-line scalar text, not an arbitrary OS mathematical layout editor.

The small plot samples x from -5 to 5 and y from -10 to 10; it skips undefined
points and large adjacent jumps. It is not a continuity proof or a CAS.

Save uses `FileWriter` to stage a direct replacement of `notebook.txt`; only a
successful commit changes the visible document. This credits the previous
file's length against the app quota. Failed writes retain the editing draft;
an uncertain commit asks the user to reopen and inspect the saved file.
Legacy `notebook.tmp` cleanup waits until the document and package/data pair
have been accepted. Export uses the same staged replacement for
`export.txt`, which can be retrieved with `lefony-sdk files export notebook
export.txt ./export.txt` after closing the app. Export includes the document's
angle/format/digit settings and evaluates each expression at x=1. Format 1 and 2
files open without alteration, retain radians/automatic/9 digits, and become
format 3 on the next successful save. Format 3 stores theme and those math
settings before the expression lines. Unknown/malformed
files disable changes and preserve the original bytes for host recovery.
At startup Notebook inspects the package/data state and reads the entire
document before accepting a pending package upgrade. Unknown schemas and
malformed documents keep editing disabled and retain the recovery pair for
explicit [host rollback](DATA-RECOVERY.md). It never guesses a private-data
migration. An unconfirmed acceptance leaves editing disabled and asks the user
to reopen and inspect the outcome.

See the [implementation ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md) for exact
qualification. Physical input, latency, storage endurance and release bundles
are separate from local emulator evidence.
