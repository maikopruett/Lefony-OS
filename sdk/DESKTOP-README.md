# Lefony native desktop SDK candidate

This experimental bundle contains the C/C++ SDK, ARM compiler, newlib, ARM GDB,
Prime G2 emulator, Python host runtime and USB dependencies. Keep `_internal`
beside `lefony-sdk` when moving the folder. No separate Python, Homebrew, compiler
or debugger installation is needed for the commands below. The bundled GDB has
no embedded Python scripting. Native Windows support and physical qualification
remain unqualified; inspect `candidate.json` for the actual host and artifact.

From the extracted folder:

```sh
./lefony-sdk doctor
./lefony-sdk new "$HOME/Documents/my-lefony-app" --template notebook
./lefony-sdk --project "$HOME/Documents/my-lefony-app" build
./lefony-sdk --project "$HOME/Documents/my-lefony-app" run --workspace development
./lefony-sdk --project "$HOME/Documents/my-lefony-app" test --headless
./lefony-sdk --project "$HOME/Documents/my-lefony-app" preview --once --scenario tests/edit.json
./lefony-sdk --project "$HOME/Documents/my-lefony-app" source --format 2
```

For a Windows candidate, extract the entire ZIP and use `./lefony-sdk.exe`
in PowerShell. Keep `_internal` beside the executable. Native Windows packaging
and complete developer journeys still require validation; see `_internal/sdk/HOSTS.md`.

Read `AGENTS.md` in the new project. `c-main` supplies ordinary C startup;
`notebook`, `ui-gallery`, `forms-tables`, `graph-explorer`, `reference-cards` and
`link-gallery` demonstrate other public APIs. The API guides, headers and
examples live in `_internal/sdk/`. Preview captures the actual ARM app and layout
records; it retains committed documents between successful runs. Workspace
exports contain app data and are not public bug-report attachments by default.

`run` opens the shared Lefony desktop emulator with the bundled Prime keyboard
and touchscreen. Layout and Scale change the complete calculator together.
Screen clicks use touch input; the keypad and computer arrows, digits, Enter
and Backspace use normal calculator keys. Save in the app, then choose
**Stop emulator**, close the window, or press Ctrl-C for normal save cleanup.
The native window runtime is included; no browser or separate Python GUI
installation is required. Older SDK bundles retain their previous interface.

For source debugging, start `debug` in one terminal and `debugger` in another,
using the same project directory:

```sh
./lefony-sdk --project "$HOME/Documents/my-lefony-app" debug
./lefony-sdk --project "$HOME/Documents/my-lefony-app" debugger
```

`debugger` opens the generated matching-symbol script with bundled ARM GDB.
The emulator and relay use private local sockets. Closing the emulator or
pressing Ctrl-C ends the run. GDB pauses are excluded from timing measurements.
CMake integration uses this executable when loaded from the bundle; installing
CMake itself is a separate choice.

`publish --dry-run` validates the project folder and prepares local evidence.
GitHub `login` and explicit `publish` submit it to the configured store;
`listing pull/push` handles metadata changes. See `_internal/sdk/PUBLISHING.md`
for immutable versions, required media and interrupted-upload recovery. The
`companion` command provides an explicit app-scoped USB/HTTPS connection; see
`_internal/sdk/CHANNEL.md`. Account and physical-device journeys have separate
qualification from offline emulator testing.

Private app identities and signed packages can also be created with this executable:

```sh
./lefony-sdk keys generate --private-key /private/app.pem --public-key /private/app-public.pem
./lefony-sdk sign ./build/my-app-1.0.0.lfapp --private-key /private/app.pem --output ./build/my-app-1.0.0-signed.lfapp
```

Keep the private key outside the project. These commands require new output paths
and use bundled OpenSSL without USB access. See
`_internal/sdk/KEYS.md` for enrollment, installation and recovery.

The examples above do not write to a calculator. Explicit installation, file
exchange and key commands require compatible Lefony firmware and normal device
consent/recovery rules. Physical migration, power loss, recovery, endurance and
input feel remain unqualified. Host signing/notarization and clean-host release
trials also remain release gates.

`candidate.json` identifies the bundled tools and firmware. `SHA256SUMS` covers
bundle files. `LICENSE.md`, `LICENSES/` and `THIRD_PARTY/` retain component
notices. Corresponding sources and build recipes must accompany distribution;
local packaging does not publish this candidate or qualify SDK 1.0.
