# Doom app-store releases — September 24, 2026

## Startup update: Doom 0.2.3

[Doom 0.2.3](https://lefony.com/#apps/doom-proof) is published under the existing
maintainer account. It is byte-identical to the signed package tested on the
physical calculator. Install Lefony OS `1.0.0+1790281237` or newer for the verified
content cache and immediate cached-file completion. Two observed physical
launches reached the first game frame in 15.114–15.229 seconds; package loading
and signature verification precede this measurement. Freedoom remains bundled,
and existing data and saves are preserved. See the
[startup qualification record](DOOM-STARTUP-PERFORMANCE.md).

- Release ID: `99499805-c424-42f9-8cb6-0f3ca1ff958e`; listing revision 16.
- Signed package SHA-256: `9a72ea4a3e76d44b3dab8714448d1a3d034c1176fe6ff40d25e8f7df9c65a927`.
- Source SHA-256: `b30233b165e383d704d0ec47b9c544b72647a1ad7ead3dfb6b9b5f09fc8e2094`.
- Complete bundle: 10,638,557 bytes, SHA-256
  `5feedb3a4a61d83a65e33cb68368b0452076bf2f25f3cab5325b3a0d41ccbb93`.
- Publication attempt: `4cda71e8-c8b7-428e-872b-f4e7088fa9ff`.

The immutable source snapshot rebuilds byte-identically. The publication replay
installs all bundled files through synthetic USB, then passes movement and menu
assertions. Public readback verifies both production signatures, the exact
installed executable, all 208 source members and every pinned game-data file.
The earlier full gameplay/save/cold-reload checks cover the same executable.

An initial publication attempt stopped on a local emulator USB connection
failure during data installation, before upload. The source runner now reuses
the existing bounded app/file bulk protocol on its already enumerated model
connection; 156 related tests and the fresh-install replay pass. This is a
host runner correction, not another firmware or game-executable change. The
full OS release host suite passed 1,959 tests with two private-fixture skips.
Evidence is retained under ignored `build/doom-startup-release-20260924/`.

## Bundled-data update: Doom 0.2.2 (superseded)

The update packages Freedoom Phase 1 0.13.0 and its license/credits with the
Doom download. Browser installation transfers them automatically through the
existing API 12 file-exchange protocol. Existing matching files are verified;
conflicting files are preserved, and saves/settings are never overwritten.
The listing description is shortened and removes manual game-data setup.

The website support is deployed as Worker version
`cdc42a2e-6912-43bc-9347-75a2054a8536`, retaining the concurrent automatic
firmware restart improvements. Older releases still return their exact original
`.lfapp` from the new download route, verified against the 0.2.1 public hash.

The complete download is a `.lfbundle` containing the signed executable,
signed data descriptor and compressed parts. Both browser and source terminal
SDK validate signatures, lengths and hashes before installation. The updated
source CLI can install this bundle; the older public frozen SDK cannot. No
firmware format, trust root, storage layout or database migration is required.
The SDK still identifies itself as `0.2.0-dev`; this is SDK 1.0 candidate work,
not a newly qualified SDK 1.0 distribution.

### Published 0.2.2 artifacts

Published under **maikopruett** (`github:66353633`) through the source terminal
SDK's `publish --dry-run` and `publish --resume` commands:

- Release ID: `c77ce11c-f0bf-47a1-8568-ad32913a68c6` (listing revision 11).
- Signed package SHA-256:
  `44e5a8172997e50b10a920801650e7867e95da1f666f0db7840d7799858a57b7`.
- Source SHA-256:
  `d3ae31446830db08f004a577ec0c94d4d51449732661e286539992c29522768e`.
- Complete bundle: 10,638,557 bytes, SHA-256
  `1e0f96c45045a44c79e06819fc70f7a4c2a9c40546a28ca48b4ebf020230bd92`.
- Publication attempt: `0bb0d32a-cfc7-408f-8509-c3084fef3077`.
- Tested SDK source identity:
  `3f49cbfc354483d8bd70dadd9bfb3457795ebaccb6576075010cea8b8a2c4ab5`.

The clean publication replay passes both movement and menu assertions after
installing every data file through synthetic USB. Public download readback
verifies the package and metadata with the existing production key, matches
the tested executable and 226-file source bundle exactly, and checks every
included data file against the pinned inputs. A live Chrome page check confirms
version 0.2.2, the shortened included-data description and the complete-bundle
download link; its screenshot is retained. The first accepted publication
exposed a local listing-baseline bug that treated data parts as images. That
host-only receipt-tracking bug is fixed; 143 related tests pass and resuming
the same immutable attempt confirms the existing accepted release without
republishing or changing its tested bytes.

### Validation and retained evidence

The exact unsigned 0.2.2 package SHA-256 is
`4eb15a837757ca2978ad510aefd81d8377aa0f0db1f78f3f9b621defc1e214aa`.
A fresh extraction of its publication source, rebuilt with the frozen macOS
SDK after an explicit lock update, produced the identical package. The normal
input gameplay harness passes movement, firing, menus, named save/reload,
normal Quit and cold saved-state restoration after installing the update over
an existing 0.2.1 synthetic workspace. The same complete harness also passes
on the fresh workspace populated through bundled-data USB installation,
including cold save restoration.

Browser file exchange also passed against the ARM emulator via synthetic USB:
create, exact readback, idempotence, conflict preservation, pre-commit
cancellation/retry and reconciliation after a lost commit acknowledgement.
Backend tests validate the complete real WAD publication/download, signature
binding and withdrawal. All 67 browser end-to-end tests pass, and the focused
SDK host suite passes 174 tests; the startup-budget/publication rerun passes
128 tests, including the new finite 180-second replay limit. All 572 website
unit tests pass (one skipped) with two workers and a 15-second per-test timeout.
Website build, lint, worker dry-run and public repository checks pass. Initial
timing failures and their successful reruns are retained in the local evidence.

Local artifacts and emulator evidence are under
`build/doom-bundled-release-20260924/`; website evidence is under its ignored
`.local/` directory. No physical calculator writes, Git commit or push occurred.
Physical performance, storage and power-loss qualification remain open.

The initial ten-second gameplay replay captured the black startup frame before
the firmware finished checking the large file root. That failed evidence is
retained. Read-only engine observations subsequently confirmed first-level play
on the fresh USB-installed workspace. The revised bounded replay allows two
minutes for startup before asserting movement and menus. This measured emulator
behavior does not establish physical startup time.

### Data provenance

`freedoom1.wad` is 28,795,076 bytes, SHA-256
`7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d`,
from the [official Freedoom 0.13.0 release](https://github.com/freedoom/freedoom/releases/tag/v0.13.0).
The recipe includes its exact BSD license and credits in both source notices
and the installed companion files. Doom requires API 12 and space for about
29 MB of game data plus saves. Sound and multiplayer remain omitted. See the
[port guide](../sdk/ports/doom/README.md) for controls and storage behavior.

## Historical 0.2.1 release (superseded by the bundled-data update)

[Doom 0.2.1](https://lefony.com/#apps/doom-proof) is published under
**maikopruett** (`github:66353633`) using the installed macOS terminal SDK's
`publish --dry-run` and `publish --resume` commands. The public SDK used here
still identifies itself as **0.2.0-dev**; this is not an SDK 1.0 qualification.

### Published artifacts

- App ID: `doom-proof`.
- Release ID: `6e5f9ecc-0fc9-4acc-b643-233674e22c4a`.
- Unsigned package SHA-256:
  `500f24f855b046bdb226aaf06a5bf956ce7516762599fe20db503dd76d7b4463`.
- Public signed package SHA-256:
  `7fb04eda54b4f8dc5f52b4fd6774f05dea94768c908fb1af53b0c054e3e34309`.
- Public source SHA-256:
  `cf495220080304e0c218dfc3aa42291d02d66f197a99c2cfd6a1faa6b514089a`.

The port was prepared from the pinned Doomgeneric recipe with display name
`Doom`, retaining its app ID and 0.2.1 engine/adapter behavior. The source
download contains 226 files, including engine and adapter code, project
configuration, SDK lock, replay, original notices, the twelve scoped MIT
runtime/interface/linker sources, generated arguments, library inventory and
matching SDK corresponding-source download references. Two actual synthetic
emulator screenshots and an original pixel monogram accompany the listing.

### Validation

The frozen CLI built the package and passed the explicit missing-game-data
replay. Publication prepared and tested its own immutable copy; its package
matched the separately tested executable exactly.

The existing normal-input gameplay harness tested this exact frozen-CLI package
against VM firmware `1.0.0+1790259014`. Only its build callback was replaced with
the already built package path; gameplay assertions and controls were unchanged.
Gameplay, movement, firing, menus, named save/reload, normal Quit, cold saved-state
restoration, restored fire bindings and clean exit passed. GDB read game state;
it did not call game functions or alter variables. The WAD was seeded into
isolated synthetic media while the guest was stopped.

A fresh extraction of the exact source submission rebuilt a byte-identical
package with the frozen CLI. The terminal SDK accepted the publication, and
`apps show doom-proof` confirmed the account owner and published release. The
public page displays the correct author, version, instructions and screenshots.
Full public package/source/screenshot downloads matched; the package signature
verified with the existing production app key, and its inner payload was
identical to the tested package. Python urllib initially received HTTP 403;
the public readback succeeded with curl without changing server policy.

Local project, synthetic media, publication receipt, rebuild and test evidence
remain under `build/doom-store-release-20260924/`. No physical calculator write,
Git commit or branch push was performed.

### Historical manual setup (0.2.1 only)

Game data is **not embedded in the app**. The listing explicitly directs users
to the official Freedoom 0.13.0 release and its `freedoom1.wad` (28,795,076 bytes,
SHA-256 `7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d`).
After installing and closing Doom, import it with:

```sh
lefony-sdk files import doom-proof freedoom1.wad ./freedoom1.wad
```

The app requires API 12 and capability mask 8252. Sound and multiplayer are
omitted. The publication replay covers the expected missing-data exit; gameplay
coverage comes from the separate WAD-equipped test described above. Physical
performance, input and storage qualification remain open. See the
[port guide](../sdk/ports/doom/README.md) for controls and storage behavior.
