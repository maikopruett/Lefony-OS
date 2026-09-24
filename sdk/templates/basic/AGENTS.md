# Developing this native Lefony app

This project targets the Lefony native SDK ABI 1. Read the matching
SDK README before editing. This is an ARM C++ app, not a Python app or OS port.

- Source is in `src/`; identity and version are in `app.json`.
- The matching SDK also supports C11 files and mixed C/C++ linkage. For selected
  source lists, include paths and bounded compiler settings, read SDK `PROJECTS.md`
  and use `project.json`. C/configured projects require `source --format 2` and a
  compatible website reader; formats 0/1 retain their original C++ restrictions.
- Use the SDK's `lefony-sdk` launcher: `doctor`, `build`, `package`, `run`, `test`, `debug`, `symbolize`, `workspace`, `lock`, `source`.
  Run these from this project; consult `lefony-sdk --help` for supported options.
- Use only shipped public `lefony/` APIs. Never access physical addresses,
  peripheral registers, private OS headers, page tables, or another app's data.
- Code is C++17, ARM mode, Cortex-A7, hard-float. Exceptions, RTTI, dynamic global
  constructors and a general C++ standard library are not supported in ABI 1.
- Handle drawing/service errors. Keep event callbacks bounded; runtime deadlines
  can terminate the app. Do not use an infinite event loop or busy-wait.
- Do not assume an app callback retains its stack after returning. Store state
  explicitly in app data; do not retain pointers into temporary variables.
- Installed apps have 64 KiB of private data through `readData` / `writeData`,
  at most 4096 bytes per call. Handle errors and missing/older records. Version
  serialized data, check lengths, and never persist pointers. Writes commit on
  normal exit; power loss before commit loses staged changes. Direct SDK previews
  have no installed namespace. Use `test --workspace NAME` to exercise a signed
  installed app in persistent synthetic NAND, then cold restart the workspace.
- Check in `sdk.lock.json`. `lock --update` explicitly adopts a new SDK;
  builds reject an unexpected identity. `build --profile debug` emits symbols,
  a linker map, memory accounting and `compile_commands.json`.
- Public JSON replay tests live in `tests/`; consult SDK `TESTING.md`. They use
  normal key and Goodix dispatch. Add assertions beyond startup and inspect frames.
- `runtime.h` provides an explicit arena and bounded containers. Handle exhausted
  capacity and cancellation. `numeric.h` is a limited app-side numeric subset.
  `expression.h` offers bounded scalar parsing/evaluation with context-owned
  handles; check every status and never serialize handles. It is not Poincare.
  `ui_model.h` / `ui_controls.h` provide bounded layout/focus/selection and screen
  stacks. Cancel capture on modal/screen/Close transitions, restore stable focus
  IDs and supply Back/Cancel buttons when optional hardware Back is unavailable.
  `extensions.h` discovery/batches are experimental and require `-3` fallbacks
  for older firmware. Do not add unrecognized ABI 1 manifest fields.
- Keep text and rectangles within the declared display bounds and use SDK colors.
- Add tests for behavior, inspect emulator frames, and record exact failures.
  An emulator pass is not physical storage, touch, or electrical qualification.
- Do not flash hardware or publish an app as a side effect of build/test.
- The local SDK account candidate provides `login`, `logout`, `whoami`,
  `apps list`, `apps show APP_ID`, and `project link APP_ID` with a matching
  website. Read SDK `ACCOUNTS.md`; credentials stay in the platform credential
  store. `app.json` owns the app ID, and linking never rewrites source.
  `.lefony/store.json` is local metadata, excluded from source submission.
  Read SDK `PUBLISHING.md` for `publish --dry-run`: prepare `store/` metadata and
  required icon/screenshots, enable source permission, then snapshot/build/test
  locally and inspect the resulting preview. Keep `.lefony/` out of Git.
  `publish` explicitly creates a release with the matching store backend;
  `--resume ATTEMPT_ID` reuses its tested bytes after interruption and `--status`
  queries progress. A dry run creates no release. Updates require a higher
  immutable version. Preserve local account/revision bindings and stop for stale
  website edits. `listing pull --dry-run` saves a comparison; apply its plan with
  explicit local/remote choices for conflicting fields. It never enables source
  permission or changes app ID/version/license. Use `listing recover PLAN_ID`
  for an interrupted local apply. `listing push --dry-run` compares metadata;
  explicit `listing push` updates the listing without rebuilding or sharing
  source. `apps withdraw APP_ID` explicitly removes active store versions.
  Both save an operation UUID before sending; use `--status OPERATION_ID` or
  `--resume OPERATION_ID` after interruption. Never alter the saved request.
- Preserve component license notices. Do not add keys, private firmware or captures.

This template is for current implemented APIs only. The service numbers, event values and wire structs in ABI 1 are frozen.
Rich Escher/Poincare controls remain planned. Developers test locally and submit
the exact package plus source and required listing media through GitHub sign-in.
The website checks and signs bytes without running submitted code. Local reports
are developer-supplied evidence, not independent certification. Publishing,
withdrawal, workspace reset and physical-device writes are explicit user actions.
