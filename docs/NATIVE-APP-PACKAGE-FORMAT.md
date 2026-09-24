# LFAPP1 signed envelope

LFAPP1 is a fixed, versioned authentication envelope around a bounded LFAPP0
manifest/ELF container. Physical installation requires ABI 1. ABI 0 remains an
emulator compatibility format and cannot be installed on physical hardware.

All integers are unsigned little-endian. No optional fields, padding variants,
trailing bytes or nested envelopes are accepted.

| Offset | Length | Meaning |
| --- | --- | --- |
| 0 | 8 | `LFAPP1` followed by two zero bytes |
| 8 | 4 | Envelope schema: 1 |
| 12 | 4 | Exact payload length |
| 16 | 4 | Inner app ABI: 1; 0 only for emulator compatibility |
| 20 | 4 | Flags, must be zero |
| 24 | 32 | SHA-256 of the RSA public key's DER SubjectPublicKeyInfo |
| 56 | 32 | SHA-256 of the entire LFAPP0 payload |
| 88 | 8 | Reserved, must be zero |
| 96 | 256 | RSASSA-PKCS1-v1_5 / SHA-256 signature over bytes 0–95 |
| 352 | variable | LFAPP0 payload |

Maximum signed size: 2,101,664 bytes. RSA keys must have a 2048-bit modulus and
public exponent 65537. The fixed signature header includes a format-specific
magic, key identity, ABI and payload digest. It cannot authenticate firmware
update manifests or a package with different content.

## Trust boundary

1. The isolated validator receives source, compiles twice and runs the guest.
2. The host consumer validates the result's source identity, ELF and evidence.
3. Only then does the host sign using an independent app private key. That key
   and the store credential never enter the container.
4. The website verifies the envelope against its configured public keys before
   atomically publishing the release and recording its signing identity.
5. The SDK verifies against its bundled or explicitly supplied public key.
6. Physical and VM guests also verify the envelope against its compiled key ring before
   passing the payload to its restricted loader.

Unsigned local development packages remain supported by the emulator. The
physical target rejects unsigned packages and ABI 0. The signature provides
publisher authenticity and integrity, not a correctness guarantee or a sandbox
qualification.

## Rotation and retirement

Deploy at most four active public keys. Add a replacement public key to the
website, physical firmware and distributed emulator before changing the host signer. Preserve the
old key while apps signed with it remain supported. Retiring a key removes it
from the accepted key ring; the website returns HTTP 410 for its package
downloads, and rebuilt firmware and emulators reject it. Already downloaded packages on old,
offline devices cannot be remotely revoked. Publish replacement app versions
and distribute an updated emulator for a compromised key.

Do not reuse the firmware updater's key. The app public key is
`ports/lefony-prime-g2/app-signing.pub`; the corresponding private key must stay
outside public source. Build-time `LEFONY_APP_PUBLIC_KEYS` points to a JSON file
containing one to four PEM paths relative to that JSON file. An unset variable
uses the checked-in deny-all guest header. No build creates an app identity.

## Commands

```sh
# Only when creating a NEW store identity; refuses to overwrite existing files.
python3 sdk/tools/signing.py keygen app-private.pem app-public.pem

# Manual signing/verification for qualification; public apps use the consumer.
python3 sdk/tools/signing.py sign unsigned.lfapp --private-key app-private.pem --output signed.lfapp
python3 sdk/tools/signing.py verify signed.lfapp --public-key app-public.pem
lefony-sdk launch signed.lfapp --public-key app-public.pem
```

The host/OpenSSL, guest/C++ and website/Web Crypto implementations have separate
verification tests. Test keys are generated in temporary directories, not
published or made default production roots.

## ABI 1 payload and service contract

The LFAPP0 inner header remains schema 0. Its word at byte 20 is the ABI
number: 0 in old previews, 1 for the frozen v1 contract. The manifest's `abi`,
inner header and signed envelope must agree. Bytes 56–63 remain zero.
The metadata is canonical ASCII JSON with exactly `abi,id,license,name,version`.

ARM EABI5 hard-float, Cortex-A7 ARM mode, C++17, GCC 16.2.0 and binutils 2.47
are the supported toolchain. Entry arguments are three uint32 values. Service
number is r0, pointer to fixed-width arguments is r1, and the result is r0.
`svc #0` crosses the boundary; no C++ object or allocator crosses it.

| Service | Arguments | Result |
| --- | --- | --- |
| 0 | None; runtime return trampoline | Callback completed |
| 1 | x,y,width,height signed int32; RGB565 uint32 | 0 or negative error |
| 2 | x,y signed int32; foreground/background uint32; pointer/length uint32 | 0 or negative error |
| 3 | None | Low 32 bits of monotonic milliseconds |
| 4 | offset, writable pointer, length (three uint32) | Private data bytes read or -1 |
| 5 | offset, readable pointer, length (three uint32) | Private data bytes staged or -1 |

Data is capped at 65,536 bytes, and one data call at 4096 bytes. User buffers
must be mapped, and read destinations cannot point to executable code. Event
values are Start=0, Key=1, Tick=2, Touch=3, Close=4. Unknown services return -3;
invalid pointers/arguments return -4. Future incompatible layouts need another
ABI number, never silent reinterpretation of this contract.

## Signed calculator icon attachment

The store's immutable PNG icon is converted to a 55 × 56 RGB565 image and
returned by `GET /api/store/releases/<release-id>/calculator-icon`. The artwork
keeps its square aspect ratio, is area-averaged to 55 × 55, and transparency
is composited onto white; the final row is white. The source PNG and executable
package are unchanged. Existing releases can acquire icons without republishing.

An attachment is exactly **6,576 bytes**: the existing 352-byte LFAPP1
signature envelope (ABI 1), followed by this distinct payload:

| Payload offset | Bytes | Meaning |
| --- | --- | --- |
| 0 | 8 | `LFICON1\0` magic; never an executable LFAPP0 payload |
| 8 | 32 | SHA-256 of the complete signed executable package |
| 40 | 4 | Width 55, little-endian uint32 |
| 44 | 4 | Height 56, little-endian uint32 |
| 48 | 16 | Reserved, all zero |
| 64 | 6,160 | Row-major RGB565 pixels, little-endian uint16 |

The normal app roots authenticate the envelope. Both browser and firmware check
exact lengths, dimensions, reserved bytes and binding to the package. Executable
loaders still require LFAPP0; an icon cannot pass as an application. The firmware
creates a fixed literal-only LZ4 stream for its existing menu renderer, rather
than parsing compressed images supplied by an app. Invalid or absent icons use
the existing puzzle fallback.

Firmware advertising app status capability bit 3 accepts icon commits through
`0x6c` after the existing `0x63`/`0x64` bounded upload. `0x6d` reads the verified
attachment digest for a current catalog index. See [storage protocol](NATIVE-APP-STORAGE.md).
Standalone SDK executable installs remain valid and use the fallback until an
icon is installed from the store.

## Explicit schema 1 extension (local candidate)

The original five-field schema 0 remains supported and is still the default.
Schema 1 uses the same 64-byte LFAPP0 header with word 8 set to 1 and an ABI 1
manifest containing exactly five additional fields. See the versioned
[package/source/USB contract](NATIVE-APP-CONTRACT-EXTENSIONS.md). This does not
change the LFAPP1 signature envelope, keys, ELF limits, storage geometry or
version-ordering policy. Older readers reject the new schema; the coordinated
reader deployment must precede publication of SDK writers that require it.
