# Back up private data and roll back a pending app upgrade

The development SDK provides explicit recovery commands over the app USB channel.
Close the app before running them. Firmware must advertise the data-recovery
extension (app hello flag 128); an older device is rejected before a recovery
request. The commands use the selected installed app's signed identity and saved
schema. They cannot enroll keys, install backup-supplied code or write firmware.

```sh
lefony-sdk data info my-app
lefony-sdk data export my-app ./my-app.lfdata
lefony-sdk data restore my-app ./my-app.lfdata
lefony-sdk data rollback my-app
```

Use the actual installed app ID. `info` reports the current package version/hash,
saved and installed schemas, private-data length/hash, pending-upgrade state,
retained rollback target and highest installed version. It does not write data.

## Private-data backups

`export` backs up the app's private byte store, up to 64 KiB. Named files require
the separate [file exchange commands](FILE-EXCHANGE.md). A private-data backup is
not a whole-app archive. Export remains available during a pending upgrade or
schema mismatch when the saved data is readable.

The SDK pins the observed generation/schema, checks the complete returned length
and SHA-256, then flushes and atomically publishes a local backup. It refuses to
replace an existing local file unless `export` includes `--replace`. A cancelled
or failed export preserves that destination. App-supplied names never choose
local paths; the user supplies the destination.

`restore` explicitly replaces the entire private byte store, including its length.
It preserves the installed package and named files. The backup's app ID and data
schema must match the installed app and saved data, with no pending upgrade.
The recorded package version is provenance; it does not request a package
downgrade. Restore validates the complete bounded local backup before USB access,
checks quota and generation, and stages the payload in RAM. No storage mutation
occurs until the complete digest matches and the final COMMIT is acknowledged.
An empty backup restores an empty private store.

The CLI retains those validated backup bytes in memory before opening USB. A
later change to the local pathname cannot substitute a different payload during
restore. Invalid, oversized, non-regular and foreign-app backups open no device.
The source and desktop entry points share this behavior. Explicit synthetic
transport options are described in [emulator qualification](FILE-EXCHANGE.md#emulator-qualification).

The format is `LFDATA1\0` (eight bytes), a little-endian uint32 JSON-header length,
that UTF-8 JSON header, and the raw private bytes. The header is at most 4096
bytes and contains exactly `schema` (1), `app`, `version`, `data_schema`, `bytes`
and lowercase `sha256`. Duplicate fields, malformed identities/versions, excessive
sizes, extra payload bytes and incorrect hashes are rejected. Backups contain
user data and integrity metadata; they are not signed app packages.

## Retained-version rollback

An [API 8 migration](DATA.md) retains the prior package/data pair until the app
explicitly accepts the upgrade. `rollback` selects that one retained pair from
the calculator. It does not accept a host file or an arbitrary historical version.
The firmware verifies the retained package signature, app ID, supported runtime
requirements and agreement between its signed schema and retained data schema.
The commit transaction verifies the referenced stored objects before publication.

The command binds BEGIN to the inspected current generation/schema and retained
package generation. BEGIN alone changes nothing. COMMIT restores the retained
package, private bytes and named-file generation together, and ends the pending
upgrade. Changes made by the newer app are replaced by the retained snapshot;
export any readable data that you want to keep first. Once the app accepts its
upgrade, this rollback path is no longer available.

Rollback preserves the highest installed version. Reinstalling the failed release
is refused; a corrected release must use a higher version. The SDK checks the
resulting package identity, schema, generation and preserved version watermark.
A failed final inspection explicitly reports that rollback already committed.

## Cancellation and uncertain completion

Before COMMIT, Ctrl-C or a client cancellation discards the staged restore. The
shared `files status` and `files cancel SEQUENCE` commands can inspect/cancel an
uncommitted transfer. USB reset or 30 seconds without transfer progress also
cancels it. The existing [transfer protocol](../docs/NATIVE-APP-FILE-EXCHANGE.md)
defines exact frame offsets and acknowledgement behavior.

After USB acknowledges COMMIT, the controller drains the transaction even if the
next event is a disconnect before OS polling starts. A lost commit response or
storage failure can leave the outcome unknown. No write is automatically retried
or cancelled after the commit request. Reconnect, run `data info`, and export
the saved bytes before deciding whether another restore is needed. A post-commit
inspection error is distinct from a failed pre-commit upload.

Ctrl-C uses the [file-exchange cancellation contract](FILE-EXCHANGE.md): the
current USB transfer finishes before cleanup. A prepared rollback can be
canceled before COMMIT; an already started commit finishes its receipt and
identity checks instead of being reported as canceled.

These are local development tools. A general damaged-media recovery workflow,
website recovery UI and physical qualification remain open. The separate
[whole-app archive candidate](ARCHIVES.md) can repair damaged mutable data when
its signed package is intact. The `data` operations described here require a readable current package/private store;
they do not repair a corrupt current root or bypass failed object verification.
See the [implementation ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md) for exact
host/ARM evidence and remaining limitations.
