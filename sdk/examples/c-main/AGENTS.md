# Developing this conventional C/C++ app

Read the matching SDK `C-RUNTIME.md`, `FOREGROUND.md` and `FILES.md` before edits.
This project uses `project.json` schema 2 and public API 3 foreground execution.

- Implement ordinary `main`; the SDK supplies startup, allocation and file
  adapters. Do not define `lefony_event` or call `lefony_program_enter` again.
- Use C11/C++17 with newlib's C headers. The current profile does not supply
  libstdc++, exceptions, RTTI, general threading or background execution.
- Source and bounded arguments belong in `project.json`; identity/version and
  explicit capability requirements belong in `app.json`. Preserve schema/API
  negotiation and use `source --format 2` with compatible website readers.
- Use the public `lefony/` interfaces. No MMIO, private firmware headers or
  VM-only app service calls belong in a portable app.
- The app stack survives sleep, yield and file waits. Handle allocation errors,
  service failures and short I/O. Check `fclose` before reporting a durable save;
  `fflush` alone does not commit. Version serialized data and never save pointers.
- Home/fault termination does not run user destructors. Already committed files
  survive a later nonzero exit; uncommitted private bytes do not.
- `new` works offline. Check in the lock produced by the first build. `lock
  --update` explicitly adopts a changed SDK or sysroot. Builds never download
  dependencies or invoke arbitrary project hooks.
- Use normal `build`, `package`, `test`, `debug`, `workspace` and `source` commands.
  Tests without `--workspace` use disposable synthetic storage. Name a workspace
  for persistence across separate launches. A `program_exit` replay assertion
  checks the signed exit status with a bounded wait.
- Add behavior assertions and inspect emulator frames. Record exact failures.
  Emulator passes do not establish physical timing, flash or touch qualification.
- Preserve licenses, exclude keys/private captures, and never flash hardware,
  reset persistent workspaces or publish as a side effect of build/test.

SDK 1.0, native host qualification and Doom distribution remain separate gates.
