# Experimental foreground runtime

The working-tree candidate adds public services 11 and 12 at API revision 3,
with manifest capability 16 (`ForegroundRuntime`). Both physical and VM firmware
compile these services. ARM behavior is tested in the emulator; physical timing,
memory pressure and power behavior remain unqualified. This is not yet in the
downloadable SDK or a completed SDK 1.0 runtime profile.

Existing projects use the freestanding `lefony_event` startup. The explicit
[foreground-newlib-1 project profile](C-RUNTIME.md) now supplies reusable
conventional `main` startup and file/allocation adapters in the ordinary builder.
Library comparison, broader C/C++ qualification and final host bundles remain
required. See [C development](C-DEVELOPMENT.md).

## Negotiation and lifecycle

Include [foreground.h](include/lefony/foreground.h); its fixed-width wire types
are in [foreground_wire.h](include/lefony/foreground_wire.h). For an app that
requires foreground execution, use a schema-1 manifest with `minimum_api: 3`
and `required_capabilities: 16`. Add bit 8 (combined mask 24) if files are also
required. Discover optional features before using them. A schema-0 app cannot
enter this profile. Firmware and website readers must deploy before the updated
SDK distributes packages requiring these contracts.

During the foreground Start callback, call `lefony_program_enter()` once.
Success resumes at the next instruction only after the heap has been cleared
and mapped. This invocation can then keep its own stack and loop across waits;
the OS resumes it instead of starting new callbacks. Do not enter twice or
attempt entry from another callback. Existing ABI 1 apps retain their original
callback, memory, package, signature and private-data contracts.

| Function | Contract |
| --- | --- |
| `lefony_program_enter()` | Select profile 1 during Start; yields while the OS prepares memory |
| `lefony_program_yield()` | Return to normal OS services/input and resume with the same execution state |
| `lefony_program_sleep(ms)` | Wait at least the requested 0–60000 monotonic milliseconds; zero still yields |
| `lefony_program_exit(status)` | Terminate this invocation and queue file cleanup; successful exit never returns |
| `lefony_program_info(&info)` | Copy heap range, stack limit, slice length and presentation counters |
| `lefony_present(pixels,x,y,width,height,stride)` | Validate and copy RGB565 pixels, then yield for OS presentation |

The runtime preempts CPU-bound user execution at a nominal 10 ms slice boundary.
Integer registers, VFP registers, status and stack contents survive preemption
and waits. Privileged service work has separate costs; a 10 ms slice does not
promise that every service completes within 10 ms. One foreground invocation
is supported, with no background jobs or general threading.

Normal input continues during a sleep and updates the input snapshot without
shortening the sleep. OS Home, Back and power handling retain their existing
ownership and termination paths; the ARM proof specifically checks Home during
a CPU loop and a long sleep. Full key-down/up/held-state input is still missing.
There is no complete event queue or powered-off suspend/resume contract yet.

Home/forced close and faults discard uncommitted private bytes. Exit status zero
allows the existing successful private-data close path; nonzero status discards
that staging. File closes that already committed remain durable. In particular,
newlib `exit` can close streams before the OS receives the status. See
[file cleanup and durability](FILES.md#durability-and-cleanup).

## Memory and request validation

Profile 1 adds an 8 MiB OS reservation with a 4 KiB unmapped guard at each end:
8,380,416 writable, non-executable bytes. Query the usable address/length with
`lefony_program_info`; do not hard-code the address. Legacy code/data limits and
the 64 KiB app stack are unchanged. The allocator must account for its metadata
inside the reported heap capacity; this service itself is not `malloc`.

The OS clears 64 KiB per deferred foreground event, allowing ordinary dispatch
between all 128 blocks. User code cannot access the heap until clearing finishes.
Exit/unload removes its mapping, and a new launch clears previous contents.
This bounds each clearing step by bytes; it is not a measured physical latency
guarantee. The reservation also reduces memory available to the OS on both
targets, even when running legacy apps; integrated workloads need qualification.

Service 11 requests are 64 bytes, schema 1, readable and writable by the app.
Initialize a fresh request for each call. Flags, reserved fields and output fields
must be zero on input. Only Enter supplies profile 1; only Sleep and Exit supply
an argument. Return 0 means success, -3 means undeclared/unsupported capability,
and -4 means invalid request, range or lifecycle state. Rejected requests leave
the program running. Public services require an explicitly declared capability;
they do not grant raw peripheral or flash access.

## Pixels and frame timing

Pixels are little-endian RGB565, two-byte aligned. Coordinates and rectangles
must fit 320 × 240; width and height must be nonzero. Stride is in pixels,
between width and 320. The readable source span is exactly
`((height - 1) * stride + width) * 2` bytes. The 40-byte schema-1 request has zero
flags. The runtime validates the complete request before changing the surface.

The OS copies pixels into its composition surface and presents through the
existing display driver. A successful call yields, and the source buffer can
be reused or freed on return. It exposes no framebuffer or DMA ownership.
`frames` counts OS presentations for this invocation; `lastFrameMillis` is the
low 32 bits of the monotonic clock after the most recent presentation, and is
zero before the first. These counters wrap modulo 2³². Existing drawing helpers
can also cause presentations. There is no promised refresh rate, vblank
synchronization or tear-free hardware guarantee.

## Validation

After building the pinned newlib candidate and both firmware targets sequentially:

```sh
.venv/bin/python vm/test-sdk-foreground.py
.venv/bin/python vm/test-sdk-files.py
.venv/bin/python vm/test-sdk-file-lifecycle.py
```

Eight foreground variants cover negotiation, malformed requests, a 6 MiB
allocation, exhaustion, zeroed relaunch, integer/VFP state, minimum sleep,
ordinary input during sleep, copied frames, Home, guard pages and non-executable
memory. Signed file probes exercise streaming, cold output and exit cleanup
through public yields. Reports bind the actual ARM package and firmware hashes;
the [implementation ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md) records results
and remaining qualification. These fixtures do not establish playable Doom or
the complete hosted C/C++ library profile.
