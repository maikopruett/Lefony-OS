# App USB channel — API 11 candidate

Include `lefony/channel.h` from C11 or C++17. Service 17 requires capability
4096 and API 11. Add that bit to `required_capabilities` and set
`minimum_api: 11` when an app depends on it. Older firmware returns `-3`;
an app which did not declare the capability receives `-5`. Existing ABI,
package, storage and installer protocols retain their meanings.

This is a local implementation candidate. See the
[implementation ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md) for exact
builds and evidence. The USB-to-HTTPS adapter and companion command now connect
the channel to the worker below. The [Link Gallery](examples/link-gallery/README.md)
application is an integrated local candidate. Existing downloads do not contain
these changes; host packaging and physical qualification remain open.

## App lifetime and consent

Only the foreground, authenticated installed app can open a session. Call
`lefony_channel_open(&session)`, then query `lefony_channel_info(&info)` while
yielding or sleeping through the ordinary foreground API. OPEN returns a new
nonzero session ID; it does not wait for a host or grant network access.

The states are CLOSED (0), WAIT_HOST (1), WAIT_USER (2), CONNECTED (3) and ENDED
(4). A host attaches to WAIT_HOST with a fresh random nonce and a printable
label. The OS displays the app name, host label and a six-digit comparison
code. Physical OK/EXE allows that session; Back denies it. Touch cannot approve.
Home, Apps and power retain their OS behavior. Pairing pauses app execution
and input delivery. Confirmation keys still held when the app resumes are
blocked until release; stale contacts and queued input are cleared.

Temporary brightness and clipboard grants end when the consent screen opens.
The app can make a new permitted request after consent. The host verifies app
ID, signer ID and optionally an exact package payload hash before attaching.
The payload hash and signer ID come from the authenticated LFAPP1 envelope,
not app-supplied request fields.

Consent is session-only. The comparison code and nonce do not encrypt USB,
authenticate a host against a compromised computer, or protect traffic from
another process with access to the same USB device. Host access policy remains
necessary. No persistent pairing key or credential vault is supplied here.

## Messages and limits

Each direction has four copied message slots. Each message has a kind from
1 through 65535 and zero through 448 payload bytes. Sequence numbers start at
one independently in each direction. The app's SEND copies bytes before it
returns, so its source buffer can immediately be reused. RECEIVE returns one
complete message with its kind, length and sequence. A too-small destination
does not consume the message. Long transfers must be split and paced by the
application protocol; message delivery alone is not a durable save or proof
that a remote HTTP mutation completed.

`lefony_channel_send(session, kind, bytes, length)` and
`lefony_channel_receive(session, bytes, capacity, &result)` return zero on
success. Empty/full queues return `-6`; yield and retry the same operation.
INFO reports queue counts, sequence counters and the next received message
length. Invalid calls preserve request/output bytes. Request and buffer ranges
cannot overlap, and all pointers must have the required app read/write ownership.

| Negative result | Meaning |
| --- | --- |
| -3 | Firmware does not implement this service |
| -4 | Invalid size, flags, operation, pointer or argument |
| -5 | Capability/foreground/installed ownership denied, or user denied consent |
| -6 | Not connected yet, full send queue, empty receive queue, or an open session already exists |
| -7 | Session ID is stale |
| -8 | Host disconnected or OS ended the session |
| -9 | Pairing deadline or host lease expired |
| -10 | App explicitly closed the session |
| -11 | Session/sequence space exhausted; counters never wrap into a reused ID |
| -12 | Receive buffer cannot hold the complete next message |

The combined WAIT_HOST/WAIT_USER deadline is 30 seconds from OPEN. Connected
sessions require a host keepalive or accepted host frame/ACK within five seconds.
Status reads and app activity do not renew the lease. Identical attach retries
do not extend the pairing deadline or clear queues. Backward clock observations
also expire the session. Close, timeout, bus reset, USB shutdown, firmware-update
ownership, Home/focus loss, app exit and fault release both queues. A reopened
session cannot read its predecessor's queued messages.

## Host transport

[`channel_device.py`](tools/channel_device.py) accepts the narrow `read`/`write`
USB transport used by SDK clients. Its `Client` requires the expected app ID
and 32-byte signer ID; callers can also pin the package payload hash. `attach`
returns the comparison code. `paired` waits for calculator consent; `keepalive`
maintains a connected session. This client sends only channel requests.

| USB request | Direction and contents |
| --- | --- |
| 0x78 | IN: 320-byte channel information, argument zero |
| 0x79 | OUT: 64-byte attach, including session, random nonce and host label |
| 0x7a | OUT: 64-byte frame header plus 0–448 payload bytes |
| 0x7b | IN: peek the next app frame; argument is the session ID |
| 0x7c | OUT: 32-byte acknowledgement of one app sequence |
| 0x7d | OUT: 32-byte keepalive |
| 0x7e | OUT: 32-byte host close, including while consent is pending |

All OUT arguments are zero. Wire integers are little-endian uint32 values;
[`channel_wire.h`](include/lefony/channel_wire.h) defines exact layouts and
reserved fields. The host nonce and session bind data and control frames.

Host reads do not consume app messages: call `acknowledge()` after accepting
one. Retrying the same ACK is safe after lost USB status. A failed SEND retains
its exact pending frame; `flush()` checks whether that sequence was accepted
before retrying it. A full device queue returns false and applies backpressure.
No different logical frame replaces an uncertain send. These rules reconcile
transport acknowledgement; they do not authorize repeating an HTTP request.

## Running the HTTPS companion

Inspect the signed package you installed, using its trusted public key:

```sh
lefony-sdk inspect installed-gallery.lfapp --public-key app-public.pem
```

The verified report includes `signer_id` and `payload_sha256`. Unsigned packages
report null for both. Copy the signer ID into the command below, replacing
`SIGNER_ID_FROM_INSPECT`, and grant the exact HTTPS origin your app needs:

```sh
lefony-sdk companion --app-id link-gallery --signer SIGNER_ID_FROM_INSPECT \
  --allow-origin https://gallery.example.org
```

Open the app's connection screen, compare the six-digit codes, and press physical
OK. The default method grant is GET/HEAD. Repeat `--allow-origin` for another
origin or explicitly add `--method POST` (and other required methods) to replace
the default grant. `--package-hash` additionally pins the exact installed
payload. Byte/deadline limits can be lowered with `--upload-limit`,
`--response-limit` and `--timeout-ms`. `--ca-file` selects a host CA bundle for a
controlled HTTPS service; it does not disable certificate or hostname checks.

This command connects to the calculator's app channel. It cannot issue app-file,
installer, diagnostics, recovery or firmware commands. It validates app/signer
identity before attach and policy before network work. The host grant is attached
to this invocation and paired session; it is not a persistent credential store.
It logs request IDs, phases and byte counts, without URLs containing query data,
headers or bodies. Ctrl-C closes the channel and stops network work. Reconnect
requires running the companion again and opening/confirming a fresh app session.
The companion does not retry the interrupted HTTP request.

The current local macOS frozen companion passes eleven ARM/model-USB cases,
including streaming, failures, disconnect and terminal-fragment handling. Other
native hosts and physical libusb behavior still require qualification. Exact
candidates are in the [SDK ledger](../docs/NATIVE-APP-SDK-1.0-PROGRESS.md).
Private signing-key enrollment uses the separate [key workflow](KEYS.md).

## HTTPS messages from C/C++

Include [`lefony/https.h`](include/lefony/https.h). Companion protocol 1 uses
the existing API 11 channel; it adds no firmware service or capability bit.
One request may be active per session. Use a nonzero request ID greater than
every previously used ID in that session. A new paired channel starts a fresh
request-ID space.

Send a 32-byte `LefonyHTTPSBegin` with schema 1, request ID, method, upload size
(or `LEFONY_HTTPS_UNKNOWN`), response limit, deadline, URL byte count and request
header byte count. Then send ordered URL/header fragments through
`lefony_https_metadata`. URLs are 1–2048 percent-encoded ASCII bytes; headers
are at most 4096 ASCII bytes consisting of `Name: value\n` lines. The metadata
contains no terminator. The method constants are GET=1, HEAD=2, POST=3, PUT=4,
PATCH=5 and DELETE=6. GET/HEAD declare a zero upload length.

| Kind | Wire payload |
| --- | --- |
| 0x100 BEGIN | Eight uint32 fields in `LefonyHTTPSBegin` |
| 0x101 URL / 0x102 HEADERS | Request ID, byte offset, 1–440 metadata bytes |
| 0x103 UPLOAD | Request ID, offset, final flag (0/1), 0–436 body bytes |
| 0x104 CANCEL | Request ID |
| 0x180 RESPONSE | `LefonyHTTPSResponse`: schema, ID, HTTP status, header byte count, uploaded bytes, expected response length or unknown, zero flags/reserved |
| 0x181 HEADER / 0x182 DATA | Request ID, byte offset, 1–440 bytes |
| 0x183 DONE | Request ID, uploaded bytes, response bytes, zero flags |
| 0x184 ERROR | Request ID, error code, flags, last known uploaded/response counts, zero reserved |
| 0x185 CREDIT | Request ID, next upload offset, maximum bytes permitted (0–436) |
| 0x186 PROGRESS | Request ID, uploaded/response counts, phase (1 connecting, 2 request starting) |

All fields are little-endian uint32. Upload exactly one chunk per CREDIT; mark
the final chunk, including a zero-byte final chunk when ending an unknown-size
stream. A zero-byte known body needs no upload messages. Do not declare an
upload complete until the protocol terminal result arrives. CREDIT offsets and
DATA offsets also provide incremental progress. Response headers are emitted
as Latin-1 `Name: value\n` bytes, before body DATA. Folded header values and
ambiguous framing are rejected. The helper does not parse response payloads.

Check every frame's kind, size, ID and offset. Drain complete channel messages;
return to the app loop on `-6` so input, cancellation and rendering continue.
Commit a downloaded file only after DONE and application-level content checks.
ERROR codes are policy=1, protocol=2, TLS=3, network=4, timeout=5 and cancelled=6.
Flag 1 means a mutation may have reached the server without a response status
delivered to the app. Byte counts on errors are the last known progress, not
proof of server-side commit. Keep your own bounded request deadline as well as
the companion deadline; close the session if a peer stops honoring the protocol.

`lefony_https_cancel` cancels an active request. Previously queued body frames
can still arrive before ERROR; discard them if cancellation has been requested.
Cancellation can also race with DONE, so the app decides whether to retain or
discard that completed response. A subsequent request needs a new ID. Protocol
violations or transport loss can end the channel; never automatically replay
a mutation on a replacement session.

The companion retains the most recently completed request ID while idle. A
well-formed trailing URL/header fragment, upload chunk or CANCEL for that ID is
acknowledged and discarded, without another result or network operation. This
covers fragments already in flight when an early ERROR or DONE was queued over
USB; sending that terminal frame does not mean the app has consumed it. The
original terminal result remains authoritative. A newer BEGIN ends this drain
window. Reused BEGIN IDs, foreign IDs, unknown kinds and malformed fragment
shapes remain protocol errors. Apps must still stop sending the completed
request once they observe its terminal result and use a new ID for refresh.

The maintainer's `vm/test-sdk-https-terminal.py` schedules these boundaries with
Link Gallery, normal calculator consent, the model USB channel and local TLS.
It delays reception of real queued fragments without altering them, then checks
cache preservation and explicit refresh. See the SDK ledger for exact candidate
results. `vm/test-sdk-frozen-companion.py --modes terminal` additionally runs a
signed C conformance app through the actual frozen companion and worker. The app
deliberately delivers well-formed fragments after consuming ERROR/DONE to exercise
the host's late-delivery path, then completes new requests without another pairing.
It verifies two HTTP requests and exact cached bytes; it does not measure physical
transport latency. Released desktop bundles have separate qualification.

## HTTPS worker implementation

Advanced emulator tooling can pass `companion --emulator-usb SOCKET` to use an
exclusive, already-enumerated QEMU USB endpoint. The same app/signer/package,
origin/method grants and normal on-screen pairing consent apply. This option
opens only the selected local model socket and never discovers a physical
calculator. It cannot reset/enumerate USB or issue file, installer or diagnostic
requests. An unavailable model socket fails without a physical fallback.
Tools holding `PrimeUSBHost` can use its `lend_connection()` context while the
external companion runs; the borrower must exit before the original host resumes.
This model path qualifies guest/host behavior, not physical USB electrical timing.
The CLI records Ctrl-C and finishes its current bounded USB transaction before
cancelling the HTTPS worker and closing the app channel. Pairing and connection
steps check cancellation before advancing to the next operation. Console consent
and progress messages are flushed immediately for pipe/GUI launchers.

[`https_worker.py`](tools/https_worker.py) implements one exchange in a spawned,
disposable host process. The caller supplies an explicit origin/method policy,
optional host-configured CA file, upload size (or unknown length), response limit
and deadline. GET/HEAD have no body; the profile also supports POST, PUT, PATCH
and DELETE when explicitly granted. URLs cannot contain credentials or fragments.
Headers are bounded and cannot override Host, framing or hop-by-hop controls.
There is no ambient cookie jar, proxy configuration or automatic redirect/retry.

The parent polls events while it continues other work. Upload credits and
response acknowledgements permit one 440-byte body chunk at a time in each
direction. Known uploads use Content-Length; unknown uploads use chunked
encoding. Responses stream with size/framing checks, and redirects are returned
to the caller for a separately authorized request. Response bytes are not
automatically decompressed. Limits default to 8 MiB per direction, with a host
configuration ceiling of 32 MiB; each request has a deadline of at most 120
seconds. Request headers are limited to 16/4096 bytes and accepted response
headers to 32/8192 bytes. Python's bounded HTTP parser processes headers before
that stricter application check; this is a host process, not calculator memory.

The bridge polls and explicitly cancels the worker on exit or transport loss.
Cancellation/deadline expiry terminates the worker, including blocked DNS,
connect, TLS and socket operations. TLS uses the native system certificate store
through pinned `truststore`, with certificate and hostname checking and TLS 1.2
or newer. An explicit `--ca-file` replaces system trust for that context without
changing the host's trust store. Missing native trust fails clearly. The
[explicit doctor probe](HOSTS.md) checks TLS through the same spawned worker.
Errors contain categories and byte counts rather than secret-bearing URLs or
headers. A failed/cancelled mutation can report an unknown outcome after its
request may have been sent; the worker never retries it.

Sources: Python's [HTTPS connection and streaming behavior](https://docs.python.org/3/library/http.client.html),
[verified TLS contexts](https://docs.python.org/3/library/ssl.html#ssl.create_default_context),
[native trust contexts](https://truststore.readthedocs.io/en/stable/),
and [HTTP semantics](https://httpwg.org/specs/rfc9110.html).
