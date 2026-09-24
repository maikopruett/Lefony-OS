# App-linked license review: conventional C and Doom

Status: **copyright ownership confirmed; additional MIT grant explicitly
approved and applied**, 2026-09-12. Maiko Pruett confirmed ownership and
separately authorized MIT as an alternative for the listed material. The scope
and complete grant are in [LICENSE.md](../LICENSE.md#additional-license-for-the-conventional-app-side-runtime)
and [LICENSES/MIT.txt](../LICENSES/MIT.txt). Final artifact qualification is separate.

The local Doom application links the pinned GPL engine with the SDK's ordinary
foreground/newlib profile. The following twelve original Lefony files now carry
`CC-BY-NC-SA-4.0 OR MIT` notices and are directly included, compiled or used to
link that profile. Recipients may choose the MIT alternative.

| Material | Files | Role in the executable/build |
| --- | --- | --- |
| C service interface | [app_c.h](../sdk/include/lefony/app_c.h) | Public types and inline service/drawing calls |
| File interface | [files.h](../sdk/include/lefony/files.h), [files_wire.h](../sdk/include/lefony/files_wire.h) | Inline calls and fixed-width file requests |
| Foreground interface | [foreground.h](../sdk/include/lefony/foreground.h), [foreground_wire.h](../sdk/include/lefony/foreground_wire.h) | Main execution, heap, timing and copied pixels |
| Input interface | [input_stream.h](../sdk/include/lefony/input_stream.h), [input_stream_wire.h](../sdk/include/lefony/input_stream_wire.h) | Physical-key mapping and ordered input requests |
| Assembly entry | [start.s](../sdk/lib/start.s) | ARM entry into the app-side startup function |
| C runtime integration | [start.c](../sdk/lib/newlib/start.c), [os.c](../sdk/lib/newlib/os.c), [files.c](../sdk/lib/newlib/files.c) | Initializers/main/exit, heap hooks and authenticated descriptor operations |
| Linker layout | [foreground.ld](../sdk/cmake/foreground.ld) | App sections, initializer arrays and memory bounds |

The generator's small startup-argument template in
[runtime.py](../sdk/tools/runtime.py) also has an explicit output permission:
generated mutable argument strings, the argv vector and argc declaration.
The host generator itself remains GPL-3.0-or-later. Project argument values and
application code remain the app author's inputs; a generator license must not
be presented as changing those inputs' terms.

## Applied change and remaining packaging work

1. Added MIT as an alternative for the copyright holder's original material in
   exactly the twelve files above, preserving existing notices and recording
   `CC-BY-NC-SA-4.0 OR MIT` where the complete file is covered by that grant.
2. Recorded the scoped grant and full MIT text in repository license/notices
   files. Both SDK packagers include the license directory and scope document;
   the source kit also includes this review and the Doom preparation recipe.
3. Gave the original startup-argument template/output the same additional
   permission, with the complete MIT notice in generated C, while retaining the
   host tool's GPL license.
4. Rebuilt a freshly prepared Doom project: its executable image is byte-identical
   to the gameplay-tested image below. Prepared source includes the engine GPL
   text, MIT text, grant scope and component notices. Complete the final
   distribution inventory/source audit before releasing artifacts.

The owner's confirmation covers the listed original material. This
change is limited to these app-side inputs; it does not relicense the firmware,
Upsilon, Escher/Poincare, unrelated SDK widgets or third-party libraries.

## Other inputs retain their own terms

| Input | Current disposition |
| --- | --- |
| Doomgeneric engine and prepared adaptations | Retain the pinned GPL-2.0-or-later source notices; preparation records each change |
| Newlib libc/libm and headers | Retain the verified `COPYING.NEWLIB`, source archive, configuration and per-component terms; the grant above is not a grant over newlib |
| GCC runtime and compiler headers | Retain the bundled compiler's notices and applicable runtime exceptions; inspect actual linked archive members |
| Freedoom Phase 1 WAD | Separate BSD-licensed asset input with its exact copyright, credits and disclaimer |
| OpenBSD math units | The map records 35 discarded `lefony_math_*` function sections and no allocated `lefony_math_*` symbol. Their source/notices remain in the SDK |
| Firmware and syscall implementation | Continue under their existing component licenses; no firmware objects are linked into this app executable |

The inspected Doom image is
`aa3b6e7f976001189a482b96d43d47329049d19d8b455439a5f8ede5762e2405`.
Its map and symbol table retain `_start`, `lefony_event`, `_sbrk` and real newlib
file routines. This confirms that the app-side entry/adapters participate in
the executable; a manifest license label cannot replace their actual terms.
The map also identifies six GCC runtime archive members, 103 libc archive
members and one libm archive member pulled into the link before section
collection. Archive membership alone is not a per-file legal audit. Preserve
the exact newlib `COPYING.NEWLIB`, corresponding archive and toolchain notices
with a final distribution. This grant resolves the identified Lefony runtime
licensing obstacle; it does not qualify unrelated dependencies or SDK 1.0.

References: [repository license policy](../LICENSE.md),
[SDK 1.0 licensing gate](NATIVE-APP-SDK-1.0-PLAN.md#3-baseline-and-early-architecture-decisions),
[CC-BY-NC-SA conditions](https://creativecommons.org/licenses/by-nc-sa/4.0/),
[MIT standard text](https://spdx.org/licenses/MIT.html),
[Freedoom asset terms](https://freedoom.github.io/about.html), and the pinned
[Doom inputs and distribution limits](../sdk/ports/doom/README.md).
