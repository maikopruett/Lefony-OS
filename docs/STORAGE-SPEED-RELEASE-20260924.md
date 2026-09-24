# Storage installation performance — September 24, 2026

Published build `1.0.0+1790277950` for HP Prime G2. The corresponding [development release](https://github.com/maikopruett/Lefony-OS/releases/tag/build-20260924-1790277950) includes the signed OS capsule, firmware, emulator and audited working-tree sources. The existing production release identity is retained.

## Physical measurements

| Operation | Previous | Optimized |
| --- | ---: | ---: |
| Complete Doom 0.2.2 installation | 735.079 s | 105.601 s |
| 1 MiB named-file import/replacement | 221.791 s | 44.777 s |
| 2,105,488-byte native OS update, through byte verification | 21.671 s | 4.887 s |

The Doom result is about 7× faster. Its WAD transfer/application took 66.360 s and final commit 17.003 s; the rest includes the executable, three notice files and preflight. The previous successful Doom retry and new fresh installation use the same signed package and WAD, but differ in retained file/flash state. The 1 MiB baseline created a file; subsequent measurements replaced it. These are observed wall-clock results on one connected calculator, not universal speed guarantees. Reboot and the independent post-install data export are outside the install timing.
The first upgrade uses the currently running firmware writer; the new OS write
speed becomes available once the optimized firmware has booted.

The flash driver's successful page-program throughput measured **2.833 MB/s**, including BCH, copying, commands, bus transfer and array-ready waits. Doom programmed 30,906,368 bytes in 10.911 s. The reported program ready/status wait averages 221 microseconds per page, including polling overhead; it does not establish an absolute silicon maximum. USB RAM staging had previously measured approximately 27.2 MB/s. USB bandwidth therefore is not the current installation bottleneck.

The optimized Doom run includes 27.700 s in BCH reads, 10.911 s programming, 0.448 s erasing, 3.235 s block usability checks and 0.514 s erased-page fallback reads. Nested ready/DMA timings must not be added again. All program/erase/raw-read operations succeeded. The 1,037 failed BCH decodes were verified erased-page fallback cases, not accepted corrupt game data. Software, hashing, metadata checks and responsive scheduling account for the remaining elapsed time. This release does not claim the physical bandwidth limit is saturated.

## Implementation and validation

Known-length host imports reserve full file space once and use the existing fixed-length transaction, with chunk readback and explicit final digest/commit. A 256 KiB metadata cache reduces repeated filesystem lookups; writes and erases invalidate affected blocks before issuing commands, failed reads are never cached, and archive/developer-key consent revalidation clears both metadata caches. Ordinary file-content reads retain their backend path. Existing quotas, signatures, geometry, bad-block handling, atomic publication, cancellation and recovery behavior remain in place.

Platform work runs at most 64 existing steps or 16 ms per batch, servicing USB between steps. Pending native OS writes avoid the old idle sleeps. Individual already bounded driver calls can exceed the batch budget. There are no NAND clock/timing, partition, filesystem-version or release-key changes. Cumulative read-only profiling uses vendor IN request `0x56`; physical/VM reports are explicitly distinguished.

Both firmware targets compiled. The retained prepared VM sources rebuild byte-identical ELF/bin artifacts. ARM checks cover boot smoke, USB bulk/profile rejection and cancellation, file exchange, archive media faults, key media recovery and scheduling. Host fault tests exposed cache freshness requirements at archive and key consent boundaries; both were fixed before physical installation. Detailed host test counts and SDK/public-download evidence accompany publication. The website distinguishes transfer, installation and final verification, and SDK/browser bulk file deadlines allow slow devices while detecting stalled progress.

The prior installed OS was independently backed up twice with matching hashes before replacement. The new capsule was byte verified on NAND and the expected build was observed after reboot. Only the task-created benchmark file and the known Doom bundle files were present before authorized cleanup. Doom was restored with its bundled Freedoom data. All four files were exported and compared byte for byte with their originals;
the complete independent readback passed in 55.217 s. Results are retained
locally; no physical captures, private dumps or keys are included in source archives.

| Artifact | SHA-256 |
| --- | --- |
| Physical firmware | `0aa77960062e314f5746d725c9c2f5fa610537f364761644c55579eac820850b` |
| VM ELF | `d5afc42f0bb32b118509c39c8cd2054d0e256af0466b968a88c3569f3bf1d8b2` |
| Signed update capsule | `dc3b30e0efac16c1ce7b896b7040a5396aa9ede5d8043892018c3181aa078f22` |
| Freedoom Phase 1 WAD | `7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d` |

Private evidence is under ignored `build/install-speed-20260924/`. Emulator success and this one-device throughput test do not qualify physical power-loss recovery, endurance, all hardware/storage states or Doom gameplay performance. The SDK remains a development preview; Linux frozen-bundle checks run under CPU emulation rather than on a native Linux host.

## Publication completion

The signed OS release, refreshed macOS/Linux SDK bundles and corresponding
sources, website progress fix and public installer are published and verified.
The final host run passed 1,957 tests with two private-fixture skips. The website
passed 584 tests and five app-install browser checks. Both frozen SDKs passed
Notebook and file-transfer tests; Linux used CPU emulation. The installed macOS
SDK passed its 1,936-file audit.
