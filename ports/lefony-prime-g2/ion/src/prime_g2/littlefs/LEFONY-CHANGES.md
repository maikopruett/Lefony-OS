# Local littlefs changes

Upstream: littlefs v2.11.3, commit
`6cb4e86540eca0d9ba62500a298385c9d863c8be`. The original
[lfs.c](https://github.com/littlefs-project/littlefs/blob/6cb4e86540eca0d9ba62500a298385c9d863c8be/lfs.c)
and BSD-3-Clause notices remain the basis of this vendored copy. No upstream
revision, filesystem format or flash geometry changed.

On 2026-09-13, `lfs_bd_read` was changed to call `lfs_cache_drop(lfs, rcache)`
when the backend fails while loading the read cache. That branch publishes cache
coordinates before calling the backend. A failed read can leave unchanged or
partially overwritten buffer contents; keeping those coordinates valid allows a
later short read to accept those bytes without consulting the backend again.
The direct-read branch does not populate that cache and is unchanged.

The regression in `tests/native/littlefs_read_error.cpp` uses real littlefs and
the production geometry. It covers I/O and corruption errors, an untouched or
partially overwritten failed buffer, repeated short reads and successful retry
after clearing the fault. Failed reads do not advance the file position or
publish output bytes, and the checks make no flash writes. Registry snapshot,
consent and transaction tests separately exercise this fix through production
storage integration. Exact build and ARM evidence belongs in the SDK ledger;
these host tests do not qualify physical NAND behavior.

On 2026-09-24, an optional `lfs_config.read_metadata` callback was added for
reads using littlefs's shared structure/allocator cache. NULL retains the
upstream backend path. Regular file reads, including application content hash
verification, retain their separate file cache and ordinary backend callback.
The Lefony volume supplies a bounded 128-page (256 KiB) RAM cache; it publishes
entries only after successful reads, clears them on mount, and invalidates the
entire affected block **before** every program or erase, including unsuccessful
attempts. Lower-level program readback therefore cannot consume pre-write data.
Archive consent and commit revalidation explicitly clear both structure caches
before inspecting the medium, so an external root change cannot be hidden.
The archive fault fixture covers this stale-root case before publication.
No record size, NAND page/block geometry or filesystem version changed.

`test_app_storage_cache.py` measures backend page reads against the independent
uncached fixture on the same populated media. Storage, named-file, archive,
registry and root fault tests cover atomic publication and failed/torn writes.
