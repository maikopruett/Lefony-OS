# C library selection for SDK 1.0

Decision, 2026-09-13: retain **newlib 4.6.0.20260123** for the explicit
`foreground-newlib-1` profile. Keep the existing callback profile for compatible
applications. Picolibc is a measured alternative, not a second supported SDK
runtime. This selects the library; broader SDK and physical qualification remain
open under the [1.0 plan](NATIVE-APP-SDK-1.0-PLAN.md).

## Alternatives and decision

| Alternative | What exists | Cost of meeting the required profile | Decision |
| --- | --- | --- | --- |
| Extend the callback subset | Four compiler memory routines, bounded app-side arenas/containers, selected math and SDK service helpers | Add and maintain conventional initialization/exit, a general allocator, C parsing/formatting, stdio buffering and its error/cleanup behavior | Retain for existing apps; do not grow this into a first-party libc |
| Newlib | Pinned maintained library, ordinary C/C++ startup, real heap and file adapters, existing Doom/minigzip integrations | Carry the checked full-width descriptor adjustment and qualified configuration; keep the function matrix and port regressions current | Selected for ordinary C/C++ programs |
| Picolibc 1.8.12 | Smaller linked conformance program; real ARM allocation, parsing, math, descriptor and explicit-close cases pass | Adapt syscall names and reentrancy; resolve stream errors, automatic close and repeated global flushing; qualify C++ and actual ports before switching | Retain isolated evidence; no production switch |

The callback alternative is a source inventory, not a fabricated performance
comparison. `sdk/lib/memory.cpp` defines `memcpy`, `memset`, `memmove` and
`memcmp`; `sdk/include/lefony/runtime.h` provides bounded C++ helpers. The
callback branch of `sdk/tools/build.py` links these, selected app-side math and
`libgcc`. It does not link a general allocator or stdio. The same ordinary-main
fixture cannot run there without implementing the facilities being compared.
No equivalent workload footprint or run time is claimed for that alternative.

Both libraries require real OS integration: see the
[newlib syscall boundary](https://sourceware.org/newlib/libc.html#Syscalls) and
[Picolibc OS interfaces](https://github.com/picolibc/picolibc/blob/1.8.12/doc/os.md).
Our experiment reuses Lefony's actual bounded foreground heap, file requests,
yielding waits and exit service. It never links dummy-host or semihosting code,
fabricates syscall success or recycles file handles.

Picolibc's smaller footprint is useful, but the selected newlib workload fits
the existing code/data reservations. A switch currently adds file-lifecycle
work and a second port qualification effort. Extending the small callback
subset would put substantially more standard-library implementation under
Lefony maintenance. The current evidence therefore favors keeping newlib and
finishing the required applications and recovery work.

## Comparison method

The shared `tests/native/sdk_c_profile.c` fixture is compiled as ordinary C11
with GCC 16.2.0, Cortex-A7 ARM hard-float, `-Os` and section garbage collection.
All groups are compiled into each executable; a configured argument selects the
group for each separately installed signed app. The firmware, QEMU, 8,380,416-byte
heap, 64 KiB stack and foreground linker script are common. File bytes are
imported/exported through the public SDK protocol against synthetic storage.

`vm/test-sdk-c-profile.py` drives the experiment. Normal newlib runs use the
ordinary SDK builder. The isolated `vm/sdk_picolibc_probe.py` compiler reuses
SDK startup and the exact OS/file adapter logic, changing only syscall symbol
names, the newlib-specific reentrant rename hook and the zero-valued `O_BINARY`
compatibility spelling. It compiles against Picolibc's own types, including
64-bit `off_t`. Existing explicit negative-offset/size checks remain in force.

The experimental project names `picolibc-comparison-1` and cannot be built by
the production SDK as a supported profile. Earlier baseline project inputs
retained the common newlib profile name, but their build reports and library
hashes explicitly record the experimental override. Final reruns use the
unambiguous experimental name.

The production builder also compiles Lefony's namespaced OpenBSD math helpers;
the comparison compiler omits them. The fixture calls the standard libc/libm
names and unused namespaced helpers are discarded by the production link.
The link maps record which objects actually contribute. Picolibc packages math
in `libc.a`; comparing its almost-empty `libm.a` with newlib's archive would be
misleading. Measurements use loaded app segments, not raw archive size.

Newlib uses its checked [profile configuration](../sdk/contracts/newlib.json),
including C99/long-long formatted I/O and full reentrancy. Picolibc uses double
formatting, no CRT, semihosting, thread-local storage or init/fini ownership,
and explicitly enabled `stdio-exit-flush`. The build recipe also supports a
separate `--fast-bufio` candidate to test its optional buffered-I/O path.
Upstream Picolibc source is unchanged in both candidates.

## ARM evidence and limitations

The final comparison uses identical C source and harness inputs for all three
library configurations. All planned newlib phases pass. Each Picolibc variant
fails four initial phases; the corresponding four cold repeats are not
attempted. Failure is the actual test outcome, not a passing qualification.

| Library/configuration | Passing phases | Failed phases | Cold repeats not attempted | App code bytes | Static data bytes, including BSS | Initialized data bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Newlib selected profile | 23 | 0 | 0 | 113,552 | 11,796 | 1,744 |
| Picolibc, default buffering | 15 | 4 | 4 | 59,828 | 9,740 | 52 |
| Picolibc, `fast-bufio=true` | 15 | 4 | 4 | 60,660 | 9,740 | 52 |

Footprints are the loaded segments of the shared all-groups fixture with the
`memory` argument, not a minimum app or a guarantee for every program. Both
Picolibc configurations pass allocation, strings, conversions, selected math,
raw descriptors, file errors, unsupported-service errors, explicit exit
handlers, immediate exit and full-width handles. Faster buffering does not fix
the four failures. The final fixture checks a committed snapshot immediately
after repeated `fflush(NULL)` and splits the stream error assertions; newlib
passes both strengthened cases and their cold repeats.

The baseline failures have retained output and pinned-source explanations:

- A write to a read-only stream returns `EOF`, but Picolibc's early permission
  branch returns before marking the stream error or setting `EBADF`. Lefony's
  selected stream profile requires those diagnostics; a successful raw
  descriptor error test does not qualify stdio error reporting.
- Normal main return and `exit(7)` leave an unclosed writer's previous committed
  contents as `before`, instead of the buffered replacement `after`. Picolibc's
  exit handler flushes streams without closing the descriptors. Lefony commits
  a staged writer on successful close or explicit sync, so flushing alone does
  not implement the SDK's normal-exit contract. This is an integration gap;
  automatically committing every descriptor in `_exit` would also change
  `_Exit` behavior and is not a valid shared fix.
- After two `fflush(NULL)` calls and explicit sync, the baseline final file
  contains `one`, not `onetwothree`. The pinned `_bufio_exit_flush` removes every
  stream from the global list while flushing; `fflush(NULL)` calls that same
  destructive traversal. Later global flushes and normal exit lose that list.
  The strengthened fixture checks committed `onetwo` before exit, separating
  repeated flushing from the independent automatic-close failure.

The final Picolibc stream failure is the missing `ferror` indication, after the
`EOF` return check has passed. Its repeated-flush case fails the pre-exit
snapshot assertion. The baseline exports described above remain retained,
rather than being replaced by later failed-run artifacts.

These observations concern the pinned library and this adapter/configuration,
not every Picolibc application. The relevant pinned sources are
[`fputc.c`](https://github.com/picolibc/picolibc/blob/1.8.12/libc/stdio/fputc.c),
[`fflush.c`](https://github.com/picolibc/picolibc/blob/1.8.12/libc/stdio/fflush.c)
and [`bufio_exit_flush.c`](https://github.com/picolibc/picolibc/blob/1.8.12/libc/stdio/bufio_exit_flush.c).

Both profiles use real bounded allocation; heap exhaustion/reuse is exercised.
Reserved heap/stack sizes are not measured peaks. No allocator fragmentation
bound, exhaustive libm accuracy, physical timing, flash endurance or production
Picolibc C++/Doom/minigzip support follows from this fixture. Emulator elapsed
times include host load and storage-model scheduling and are not comparative
hardware performance numbers. Prior newlib C++ and port evidence retains its
own exact candidates in the [implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).

## Reproduction and retained inputs

Run from the OS checkout with its development environment, pinned compiler,
QEMU, firmware and matching debug ELF already prepared. Meson 1.7.2 and Ninja
are additional build-only requirements for the Picolibc experiment. Choose fresh
output directories for every candidate; do not overwrite earlier evidence.

```sh
.venv/bin/python scripts/build_sdk_picolibc_comparison.py \
  --output build/picolibc-comparison --meson /path/to/meson-1.7.2
.venv/bin/python vm/test-sdk-c-profile.py \
  --firmware dist/lefony-os-prime-g2-file-abort-vm.elf \
  --output build/newlib-comparison --profile release --keep-going
.venv/bin/python vm/test-sdk-c-profile.py \
  --firmware dist/lefony-os-prime-g2-file-abort-vm.elf \
  --output build/picolibc-comparison-run --profile release --keep-going \
  --comparison-picolibc build/picolibc-comparison
```

Use `--archive PATH` for the exact offline Picolibc source archive. Build another
fresh candidate with `--fast-bufio`, then run the same fixture against it.
`--keep-going` preserves independent results after a failure and still returns
nonzero. It never turns failures or unattempted cold repeats into passes.

Completed comparison reports are retained under ignored
`build/sdk-library-comparison/`:

| Report | SHA-256 |
| --- | --- |
| `newlib-final/report.json` | `0507c907cbbf68e30bbba2ed40d3c33bfd587da82ac82e1aeb1c048dbf4874ca` |
| `pico-final/report.json` | `abebfb6e103ce692f9811bebf06dd7dd3a65df8432304f14e9a5afcb451a8327` |
| `pico-fast-final/report.json` | `01d16182046cc780c5deb036c20df4cc865979e8895c75c4e847d16b89a72990` |

All three runs use SDK identity
`42954442d3457d5183527b94e0f474a41fc08f5f51fc139200b4ec71a7d21342`,
API 12 firmware `9efe4a74da490bdde5b667c124e3f1e80e3e0f25b38ab8eb0441f91e24629844`
and developer QEMU `2b407a4285d46c01a385124568d79148411845dba00700ee09183634995231d0`.
The shared fixture hash is
`f2262184d9456bce2be7ae0171cf9af9c8458ba23e0892039e78eacdb3ffb90a`.
Recording the selection later changes only the `qualification` text in the
newlib contract, giving SDK identity
`ed6212eaec7c9c4c3fd31faeda4848e48bc8c7b179177e6e115280f33ba4161c`.
The tests above retain their original identity. The implementation ledger records
the separate rebuild verification; no library, compiler or firmware pin changes.

Picolibc is pinned at commit `2ae376c6cdf4fef90ca2388ecf7a07457fa63cff`, source
archive SHA-256 `2946ea55b915f7f4555d60bffbaea6a3edc0b8993b7ded3935be9a15cfb7157b`.
The recipe copies the real `COPYING.picolibc` inventory and records its hash,
all installed files, build options and compiler/recipe identity. The probe
verifies source, notices and installed bytes before compiling. The first recipe
used newlib-style notice filenames and omitted the separate inventory; the full
source archive was retained, and corrected candidates require the actual file.

The original source and per-file terms remain authoritative. Picolibc's inventory
includes separate terms for library, test and auxiliary-script files; this is
not a blanket permissive relicense of the source tree. The comparison does not
use its AGPL cross-file generator or GPL printf tests. Newlib keeps its complete
`COPYING.NEWLIB` and source archive. Lefony's previously approved MIT alternative
remains scoped to the [listed original app-linked code](NATIVE-APP-LINKED-LICENSE-REVIEW.md).
The native desktop dependency-source audit remains a separate release gate.

Runtime/SDK maintenance must preserve the function matrix, exact library pins,
checked source adjustments and conventional C/C++ cleanup tests when upgrading
newlib. Reconsider Picolibc if its integration gaps are resolved and repeated
real-app measurements justify the switch. Do not change a shipped library ABI
without matching rebuilt headers/app objects, explicit lock adoption and the
corresponding compatibility evidence.
