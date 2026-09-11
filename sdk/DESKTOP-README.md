# Lefony native SDK for macOS Apple Silicon

This development bundle contains the native C++ SDK, ARM compiler, Prime G2
emulator and host dependencies. It is locally tested on macOS 26.6.2 (ARM64).
It is not notarized; use macOS's normal security review for downloaded software.
No Homebrew or separate Python installation is needed. Keep `_internal` beside
`lefony-sdk` when moving the folder.

Open Terminal in the extracted `lefony-sdk` folder, then run:

```sh
./lefony-sdk doctor
./lefony-sdk new "$HOME/Documents/my-lefony-app"
./lefony-sdk --project "$HOME/Documents/my-lefony-app" build
./lefony-sdk --project "$HOME/Documents/my-lefony-app" test
./lefony-sdk --project "$HOME/Documents/my-lefony-app" run
./lefony-sdk --project "$HOME/Documents/my-lefony-app" source
```

Read `AGENTS.md` in the new project. Edit its `app.json` and `src/main.cpp`.
`test` writes a frame and report under the project's `build` folder. `run` opens
the emulator; close its window or press Ctrl-C to stop. The SDK API guide,
examples and headers are in `_internal/sdk/`.

Upload `build/app.lfsrc` through https://lefony.com/#developers once submissions
are enabled. Provide the matching app name, description, icon and at least one
screenshot. Passing apps publish automatically. GitHub is the account provider.
A downloaded signed app can be tested with:

```sh
./lefony-sdk launch /path/to/downloaded.lfapp
```

These SDK commands do not write to a calculator. The website provides USB app
installation on compatible Lefony firmware. Physical storage setup requires
explicit consent to retire part of the stock filesystem and a verified backup;
it remains a development feature awaiting hardware qualification.

`candidate.json` records the bundled firmware hash. `SHA256SUMS` covers the
bundle files. `LICENSE.md`, `LICENSES/` and `THIRD_PARTY/` contain license notices.
The three corresponding-source archives beside this download contain the
compiler, dependencies, Lefony firmware and patched QEMU sources. Native apps
use C++; Python is only a bundled host-tool dependency.
