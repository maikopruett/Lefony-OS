# Third-party sources and notices

- **Qt for Python / Qt WebEngine:** the desktop emulator wrapper uses PySide6
  6.11.2 and the Qt/Chromium runtime supplied in its upstream wheels. These
  retain their upstream LGPL/GPL and third-party licenses; see
  <https://doc.qt.io/qtforpython-6/licenses.html> and
  <https://doc.qt.io/qt-6/qtwebengine-licensing.html>. Native wrapper builds
  preserve installed wheel metadata/notices. Corresponding Qt/Chromium source
  collection is required before releasing new complete SDK binaries; the old
  SDK source inventories do not cover this added runtime. See
  [desktop builds](docs/EMULATOR-DESKTOP.md).

- **HP Prime Virtual Calculator skins:** version 2.4.2 (2026-09-09), from
  Moravia Consulting. Original PNGs and XML definitions are in
  `sdk/assets/prime/`, together with provenance hashes and the original EULA.
  These proprietary assets are not relicensed by Lefony. The EULA prohibits
  distribution; no separate redistribution grant was identified. See the
  [asset notice](sdk/assets/prime/README.md).

- **Upsilon / NumWorks Epsilon lineage:** calculator UI, applications, Poincare
  and Ion interfaces. Pinned Upsilon commit:
  `f36520e0ed5faabbfea8a2b9f4e1309edc077927` at
  <https://github.com/UpsilonNumworks/Upsilon>. Its root license is
  CC-BY-NC-SA-4.0. Component-specific notices in that tree also apply.
  Lefony modifies hardware drivers, input, display, app integration, theme,
  storage, recovery and build configuration. This repository's overlays and
  patches describe those modifications; the upstream source is fetched at build.
- **Historical HP Prime port:** Jean-Baptiste Boric's Epsilon work at
  <https://github.com/boricj/epsilon>, commit
  `d0e1e0e98b890daa8ac84a18d0e237ec5ff97868`, is a documented hardware/input
  reference. Do not infer a license for copied code from a project name;
  preserve any original notice when importing material.
- **QEMU:** <https://www.qemu.org/>, pinned by `vm/build-prime-g2-qemu.sh`.
  The Prime-specific model and applicable patches retain GPL-2.0-or-later
  notices. QEMU is a separate host program, not linked into the calculator OS.
- **U-Boot:** public upstream source and the public Prime port are pinned by
  `vm/build-u-boot.sh` and `scripts/build_prime_g2_physical_updater_uboot.sh`.
  U-Boot and its integrations retain GPL-2.0-or-later notices and applicable
  per-file licenses. It is a separate boot component.
- **Linux/Prinux hardware references:** public source URLs and revisions are
  recorded in `hardware/prime_g2/reference/sources.json`. Only curated register
  facts and protocol/geometry fixtures are included. Private device-tree
  binaries, captured firmware payloads and vendor manuals were excluded.
- **littlefs:** flash filesystem from <https://github.com/littlefs-project/littlefs>,
  v2.11.3 at `6cb4e86540eca0d9ba62500a298385c9d863c8be`. Sources
  and [BSD-3-Clause license](ports/lefony-prime-g2/ion/src/prime_g2/littlefs/LICENSE.md)
  are vendored; Lefony supplies a separate NAND/static-runtime adapter and a
  [documented failed-read cache fix](ports/lefony-prime-g2/ion/src/prime_g2/littlefs/LEFONY-CHANGES.md).
- **Toolchain and libraries:** compiler runtime libraries, Python components,
  app assets and other upstream dependencies keep their own notices. Before a
  binary release, collect the full notice set from the exact source/toolchain
  used; the top-level upstream license alone is insufficient.
- **Windows native tool inputs:** the [component lock](scripts/sdk-windows/native-components.json)
  and [assembler](scripts/collect_native_windows_sources.py) retain exact source
  archives, recipes and notices for the compiler, GDB, Prime QEMU, libusb,
  OpenSSL and their recorded dependencies. GCC 13 runtime terms come from its
  exact nested original archive. Original common-license texts referenced by
  Debian copyright records accompany the GDB component. Source correspondence
  checks do not qualify native execution or a complete SDK release.
- **Windows CPython runtime:** the [runtime/source lock](scripts/windows_cpython_sources.json)
  binds the original full CPython 3.14.7 x64 ZIP, CPython source and 33
  SBOM-referenced source archives. The collector preserves original runtime and
  source notices, including the historical macholib attribution and SQLite's
  source copyright disclaimer. CPython's Microsoft runtime DLLs retain the
  original `LICENSE.txt` distributable-code conditions; they are not classified
  as open source or as having available corresponding source. The signed release
  manifest binds the runtime ZIP. Upstream rebuilds and individual Authenticode
  verification remain separate from these source and byte checks.
- **Windows Python inputs:** the [source lock](scripts/windows_python_sources.json)
  and [collector](scripts/windows_python_sources.py) retain 14 Python source
  distributions, wheel notices and 17 embedded Pillow library/build source
  archives. Native file mappings include Pillow extensions, PyInstaller
  bootloaders and setuptools launchers; their original licenses, vendored
  notices and patent files remain with the sources. The separate CPython inventory
  above covers its runtime licensing. Complete frozen-bundle inputs and upstream
  rebuild qualification remain separate. See the [Windows input notes](scripts/sdk-windows/README.md#python-packaging-inputs).
- **Windows OpenSSL build:** the [recipe](scripts/build_sdk_windows_openssl.py)
  retains OpenSSL 3.0.13 with Ubuntu `3.0.13-0ubuntu3.15` patches. Its two
  [Windows adaptations](scripts/sdk-windows/README.md#openssl-patches) and
  reproduced source fragments retain [Apache-2.0](LICENSES/Apache-2.0.txt).
  Exact source archives, upstream/Debian notices and build records accompany
  the component; the standalone host recipe is GPL-3.0-or-later.
- **Windows libusb build:** the [recipe](scripts/build_sdk_windows_libusb.py)
  retains Ubuntu's libusb `1.0.27-1` source package and downstream patches.
  The LGPL-2.1-or-later library, complete source inputs and copied notices
  accompany the component. Cross compilation does not qualify physical USB.
- **Windows QEMU libraries:** the [dependency recipe](scripts/build_sdk_windows_qemu_dependencies.py)
  and [source pins](scripts/sdk-windows/qemu-dependencies.json) retain the existing
  Ubuntu GLib, PCRE2, libffi, SDL2, pixman, zlib and libusb source versions, plus
  GNU libiconv 1.19 and gettext 1.0 for Windows message catalogs. Their own
  file-level LGPL, GPL, BSD and other notices accompany exact source archives;
  the standalone build tools are GPL-3.0-or-later. See the
  [source notes](scripts/sdk-windows/README.md#qemu-dependency-sources).
- **Newlib:** version 4.6.0.20260123 is pinned in
  [the runtime contract](sdk/contracts/newlib.json). The conventional app runtime
  links its C and math libraries; complete upstream sources and `COPYING.NEWLIB`
  accompany bundled sysroots. The [build recipe](scripts/build_sdk_newlib.py)
  preserves upstream notices, enables 64-bit/C99 formatted I/O and applies a
  hash-checked adjustment widening both `FILE` descriptor fields from `short` to
  `int`. This requires matching library/application rebuilds; see the
  [C library guide](sdk/C-LIBRARY.md#full-width-file-descriptors-and-rebuilds).
- **SDK app-side OpenBSD/fdlibm subset:** exact files extracted from the pinned
  Upsilon `liba/src/external/openbsd/` directory. The [source manifest](sdk/lib/vendor/openbsd-math/manifest.json)
  records every original hash. Sun Microsystems and other original file-level
  permission notices remain in the source. Lefony's separate private C headers
  adapt types and prefix exported names; these routines run in app memory.
  The full corresponding subset is included in the SDK source kit.
- **mpmath:** version 1.3.0, BSD-3-Clause, used only as a development/test oracle
  at 400 decimal digits. It is not linked into apps or shipped as an SDK runtime
  dependency. Numerical tests also exercise the compiled library on ARM.
- **truststore:** version 0.10.4, MIT, supplies native host certificate-store
  verification for the SDK account client and HTTPS companion. It is not linked
  into calculator applications. Desktop source manifests retain the exact source
  archive and binary bundles include its license notices. See the upstream
  [project](https://github.com/sethmlarson/truststore) and
  [context documentation](https://truststore.readthedocs.io/en/stable/).
- **pefile:** version 2024.8.26, MIT, inspects Windows executable/DLL dependency
  tables during desktop packaging and host tests. It is not linked into
  calculator applications. The dependency-source collector retains its exact
  source archive and notices. See the [upstream project](https://github.com/erocarrera/pefile).
- **Minigzip/zlib:** the optional [existing C tool recipe](sdk/ports/minigzip/README.md)
  pins zlib 1.3.2 and its upstream minigzip utility. The archive and selected
  source hashes are in [source.json](sdk/ports/minigzip/source.json). Preparation
  preserves the Zlib license and source notices, and marks the utility's
  temporary-output/atomic-replacement adaptation. Compression library sources
  are unchanged. The conventional Lefony startup/adapters listed in
  [LICENSE.md](LICENSE.md#additional-license-for-the-conventional-app-side-runtime)
  now offer MIT as an alternative to CC-BY-NC-SA-4.0; other SDK components
  retain their own notices.
- **Doomgeneric:** the optional [Doom recipe](sdk/ports/doom/README.md) pins
  commit `dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284`. The GPL-2.0-or-later
  engine retains its original notices; the recipe records checked changes
  and includes the complete engine license in prepared source projects.
  Lefony's separate platform adapter is GPL-2.0-or-later.
- **Freedoom:** the Doom workload separately uses the BSD-licensed Phase 1
  WAD from release 0.13.0. Its archive, WAD, license and credit hashes are
  recorded in [assets.json](sdk/ports/doom/assets.json). Game data is not
  embedded in the SDK or app source package. Distributing that data requires
  retaining its exact copyright, license and credits.

The emulator signing key in `tests/fixtures/` is deliberately public test data.
It grants no trust in production and must never be used as a release key.

HP, HP Prime, NumWorks, Upsilon, and other third-party names/logos are their
owners' marks. Use here identifies compatibility and provenance, not endorsement.
