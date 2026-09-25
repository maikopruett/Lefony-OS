# Maintainer macOS SDK trial

The current trial scope is the maintainer's Mac. This is development feedback;
independent developer and clean-host acceptance remain unverified. No calculator
is needed for the steps below. Physical USB, power-loss recovery and flash
endurance require a separate, explicitly authorized hardware session.

## Candidate

The public macOS ARM64 SDK includes the shared desktop QEMU emulator, the
complete 51-key Prime keyboard and a 320 × 240 touchscreen. Layout and Scale
controls resize the calculator together. Frozen desktop checks pass touch and
keyboard counter input, clean Stop, and Notebook edit replay.

The SDK **0.2.0-dev**, ABI 1 candidate requires macOS 26+ on Apple Silicon.
Its archive SHA-256 is:

```text
181aee86153bc6cda200ba23416f519a88d58f1ed191c72f32cc0a0cff3e3136
```

Download it from [lefony.com](https://lefony.com/#developers). Exact source hashes
and public rollout evidence are in the
[desktop SDK release record](DESKTOP-SDK-RELEASE-20260925.md).
Existing projects retain their SDK lock; use `lock --update` explicitly when
choosing to adopt this revision. Their saved workspaces remain independent.

It includes the current SDK, native ARM compiler and GDB, Python, Prime emulator,
store-enabled VM firmware and public store trust. It is locally signed for
execution, without Developer ID distribution or notarization qualification.
The bundled `candidate.json` and `SHA256SUMS` identify its exact inputs/files.

## Try the developer workflow

Extract the archive into a fresh directory with room for about 2 GB of SDK
files and separate projects. In Terminal, enter the extracted `lefony-sdk`
directory. Keep `_internal` beside the executable. Then run:

```sh
./lefony-sdk doctor
./lefony-sdk new ../Trial-Notebook --template notebook
./lefony-sdk --project ../Trial-Notebook test --headless --workspace trial
./lefony-sdk --project ../Trial-Notebook preview --once
open ../Trial-Notebook/build/preview/frame.png
./lefony-sdk --project ../Trial-Notebook run --workspace trial
```

The last command opens the desktop window described above.
Review the Notebook's
labels, controls and text; save a change through its own UI, then quit and run
that same command again. Record whether the saved document reappears. The
`trial` workspace contains synthetic calculator storage and is separate from a
physical calculator. Use **Stop emulator** after saving to close the app and
drain storage. Closing the desktop window performs the same cleanup and ends
the terminal session. No browser or reconnect URL is used.

Edit the project's C/C++ source and run `preview` without `--once` to watch
saves. It writes the current captured ARM frame and layout report beneath
`build/preview/`. Stop the watcher with Ctrl-C. Record the first build and later
edit-to-preview wait separately, including any unexpectedly frozen or incomplete
screen. The automated checks do not supply human usability acceptance.

## Account check

If this Mac already has an approved Lefony SDK session, the new executable can
read it from macOS Keychain:

```sh
./lefony-sdk whoami
./lefony-sdk apps list
```

Otherwise use `./lefony-sdk login` and follow its browser instructions. Do not
include credentials, browser codes or private keys in trial notes. Publication
creates public store content: prepare a distinct trial app and its listing, and
review `publish --dry-run` before an intentional publication. Existing public
apps are not disposable trial fixtures.

## Record the result

For each attempt, record the archive hash, macOS version, CPU architecture,
command, observed result and any non-secret diagnostic/report path. Useful
feedback includes:

- Where installation or the first project required guessing.
- Whether build errors point to a useful source location.
- Text readability, selection, scrolling, clipping and input responsiveness.
- Preview latency on first build and after a small edit.
- Whether an explicitly saved document survives closing and relaunching.
- Whether Keychain/browser prompts are understandable.

A passed automated run is recorded separately from maintainer feedback. The
[implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md) remains the source of
qualification status and outstanding SDK 1.0 requirements.
