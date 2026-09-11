# Developing this native Lefony app

This project targets the Lefony native SDK ABI 1. Read the matching
SDK README before editing. This is an ARM C++ app, not a Python app or OS port.

- Source is in `src/`; identity and version are in `app.json`.
- Use the SDK's `lefony-sdk` launcher: `doctor`, `build`, `package`, `run`, `test`, `source`.
  Run these from this project; consult `lefony-sdk --help` for supported options.
- Use only the shipped `lefony/app.h` and `lefony/ui.h` APIs. Never access physical addresses,
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
  have no installed namespace. Test persistence with the installation VM suite.
- Keep text and rectangles within the declared display bounds and use SDK colors.
- Add tests for behavior, inspect emulator frames, and record exact failures.
  An emulator pass is not physical storage, touch, or electrical qualification.
- Do not flash hardware or publish an app as a side effect of build/test.
- Preserve component license notices. Do not add keys, private firmware or captures.

This template is for current implemented APIs only. The service numbers, event values and wire structs in ABI 1 are frozen.
Rich Escher/Poincare controls remain outside this initial API. Source bundles can be submitted
to a configured store for automatic emulator checks. Physical storage migration and electrical behavior still require hardware qualification.
