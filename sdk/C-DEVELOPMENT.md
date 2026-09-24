# C development candidate

The working-tree builder accepts `.c` and `.cpp` files recursively under `src/`.
It selects the pinned `arm-none-eabi-gcc` C11 frontend for C files and the pinned
`arm-none-eabi-g++` C++17 frontend for C++ files. Linking uses the C++ driver with
the existing freestanding ABI 1 linker contract. Both compilers must report the
SDK's pinned version, currently 16.2.0. Generated assets remain C++ translation
units and link into pure-C projects through the same build pipeline.

This is an implementation step toward the [1.0 plan](../docs/NATIVE-APP-SDK-1.0-PLAN.md),
with callback projects retained as the default. The explicit
[foreground-newlib-1 profile](C-RUNTIME.md) builds ordinary `main` programs with
startup, initializer/exit handling, allocation and real stdio over the
[public asynchronous file service](FILES.md), including large files and durable
close/atomic rename. Its waits use the [API 3 foreground candidate](FOREGROUND.md),
which compiles into both targets and passes ARM execution/memory tests. The
[library comparison](../docs/NATIVE-APP-C-LIBRARY-COMPARISON.md) selects newlib;
broader function coverage and physical behavior still need qualification.
Downloads await coordinated qualification.
The [C library matrix](C-LIBRARY.md) defines the selected functions, error behavior
and dependency changes that require a matching library/application rebuild.

## Existing ABI 1 interface from C

```c
#include <lefony/app_c.h>

void lefony_event(lefony_event_t event, uint32_t first, uint32_t second) {
  (void)first;
  (void)second;
  if (event == LEFONY_START) {
    lefony_rect_t screen = {
      .x = 0, .y = 0, .width = LEFONY_WIDTH, .height = LEFONY_HEIGHT,
      .color = LEFONY_GREEN
    };
    lefony_fill(screen);
  }
}
```

Use the normal build, package, test and workspace commands. A C++ function called
from C needs an `extern "C"` declaration/definition in its C++ translation unit.
Wire structures use fixed-width fields and ARM pointer widths. The C interface
offers existing fill/text, millisecond query and private-data transfers. It does
not change service numbers, callback deadlines, signing or memory limits.
Private-data writes retain the existing staged-save and normal-close behavior.

Build reports list the project languages. `compile_commands.json` records the
correct compiler and language flags for each file. Changing a C file rebuilds
that translation unit; unchanged C++ files remain cached. C syntax/compile
errors fail the build and do not produce a successful build report.

Source formats 0 and 1 still accept only `.cpp`/`.h` source and keep their frozen
limits. Use [source format 2 and project configuration](PROJECTS.md) for C and
larger source trees. The local SDK and matching website reader candidate
implement this format; publication requires those reader changes to be deployed
before the updated SDK is distributed.

## Qualification

```sh
.venv/bin/python -m pytest tests/test_sdk_c.py tests/test_sdk_maturity.py -q
.venv/bin/python vm/test-sdk-c.py
```

The host tests compile C11-only language constructs, check ARM wire layouts,
mixed C/C++ linkage, incremental builds and relocated deterministic artifacts.
The VM test uses a signed installed package, normal keypad dispatch, checked
service failures and persistence across cold boots. It uses synthetic storage
and the explicitly public emulator signing fixture. Physical qualification is
separate.

Maintainers can build a pinned newlib architecture candidate with:

```sh
.venv/bin/python scripts/build_sdk_newlib.py
```

The command verifies the source archive hash, compiles ARM hard-float libraries
and records their identities under ignored `build/sdk-newlib/`. `--archive PATH`
uses the exact source archive offline. This POSIX maintainer build prepares the
library; the explicit [main profile](C-RUNTIME.md) supplies SDK startup and real
OS/file adapters. A library build alone does not establish their correctness.
The [newlib/Picolibc comparison](../docs/NATIVE-APP-C-LIBRARY-COMPARISON.md)
records measured behavior, footprint and integration tradeoffs. Broader function
coverage and complete artifact license qualification remain open.

`vm/test-sdk-c-profile.py --firmware PATH --output DIRECTORY` exercises the
ordinary main profile, actual heap, formatting/scanning, math, public descriptor
and stream I/O, durable cold files and exit behavior. Its synthetic descriptor
boundary cases require a matching firmware debug ELF (selected with
`--firmware-debug`); `--cases` selects individual groups. `--sdk` can qualify the
source from a relocated kit, and `--profile release` uses optimized app objects.
The [matrix](C-LIBRARY.md) explains what these cases do and do not establish.

After building that candidate, `.venv/bin/python vm/test-sdk-libc.py` links an
actual ARM probe and checks allocation/exhaustion, failed-realloc preservation,
integer/float formatting and parsing, sorting/searching, math and explicit
unsupported-file errors. Its 256 KiB test heap lives in app memory. This proves
a bounded non-file libc starting point under the existing callback runtime;
it does not qualify conventional execution, filesystem adapters or all libc.

The separate [foreground execution proof](../docs/NATIVE-APP-EXECUTION-EXPERIMENT.md)
tests kernel preemption/resumption, preserved registers and stack, and normal
Home interruption with `vm/test-sdk-execution.py`. Its opt-in services exist
only in VM firmware and are not a public SDK runtime contract. The newer
`vm/test-sdk-foreground.py` tests public API 3 instead. `vm/test-sdk-main.py` tests
ordinary SDK startup, constructors and exit cleanup. Broader input/lifecycle
coverage and final developer-bundle qualification remain
open.
