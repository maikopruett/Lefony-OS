# Windows cross-build inputs

The [host guide](../../sdk/HOSTS.md#windows-compiler-inputs) documents the compiler
and library recipes. These recipes build Windows x86-64 components on Linux;
PE inspection does not establish native Windows execution or USB behavior.

## Python packaging inputs

`requirements-python-x86_64.txt` selects the reviewed CPython 3.14.7 Windows
packaging wheels. `../windows_python_sources.json` binds the wheels and all
20 included PE files to Python source distributions and embedded native sources.
The collector preserves original wheel metadata, nested licenses, source
notices/patent files, and the actual recipe. Setuptools includes launchers for
multiple architectures; the final SDK's used executables still require the
Windows x86-64 dependency audit.

Pillow's Windows build recipe and wheel license inventory cover Brotli,
FreeType, HarfBuzz, Little CMS, libavif and its codecs, JPEG, PNG, WebP, OpenJPEG,
TIFF, xz and zlib-ng. Vendored raqm, the FriBiDi loader shim and Python C API
compatibility header remain in the Pillow sources. The optional FriBiDi DLL is
not present in this wheel. This source record does not qualify that optional
dynamic loading path. PyInstaller's source distribution includes its bootloader
and bundled zlib sources; setuptools includes `launcher.c`.

No license is reassigned by this inventory. Source correspondence and preserved
notices are separate from an independent rebuild or Windows execution check.
See the [packaging commands and scope](../../sdk/HOSTS.md#windows-packaging-inputs-and-checks).

## OpenSSL patches

The OpenSSL recipe retains Ubuntu's `3.0.13-0ubuntu3.15` source archives and
security patches. It additionally applies two checked Windows adaptations:

- `openssl-mingw-avx512.patch` is the unmodified upstream OpenSSL commit
  [`224ea84b4054de105447cde407fa3d39004a563d`](https://github.com/openssl/openssl/commit/224ea84b4054de105447cde407fa3d39004a563d),
  authored by Andrey Matyukov. It fixes assembly label decoration for MinGW.
- `openssl-portable-getenv.patch` adapts Ubuntu's added `crypto/fips_mode.c`
  to OpenSSL's existing `ossl_safe_getenv` wrapper. It replaces the two glibc-only
  `secure_getenv` calls and includes the wrapper declaration. The existing
  privilege check and Windows environment handling belong to that wrapper.
  FIPS certification and native runtime behavior are not established by this build.

The patches and their OpenSSL/Ubuntu source fragments retain **Apache-2.0**;
see the [full license](../../LICENSES/Apache-2.0.txt). Original OpenSSL and Debian
copyright notices remain in the exact source archives and copied notices.
The standalone Python build scripts retain their GPL-3.0-or-later notices.

The recipe checks the patch bytes and complete affected source files before
applying each patch, then checks the resulting source hashes. Repeated runs on
already prepared sources succeed without modification; unknown or mixed contexts
are rejected. Every candidate retains the actual recipes and patches it used.

## QEMU dependency sources

`qemu-dependencies.json` pins seven existing Ubuntu source packages plus GNU
libiconv 1.19 and gettext 1.0. The latter two supply Windows charset conversion
and message catalogs for GLib's gettext dependency. The GNU archive URLs and
hashes are explicit; upstream signatures are retained alongside the archives.
The development source collection verified both signatures with Bruno Haible's
key `E0FFBD975397F77A32AB76ECB6301D9E1BBEAC08` from the GNU keyring. This is a
source-input signature, independent of calculator/app release signing keys.

The library recipe builds real libintl with libiconv and enables GLib's native
language support. It does not substitute the proxy-libintl fallback. GNU
libiconv and gettext libraries retain their LGPL notices; accompanying command
line programs retain their separate GPL notices. Exact source archives and
copied file-level license notices accompany the dependency candidate. Meson,
gettext's native build tools and libtool's `libltdl-dev` macros are build-host
prerequisites in `Dockerfile.qemu-cross`.

The QEMU recipe consumes the same prepared 11.1.1/r70 source archive used by the
Linux candidate and a separately hash-verified Windows dependency candidate.
It explicitly enables ARM softmmu, internal FDT, SDL, pixman and libusb. Cross
compilation and PE inspection do not verify Windows display, sockets, guest
execution, source debugging or physical USB. Those require a Windows host.

## Full CPython runtime and source inputs

`../windows_cpython_sources.py` and its adjacent JSON lock collect the original
full Windows CPython 3.14.7 x64 ZIP, release metadata, CPython source and 33
SBOM-referenced dependency sources. The collector extracts bounded, validated
ZIP paths and retains 112 source notices plus three original runtime notices.
Microsoft runtime DLLs retain the upstream distributable-code conditions;
no source availability or open-source classification is asserted for them.

The binary packager requires `--cpython-runtime` pointing to that exact original
ZIP, checks the base interpreter/stdlib before freezing, and checks frozen
CPython DLL hashes. Both binary and source packaging require the matching
`windows-cpython` source component. See the [host instructions](../../sdk/HOSTS.md#windows-packaging-inputs-and-checks).

QEMU's MinGW libffi and CPython's MSVC libffi have the same DLL name and different
bytes. QEMU and its dependency closure now live in `_internal/runtime`, outside
PyInstaller collection. The final audit keeps their process scopes separate.
Static dependency audits and offline byte checks do not establish native Windows
execution, credential stores, USB behavior or clean-host qualification.

## Native source assembly

`../collect_native_windows_sources.py` and `native-components.json` join the
reviewed compiler, debugger, QEMU, libusb and OpenSSL artifacts with the 16 Python
source components. Exact original checksum inventories bind every collected
file; changed files, omitted notices, symlinks and rewritten tool catalogs fail
validation. GCC 13's five runtime license texts are read from the exact nested
source archive. The retained GDB component also carries the complete common
license texts referenced by Debian copyright files.

Generated `__pycache__` records remain in the original artifact inventories but
are excluded from collected corresponding sources. Source archives retain their
selected native catalogs for independent extraction checks. The binary packager
also binds its Windows PE and toolchain/OpenSSL outputs to this source inventory.
See [assembly commands and remaining qualification](../../sdk/HOSTS.md#windows-packaging-inputs-and-checks).
