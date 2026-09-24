# Link Gallery connected-app candidate

Link Gallery downloads a small RGB565 image through the SDK USB/HTTPS companion,
validates it, and retains the last complete image for offline viewing. It uses
ordinary C++ `main`, public channel/file/UI/system APIs and the normal ARM build.
There is no app-specific firmware path or hosted Lefony service.
Version 0.2 requires local API 12 writer cancellation in addition to API 11
channels. It is not compatible with the earlier published firmware.

Create an external project:

```sh
lefony-sdk new my-gallery --template link-gallery
```

Set `project.json`'s `arguments` to one HTTPS URL, at most 128 printable ASCII
characters, pointing to an image in the format below. The empty default runs
offline and asks for that configuration. Build/package/test through the ordinary
SDK commands. The SDK's `CHANNEL.md` describes the explicit companion grant and
pairing command; private physical installation still needs an authorized app
signing key. This example does not enroll keys or modify firmware.

Download starts a connection. Compare the host and calculator pairing code and
press physical OK. Refresh reuses that authorized session for another explicit
GET. Back/Cancel stops a request while its Cancel control is enabled; Disconnect
ends the session. Preparing and Saving disable controls during storage calls.
After a USB disconnect, restart the companion and choose Refresh to establish
new consent. The app never automatically retries a request. Home/power remain
OS-owned. The last image remains visible while another image downloads.

The current companion also preserves the session when cancellation races with
a completed response, or when queued URL metadata arrives after an early grant
refusal. Late fragments are drained without another network operation. A refused
grant still requires an explicitly corrected companion grant; Refresh never
widens it. `vm/test-sdk-https-terminal.py` exercises these boundaries, including
refresh on the same paired session after a cancelled response and cold cache
readback. Older downloadable companions may predate this fix.

Only a complete successful HTTP 200 response can replace `image.cache`. The app
streams bytes into a staged replacement of `image.cache` using `FileWriter`.
It checks image dimensions, exact length, reserved fields and checksum in a
separate bounded allocation before committing. Cancellation, malformed content,
failed writes and disconnect abort the replacement; the previous cache remains
available. A commit error is uncertain and asks the user to reopen and inspect
the cache. Legacy `download.part` scratch is removed on the next start.
The previous file's length is credited against the quota, avoiding a second
named temporary file's logical usage. Shared physical headroom is still required.
Two 73,728-byte pixel allocations can coexist before the displayed image changes.
This is not a measured total memory peak or physical durability qualification.

## Image wire/file format

The same 73,760 bytes are returned by HTTPS and stored as the cache. Serve them
with `Content-Type: application/octet-stream`; fixed length and HTTP chunked
responses are supported. TLS and the explicitly granted origin provide transport
authentication. The image checksum detects malformed/corrupt cache contents;
it is not a cryptographic signature.

| Offset | Contents |
| --- | --- |
| 0 | Eight ASCII bytes `LFGAL1\r\n` |
| 8 | Little-endian uint32 width, exactly 288 |
| 12 | Little-endian uint32 height, exactly 128 |
| 16 | Little-endian uint32 payload length, exactly 73,728 |
| 20 | Little-endian uint32 FNV-1a checksum of the pixel bytes |
| 24 | Two zero uint32 reserved words |
| 32 | Row-major little-endian RGB565 pixels, no row padding |

FNV-1a starts at 2166136261; for every payload byte, XOR the byte into the state,
then multiply by 16777619 modulo 2^32. The image dimensions are this example's
bounded format, not a limitation of the generic HTTPS or graphics APIs.

The maintainer's `vm/test-sdk-link-gallery.py` supplies generated public test
images and a temporary localhost TLS service. Its journeys cover real USB and
normal Goodix/keypad input, explicit reconnect, cancellation, content rejection
and cold cache reopening. See the implementation ledger for the exact completed
runs; the current app remains a development candidate.
The optional `--full-quota` cases seed the production filesystem to the real
32 MiB app limit, then check replacement, malformed-input preservation,
cancellation and cold cache reopening.
