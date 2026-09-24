# C library support candidate

The `foreground-newlib-1` profile provides C11/C++17 source builds, conventional
`main` and a pinned app-linked newlib. This guide defines the selected library
surface being qualified for SDK 1.0. It does not promise a complete hosted C
environment or every symbol exported by newlib. See [C runtime](C-RUNTIME.md)
for setup, startup, arguments, heap size and language limitations.

The ARM conformance fixture is `tests/native/sdk_c_profile.c`, driven by
`vm/test-sdk-c-profile.py` in the OS checkout. It runs ordinary signed apps,
uses the real allocator and file service, and exports committed results through
the public USB file protocol. Reports record exact SDK, library, firmware and
QEMU identities. The implementation ledger records completed results and limits;
the presence of a test or a successful build alone is not a qualification pass.
The [library comparison](../docs/NATIVE-APP-C-LIBRARY-COMPARISON.md) records why
ordinary C/C++ programs use newlib and why the small callback subset is retained.

## Selected function and behavior matrix

| Area | Functions in the selected profile | Behavior exercised by the ARM fixture |
| --- | --- | --- |
| Allocation | `malloc`, `calloc`, `realloc`, `free` | `max_align_t` alignment, zeroed allocation, preserved bytes on growth/shrink and failed growth, multiplication/size overflow, real heap exhaustion, free/reuse and a 6 MiB allocation |
| Memory | `memcpy`, `memmove`, `memset`, `memcmp`, `memchr` | Return values, byte contents, search misses and overlapping moves in both directions |
| Strings | `strlen`, `strcpy`, `strncpy`, `strcat`, `strncat`, `strcmp`, `strncmp`, `strchr`, `strrchr`, `strstr`, `strspn`, `strcspn`, `strpbrk`, `strtok` | Terminators, bounded padding/concatenation, searches and tokenization; callers still own buffer sizing |
| Character classification | `isalnum`, `isalpha`, `isblank`, `iscntrl`, `isdigit`, `isgraph`, `islower`, `isprint`, `ispunct`, `isspace`, `isupper`, `isxdigit`, `tolower`, `toupper` | Every ASCII value 0–127 and selected EOF behavior in the C locale; arguments must be EOF or representable as `unsigned char` |
| Locale | `setlocale`, `localeconv` | Explicit C locale and `.` decimal point; translated locales and Unicode classification are not in this profile |
| Formatting | `snprintf`, `vsnprintf`, `fprintf` | Integer, hexadecimal, string and floating-point formatting, including 64-bit limits and C99 size/offset/hex-float formats; truncated output and the required length from a zero-sized `snprintf` destination |
| Parsing | `strtol`, `strtoul`, `strtoll`, `strtoull`, `strtod`, `strtof`, `atoi`, `atol`, `atoll`, `atof`, `sscanf`, `vsscanf`, `fscanf` | End pointers, no conversion, signed/unsigned integer bounds, floating overflow/underflow, signed zero, bounded string scans and conversion failure |
| Search/arithmetic | `qsort`, `bsearch`, `abs`, `labs`, `llabs`, `div`, `ldiv`, `lldiv`, `srand`, `rand` | Ordering, found/missing keys, quotient/remainder and repeatable sequences; `rand` is not a cryptographic source |
| Binary64 math | `sin`, `cos`, `tan`, `atan2`, `sqrt`, `hypot`, `exp`, `log`, `pow`, `log10`, `fabs`, `floor`, `ceil`, `trunc`, `round`, `fmod`, `frexp`, `ldexp`, `modf`, `copysign` | Representative finite values, negative rounding, decomposition, signed zero and domain/pole errors; this is not an exhaustive ULP qualification |
| Classification macros | `isfinite`, `isinf`, `isnan`, `signbit`, `fpclassify` | Finite values, infinity, NaN, zero and the smallest normal binary64 value |
| Streams | `fopen`, `fdopen`, `fileno`, `fclose`, `setvbuf`, `fflush`, `fread`, `fwrite`, `fseek`, `ftell`, `rewind`, `fgetpos`, `fsetpos`, `feof`, `ferror`, `clearerr` | Files beyond 64 KiB, user-provided buffers, short underlying transfers, buffered updates across storage chunks, append after seek and live sync, reader snapshots across replacement/rename, seek gaps, pushback/position restoration, EOF/error clearing, valid compatible descriptors and cold persistence |
| Character/string I/O | `getc`, `fgetc`, `ungetc`, `putc`, `fputc`, `fputs`, `fgets` | Pushback, line boundaries, EOF and writing to a read-only stream |
| File descriptors | `open`, `read`, `write`, `close`, `lseek`, `fsync`, `stat`, `fstat`, `mkdir`, `rename`, `unlink`, `remove` | Short transfers, zero-filled seek gaps, append after seek, metadata, atomic rename, directories, stale handles, access errors and reader/writer limits |
| Exit | `atexit`, `exit`, `_Exit` | Reverse registration order, normal cleanup of unclosed streams on main return and nonzero exit, repeated `fflush(NULL)`, immediate-exit discard and preservation of explicitly committed files; C++ initializer/destructor coverage is in `vm/test-sdk-main.py` |
| OS time/waits | `lefony_millis`, `lefony_program_sleep`, `lefony_program_yield` | Real OS waits/yields with unsigned elapsed time; no fabricated calendar or process-time result |
| Explicitly unsupported services | `gettimeofday`, `times`, `getpid`, `kill`, `isatty` | Calendar/process calls fail with `ENOSYS`; terminal detection returns false with `ENOTTY` |

### Limits callers must handle

Allocation metadata shares the 8,380,416-byte app heap. Failed allocation returns
null with `ENOMEM`; failed nonzero `realloc` leaves the original allocation
owned by the caller. Zero-sized allocation may return a freeable pointer or
null; callers must not use it as storage. Integer arithmetic outside the tested
library conversions follows C rules, including undefined signed overflow.

Optional [newlib heap diagnostics](TESTING.md#observing-newlib-allocations) report
allocated chunk and arena peaks for an instrumented ARM workload. They include
allocator padding/metadata, exclude static buffers and custom suballocator
usage, and add free-list scanning overhead. Ordinary builds leave them off.

The target has 8-bit bytes, 32-bit `int`/`long`/pointers and 64-bit `long long`
and `double`. Floating-point tests cover representative binary64 behavior;
general floating-environment control and every special-value combination are
not advertised. Check `errno` only where the function defines it, and clear it
before conversions where zero is also a successful result. `atoi`-family calls
are for valid representable input; use `strto*` when failure must be diagnosed.

Strings and files contain bytes. The C locale has ASCII classification and a
period decimal separator. This does not give UI text or file paths a new
encoding contract: the [text/UI](UI.md) and [file](FILES.md) limits still apply.

There are four snapshot readers and one staged writer per app. Descriptor
transfers may stop after 2048 bytes; callers loop and check errors. stdio handles
those short transfers through its real newlib buffering. `fflush` transfers
buffered bytes into staging. Check `fflush`, then `fsync(fileno(stream))` for a
durable live save. A successful writer `fclose` also commits; a failed close is
an error requiring inspection, not proof that the previous file was replaced.
API 12 additionally offers explicit staged-writer cancellation. See
[files](FILES.md) for snapshots, quotas, commit points and cancellation.

On an update stream (`r+b` or `w+b`), use a positioning operation between
reading and writing; output may also be followed by `fflush` before input.
Input that reaches EOF permits subsequent output without positioning. An
append stream (`a+b`) can read at a chosen position, but every write still goes
to the end, including after `fsync`. Seeking beyond EOF alone does not enlarge
a file; a later ordinary write fills the gap with zero bytes. Reader handles
retain their committed snapshot across replacement and rename; reopening by
name observes the newly committed file.

The `stdio-update`, `stdio-append`, `stdio-snapshots` and `stdio-position` ARM
cases exercise these transitions with exact host-verified exports and cold
readback. The largest file is 262,175 bytes; its edits cross two storage-chunk
boundaries. These cases use real newlib buffering and public file operations,
without replacing syscalls or editing the synthetic filesystem. The
[implementation ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md) binds each run to
its actual firmware and debug/release package. The underlying stream rules
follow newlib's [open](https://sourceware.org/newlib/libc.html#fopen),
[position](https://sourceware.org/newlib/libc.html#fseek) and
[pushback](https://sourceware.org/newlib/libc.html#ungetc) contracts; durable
commits and reader snapshots are Lefony-specific behavior.

Normal main return and `exit`, including a nonzero status, run stream cleanup.
Buffered named-file writers are flushed and closed, committing successful
closes. `_Exit`, Home and faults do not run this cleanup; writes since the last
successful close/sync remain uncommitted. Automatic exit cannot report a failed
close to the application. For user-visible save success, explicitly check
flush/sync or close before reporting completion. An application-provided stdio
buffer must remain alive until its stream closes; a local buffer that expires
when main returns cannot safely be used during later exit cleanup.

`fdopen` is qualified for an already valid descriptor with a compatible mode.
This newlib configuration has no `fcntl` adapter and does not validate every
invalid descriptor or mode mismatch at `fdopen` itself. Later I/O still enforces
the OS handle and access checks. There is no `dup`, general descriptor recycling,
console or redirected stdin/stdout/stderr contract. Operations on descriptors
0, 1 and 2 fail. `tmpfile`, pipes, processes, threads, signals, dynamic loading,
POSIX filesystem parity and a general C++ standard library are not supplied.

## Full-width file descriptors and rebuilds

The pinned build explicitly enables newlib's long-long and C99 formatted I/O.
Without these options, upstream's default configuration can silently treat a
64-bit format as a 32-bit one. The profile tests both formatting and scanning
with the required options; their settings are part of dependency identity.

Lefony deliberately does not reuse file handles during an OS instance, so a
closed or cancelled handle cannot affect a newer file. Valid handles fit in a
positive 31-bit `int`. Upstream newlib's `FILE` structures store `_file` as
`short`; that truncates valid handles once the counter exceeds 32,767.

The pinned build recipe applies the checked `stdio-descriptor-32-v1` source
adjustment to both normal and large-file `FILE` structures. Their descriptor
fields become `int`. Every other header byte, including upstream notices, is
preserved. The contract records exact before/after hashes; unexpected source is
rejected, and repeating the preparation is harmless. The upstream archive pin
and firmware ABI remain unchanged.

This adjustment changes the app-local newlib structure layout. Rebuild the
library and **all app objects with matching headers**; do not mix old objects or
libraries with the revised headers. The SDK rejects old sysroot reports and
incompatible headers, records the adjustment in dependency identity and requires
an explicit `lock --update` for an existing project. Previously compiled apps
retain their original library behavior until rebuilt.

The boundary fixture seeds the synthetic emulator's OS handle counter with GDB,
then uses normal `fopen`, `fdopen`, read/write, sync, close and stale-handle checks
across 32,767, 65,535 and near `INT_MAX`. This tests numeric boundary behavior;
it does not stand in for thousands of physical opens or flash endurance testing.
