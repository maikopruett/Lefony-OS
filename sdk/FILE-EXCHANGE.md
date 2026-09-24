# Import and export app files

The development SDK adds explicit file management over the app USB channel.
Close the app on the calculator before transferring its data. This requires
firmware advertising file-exchange protocol 1; older firmware is rejected before
any transfer request. This candidate is not physically qualified.

```sh
lefony-sdk files info doom
lefony-sdk files list doom
lefony-sdk files import doom freedoom1.wad ./freedoom1.wad
lefony-sdk files export doom doomsav0.dsg ./my-save.dsg
lefony-sdk files import doom doomsav0.dsg ./my-save.dsg --replace
lefony-sdk files status
lefony-sdk files cancel 17
```

Use the actual installed app ID and app-relative file names. The `list` command
accepts an optional directory. `status` reports the current transfer sequence;
pass that exact value to `cancel`. These commands never select firmware, raw
NAND, other apps' files or a recovery partition. Import/export is a separate
user action; package installation does not export data automatically.

`--replace` is required to replace an existing destination. On import that means
the app's file; on export it means the local destination. An export is written
to a private temporary file, checked for exact size and SHA-256, flushed and
published only on success. A failed or cancelled export preserves an existing
local destination. Paths received from the calculator never choose a host file.

Imports use the installed app's identity, current data schema and root generation.
A generation change requires a fresh inspection. Imports are refused during a
pending app upgrade or schema mismatch; exports remain available to recover
readable data. Imports accept regular local files only. Hashing reads the
declared length in bounded chunks and can be cancelled before USB transfer.
Source length and SHA-256 are computed before import. The device
checks quotas, streams into an uncommitted replacement, checks the complete hash
and only then publishes the new root. A changed or truncated source cannot
silently publish different bytes. Individual files are atomic; a series of
imports is not a multi-file transaction or a data-schema migration.

The normal quota is 32 MiB of mutable data per app, including its private byte
store. Shared flash space, retained roots and file-index limits also apply.
Existing oversized data remains readable/editable under the [quota policy](FILES.md#per-app-quota-policy).
Directory parents must already exist. [Private-data backup/restore and retained-pair
rollback](DATA-RECOVERY.md) use the separate `data` commands and require the
recovery extension. The separate [whole-app archive candidate](ARCHIVES.md)
transfers signed code and complete current/retained data snapshots together.
App-side checkpoint/migration controls use the separate [data API](DATA.md).

Transfers have bounded frames and operation waits. Cancellation before the final
commit discards staging. Disconnection or 30 seconds without progress while
waiting for the host cancels an uncommitted session. Processing an acknowledged
commit continues to a result even if USB disconnects. A lost commit response is
ambiguous: the SDK does not retry or automatically cancel it. Reconnect, inspect
and export the saved file before deciding whether another import is needed.

The CLI handles Ctrl-C after the current bounded USB control transfer finishes.
Before commit it cancels the owned session and exits with status 130; repeated
Ctrl-C does not interrupt cleanup. Cleanup waits for an acknowledged chunk to
finish processing before sending CANCEL. If commit has already started, it finishes
the bounded receipt check and reports the actual result, including an unknown
outcome when the connection fails. A verified commit remains success. These
rules also apply to `data` and `archive` transfers. Read-only inspection commands
finish their bounded exchange before reporting cancellation.

The current firmware candidate fixes a control-transfer status race: a completed
status ACK is processed before a following SETUP can abandon the previous frame.
The SDK still refuses unexpected offsets and reports the expected/observed values;
it does not retry ambiguous writes. The whole-WAD ARM/USB-model journey also
passes exact import, quota refusal, cancelled replacement and cold export;
these results do not establish physical transfer behavior.

The CLI uses a bounded libusb adapter that accepts only app file-management
requests. Source SDK users install libusb using the host's package manager;
the desktop SDK includes its native library. Native Windows and
physical throughput/disconnect/power-loss qualification remain open. The SDK
client can also use the existing synthetic QEMU USB transport for tests; those
checks do not contact a physical calculator.

## Emulator qualification

The explicit `files --emulator-usb PATH OPERATION`,
`data --emulator-usb PATH OPERATION` and `archive --emulator-usb PATH OPERATION`
forms use an already enumerated QEMU USB socket. The runner must exclusively
lend its connection until the command exits. Each family retains its ordinary
request restrictions, signature/generation checks and commit behavior. The model
adapter never enumerates or resets USB, discovers a physical device or falls back
to hardware. These forms are for controlled emulator tests; ordinary app preview
uses synthetic workspaces automatically. Exact packaged workflow evidence is
recorded in the implementation ledger.

See the [wire protocol](../docs/NATIVE-APP-FILE-EXCHANGE.md) and implementation
ledger for validation evidence. Website file-management UI is not yet included.
