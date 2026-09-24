# Configured C/C++ projects and source format 2

The local SDK candidate supports `project.json` schemas 1/2 and
`lefony-sdk source --format 2`. Matching website reader changes are required
before publication; existing downloadable bundles and deployed services do not
gain support from these source changes. Source formats 0 and 1 remain supported
with their original C++ paths and size limits.

## Host text encoding

SDK metadata, generated C/C++, debug scripts and preview HTML use UTF-8.
SDK-authored text uses LF line endings. Project source and asset bytes retain
their original contents during source exchange; the SDK does not transcode user
files or expand the permitted source-path/manifest character sets.

Redirected CLI stdout/stderr use UTF-8 independently of the host locale.
Interactive consoles retain their native configuration, and importing SDK
helpers does not reconfigure the caller's streams. Compiler path/version output
is decoded strictly as UTF-8. Human diagnostic output may show replacement
characters for invalid bytes; failed compiler output remains in the raw preview
build log, and its failed status is preserved. Invalid UTF-8 metadata is rejected.

The host-text regression disables Python UTF-8 mode and locale coercion and
checks real source/debug/document workflows. This removes reliance on the
[locale-dependent text default](https://docs.python.org/3.13/library/io.html#text-encoding);
native Windows compiler, filesystem, console and full-bundle qualification remain
separate gates in the [host guide](HOSTS.md).

## Select source files and compiler settings

Small projects can still omit configuration: the builder discovers up to 64
`.c`/`.cpp` files under `src/`. Use an explicit source list for larger projects
or to exclude upstream adapters for other platforms:

```json
{
  "schema": 1,
  "sources": ["src/main.c", "src/vendor/engine.c", "src/ui.cpp"],
  "include_dirs": ["src/vendor"],
  "defines": {"SCREEN_WIDTH": 320, "TITLE": "\"Example\""},
  "c_flags": ["-fwrapv", "-fno-strict-aliasing"],
  "cxx_flags": ["-ffp-contract=off"]
}
```

Only `schema` and `sources` are required. Paths are relative to the project,
use `/`, and stay under `src/`. Configuration allows up to 256 unique C/C++
translation units, 32 include directories and 64 defines. Sources are built in
sorted path order; include-directory order is retained. Every referenced source
and include directory must exist. Absolute/escaping paths, symlinks, platform
device names, duplicate fields and unknown settings are rejected.

Macro names are C identifiers of up to 64 characters. Values are signed 32-bit
JSON integers or up to 128 printable ASCII characters passed as a single `-D`
argument; use a string for a C floating-point literal or quoted string literal.
Flags are restricted to `-fwrapv`, `-fno-strict-aliasing`, `-ffp-contract=off` and
`-Wno-error`. The last relaxes warnings for a port without hiding diagnostics.
These settings apply only to project translation units, except the explicit
`LEFONY_PROFILE_HEAP` integer define (`0` or `1`). Enabling it in a schema-2
newlib project also instruments the SDK's allocator hooks; see
[heap diagnostics](TESTING.md#observing-newlib-allocations) for measurement scope,
cost and how to return to an ordinary build. There are no shell commands, response files,
compiler plugins, automatic downloads or user-provided linker hooks.

The normal `build`, `package`, `test` and CMake entry point all use this same
configuration. C remains C11 and C++ remains C++17. `compile_commands.json`
records each selected source and its actual arguments. Build reports record
the configuration and include it in source identity; changes to effective
compiler flags invalidate affected cached objects. The SDK lock continues to
pin the SDK/toolchain independently of app project settings.

Schema 2 additionally requires `runtime: "foreground-newlib-1"` and permits an
optional `arguments` array of up to 16 printable ASCII strings, at most 128
characters each. It selects the [conventional main profile](C-RUNTIME.md).
The manifest must explicitly require API 3 and capability 16; files also need
bit 8. Newlib content hashes join the project lock. Schema 1 does not accept
these new fields and retains its callback behavior. Source format 2 preserves
both configuration schemas; matching website readers validate the same limits.

## Exchange the complete project inputs

```sh
lefony-sdk test
lefony-sdk source --format 2
```

Format 2 carries `.c`, `.cpp`, `.h`, `.hpp` and `.inc` files under `src/`, optional
`project.json`, and the format 1 asset/test/notice/lock inputs. It retains hashed
UTF-8 descriptors and canonical base64 for bounded binary assets. Files outside
these allowlisted roots are excluded; unsupported files inside them fail
validation. There is no recursive upload of the whole project directory.
An explicit source list controls compilation; the source archive preserves
other permitted source/header files too, such as unused upstream platform code.

| Limit | Formats 0/1 | Format 2 |
| --- | --- | --- |
| Files | 64 | 512 |
| Source/notice file | 64 KiB | 256 KiB |
| Individual asset, test, configuration or lock file | 64 KiB | 64 KiB |
| Total decoded file contents | 512 KiB | 4 MiB |
| Encoded source bundle | 1 MiB | 8 MiB |
| Build translation units | 64 | 64 discovered, or 256 explicitly configured |

The new bounds accommodate the measured Doom tree: 192 C/header files totaling
1,696,790 bytes, 80 selected portable C units, and a 139,548-byte largest file.
They also bound parser work and archive extraction. C source and configuration
are rejected by older formats instead of silently omitted. Hash, case-collision,
path, declared-input and size checks run on both SDK and website ingestion.
The website's local-SDK submission request limit is 20,000,000 bytes to cover
the source bundle, existing package and existing listing-media limits together.

This is source exchange and build configuration. The public ABI 1 memory,
callback, embedded-resource and private-data contracts are unchanged. Large
streamed game assets remain a separate file-service concern; conventional
execution is an explicit negotiated profile. Keep original dependency licenses and source notices; a
manifest license does not override incorporated code or SDK terms.

## Validation and rollout

Host tests build an 81-unit mixed project, preserve selected inputs and flags,
rebuild after configuration changes and compare relocated source-roundtrip ARM
bytes. The installed C test runs the extracted package through signed synthetic
installation, normal keys and cold persistence. SDK/website tests share the
same project-validation corpus and separately exercise source boundaries and
the Worker signing/download path.

Deploy compatible website readers before releasing a source-2-writing SDK.
The store `/capabilities` response advertises `source_formats` (`[0,1,2]` in
local-SDK mode, `[0]` in the legacy server-builder mode). Existing immutable
release bytes are not converted. Host qualification and full account/folder
publishing are still governed by the [1.0 plan](../docs/NATIVE-APP-SDK-1.0-PLAN.md).
