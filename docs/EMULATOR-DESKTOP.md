# Shared desktop emulator

`make run` and SDK `run` / `launch` use the same desktop window and bundled
Prime keyboard. QEMU runs the ARM firmware; the window embeds the shared
HTML/canvas renderer using Qt WebEngine. No browser tab is opened, no browser
installation is required, and there is no browser mode or browser fallback.

## Source installations

Install `requirements-dev.txt` in the repository virtual environment. Standalone
SDK source kits use `python -m pip install -r sdk/requirements-emulator.txt`
in addition to their existing CLI dependencies. Python 3.11 or newer is required.
The pinned PySide6 wheels provide Qt on macOS 13+, Windows x86-64 and current
Linux distributions. Linux also needs its normal desktop libraries; on Ubuntu
24.04:

```sh
sudo apt-get install libnss3 libxcomposite1 libxdamage1 libxrandr2 libxtst6 \
  libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 libxcb-keysyms1 \
  libxcb-shape0 libxcb-icccm4 libpulse0 libasound2t64 libegl1 libgl1
```

```sh
make run
.venv/bin/python sdk/tools/cli.py --project /path/to/app run
```

`--headless` is retained for automated checks. Raw Cocoa/SDL displays remain
explicit QEMU diagnostic modes; they do not open a browser. SDK GDB sessions
retain their existing diagnostic display and debugger transport.

The renderer's loopback server is a private implementation detail. It uses a
random session path, validates Host/Origin, and serves only the renderer,
frames and declared skin assets. The embedded view blocks outside requests,
new windows, downloads and navigation away from its session. It uses an
in-memory profile. No public listener or user browsing profile is used.

Closing the window, clicking **Stop emulator**, or pressing Ctrl-C releases
held keys/touch. The SDK then leaves the app through Home and drains workspace
saves before stopping QEMU. A window startup failure is reported as an error;
it never falls back to opening a browser.

## Build native window bundles

Run on each target host (macOS, Linux or Windows), in a dedicated Python virtual
environment. Qt's native platform plugins come from the pinned wheels; the
launcher and renderer are shared source. Build outputs stay under ignored
`build/`.

```sh
python -m pip install -r sdk/requirements-emulator.txt pyinstaller==6.20.0
python scripts/build_emulator_window.py --output build/emulator-window-native
python vm/test-emulator-window.py --window-bundle build/emulator-window-native
```

The build produces a macOS `.app`, a Windows `.exe` with runtime files, or a
Linux executable with runtime files. It records the host, Qt version, launcher
source hash and runtime file hashes in `window.json`. The full SDK packager
requires `--emulator-window build/emulator-window-native` and checks the bundle
before and after copying it. It remains independent of the CLI's Python runtime.

Window bundles include wrapper source and upstream wheel notices. Qt/PySide and
Qt WebEngine/Chromium retain their own licenses; see the Qt licensing and
third-party notices supplied in those distributions. Existing SDK corresponding
source downloads include matching Qt/PySide/Chromium source and notices as a
shared desktop-window archive, alongside each platform’s compiler, runtime and
Lefony/QEMU archives. A successful window build alone is not a complete SDK
release qualification.

For a release, inventory the frozen window in its build environment with
`scripts/emulator_window_sources.py --toc <Analysis-00.toc> --window <bundle>
--output <inventory>`. Collect the exact native dependency sources identified
by that inventory. Pass both `--emulator-window-inputs <inventory>/inputs.json`
and `--emulator-qt-sources <upstream-source-directory>` to the full SDK packager.
It checks the native source versions, file hashes and pinned Qt/PySide archives,
then includes public input and source-verification reports in the SDK. The
private Debian collection input is build evidence and is not distributed.
This source verification does not claim byte-identical upstream wheel rebuilds.

The desktop-window CI job builds and smoke-checks the native wrapper on all
three operating systems. Its smoke uses a synthetic frame and checks that the
embedded renderer loads and exchanges frames; it does not qualify guest input
or physical hardware. The macOS OS/SDK journeys additionally exercise real
QEMU. Windows and Linux interactive acceptance should be recorded on those
hosts before calling complete SDK distributions qualified.
