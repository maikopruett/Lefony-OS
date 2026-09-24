# Minigzip C portability candidate

This is the existing zlib **1.3.2 minigzip utility**, using the SDK's ordinary
`foreground-newlib-1` startup, allocation, descriptor and stdio adapters.
The engine sources retain their upstream notices. The 0.2 adapter requires local
API 12 and capabilities 8 + 16 + 8192 (8216). A marked modification to the
utility stages its destination directly, verifies complete gzip processing,
checks a direct descriptor close, then releases the detached stream buffers.
It checks deferred gzip read errors before another read and removes the input
only after committing output. No new `.part` file is created, and existing
partial files are not automatically deleted.

From the OS or source SDK checkout, prepare an external project once:

```sh
python3 scripts/prepare_sdk_minigzip.py --project /tmp/minigzip -- input.dat
python3 sdk/tools/cli.py --project /tmp/minigzip package
python3 sdk/tools/cli.py --project /tmp/minigzip source --format 2
```

Preparation downloads a pinned archive and verifies its published SHA-256 and
the selected file hashes. `--archive PATH --offline` uses a local archive.
Existing projects are preserved. Build/package/source thereafter are ordinary
SDK operations; no application-specific firmware or private execution hooks
are used. The source package contains the complete selected C/header inputs,
notices, configured flags and arguments. Libraries and compiler are pinned by
the normal SDK lock. The script is maintainer tooling, not a project build hook.

`project.json` arguments choose upstream file-mode options: `input.dat`
compresses to `input.dat.gz`; `-d input.dat.gz` decompresses. A successful
operation removes its input, following minigzip behavior. Paths are app-private,
relative and limited by the SDK file contract. The profile has no standard
terminal streams: pipe/stdin/stdout mode and useful console error text are not
supported. This candidate returns a nonzero exit on tested failures.

Use `lefony-sdk files import minigzip input.dat ./input.dat` while the app is
closed, then run the matching package. Export the result with
`lefony-sdk files export minigzip input.dat.gz ./result.gz`. The
SDK's `FILE-EXCHANGE.md` documents permission, identity and overwrite checks.
The original `vm/test-sdk-minigzip.py` seeds synthetic storage and independently
checks output; `vm/test-sdk-minigzip-workflows.py` uses the public file exchange
for user inputs, outputs and retries. Do not substitute an empty startup test
for useful input, gzip integrity, cold reopen and error acceptance. Physical and release
qualification remain open.

Nine signed ARM cases now pass: missing input, large compression, cold
decompression across an update, host-produced gzip, truncated and CRC-corrupt
inputs, a corrected-input retry of each identical failed package, and path
rejection. The input is 262,176 bytes and compressed output 262,274 bytes.
Host decompression and exact exports check the output; source-format-2
extraction rebuilds identical ARM bytes. The separate public-exchange workflow
covers 15 workloads and 40 phases: ordinary/empty compression and decompression,
unsupported stdin/stdout, full-quota replacement in both directions, a one-byte
output shortfall, rejected growth and retry, corrupt/truncated input and repaired
retries, real heap exhaustion, Home interruption and cold reopening. It preserves
an existing legacy partial file and verifies that failed/aborted conversions do
not advance the committed root. Successful output is checked independently.

The pressure fixture retains more than 7 MiB through real `malloc` calls; it
does not replace the allocator. Read-only GDB samples measure retained heap and
locate an in-progress staged write before normal Home input. Public file exchange
supplies all user inputs and repairs; only the full-quota filler uses the
host-compiled production filesystem. No test writes a physical calculator.

From the OS checkout, use the matching API 12 VM candidate:

```sh
.venv/bin/python vm/test-sdk-minigzip.py --firmware dist/lefony-os-prime-g2-file-abort-vm.elf --output build/minigzip-regression
.venv/bin/python vm/test-sdk-minigzip-workflows.py --firmware dist/lefony-os-prime-g2-file-abort-vm.elf --output build/minigzip-workflows
```

Choose a new output directory; `--cases` selects named workflow cases. Reports
record firmware, package and source hashes, public exchange results, exit status,
preserved bytes and observed elapsed time. These are synthetic per-app quota
tests, not physical full-media, power-loss or endurance qualification. Shared
flash exhaustion and modeled read faults have a separate 23-phase ARM matrix:

```sh
.venv/bin/python vm/test-sdk-minigzip-media.py --firmware dist/lefony-os-prime-g2-media-io-vm.elf --output build/minigzip-media
```

Compression and decompression retain input and the prior destination when an
input page becomes unreadable or the shared filesystem is full. Retries succeed
after clearing the modeled fault or freeing fixture files, with cold reopening
checks. A corrected-read case retains the original decoded bytes. The fixture
fills real synthetic littlefs blocks independently of the app quota; QEMU fault
registers select the read error. An emulator-only constructor gate waits for
model setup before ordinary `main`; it replaces no allocator or file syscall.
Physical read correction, program/erase failures, power loss, endurance and
timing remain separate qualification work. Exact candidates and reports are in
the SDK implementation ledger.

A failed first run of an app update retains package/data recovery state. The
test corrects the input and retries the identical package successfully before
installing another version. It does not bypass pending-upgrade protection.
Offline fixture preparation is not a substitute for public data exchange.
The workflow test uses an unchanged package across input repairs, so public
imports do not need to bypass pending-upgrade protection.

The library uses `DYNAMIC_CRC_TABLE` to construct CRC tables in app memory and
omit the unused 591,749-byte precomputed header from source exchange. This is
an upstream build option, with no compression-library source changes. All
selected files fit the existing source-format-2 limits.

Upstream minigzip is an example utility with limited error handling. The port's
limited supported behavior is documented here; it is not a general gzip CLI or
a complete zlib support guarantee. zlib sources are under the Zlib license;
the conventional SDK runtime now offers a scoped MIT alternative. The existing
minigzip recipe still selects its original CC-BY-NC-SA-4.0 alternative, recorded
with Zlib in the manifest; it does not grant rights over unrelated SDK code.

The unmodified upstream 1.3.2 utility was reproduced returning success for a
gzip input missing its eight-byte trailer. `gzread` can return bytes while
recording a recoverable error; its next invocation can clear that status. The
marked utility adaptation checks `gzerror` immediately after each read. The
compression-library sources remain unchanged.

## Transaction and cleanup contract

`gzflush(Z_FINISH)` emits and checks the complete compressed stream before the
adapter saves it. Decompression checks the input's final status and close before
flushing output. Direct descriptor `close` commits the resulting file and
invalidates its writer, without reopening it. Only afterward does
`gzclose`/`fclose` release library buffers. The expected invalid-descriptor result
from that cleanup cannot write another gzip member or publish a partial file.
This uses ordinary public SDK operations, with no changes to zlib sources,
successful syscall stubs or new file-service operations.

An `atexit` handler aborts an uncommitted writer before normal stdio cleanup on
processing/allocation errors. If abort itself fails, `_exit` transfers cleanup
to the OS instead of allowing buffered output to publish. Home/fault cleanup is
also OS-owned. A failed commit can be ambiguous: the input is retained, and the
user must inspect the destination before retrying. Successful output followed by
failed input deletion can leave both files present; this is reported as failure.
The input and output are not one atomic multi-file transaction.

Direct replacement credits the previous destination's length toward the logical
quota. It still needs shared flash headroom. The full-quota workflow seeds only
the large filler through the host-compiled production filesystem; actual input
imports, retries, execution and output exports use the normal public interface.
Consult the SDK implementation ledger for completed cases and current resource,
interruption and physical-qualification limits.

The cleanup design follows zlib's documented ownership: `gzdopen` associates a
descriptor with a gzip stream, and `gzclose` writes pending bytes before closing
that descriptor. The pinned 1.3.2 sources are checked alongside the
[zlib manual](https://zlib.net/manual.html); the website manual currently identifies
itself as 1.3.1. Explicit commit or abort invalidates the owned descriptor before
codec cleanup, and SDK handles cannot be reused to target a newer writer. This
cleanup sequence relies on that SDK contract and is not a generic POSIX pattern.

Sources: [zlib release and published digest](https://zlib.net/),
[upstream minigzip](https://github.com/madler/zlib/blob/v1.3.2/test/minigzip.c),
[license](https://github.com/madler/zlib/blob/v1.3.2/LICENSE).
