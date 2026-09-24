# Experimental public API reference

The local API 12 [writer-abort candidate](FILES.md#explicit-writer-cancellation)
adds explicit discard of uncommitted named-file writes. C programs use
`lefony_file_abort`; C++ programs can use `lefony/file_writer.h` for direct
staged replacements with explicit commit. The new operation requires declared
capability 8192; old request layouts and ABI 1 retain their meanings.

The API 11 [app-channel candidate](CHANNEL.md) adds session-scoped USB messages
with OS-owned consent and bounded queues. Its host HTTPS worker is separate;
the `companion` command and `lefony/https.h` protocol now bridge it to app
requests. Link Gallery is the local connected-app candidate; full qualification
remains open.

The API 10 [system-service candidate](SYSTEM.md) adds bounded clock/battery,
OS palette/preferences, temporary brightness and user-initiated clipboard APIs.
See its guide for validity, gesture ownership and lifecycle limits.

The header paths below are the supported include boundary. Ordinary apps execute
through callbacks; the negotiated [foreground candidate](FOREGROUND.md) can
resume one invocation across waits. There are no background threads. Never retain pointers
to callback stack storage. Return regularly so Home and cancellation can run.
The runtime enforces a modeled 1000 ms callback budget including services.

## `lefony/app.h` — ABI 1

`Event` numbers are Start=0, Key=1, Tick=2, Touch=3, Close=4. Export
`extern "C" void lefony_event(Lefony::Event,uint32_t,uint32_t)`.
Start initializes the app, while Close allows staging final state on normal
exit. Fault termination can skip Close; it is not a durable checkpoint.

`fill(Rect)` draws a positive rectangle entirely inside 320 × 240. Colors are
RGB565 values 0–65535. `text(Text)` takes 0–128 printable ASCII bytes and copies
them during the call. Newline, UTF-8 bytes and control characters are rejected;
missing glyphs are not silently transliterated. Input pointers must remain valid
for the call. Service success is 0, unsupported is -3, and bad arguments are -4.
Drawing is privately composed and presented after a successful callback.

`millis()` is monotonic modulo 2^32. Subtract unsigned values for elapsed time;
do not count Tick callbacks or assume a precision scheduler. `Input::x/y` decode
signed coordinates. `Input::phase` gives Down/Move/Up/Cancel; contact count is
`second >> 8`. Multiple contacts cancel basic button capture.

`readData(offset,buffer,length)` / `writeData(offset,buffer,length)` transfer up
to 4096 bytes inside the private 64 KiB store. Read destinations must be writable.
They return transferred bytes or a negative error. The namespace exists only
for installed apps. Missing data is an error, not a fabricated zero record.
Writes stage until normal close; faults discard staged changes. Check all
lengths, magic/schema fields and counts before accepting saved state. No stored
pointer, implicit upgrade migration, atomic checkpoint or named file is provided
by these legacy byte-store services. Named files use the separate extension below.

## `lefony/runtime.h` — app-local support

`Arena<N>` owns N bytes, aligned to 16. `allocate(size,alignment)` returns null
for zero size, insufficient capacity, non-power-of-two alignment or alignment
over 16. Failure does not consume capacity. `used`, `remaining`, `peak` and
`failures` expose accounting. `reset()` invalidates every allocated pointer and
retains peak/failure counters. Arenas do not construct/destruct C++ objects and
do not define a global throwing `new`. Their memory is part of static app data.

`Vector<T,N>` stores N value-initialized objects in the app. `push`/`pop` return
false at full/empty boundaries; `at` returns null out of range. `clear` resets
the logical count; removed elements are not securely erased. Element assignment
must be bounded and compatible with the freestanding language subset.

`Task::step(budget,work)` runs at most budget units and updates `completed`.
Cancellation or a false work result stops it. Each work unit must itself be
bounded. Call step from successive callbacks to keep input responsive. There
is no hidden OS scheduling or unlimited privileged compute call.

Compiler-required `memcpy`, `memmove`, `memset` and `memcmp` are app-local code.
They obey ordinary buffer lifetime/size contracts. `memcpy` requires nonoverlap;
use `memmove` for overlapping regions. Invalid buffers can fault the app.
No allocation, locale, I/O or general libc is implied by these four routines.

## `lefony/extensions.h` — optional services

Initialize `Capabilities`, then call `discover`. It requires size 48, version 1,
and zero reserved fields. Success fills features, ABI, geometry and quotas;
old ABI 1 firmware returns -3. Capability bit 1 announces rectangle batches;
bit 2 announces copied input snapshots; bit 4 announces app Back navigation;
bit 8 announces the experimental API 2 named-file service; bit 16 announces
the API 3 foreground runtime and copied-pixel services; bit 32 announces the
[API 4 input stream](INPUT.md) with held/down/up keys, ordered key/touch events
and overflow/focus resynchronization.
Schema-0 manifests keep these services optional and need compatible fallbacks.
Explicit schema-1 manifests may require them; see the [package contract](../docs/NATIVE-APP-CONTRACT-EXTENSIONS.md).
ABI 1 itself and this 48-byte discovery structure are unchanged.

`batch(rects,count)` copies 1–64 descriptors; the total requested area must not
exceed 76800 pixels. Every rectangle obeys `fill` bounds. All validation precedes
drawing; an invalid later rectangle leaves the whole batch unapplied. The array
remains app-owned and can be reused after return. No asynchronous handle, DMA,
physical framebuffer, transparency or scaling is exposed.

## `lefony/files.h` — experimental named files

Service 10 accepts bounded asynchronous requests in an authenticated installed
app namespace. It provides four snapshot readers, one writer, seek/stat,
directories, deletion and atomic replacement. Check completion errors; writes
become durable when writer CLOSE completes. API 5 adds SYNC (capability 64) to
commit while retaining the descriptor and position. See [the complete file contract](FILES.md)
for request ownership, limits, cleanup and the distinction between libc buffering
and durable commits. The service compiles into both targets; the maintainer newlib
adapter now waits through the public API 3 foreground service. The explicit
[foreground-newlib-1 profile](C-RUNTIME.md) supplies conventional startup in
ordinary developer builds. API 6/capability 128 adds paged directory listing and
committed/staged/shared usage queries, with conventional runtime helpers.
API 7/capability 256 adds a per-app quota query; growth is limited to 32 MiB
of mutable data with oversized existing roots preserved. See [quota policy](FILES.md#per-app-quota-policy).
Explicit host-side [per-file USB import/export](FILE-EXCHANGE.md) is available
in matching development firmware. Whole-app archive/restore and physical
qualification remain unfinished.

## `lefony/data.h` — private-data checkpoints and migrations

Service 14 requires API 8 and declared capability 512. It provides asynchronous
inspection, a copied private-data checkpoint, explicit migration, upgrade
acceptance and cancellation through a 64-byte request. Named-file descriptors
must be closed before submitting an operation. Poll a fresh request using the
returned token; submission success is not durable completion. Later private
edits remain unsaved after a checkpoint completes. See [the data contract](DATA.md)
for generation/schema checks, Close/fault behavior and retained recovery pairs.
Explicit [host backup/restore and rollback](DATA-RECOVERY.md) operate over USB
while the app is closed; they do not add an app syscall or grant installer access.
Whole-app file archives and general damaged-data recovery are still pending.

## `lefony/foreground.h` — experimental resumable execution and pixels

Services 11/12 require API 3 and explicitly declared capability 16. The foreground
Start callback can enter profile 1 once, then preserve its stack across user-code
preemption, yield, sleep and copied RGB565 presentation. It adds a guarded,
non-executable heap and exposes memory/frame counters. See [the complete contract](FOREGROUND.md)
for entry/exit rules, strict requests, limits, buffer ownership, compatibility,
validation and remaining libc/input/physical qualification.

## `lefony/input.h` — copied input snapshot prototype

Initialize `InputSnapshot`, then `readInput(snapshot)` within a callback. The
128-byte request requires size 128, version 1 and a zero `reserved` field. The
whole destination must be writable. Success is 0, malformed pointers/headers
return −4 without writing a partial response, and older firmware returns −3.
Check discovery's `InputSnapshots` bit, or handle unsupported directly. ABI 1
callback event numbers and original `first`/`second` values are unchanged.

The OS copies the current callback's event, monotonic modulo-2³² time, sequence,
key/text/modifier state or touch contacts. It does not return driver pointers or
permit input injection. Sequence increments per callback and wraps modulo 2³²;
loading another app starts a new sequence. Tick, Start and Close snapshots have
empty key/text/contact state. Retained copies are ordinary app values, not live
OS handles. Reads within one callback give the same snapshot.

`InputKey` preserves existing logical codes and adds operators, parentheses,
square/root, trig/log, exponent and modifier/tool keys. `physicalKey` is the
native KPP row×8+column corresponding to the event's base key, using
`contracts/keys.json`; 255 means unmapped. OS-remapped/special events may not
retain a physical base key. It is not an independent key-down matrix snapshot.
`modifiers` records the event's Shift/Alpha page plus current Alpha-lock state.
`repeatFactor` is the OS repetition acceleration factor (1–65535), not a repeat
count or proof of a separate physical press. Raw key release events are not
provided by this version. Home, Apps and power retain OS ownership. Back exits
normally unless the app explicitly requests the bounded navigation behavior below.

`textBytes` is 0–32 and `text` is length-delimited UTF-8, not necessarily
NUL-terminated. C0/C1 controls, invalid/overlong encodings, surrogates and out-of-range
scalars are excluded. OS math templates containing internal control bytes, or
text longer than 32 bytes, set `TextUnavailable` and leave an empty payload;
apps can use the logical key to offer a supported composition action. The pure
`validInputText` helper validates the same bounded payload. ABI 1's drawing
service still accepts ASCII only; receiving Unicode does not imply a glyph
renderer. No clipboard or another application's text is exposed.

Touch snapshots include up to two Goodix contact IDs and both coordinate pairs,
sorted by stable ID. Coordinates are 320×240 canvas coordinates. `touchPhase`
is Down=0, Move=1, Up=2, Cancel=3; `ContactsChanged` means finger-set membership
changed and gesture baselines should be reset. Up/Cancel set `contactCount=0`
and retain the ending coordinates/IDs. The unused second contact is zero for
one-contact reports. Lost/replaced IDs and malformed streams cancel capture;
tracking resumes after all fingers lift. Modal and focus transitions still
require app-side capture cancellation. This service is available on both
targets; only the test inputs themselves are VM-only.

`navigationDepth(depth)` uses service 9 with a 16-byte size/version-tagged request
(version 1, reserved zero). Depth 0–8 succeeds with 0; malformed requests/depth
return −4; older firmware returns −3. At depth >0, Back is delivered as a Key
callback with `InputKey::Back` in the snapshot; base ABI 1 `first` stays Unknown.
At depth 0 it exits normally. This value is app-scoped and resets on launch;
faults cannot retain Back interception. Home, Apps and power always remain
OS-owned. It is not a request to trap the user or suppress system termination.
Keep it synchronized with the actual app stack and provide an on-screen Back/
Cancel action. The `UI::Navigation` helper performs the updates for its own stack.

## `lefony/numeric.h` — prototype numeric subset

`Numeric::Statistics` uses double-precision Welford accumulation, at most 65536
finite samples. `add` rejects invalid/non-finite/overflowed calculations without
changing prior state. `mean`, `range` and `variance` leave output unchanged when
empty. Sample variance (default) divides by n−1 and requires two values;
population variance divides by n. Status values are Ok, Empty, Invalid, Domain,
Limit and Cancelled. NaN/infinity are errors, never plausible results.

`Numeric::bisect(function,low,high,tolerance,limit,cancel)` evaluates entirely
in app space. Bounds/tolerance must be finite and ordered, tolerance positive,
and limit 1–256. The continuous function must bracket a sign change. Cancellation
is checked before work and each iteration. Non-finite values return Domain;
no convergence or floating-point stagnation returns Limit. Ok requires an exact
endpoint zero or absolute residual no larger than tolerance. The algorithm does
not certify continuity, units, conditioning or relative accuracy.

This subset is independent of built-in variables and preferences. Poincare
expressions, symbolic operations, matrices, distributions, units, angle modes,
serialization and general plots remain roadmap work; they are not stub APIs.
All original SDK headers/runtime helpers/examples retain CC-BY-NC-SA-4.0 notices.

## `lefony/expression.h` — bounded scalar expression prototype

`Expression::Context` parses and evaluates in app memory. It does not read or
modify built-in calculator variables, preferences or the Poincare pool. It is
not a Poincare compatibility interface or a full symbolic/numeric engine.

```cpp
Lefony::Expression::Context context;
context.set("x", 7);
const char source[] = "sqrt(x*x)+2^-2";
auto parsed = context.parse(source, sizeof(source)-1);
if (parsed.status == Lefony::Expression::Status::Ok) {
  auto answer = context.evaluate(parsed.expression);
  // Check answer.status before using answer.value (7.25 on success).
}
```

The grammar accepts ASCII decimal/scientific literals, parentheses, `+ - * /`,
unary signs and real powers `^`. Powers associate to the right; `-2^2` is −4.
Unary functions are `abs`, `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`,
`exp`, `ln`/`log` (natural log), `log10`, `log2`, `floor`, `ceil`, `round` and
`erf`. Constants `pi` and `e` are reserved. All names are case-sensitive.
Variables contain 1–15 ASCII letters/digits with an initial letter; at most 16
finite bindings are stored. `set` returns false without changing bindings for
invalid input or full capacity. `clearVariables` removes bindings without
changing the expression. Other functions return Unsupported. Units, complex
values, user functions, symbolic operations and implicit multiplication remain
unsupported by this parser.

Contexts start in radians. `angle(Math::Angle::Degrees)` or
`angle(Math::Angle::Gradians)` sets a local override;
trig inputs and inverse-trig outputs use that mode. Invalid enum values return
false without changing it. `angle()` reads the current mode. This never changes
the OS or another context. Transcendentals use the app-linked `Math` subset below.

Source length is explicit, 1–256 bytes; the caller keeps that range readable
through `parse`. Embedded NUL/UTF-8 bytes are invalid, not implicit terminators.
At most 128 nodes and 16 nested parser levels are allowed. Literal decimal
exponents have magnitude at most 308. Decimal conversion is bounded floating
arithmetic, not a correctly-rounded decimal parser; intermediate overflow is
rejected. IEEE double arithmetic can round and underflow to zero. These limits apply even
when unused names or subexpressions could later simplify away.

Every parse attempt invalidates prior handles. Handles belong to their specific
context and are not serializable; passing an old/foreign handle returns Stale.
Generation exhaustion returns Limit. Store source text with an app-owned schema
instead of storing a handle, context bytes or engine pointers. On a parse error,
`position` is the zero-based byte where parsing stopped; on an evaluation error,
it identifies the failing operator/name. Failed parsing does not change bindings.

Evaluation is iterative, at most one pass over 128 nodes, with an optional
`evaluate(handle,cancel)` callback checked before every node. Cancellation returns
Cancelled and the completed step count; it does not return a partial answer as
success. Contexts use approximately 4.5 KiB plus a 1 KiB evaluation scratch array;
exact target sizes are in build evidence. Limit context count yourself with app
memory budgets. Calls run within the normal app deadline, never in privileged
OS code. The cancellation callback must itself return promptly.

Statuses are Ok, Invalid (syntax/arguments), Limit (source/depth/node/exponent
budget), Unbound (unknown variable), Domain (division by zero, negative square
root, `0^0`, zero to negative power, non-finite result), Cancelled, Stale and
Unsupported (unrecognized function). Result values are only
meaningful for Ok. NaN/infinity are never returned as successful answers.

## `lefony/math.h` — app-linked binary64 math

The original OpenBSD/fdlibm C subset is pinned by per-file source hashes and
included in every source kit. Only used functions survive link-time section
collection. C symbol names are prefixed `lefony_math_`; private compatibility
headers are not on app include paths. No errno, exceptions, allocator, host I/O,
shared calculator state or privileged math service is involved. The library is
little-endian binary64 and compiled with the SDK's pinned hard-float toolchain.

`Math` provides `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `sqrt`,
`exp`, `expm1`, `log`, `log1p`, `log10`, `log2`, `pow`, `hypot`, `erf`, `erfc`,
`abs`, `floor`, `ceil`, `trunc`, `round`, `fmod`, `copySign` and `nextAfter`.
Angles for these raw functions are radians. `round` uses nearest integer with
halfway values away from zero. `fmod` is the remainder with truncated quotient.
`scale(x,n)` multiplies by a power of two; `fraction(x,whole)` writes the truncated
integer part and returns the fractional part; `fractionExponent(x,exponent)`
writes the binary exponent and returns the signed fraction.

Raw functions retain IEEE-style signed zeros and return NaN/infinity for
applicable domains/overflow. `pow(0,0)` is 1 in this raw library; the expression
parser deliberately rejects that expression as Domain. `checked(value)` reports
`Numeric::Status::Ok` for finite values or `Numeric::Status::Domain` otherwise and retains the
original value. `finite` is also available. `Pi`, `E`, `radians(value,Angle)` and
`degrees(radians)` / `gradians(radians)` are app-local helpers; an invalid Angle
returns NaN. SDK Angle ordinals are radians=0, degrees=1 and gradians=2; system
preference ordinals are degrees=0, radians=1 and gradians=2. Convert explicitly.

760 finite reference cases compared with mpmath at 400 decimal digits pass with
an eight-ULP tolerance on host and ARM, alongside helper/domain/signed-zero cases.
Inputs include subnormals, maximum finite doubles and large-angle reduction.
Host ASan/UBSan also pass. This corpus does not establish an exhaustive ULP bound
or correctly rounded results. Scalar calls run within the app deadline; use
cooperative work between callbacks when processing many values.

## `lefony/number_format.h` — explicit numeric presentation

The C-compatible app-linked newlib-profile helper
`lefony_format_number(destination,capacity,value,digits,format)` formats a finite
binary64 value with 1–14 significant digits in the C locale. Format 0 is automatic
(`%g`), 1 is scientific (`%e` with digits minus one fractional places), and 2 is
engineering notation. Engineering uses the same rounded significand with an
exponent divisible by three, including subnormal values. For 123456 and four
digits the results are `1.235e+05`, `1.235e+05` and `123.5e+3`. Automatic notation
removes trailing fractional zeros; scientific/engineering retain significant
zeros. The engineering exponent is signed without zero padding. Negative zero
is preserved. This helper never reads or changes OS preferences.

Success returns bytes excluding NUL. Capacity includes NUL. Errors are -1 for
invalid pointers/options or formatting failure, -2 for insufficient capacity and
-3 for nonfinite input. Failures leave all destination bytes unchanged. Callers
retain ownership and provide writable storage; this is not a privileged service
that validates arbitrary pointers. Decimal input parsing is a separate contract.

## `lefony/linear.h` — bounded dense matrices

`Linear::Matrix<Rows,Columns>` owns a zero-initialized binary64 array with each
dimension in 1–16. `at(row,column)` returns a pointer within that array or null
for an invalid index; `finite()` validates its current values. There is no heap.
Public `values` are row-major and remain app-local, never wire structures.

`multiply(A,B,out)`, `transpose(A,out)`, `solve(A,B,out,tolerance,cancel)` and
`inverse(A,out,tolerance,cancel)` support aliased output and preserve it on
failure. Multiply accepts an optional cancellation callback. Solve handles
multiple right-hand columns using scaled partial-pivot Gaussian elimination and
back substitution. The relative pivot tolerance defaults to 1e-12 and must be
finite in (0,1). Singular includes pivots rejected as too small relative to their
original row scale. It is not a condition-number or accuracy certificate.

Statuses are Ok, Invalid (nonfinite inputs/bad tolerance), Domain (nonfinite
intermediate/result), Singular and Cancelled. Cancellation is checked before
each solve setup/elimination/back-substitution row or multiply output row.
The largest multiply has 4,096 inner terms; solve has fewer than 8,192
elimination/back-substitution terms plus bounded pivot scans. Scratch for
the largest solve is 4,224 bytes plus scalars, and inverse adds a 2,048-byte
identity. All work remains under the normal app deadline. The cancellation
callback itself must be bounded. No determinant, decomposition object or sparse
matrix contract is implied.

Host sanitizer and ARM cases cover 120 constructed systems at dimensions
1/2/3/4/8/16, inverse residuals, aliasing, pivoting, scale differences, singular
and near-singular systems, invalid values, overflow and every solve cancellation
checkpoint. Failed operations preserve sentinel outputs.

## `lefony/expression_input.h` — expression text composition

`Expression::edit(buffer,snapshot)` handles selection arrows, Delete, supported
operators, trig/inverse-trig/log functions, Pi, Exp and the XNT variable `x`.
Prime Log inserts `log10(`; Ln inserts `ln(`. Functions insert an opening
parenthesis, and the user supplies the closing one. Alpha text takes precedence
over mathematical token mapping. Other text passes through
`Expression::insertText(buffer,text,bytes)`, which accepts up to 1024 input bytes
and atomically replaces the selection after normalization. Printable ASCII is
preserved; π→`pi`, ×/·→`*`, ÷→`/`, −→`-`, ᴇ/ℯ→`e`, √→`sqrt`, and ²→`^2`.
Roots require parentheses in the resulting grammar. Unknown Unicode, malformed
text and controls (including tabs/newlines) return `TextStatus::Unsupported`;
input or destination overflow returns `Full`. Neither changes text/selection.
Empty input returns `Ok` without deleting the selection. Successful insertion
does not prove the resulting expression parses. Obtaining clipboard bytes is a
separate gesture-controlled [system service](SYSTEM.md).

## `lefony/ui_model.h` / `lefony/ui_controls.h` — UI prototype

These are app-side helpers. They use fixed storage, the original drawing API,
optional copied input and optional bounded Back navigation. They do not expose
Escher objects, driver pointers, a framebuffer or cross-app state.

`Box::contains` uses half-open bounds; `intersect` checks edges with 64-bit
arithmetic so extreme signed coordinates cannot overflow. Nonpositive extents
are empty. `Row`/`Column::take(extent)` consume the available width/height with
a nonnegative gap, clamp the final cell and return an empty box when exhausted.
They do not infer scrolling or reposition an off-screen action automatically.

`Focus<N>` holds 1–64 nodes (32 by default). `add` requires unique nonzero IDs
and positive bounds. `move(sign)` cycles through enabled items in insertion
order; `select(id)` selects an enabled ID, and `enable` adjusts availability.
No enabled item means focused ID 0. `confirm()` returns the focused ID. Keyboard
movement, selection and confirmation cancel outstanding touch capture.

`touch(phase,contactCount,x,y,changed)` returns a node ID only on a matching
single-finger Down/Up within its bounds. Leaving bounds, multiple contacts,
membership changes and Cancel discard capture. A disabled topmost overlapping
node blocks touch-through. Fresh Down is required after cancellation. `cancel`
must be called on screen/modal/focus loss and Close; `clear` does this while
removing nodes. Rebuilds retain IDs/values only, never pointers to old controls.

`TextBuffer<N>` has capacity 2–1024 bytes including NUL. It maintains UTF-8 byte
indices on code-point boundaries for caret and selection. `insert` accepts a
validated 0–32-byte chunk and replaces the selection atomically; zero length
deletes it. Full/invalid input returns false and preserves text and selection.
Self-insertion is supported. `move(sign,extend)` moves by one code point (or
collapses selection); `erase` removes the selection or previous code point.
`insertText` accepts a complete larger UTF-8 payload, validating all chunks before
changing the original value. Zero length deletes the selection, as with `insert`.
`selectAll`, `clear`, `text`, `size`, `caret` and selection endpoints are exposed.
This is code-point editing, not grapheme-cluster, bidirectional or IME layout.

`SliderModel(min,max,value)` clamps values within unsigned inclusive bounds;
an inverted range collapses to its minimum. `move(sign)` changes by one,
`set(value)` clamps, and `value()` reads it. Touch uses the same phase/contact
conventions as Focus and the widget's track, inset ten pixels at each end.
Width must be at least 21 pixels. Down starts a draft drag; Up commits locally.
Cancel, leaving bounds, contact changes or multiple contacts restores the Down
value. `cancel()` must also run on screen/focus changes. Persistent saving remains
the application's responsibility. [Notebook](UI.md) demonstrates the model.

`Canvas` clips to a subrectangle of the 320×240 display. Fill, outline and text
work are bounded; `error()` retains the last negative drawing-service result.
Text inputs have explicit length at most 1024 bytes; at most 46 glyph positions
are considered per line. The pinned small font is 7×14. Partially clipped glyphs
are omitted, and non-ASCII code points use a visible `?` fallback until a proper
glyph/asset renderer is available. The theme supplies spacing and RGB565 tokens.

`button`, `toggle`, `field` and `progress` draw consistent focused/pressed/disabled
states with text/checkmark/caret feedback. Fields horizontally scroll to keep the
caret visible. Progress clamps completed to total; total zero displays an empty
track. Applications own control values, action dispatch, validation/error text,
table/list models and any scrolling beyond the field. `UI::edit` handles text,
Delete and Shift-arrow selection; expression-specific composition remains explicit.

`UI::read(baseInput,snapshot)` uses the optional input service and falls back on
−3 to ABI 1's arrows/digits/decimal/minus and primary touch data. Other service
errors return false. `UI::Navigation<N>` holds up to eight screen/focus ID pairs.
Push/pop update OS Back depth before changing the stack; failed requests preserve
it. Unsupported older firmware still permits software Back/Cancel controls and
reports `hardwareBack()==false`. Pop returns the prior screen and focus ID;
rebuild the target's controls and restore that ID if it still exists.

[Forms and Tables](examples/forms-tables/README.md) exercises these APIs with
normal keyboard/Goodix input and inspected frames. Rich menus, choices/sliders,
general scrolling/text layout, localization, complete glyphs, assets and advanced
gestures remain roadmap work; this header does not claim a finished Escher replacement.

## `lefony/graphics.h` / `graphics_screen.h` — clipped raster drawing

Portable primitives call a supplied `sink(x,y,width,color)` with clipped
horizontal spans; returning false stops the primitive with OutputFailed. Other
statuses are Ok and Invalid. The clip is intersected with 320×240. There is no
anti-aliasing or allocation, and caller buffers remain readable for the call.

`line(clip,a,b,color,sink)` validates finite endpoints in ±1e9, clips the segment,
rounds pixel endpoints and uses bounded integer rasterization (at most 320
pixels). Fully clipped lines return Ok without output. `circle` supports outline
or filled circles with radius 0–512 and center x in −1024..1344, y in −1024..1264.
It emits at most 4,104 clipped spans; duplicates are permitted. Invalid arguments
emit nothing. A sink failure may leave already emitted spans visible.

`image(clip,x,y,width,height,stride,pixels,bytes,sink,transparent,key)` validates
all dimensions before output: width 1–320, height 1–240, row stride between
width×2 and 640 bytes, and buffer length at most 153600 covering every source
row. Pixels are little-endian RGB565, 1× scale, optionally skipping one transparent
color. Equal adjacent pixels form a span. No compression, runtime format decoder,
alpha blending or resource/package schema is implied.

`Graphics::Screen` owns 64 rectangle descriptors, coalesces consecutive spans,
and flushes within 64-rectangle/76800-pixel syscall limits. Call `flush()` explicitly
after rendering; destruction performs no drawing. Service −3 selects original
fills for that instance, and any other negative result is retained by `error()`.
Errors stop subsequent work; earlier successful batches may already be visible.
`calls()` counts attempted drawing calls and `pixels()` counts queued pixels,
including overlaps. These are workload counters, not timing or display-frame
measurements. Presentation remains OS-owned at callback completion.

## `lefony/plot.h` — resumable curve sampling

`Plot::View` holds finite x/y bounds within ±1e6, with each span at least 1e-6.
`pan(dx,dy)` shifts by fractions of the current range, each in [−1,1].
`zoom(factor,anchorX,anchorY)` accepts factor 0.125–8 and normalized anchors 0–1;
invalid or out-of-range changes preserve the view. `project(point,box)` maps
world coordinates into the clipped pixel viewport; invalid views/empty boxes
produce NaN coordinates.

`Plot::Curve::begin(options)` validates then replaces its state. Options define
the view/box, increasing finite parameter interval within ±1e6, 1–256 coarse
intervals, midpoint error tolerance 0.25–16 pixels, depth 0–8 and at most 4096
function evaluations. Defaults are 32 intervals, 1 pixel and depth 6. The fixed
stack has nine segments. No function objects or foreign handles are retained.

Call `step(budget,function,emit,cancel)` from successive callbacks. Budget is
0–64 evaluations per step. Keep the function/view semantics consistent until
completion or cancel/restart. The function returns a world Point, allowing
Cartesian `(t,f(t))`, parametric `(x(t),y(t))` or caller-converted polar curves.
The emitter receives pixel Point pairs and returns false on output failure.
Nonfinite/out-of-range projections and unresolved high-error segments become
gaps; the finite midpoint test cannot prove continuity or find every narrow
feature. It is deliberately not a root/domain theorem.

Progress reports status, evaluations, emitted segments, gaps, completed coarse
intervals and total intervals. Statuses are Idle, Running, Complete, Invalid,
Limit, Cancelled and OutputFailed. Complete with gaps is distinct from a fully
resolved curve; Limit may leave a partial plot. Invalid begin/step arguments
preserve the previous task. Cancel is checked between evaluations; callbacks
and function/emitter/cancel bodies still have the normal app deadline.

## `lefony/gestures.h` — viewport gestures

`UI::Gestures(bounds)` consumes copied input and emits Begin, Pan, Pinch, Tap,
LongPress, End, Cancel or None. Pan uses a five-pixel threshold, then incremental
pixel deltas. Pinch reports incremental center translation and old/new separation
ratio; ratios use separations of at least eight pixels. Apply a bounded zoom
policy appropriate to the view. Tap requires one finger, no drag/hold, and
release before 500 ms. LongPress is emitted once by a Tick after 500 ms using
unsigned monotonic time, including rollover.

Capture starts inside bounds and may continue outside. Adding/removing the
second finger rebases without a jump when an existing ID survives. Reordering
the same IDs is allowed; replacement IDs, inconsistent membership flags,
invalid contacts or Cancel discard capture. Release after a multi-touch
transition cannot become a tap. Key/Start/Close discard capture; call `cancel()`
on modal or focus loss as well. An Up at a displaced position cannot create a
false tap. These viewport semantics differ from button capture in `Focus`.

Host sanitizer and ARM fixtures cover geometry/buffers, bounded sampler work,
discontinuity gaps, cancellation and gesture transitions. Graph Explorer's normal
Goodix replay covers actual pan/pinch/hold/trace and button cancellation, with
reviewed frames. No physical touch-feel or 20-fps claim follows from those tests.

## `lefony/resources.h` and `assets.json` — local resources

An opt-in `assets.json` contains exactly `schema: 1` and `resources`, an array
of 1–32 records. Each record has a unique lowercase `id` (letter followed by
0–22 letters/digits/underscore/hyphen), an `assets/` relative `path`, and `type`
`blob` or `rgb565`. RGB565 accepts an optional uint16 `transparent` color key.
Inputs are regular files of 1–65536 bytes; symlinks, traversal, platform-reserved
names and case collisions are rejected. The total declared input budget,
including the configuration, is 524288 bytes. Source export additionally counts
code, tests, locks and notices in that same source budget.

Blob conversion preserves bytes. RGB565 conversion takes a single-frame PNG,
1–320 by 1–240 pixels, with pinned Pillow 12.3.0. Channels quantize with
`r >> 3`, `g >> 2`, `b >> 3`, then encode little-endian uint16 pixels. No color
profile transform, resizing or dithering occurs. Alpha must be 255, or 0 with an
explicit color key; partial alpha and opaque pixels that quantize to the key are
errors. Image headers are bounded before decoding. JPEG/BMP decoding, font
conversion, alpha blending and compression at runtime remain unsupported.

The converter writes `build/generated/resources.bin` and a generated C++ array.
It sorts IDs, uses no timestamps, and reports input/output SHA-256 hashes and
the converter version in `build/build.json`. Source export requires `source
--format 1`, which retains original assets and configuration. No conversion runs
on the website. SDK locks pin the converter; editing an asset rebuilds the
generated translation unit. Generated resources are counted within the original
1 MiB code reservation. The `embedded_resource_bytes` report is a subset of
`code_bytes`, not an additional allocation.

`Resources::embedded` and `embeddedBytes` are generated read-only symbols.
Call `Bundle::open(data,bytes[,cancel])` explicitly, usually during Start; there
is no global initializer. It validates a maximum 524288-byte immutable bundle,
all table bounds/types/IDs, and CRC-32 before exposing any resource. `Ok` replaces
the view; `Invalid` or `Cancelled` preserves its prior view. Cancellation is
polled for every table entry and every 1024 CRC bytes. Worst-case work is 32
entries and a bytewise CRC over 512 KiB; it executes in app user mode under the
normal callback deadline. No I/O, allocation or privileged service is involved.

`count`, `name(index)`, `at(index,out)` and `find(id,out)` provide bounded borrowed
views. Missing/invalid indices or IDs return null/false and preserve `out`. Keep
the bundle bytes alive and **immutable** while any view is used; changing them
after validation violates the ownership contract. `Resource` supplies data,
length, kind and RGB565 dimensions/stride/transparency. Pass these to
`Graphics::image` to render through a clipped span sink. Raw pointers must be
valid app memory; this is not a privileged pointer-validation service.

The app-local wire format is LFRSRC1 plus NUL, version 1, with a 32-byte header
and 64-byte entries. Header words at 8/12/16/20/24/28 contain version, count,
exact total bytes, table offset 32, data offset `32+64*count`, and standard CRC-32
of bytes from 32 onward. Each entry has a zero-padded 24-byte ASCII ID and ten
uint32 words: kind (1 blob, 2 RGB565), offset, bytes, width, height, stride,
flags (0/1 for color key), key, reserved 0, reserved 0. IDs are strictly sorted;
payloads are contiguous and fill the bundle exactly. Blob image fields are zero;
RGB565 has stride `width*2` and length `stride*height`. CRC is corruption
detection; the unchanged app signature authenticates distribution bytes.

The [Reference Cards example](examples/reference-cards/src/main.cpp) uses only
public APIs for PNG/text resources, native controls, keys and touch cancellation.

## API 9 typography and C++ UI candidate

[The UI guide](UI.md) documents service 15, capability 1024, the four OS fonts,
bounded Unicode/measurement/clipping contract, configurable widgets, Notebook
and actual ARM preview with source/layout inspection. API 9's combined feature
mask is 2047. Existing services, ABI and package/storage formats remain unchanged.
