# Physical installation performance

The September 24 Doom baseline is 28,795,076 bytes received in RAM in 1.058 s,
605.176 s in file application, and 94.325 s finishing the commit. Successful
end-to-end retry: 735.079 s. The ten-minute host timeout was corrected separately.

The user authorized physical measurement, optimization, repeated app/firmware
installation tests and publication of the required firmware, SDK and website.

1. Install a timing-only firmware candidate after both target builds and normal
   boot/protocol tests. Add cumulative, read-only NAND driver counters at IN
   request `0x56`; no raw write/erase benchmark command or address input.
2. Measure ordinary allocator-owned file writes and reads on the connected
   Prime. Compare driver programming/read/erase time, NAND ready waits, block
   checks and command DMA against complete installation time. Nested categories
   are not additive. This measures the current raw driver's throughput and
   array waits; it is not proof of an absolute electrical/silicon ceiling.
3. Use those measurements to optimize repeated block checks, allocation and
   verification, and bounded file processing. Preserve signatures, geometry,
   bad-block handling, quotas, readback, existing file formats and atomic commit.
   Avoid hardware timing/clock changes without primary-source verification.
4. Run host and emulator storage/fault tests and both firmware builds. Repeat
   physical Doom installation, verify the committed game data and compare exact
   byte counts and elapsed phases. Restore the requested ready-to-play Doom app
   and remove only the temporary benchmark data created by this task.
5. Publish tested firmware, SDK bundles and corresponding sources, and the
   website progress/timeout fix. Verify public hashes and preserve existing
   release keys and app data. Publication may require Cloudflare reauthorization.

Private artifacts, captures and physical measurements remain in ignored
`build/install-speed-20260924/`. Earlier evidence remains in
`build/physical-doom-20260924/`. No private captures or signing keys are published.

## Measured baseline and first optimization

Timing-only physical build `1.0.0+1790275148` booted after a signed, verified
native installation. The prior installed OS was independently read twice and
retained locally before replacement. The 2,105,488-byte OS update completed
writing and byte verification in 21.671 seconds, then booted the expected version.

A 1,048,576-byte deterministic file was imported into the existing Doom namespace
through the SDK file API and committed with its expected SHA-256. Its 221.791 s
includes catalogue inspection (4.864 s), preparation (94.128 s), transfer and
application (25.781 s), and final commit (96.997 s). Existing game data remained.
The driver recorded 550 successful page programs in 0.397603 s: **2.833 MB/s**,
including commands, copying, BCH, bus transfer and array-ready waits. Eighteen
successful block erases took 0.020666 s. The ready/status portion of programming
averaged 221 microseconds per page; this includes polling and status commands,
so it is not a pure NAND datasheet tPROG or proof of an electrical maximum.

The import requested 148.904 MB of BCH page reads. Of 72,707 read attempts, 3,117
used the existing verified-erased-page fallback, rather than reporting damaged
user data as readable. All program, erase, block-check and raw-read operations
succeeded. Total disjoint driver time was 39.821 s. Nested DMA and ready-wait
counters are excluded from that sum. The remaining time motivates batching
storage state-machine steps between full platform scans and measuring redundant
reads before considering any driver or filesystem changes.

The first optimization uses up to 64 existing steps or 16 ms per platform scan,
servicing USB between steps. Completion/failure ends the batch immediately.
Unsigned timer arithmetic handles wrap, and the iteration limit handles a stopped
timer. An individual bounded operation can exceed the batch time budget. OS
updates also count as deferred work, removing their former idle sleeps.
Read-only profile snapshots are available during active transfers; no write,
reset, arbitrary address or raw NAND benchmark command was added.

The benchmark file was subsequently exported through the SDK and compared byte
for byte against its local source. This complete physical readback passed.

## Import and filesystem changes

The first batched physical replacement completed in 69.419 s (the initial file
was already present): preparation 26.112 s, transfer/application 11.477 s, and
commit 26.994 s. Its expected SHA-256 and committed generation were confirmed.
A larger single littlefs cache was evaluated and rejected: it did not reduce
reads in the targeted host experiment and exceeded the registry RAM bound.

Named imports now use the existing declared-length `beginFile` transaction.
Quota, exclusive-create/replace, schema, legacy conversion, expected digest,
per-chunk physical readback, root publication, cancellation and disconnect
boundaries remain enforced. Space is admitted for the full file once instead
of using the unknown-length streaming writer's per-chunk admission. Ordinary
app-created streams retain their existing growing-file behavior.

The filesystem also has a separate, bounded 128-page structure cache. Entries
are cleared on mount, failed reads are not cached, and all entries in an affected
block are invalidated before program/erase, including failures. Normal file-data
reads and application content hashing bypass it. Archive authority revalidation
clears both metadata caches before rereading the root across consent and commit
boundaries; the existing external-root-change fault test caught and now covers
this requirement. See the precise littlefs hook
and validation contract in [littlefs changes](../ports/lefony-prime-g2/ion/src/prime_g2/littlefs/LEFONY-CHANGES.md).
A representative synthetic 28,795,076-byte file workload fell from 222,778 to
45,811 backend reads. Writing a subsequent 1 MiB file fell from 13,184 reads
with streaming admission to 1,159 with fixed-length admission and the cache.
These are host operation counts, not physical timings.

The physical measurement launcher encountered a macOS libusb shutdown deadlock
after an already verified reboot. Independent read-only inspection confirmed
the new firmware. Subsequent measurement launchers isolate reboot/USB teardown
from reconnection checks so cleanup cannot hide the device's actual result.

The completed candidate measurements and release identities are recorded in
[the storage-speed release](STORAGE-SPEED-RELEASE-20260924.md).
