# Installed app launch performance

Installed apps previously authenticated the same package twice before leaving
the launcher: `NativeApp::load()` verified the signature and inner package,
then `AppManagement::open()` called `parseMetadata()`, repeating RSA verification,
both package hashes and manifest parsing on the same bytes.

The loader now returns its authenticated manifest after executable validation
and memory setup succeed. The installed-app session uses that manifest for
identity, version, data schema and capabilities. Every launch still reads the
package from storage and verifies its signature, integrity, supported manifest
and ELF layout. There is no persistent verification cache. Installed packages
still require signatures on both targets; unsigned VM developer previews retain
their separate entry point. The loader now checks signed-envelope/inner ABI
agreement itself, preserving the check previously performed by the second parser.

The benefit applies to installed apps generally, including legacy ABI 1 apps
such as Surface 3D; app packages do not need rebuilding. Built-in applications
do not use this package loader. App-specific initialization and asset reads are
unchanged.

## Reproduction

`vm/test-sdk-launch-latency.py` builds Counter in a temporary directory and
installs it into synthetic NAND using the public emulator fixture key. It runs
six Enter-key and six Goodix-touch launches across two emulator boots. These
use the normal input/controller path and include package loading, verification
and the Start callback. Installation and the finger-down hold before touch
release are excluded. Screenshots and a JSON report are retained.

Preserve the old VM ELF before rebuilding, then run baseline and candidate
sequentially with other build/test workloads finished:

```sh
.venv/bin/python vm/test-sdk-launch-latency.py \
  --firmware build/app-launch-baseline.elf --output build/app-launch-baseline
.venv/bin/python vm/test-sdk-launch-latency.py \
  --firmware dist/lefony-os-prime-g2-vm-native.elf --output build/app-launch-candidate
```

The output directories must be new. Timings are host elapsed time in QEMU,
not cycle-accurate hardware measurements. Each boot's timed launches follow
one untimed launch used by the existing SDK runner to establish installation.
This is not a measurement of the first launch after physical power-on.

## Measured result

On the same host and QEMU, with the same Counter package and no concurrent
build/test workload during the timed runs:

| Normal input | Baseline median | Candidate median | Reduction |
| --- | ---: | ---: | ---: |
| Enter key | 193.776 ms | 133.990 ms | 30.9% |
| Goodix touch release | 214.221 ms | 133.247 ms | 37.8% |

There are six samples per input method per firmware. All 12 corresponding
baseline/candidate frames are pixel-identical. The shared unsigned Counter
input has SHA-256
`7c48a894db5d2dd7ea17fe85344afef7a113729f5d543d5b34c82246ed852a7d`;
the runner signs it deterministically with the public emulator fixture before
installation. Raw timing reports are `baseline-run3/report.json` and
`candidate/report.json`; the pixel comparison is `comparison.json` under the
evidence directory below. The initial two baseline harness attempts were
corrected to use the Apps key and avoid pressing EE when Counter was already
selected; neither attempt produced a timing comparison.

## Qualification

September 24, 2026 local candidate, based on `a017cd036dbd` with the scoped
loader changes above:

| Artifact | SHA-256 |
| --- | --- |
| Baseline `prime_g2_vm` ELF | `af2beae50d1ac74e9a28cc37dea05bb8c3eb6799cb9454d31b635f042ddadc48` |
| Candidate `prime_g2_vm` ELF | `5ad671ac30b13b15fd1cb1bdb53d3fe2fd6ce3717031b4342b852090ffa16d6d` |
| Candidate physical `prime_g2` binary | `f26cb519641bc7543ef495b1a8465cc908073510f051e53d82a678b39f8e3841` |
| QEMU | `2c779a125a52f4e9e593f676a36e9994525860509d5ae5973dac841a26fb4f4f` |

Both builds passed with the existing public release/store trust configuration:

```sh
LEFONY_APP_PUBLIC_KEYS=ports/lefony-prime-g2/app-trust-roots.json make firmware-vm
LEFONY_UPDATE_PUBLIC_KEY=ports/lefony-prime-g2/release-signing.pub \
  LEFONY_APP_PUBLIC_KEYS=ports/lefony-prime-g2/app-trust-roots.json make firmware
```

The physical binary contains the existing release/store public moduli and
excludes the emulator fixture modulus. Both comparison VM ELFs contain the
existing store trust root. The expanded
`vm/test-sdk-contracts.py` passed 12 ARM cases, including invalid signatures,
payloads and signers, a correctly signed envelope with a mismatched inner ABI,
and a correctly signed invalid ELF entry point. The optional old-loader case
was skipped because no `--old-firmware` was supplied.

`vm/test-sdk-documents.py` passed signed FILE3 loading, data-only saves, cold
reopen, package upgrades, schema-0 acceptance, schema mismatch and faulted
close. `vm/test-native-comprehensive.sh smoke` passed all four selected cases.
`make test` passed 1,981 tests with two expected private-DTB/DTS skips.
`make check-public` and `git diff --check` passed.
The store-configured document test initially timed out in
`Controls.key('ok')` (`normal OS dispatch did not deliver the key`) while the
full host suite was running. The unchanged candidate passed the complete test
in isolation. The timeout's cause is not established; it is not claimed as a
confirmed pre-existing failure. Both logs are retained as
`documents-store.log` and `documents-isolated.log`.
Logs and detailed reports are retained under ignored
`build/app-launch-speed-20260925/`.

No physical calculator has been flashed for this change. Surface 3D's observed
two-second hardware launch still needs a before/after measurement on matching
firmware. This original candidate was local; the combined, versioned fixes were
subsequently [published as development release 1.0.0+1790315562](UI-STARTUP-RELEASE-20260925.md).
