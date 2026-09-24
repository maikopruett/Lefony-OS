# Doom application components

The prepared application is GPL-2.0-or-later. Each dependency retains its own
notice. The manifest's license field does not describe the entire SDK or OS.

- Doomgeneric engine, pinned at `dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284`:
  retain the original source notices and complete `notices/doomgeneric.txt`.
  `notices/port.txt` records every checked engine adaptation. Lefony's
  platform implementation and `output.c`/`output.h` transaction adapter are
  GPL-2.0-or-later.
- Lefony's conventional app-side runtime: use the MIT alternative for the
  twelve files and startup-argument template named in
  `notices/lefony-license-scope.md`. Retain `notices/lefony-runtime-MIT.txt`.
  The generated startup arguments also carry the full notice. This grant
  excludes firmware, unrelated SDK components and third-party material.
- Newlib 4.6.0.20260123: the SDK sysroot contains the verified `COPYING.NEWLIB`
  with the component copyright/permission notices, its exact source archive,
  configuration and library hashes. Keep these with the corresponding SDK
  distribution; newlib is not relicensed under Lefony's MIT grant.
- GCC runtime and compiler headers: retain the exact toolchain's GPL notices
  and GCC Runtime Library Exception. The desktop SDK's component source and
  notice collection is separate from this small app source bundle.
- Freedoom Phase 1 0.13.0: game data is supplied separately, with its exact
  BSD notice in `COPYING.txt`, `CREDITS.txt` and `CREDITS-MUSIC.txt`. Preserve
  these alongside any distributed WAD. The app source bundle contains no WAD.

Before distributing binaries, retain the actual linked-input inventory,
matching application source, SDK runtime source/build instructions, library
notices and corresponding source material. A successful emulator test alone
does not satisfy that packaging audit or physical release qualification.
