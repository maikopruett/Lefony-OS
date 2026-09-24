# Working on the Minigzip Lefony app

This is an ordinary foreground C project. Read README.md and the SDK's
C-RUNTIME.md and FILES.md. Build and package with the installed SDK CLI or
CMake integration. Use source format 2. Input files live in app-private storage;
they are not host paths or inline app assets.

Preserve upstream zlib notices. The marked minigzip output adaptation preserves
the prior destination until verified stream completion and explicit descriptor
close. Abort staging on errors before library cleanup, and check the documented
expected invalid-descriptor cleanup result. Keep the error-path abort before
exit's stdio cleanup. Do not restore unchecked direct overwrite/removal, add
successful syscall stubs, or
copy private VM hooks into the program. SDK runtime changes belong in the SDK.

Check real compression/decompression, output integrity and error exit status.
A startup screenshot is insufficient. Use synthetic data for emulator tests,
retain exact input/output/package hashes, and distinguish model tests from
physical power-loss, timing and flash qualification. SDK standard streams are
not a console; named-file mode is the supported candidate.

Build/test/source commands never publish or write a calculator implicitly.
Publication, device operations and trust-root changes require explicit user
authorization. Never include credentials, local paths, captures or keys in
source bundles. Keep generated output under build/ and private workspaces under
.lefony/.
