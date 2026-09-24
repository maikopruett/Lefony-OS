# Local SDK tests and debugging

`lefony-sdk test` runs all JSON replay files below `tests/`, including nested
directories, in sorted path order. Each case starts
a new ARM guest. `--suite tests/example.json` selects one case; `--suite startup`
selects the explicitly limited startup test. A missing author suite is recorded
as skipped. A failed assertion/fault exits nonzero and remains in `build/run.json`.
Building/testing never authenticates, publishes or touches physical USB.

## Replay schema 1

```json
{
  "schema": 1,
  "name": "counter-input",
  "steps": [
    {"capture": "initial"},
    {"key": "ok"},
    {"capture": "incremented"},
    {"different": ["initial", "incremented"]},
    {"touch": [[0, 200, 160]]},
    {"touch": []},
    {"capture": "reset"},
    {"same": ["initial", "reset"]}
  ]
}
```

Names contain letters, digits, underscores or hyphens and start with a letter.
Each step has exactly one action. Cases contain at most 256 steps / 180 seconds
of requested interaction, and suites contain at most 32 cases. Test JSON is
bounded to 64 KiB. Unknown actions, unsafe capture names, duplicate contact IDs,
out-of-bounds coordinates and references to missing captures are rejected before
QEMU starts. The SDK does not execute author shell/Python hooks.

| Action | Meaning |
| --- | --- |
| `key: "ok"` | Press/release a physical matrix key through normal event dispatch |
| `keys: ["left","shift"]` | Set the held matrix keys; `[]` releases all; use `wait_ms` for the intended hold duration |
| `touch: [[id,x,y], ...]` | Goodix frame with zero to two contacts; empty means release |
| `wait_ms: 300` | Host wait, 0–5000 ms; does not fake a precision guest clock |
| `program_exit: 0` | Wait up to 20 seconds for foreground exit, fail on faults/timeouts, and assert the signed 32-bit status |
| `capture: "name"` | Capture a 320 × 240 frame under `build/tests/CASE/` |
| `same: ["a","b"]` | Assert identical RGB pixels in two earlier captures |
| `different: ["a","b"]` | Assert at least one RGB pixel changed |
| `pixel: ["a",20,30,[0,0,0]]` | Assert exact RGB color at a captured coordinate |
| `relaunch: true` | Send normal Home/release, drain installed storage for at most 10 seconds, then reload the raw preview or reopen the installed app with fresh globals |

The [Prime key names](contracts/keys.json) are checked against the firmware's
authoritative matrix. Keys include arrows, `ok`, `backspace`, `zero` through
`nine`, `shift`, `alpha`, `back`, `home`, and `apps`. The dedicated power key is
not a matrix key and is deliberately excluded from this replay format.
Key injection waits for the OS to observe release before the next press. Test
cadence is a model synchronization choice, not physical input-latency evidence.

The base ABI 1 callback receives primary coordinates and contact count. The
optional `input.h` snapshot service adds both contact IDs/coordinates, fuller
key tokens/modifiers and bounded text. Replays exercise it through the same
Goodix/keypad path; they do not inject a prepared snapshot. Forms/Tables and
Graph Explorer replays cover editing/focus, modal cancellation, pan, pinch,
long press, trace and keypad alternatives. The negotiated
[API 4 input stream](INPUT.md) adds held/down/up masks and ordered key/touch
events, including overflow and focus reset. Full mathematical layout remains
separate work.

## Persistence

`test --workspace NAME` and `run --workspace NAME` use persistent synthetic NAND.
The SDK signs the local package with the explicitly public emulator fixture,
installs through the normal modeled USB app protocol, verifies readback and
launches through the normal installed-app loader. Physical firmware never
trusts that fixture. Real firmware/NAND captures are unnecessary.

Every replay case cold-boots the same workspace. Put a save-and-Back scenario
before a reopen assertion when testing persistence; inspect the saved frame
after the next process starts. The runner closes installed apps normally at the
end and waits for storage to finish. A test that presses Back explicitly already
closed the app. A changed package at the same version is rejected; increment
`app.json` or reset a disposable workspace. No downgrade bypass is provided.

Apps retain the ABI 1 private byte store and can use negotiated
[checkpoints/migrations](DATA.md) and [named-file APIs](FILES.md).
Workspace snapshots preserve committed synthetic state. They cannot qualify
physical flash endurance, real power loss or recovery.

## Reports and diagnostics

Replay `build/run.json` schema 1 includes exact package/SDK/firmware/QEMU identities,
cases, steps, assertions, failures and skips. Normal callback reports include
PC, event, result, service count, last service, fill pixels and modeled callback
time when supported by the VM. Old firmware may return unavailable diagnostics;
they are recorded as null. Stack peaks and fault addresses are not measured.

Layer labels distinguish ARM interaction and installed workspaces. Reports say
`developer-local`, `independently_verified: false` and `physical: not_tested`.
They contain no private data exports. They are editable local evidence, not
certification or source/binary correspondence proof. Source format 0 excludes
tests and locks, so retain those separately in the app repository.

The replay engine writes `status: running` before validating the requested test
files or starting QEMU. It saves completed cases between replays. Ctrl-C records
`status: cancelled`, retains completed cases/steps and marks the active case/step
as cancelled; later cases remain `not_run`. Validation and unexpected execution
errors record `status: failed`. A hard-killed process can leave `running`, which
means an incomplete result and does not establish that any process is still alive.
Successful suites retain the existing passed/failed/skipped summary; incomplete
suites add counts for their `running`, `cancelled` or `not_run` cases. If the
initial report cannot be written, the replay engine refuses to start an emulator.
Use a project-relative JSON filename for `--suite`, or `all` for `tests/**/*.json`.
Key release and socket cleanup still run after Ctrl-C. A secondary cleanup error
does not turn interruption into an ordinary failed case and continue the suite;
its exception type is retained in the case's `cleanup_errors` when available.

A failed startup replaces an earlier `build/run.json` success with `status:
failed`, an unknown (`null`) app result and `os_responsive: false`. Interruption
records `status: cancelled`; it cannot leave an earlier startup pass in place.
Emulator failures include a separate `emulator_failure` summary: exact loaded
package/SDK/firmware/QEMU hashes, phase, control operation, process exit at the
failure and after cleanup, and log lengths/completeness. Cleanup termination is
distinguished from a process that had already exited. These host failures are
separate from the app's own fault/exit diagnostics.

Raw local diagnostics live in a new `failure-*` directory below `build/emulator`
for startup/run, `build/tests/NAME/emulator` for a replay, or
`build/preview/emulator` for preview. The preview page links to its failure
details and logs. Each retains at most the last 64 KiB of QEMU stderr and guest
UART, with total byte counts and truncation markers. Stderr is drained while
QEMU runs so a full host pipe cannot strand the emulator. Log-save failures do
not replace the original error. Raw logs can contain local paths and belong to
the developer's build directory; they are not embedded in the structured test
report or automatically included in an app source archive.
Starting a new preview clears the previous emulator-failure attribution while
retaining its saved frame/data; a later build or validation error does not link
to the earlier emulator's logs. The earlier diagnostic files remain available.

## Observing app resources

`lefony-sdk test --measure-resources` (also accepted by `run`) opts into
instrumented ARM emulator execution. It requires matching VM firmware with
resource-profile version 1; older firmware fails clearly before app load.
Without this option the runtime keeps its original initial stack contents and
reports no runtime resource observations. No physical control or app ABI changes.

Each case's `runtime.resources` in `build/run.json` records:

- Code/static ELF segment sizes and the heap reservation actually mapped.
- The deepest changed stack byte and deepest user SP sampled at SVC, IRQ and
  fault boundaries, in bytes within the separate 64 KiB stack.
- Their maximum as `stack_observed_bytes`, with an advisory when that observation
  reaches 90% of capacity; an out-of-range sampled SP is reported separately.
- Loads, completed unloads, execution slices, samples, services, frames, faults
  and maximum instrumented slice duration. Counters saturate with an explicit flag.

The profiler paints unused stack bytes with `0xa5` only for successfully
validated loads whose complete inner LFAPP0 SHA-256 matches the requested
package. It aggregates those loads, including relaunches and normal close,
until the runner finishes cleanup. Another package cannot replace or contribute
to these measurements. Fault details survive later successful loads and cause
the measured test to fail. Invalid loads contribute no new measurements.

The [Arm calling convention](https://github.com/ARM-software/abi-aa/blob/main/aapcs32/aapcs32.rst)
defines a descending stack with its extent in SP. The profiler scans at explicit
snapshots and before unmapping, using the app's mapped cache alias. SP sampling
also detects reserved frames that have not been written. Nevertheless, short
excursions between samples, untouched reservations and writes matching the paint
can escape observation. Direct writes to stack addresses also affect the scan.
These are observed extents, not a proved worst-case stack requirement or a
guarantee of spare capacity. `stack_peak_bytes` stays null. The
[FreeRTOS discussion of untouched reservations](https://www.freertos.org/FreeRTOS_Support_Forum_Archive/March_2018/freertos_uxTaskGetStackHighWaterMark_is_too_optimistic_2aac6effj.html)
describes the same limitation of paint-only high-water measurements.

The heap reservation is not allocated/live heap use. By default,
`heap_peak_bytes` remains null. Static arenas are included in static data.
Instrumentation changes initial unused stack bytes and adds overhead; slice
durations, debugger pauses and host elapsed times do not qualify physical
performance. Keep ordinary, uninstrumented regression runs as separate evidence.

### Observing newlib allocations

For a `foreground-newlib-1` project, explicitly add this integer define to its
existing `project.json` configuration, then rebuild and run with
`--measure-resources`:

```json
"defines": {"LEFONY_PROFILE_HEAP": 1}
```

Preserve any other project defines. This setting enables app-local allocator
hooks in both debug and release profiles; choosing a release profile does not
disable it. Remove the define or set it to `0` for an ordinary build. Callback
projects cannot enable it. The diagnostic ELF/package has a different identity
and follows the same install/version rules as any other changed package.

The pinned newlib allocator records allocated chunk bytes and its arena extent
at completed allocator unlocks. This includes alignment and allocator metadata,
and sees transient overlap when `realloc` allocates before freeing the old block.
Freeing blocks reduces current usage while retaining the peak. It does not
measure requested payload bytes, static buffers or usage within custom
suballocators such as Doom's zone. Arena extent includes free allocator space
and is reported separately from allocated bytes and the OS heap reservation.

The host validates a 40-byte diagnostic section in the exact package ELF and
requests heap-profile version 1 from matching VM firmware. The VM collects the
record only from that package's initialized writable data. Measurements cover
matching loads through runner cleanup; another package cannot contribute.
Peaks aggregate across relaunches, while current values and allocator observation
counts describe the latest sampled load. Fault/unload collection retains peaks.
An incomplete update reports `partial`; invalid records fail the measurement.
An instrumented app with no allocator observations reports `not_observed`.
Neither status is a measured zero or supplies the top-level `heap_peak_bytes`.
For `observed` results that field equals `heap.allocated_peak_bytes`; inspect
`resources.heap` for the method, scope, counters and separate arena values.
This is a workload observation, not a worst-case memory bound.

The hooks scan allocator free lists at each unlock and preserve `errno`.
This can add substantial cost to allocation-heavy workloads. Merely building
with the define incurs that cost even without `--measure-resources`; ordinary
builds leave the hooks off. No allocator library is replaced, no new application
service is exposed, and heap collection has no physical-device control. Older
VM firmware explicitly refuses heap collection for an instrumented package;
ordinary packages retain the existing stack-profile protocol.

Maintainers exercise real written/untouched stack frames, guard faults, default
zero initialization, conventional main, relaunches and package attribution with
`vm/test-sdk-resource-profile.py`. The four proving-app harnesses accept
`--measure-resources` to attach observations to their existing user journeys.
`vm/test-sdk-heap-profile.py` covers real allocator transitions, short-lived
peaks, no-allocation/default builds, relaunches, faults, incomplete/corrupt records
and package attribution. Notebook, minigzip and Link Gallery additionally accept
`--profile-heap --measure-resources` to instrument their temporary projects.
For Doom, set the define in a separate prepared project and use the existing
gameplay harness with `--measure-resources` and a seeded synthetic workspace.

## Debug sessions

Run `lefony-sdk debug`, then `lefony-sdk debugger` from the same project in
another terminal. The desktop candidate bundles ARM GDB; source users provide
`arm-none-eabi-gdb` on PATH. See [native host tooling](HOSTS.md).
The generated `build/debug.gdb` selects matching symbols, maps source paths,
connects through the relay to the private per-session socket, sets a hardware
breakpoint at `main` or `lefony_event` and continues. Use `next`, `step`, `bt`, `info registers`, or
`print` from GDB. Ctrl-C in the SDK terminal ends the VM and removes its socket.
This is a full-system host debugger; it is never a physical app capability.

The debugger follows [QEMU's local GDB interface](https://www.qemu.org/docs/master/system/gdb.html).
Debug pauses/stepping alter timer behavior, so deadline qualification must run
separately. SDK reports mark debugger sessions `debug-session`.

For a reported PC, use `lefony-sdk symbolize PACKAGE PC`. The SDK verifies both
the load image and debug ELF against the build report before running
`arm-none-eabi-addr2line`. An incorrect package or changed symbol file is rejected.
ARM exception PCs account for [the exception LR offset](https://documentation-service.arm.com/static/5e8e2d19fd977155116a71be).
Malformed pointers, illegal instructions, stack guards and deadlines are tested
in `vm/test-native-app-sdk.py`; these adversarial fixtures are not store apps.

## Platform library qualification

Maintainers run `tests/test_sdk_math.py`, `tests/test_sdk_linear.py`,
`tests/test_sdk_graphics.py` and `tests/test_sdk_architecture.py` under the host
suite. These include sanitizers, high-precision numeric reference cases,
constructed matrix solutions, raster buffer/clipping cases, sampler/gesture
limits and transaction interruption experiments. `vm/test-sdk-math.py`,
`vm/test-sdk-graphics.py` and `vm/test-sdk-input.py` exercise the actual ARM
payload and normal screen/input paths. The transaction experiment remains
host-only and is not a firmware durability test. The math oracle is a development
dependency; SDK app builds require no mpmath/Python numerical runtime.

Contract negotiation checks live in `tests/test_sdk_contracts.py` and
`vm/test-sdk-contracts.py`. The shared 77-case corpus covers canonical schemas,
unknown required/optional features, integer boundaries and old-reader rejection.
The VM check also verifies a noncompliant host cannot install an incompatible
update, then cold-boots and reads back the original app. Use its optional
`--old-firmware` argument with a preserved older VM ELF for reader rejection.

Resource checks live in `tests/test_sdk_resources.py`, `vm/test-sdk-resources.py`
and the `reference-cards` example replay. Host tests cover deterministic
conversion, exact colors, source roundtrip, corrupted/rehashed malformed tables,
read-only ELF placement and incremental rebuilds. The ARM bound check validates
a complete 524288-byte resource bundle plus cancellation and lookup under the
normal callback deadline. The example checks real PNG/text presentation through
a signed installed app, keys, Goodix touch and capture cancellation.

## Frozen companion qualification

Maintainers can run the actual macOS desktop companion against the bundled ARM
guest and QEMU USB model:

```sh
.venv/bin/python vm/test-sdk-frozen-companion.py \
  --bundle /path/to/lefony-sdk --output build/frozen-companion-check
```

Use a fresh output directory and the source revision matching the bundle. The
harness verifies bundle hashes and source identity, builds external C projects
with the relocated executable, and runs its companion with Homebrew/checkout
access denied. Ten cases exercise fixed/chunked streaming, origin/TLS rejection,
timeout, cancellation, truncated input and host interruption. Normal OS pairing,
worker shutdown and exported cache bytes are checked. The fixture uses a local
CA and synthetic storage; it never opens a physical calculator. These checks
do not qualify real USB electrical behavior, other native hosts or production
accounts. Exact completed runs and their limitations belong in the SDK ledger.

For store transport changes, run `tests/test_sdk_store_http.py` with the account,
upload, publication, listing and TLS tests. These include real local TLS, exact
maximum-size transfers, blocked DNS/native verification, a worker that stops
reading IPC, partial IPC output, worker death, and Ctrl-C during startup/cleanup.
Each case checks that the worker and IPC thread stop.

The macOS desktop check uses the actual relocated executable with
Homebrew/checkout access denied:

```sh
.venv/bin/python vm/test-sdk-desktop-store-deadline.py \
  --bundle /path/to/lefony-sdk --output build/frozen-store-deadline
```

It reads the native credential store only to require an empty ephemeral fixture
origin. No account is issued or saved. Local first-login failures cover stalled
TLS/headers, a slowly delivered response, Ctrl-C, truncation and redirects; the
harness checks request counts, credential absence and process shutdown. Use the
separate `vm/test-sdk-desktop-accounts.py --native-credentials` check for the
account lifecycle with temporary native credentials and verified final cleanup.
