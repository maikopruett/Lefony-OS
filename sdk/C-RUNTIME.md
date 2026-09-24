# Conventional C/C++ runtime candidate

`foreground-newlib-1` is an explicit development profile for the working-tree
SDK. Projects define ordinary `main`; the SDK supplies startup, allocation and
file adapters using public API 3 foreground services. Firmware still runs one
protected foreground app. The [selected function matrix](C-LIBRARY.md) defines
library behavior and limits. The [library comparison](../docs/NATIVE-APP-C-LIBRARY-COMPARISON.md)
selects newlib for this profile. Doom and minigzip have local ARM journeys;
broader profile and physical qualification required by SDK 1.0 remain open.
Existing projects keep their callback profile unless explicitly changed.

## Build a project

Use the `c-main` template, or add this project configuration:

```json
{
  "schema": 2,
  "runtime": "foreground-newlib-1",
  "sources": ["src/main.c"],
  "arguments": ["input-file"]
}
```

The app manifest must use schema 1, `minimum_api` at least 3 and required
capability 16. Add capability 8 for named files (combined mask 24). These are
explicit requirements; the builder never rewrites them silently. Project
schema 1 retains its existing field set and callback behavior. Older SDK/store
readers reject project schema 2, so deployment must precede distribution.

```sh
lefony-sdk new /tmp/c-main --template c-main
lefony-sdk --project /tmp/c-main package
lefony-sdk --project /tmp/c-main source --format 2
```

The normal build/package, debug, workspace and CMake entry points share this
configuration. Creating the project works offline; its library lock is written
on the first build. The [example](examples/c-main/README.md) counts saved visits
using stdio and checked close. It contains no custom startup or syscall adapter.
Run/test without a named workspace uses a disposable signed installation in
synthetic storage, so foreground entry uses the normal loader. Name a workspace
to retain data between separate invocations. Use a `program_exit` replay assertion
to check a finite program's status with a bounded 20-second wait. Startup-only
tests still do not prove useful completion or interaction.

The profile uses newlib 4.6.0.20260123, built for Cortex-A7 ARM hard-float with
the SDK's pinned GCC. A bundle can include the verified sysroot. Maintainers
and source-kit users can prepare it with:

```sh
python3 scripts/build_sdk_newlib.py
```

The recipe downloads only its pinned archive and verifies SHA-256 before
extracting/building it. `--archive PATH` uses that archive offline. Builds use
fresh source/object trees and canonical temporary paths for reproducible debug
records. This setup requires the pinned compiler and `make`; it is separate
from ordinary project builds, which perform no downloads or dependency builds.

The recipe enables 64-bit/C99 formatted I/O and applies a hash-checked source
adjustment that widens newlib's `FILE`
descriptor fields to match Lefony's non-reused 31-bit handles. Library and app
objects must be rebuilt together with matching headers. Old sysroots are rejected;
existing projects explicitly adopt the new dependency with `lock --update`.
See [the descriptor adjustment](C-LIBRARY.md#full-width-file-descriptors-and-rebuilds).

The candidate uses full newlib reentrancy (`--disable-newlib-reent-small`). The
small variant failed plain-C exit when optional atexit metadata was absent;
the C++ case had pulled that metadata in and did not expose the failure. Both
language paths must pass. Atexit registration uses fixed upstream capacity
because dynamic exit-handler allocation is disabled; callers must check it.

Resolution uses an explicit `LEFONY_SDK_NEWLIB` directory when set, otherwise
`sdk/runtime/newlib` in a bundle, otherwise `build/sdk-newlib` beside the source
SDK. The directory must contain `candidate.json`, `COPYING.NEWLIB` and the
reported install tree. All 134 installed header files, both library archives,
compiler version, source pin and notice are checked before building. A missing
or changed dependency fails clearly. The project lock records content hashes
without recording the developer's local dependency path. `lock --update`
explicitly adopts changed SDK/library identities.

## Startup and language behavior

The SDK enters foreground mode before pre-initializers and C++ dynamic globals.
The OS supplies initialized data and zeroed BSS, then clears/maps the guarded
heap. Initializers execute once per launch and can allocate and wait. After
initialization, startup calls `main(argc, argv)` once. `main(void)` is also valid.
Returning from main calls newlib `exit` with the returned status. Normal exit
runs registered `atexit` handlers, C++ global destructors and finalizer arrays,
then stream cleanup and the OS exit service. Home and faults do not run user
destructors; the OS owns forced resource cleanup.

`argv[0]` is the manifest app ID. Up to 16 configured arguments follow it, each
at most 128 printable ASCII characters, including empty strings. `argc` includes
the app ID; `argv[argc]` is null. Argument strings and the vector are writable
for the invocation. These are build-time inputs, not a shell or device command
line. There is no expansion of environment variables, quotes or backslashes.

C sources use C11 and C++ sources C++17. The supplied newlib headers use C names
such as `<stdlib.h>` and `<stdio.h>` in either language. The current compiler
bundle has no libstdc++ headers/library: `<cstdlib>`, standard containers,
iostreams and general C++ `new`/`delete` are not supplied by this profile.
Exceptions and RTTI remain disabled; there is no general threading contract.
Existing Lefony app-side helpers and their namespaced math functions remain
linked independently of newlib's standard math functions.

The builder places GCC's compiler-owned headers before newlib and disables
ambient target include directories. This preserves the compiler's stdatomic,
stddef and stdint definitions while resolving libc headers from the verified
sysroot. A successful zlib atomic-initialization workload does not qualify
every C11 atomic type or multithreaded application behavior.

## Library and service boundary

| Area | Candidate behavior |
| --- | --- |
| Allocation | `malloc/calloc/realloc/free` use the 8,380,416-byte foreground heap; allocator metadata shares that capacity; exhaustion returns failure and `ENOMEM` |
| Strings/formatting/math | Real pinned newlib routines; the conformance suite exercises a subset, not every exported function |
| Files | Real descriptor/stdio adapters over authenticated API 2 files; short transfers, seek/stat, directories and atomic rename use bounded requests and public yields |
| Per-app quota | API 7/capability 256 supplies `lefony_file_quota`; writes enforce 32 MiB of mutable data with `EDQUOT`, preserving existing oversized roots. See [FILES.md](FILES.md#per-app-quota-policy) |
| Directory/space queries | API 6/capability 128 adds `lefony_file_list` and `lefony_file_space`; generation-checked pages and committed/staged/shared usage are described in [FILES.md](FILES.md) |
| File durability | `fflush` sends buffered bytes to staging; successful `fclose` commits a writer. API 5/capability 64 adds `fsync(fileno(stream))` after checked `fflush` for saving while the stream remains open; see [FILES.md](FILES.md) for requirements and errors |
| Explicit discard | Local API 12/capability 8192 adds `lefony_file_abort` and the C++ `FileWriter` adapter. Staged edits are discarded without closing other readers; failed commits still require inspection. See [writer cancellation](FILES.md#explicit-writer-cancellation) |
| Timing | Use `lefony_millis` and `lefony_program_sleep`; ordinary input does not shorten sleep |
| Calendar/process services | `_gettimeofday`, `_times`, process identity/signals fail with `ENOSYS`; no fabricated clock date or process support |
| Standard streams | No console, terminal or redirected stdin/stdout/stderr contract; descriptor operations on 0/1/2 fail |
| Exit | Completed file commits remain durable even on nonzero exit; staged private bytes are discarded for nonzero/forced exit |

See [files](FILES.md) and [foreground execution](FOREGROUND.md) for limits,
ownership, cancellation and error contracts. File waits yield through service
11; they use no VM-only execution hooks. Library buffers and app pointers remain
inside the app's protected memory. Allocation overflows, unsupported formats,
library facilities beyond the tested subset and physical service latency remain
part of qualification; a successful link is not a support guarantee.

## Packaging and validation

Source bundles retain project schema 2 and the exact runtime/arguments inputs.
Compatible website ingestion validates the same bounded schema and manifest
requirements without executing uploaded source. Maintainers can include a
portable ARM sysroot with its full upstream source archive and notices:

```sh
python3 scripts/package_native_sdk.py --output build/sdk-main.tar.gz --newlib build/sdk-newlib
```

The desktop packager requires `--newlib`, `--gdb-runtime` and `--libusb` for its
current complete-toolchain candidate. Runtime files are selected from a
verified allowlist; logs, unrelated build outputs and local credentials are not
included. Omitting the option produces a source kit that requires separate
sysroot setup before using this profile. A bundled library does not qualify
native Windows or other host journeys by itself.

Host tests check source roundtrips, exact relocated ARM bytes, incremental builds,
dependency changes and manifest requirements. The installed ARM checks exercise
constructors that allocate/wait, arguments, main, errors, `atexit`/destructors,
files and cold launches. Release evidence belongs in the OS checkout's
`docs/NATIVE-APP-SDK-1.0-PROGRESS.md` implementation ledger. App-linked files
have a scoped MIT alternative for the twelve original conventional runtime,
interface and linker files plus the startup-argument template. See the exact
grant in the kit's `LICENSE.md` and `LICENSES/MIT.txt`. Third-party libraries
retain their notices; the complete distribution audit remains a release gate.
