# Native Lefony licensing and distribution notes

See [the repository license map](../LICENSE.md) for the agreed component
licenses and [third-party notices](../THIRD_PARTY_NOTICES.md) for attribution.

The pinned Upsilon source applies Creative Commons
Attribution-NonCommercial-ShareAlike 4.0 (`CC-BY-NC-SA-4.0`) at its repository
root. Redistribution of the native image must therefore be noncommercial,
retain attribution and the license notice, identify modifications, provide a
source link, and use the same or a compatible ShareAlike license for adapted
material. This is an engineering inventory, not legal advice.

The build does not require or redistribute an HP firmware dump, HP signing key,
NumWorks proprietary firmware, stock NAND image, or calculator-specific secret.
Upsilon source, the Lefony overlay, and pinned public U-Boot source produce the
native artifact. Raw HP recovery/firmware inputs remain outside the repository.

U-Boot is built from pinned source under GPL-2.0-or-later and is shipped as a
separate boot component in the emulator artifacts. QEMU is a host-side GPL
development dependency and is not bundled in the calculator payload. The GNU
Arm embedded compiler and Debian build image are build tools rather than linked
payload components. Upsilon contains additional component notices, including
the Atomic and RPN app license files; release packaging must copy the complete
pinned upstream notice set rather than replacing it with this summary.

Reader and External applications are excluded from the native product. They
depend on filesystem/loading policies that are not implemented or reviewed for
the bare-metal target. HP, HP Prime, NumWorks, Upsilon, and associated logos are
names or marks of their respective owners; the project must not imply
endorsement or official firmware status.

Generate the reproducible SPDX 2.3 component inventory with:

```sh
./vm/generate-native-sbom.py
```

The result is `build/lefony-prime-g2-native.spdx.json`. Before any public
release, complete a dedicated legal/trademark review, add full corresponding
source and build instructions beside binaries, and include all notices from the
exact pinned source trees and toolchain runtime libraries.
