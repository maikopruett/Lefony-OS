# SDK capability and compatibility matrix

This inventory describes checked-in source, not qualification of downloads.
SDK `0.2.0-dev` is an experimental implementation candidate. The maturity
roadmap remains open; this matrix does not label the SDK beta or 1.0.

| Built-in capability | Public SDK equivalent | Limits / remaining gap |
| --- | --- | --- |
| Native app launch | `lefony_event`, or opt-in ordinary C/C++ `main` with the newlib profile; main-menu installed tile | One foreground app; Home/power stay OS-owned; broader libc/C++ qualification remains |
| Drawing | `fill`, ASCII `text`, rectangle batches; app-side clipped lines/circles/RGB565 images | 320 × 240; original text API 128 ASCII bytes; API 9 adds measured/clipped OS fonts; arbitrary font/assets/polygon pipeline remains |
| UI controls | Rows/columns, focus, Back stack, bounded UTF-8 field with touch caret/selection, wrapping paragraphs, button/toggle/progress/choices, cancellable slider, captured pixel lists, menus, confirmation dialogs, Forms/Tables, Notebook and UI Gallery | Notebook 0.6.2 and UI Gallery 0.1.2 use paragraphs for complete recovery instructions and long/blank-line text. Normal-touch editing/cancellation, long/accented fields, clipping, four fonts, disabled/pressed/focused states, themes and empty/loading menus have local ARM evidence. Current paragraph and bundle qualification belongs in the ledger. Broader glyph/localization/accessibility coverage and physical feel remain |
| Keyboard | Base input plus optional operators/modifiers/UTF-8; API 4 ordered physical held/down/up stream | Full glyphs and two-dimensional mathematical editing remain; physical input qualification is separate |
| Touch | Two stable IDs/coordinates; viewport tap/hold/pan/pinch and control capture cancellation | Physical feel and full modal/lifecycle qualification remain |
| Timing | `millis`, 300 ms nominal Tick, `Task::step` | Unsigned rollover; callbacks must yield; no precision timer guarantee |
| Memory | `Arena`, `Vector`; opt-in foreground heap and newlib `malloc/calloc/realloc/free` | Fixed capacities and explicit failures; no exceptions, RTTI or general STL |
| Mathematics | Binary64 math, bounded matrices, scalar contexts with degree/radian/gradian modes, explicit significant-digit formatting, statistics/bisection | Complex/units/scoped functions/symbolic operations, distributions/datasets and broader numerical methods are outside the current selected subset |
| Graphing | Adaptive resumable point-curve sampler, pan/zoom/trace; Graph Explorer | No continuity guarantee; full axes/labels, scatter/histograms, dataset integration and software 3D remain |
| Documents | ABI 1 `readData` / `writeData`; API 8 checkpoint/migration controller; explicit host private-data backup/restore and retained-pair rollback | 64 KiB byte store, 4096-byte app transfers; explicit snapshots retain later dirty edits and upgrades retain the recovery pair until acceptance; broader damaged-media recovery remains |
| Named files | Authenticated API 2 requests, newlib stdio, API 5 live `fsync`, API 6 directory/usage queries, API 7 quota query/enforcement and local API 12 explicit writer abort | Four snapshot readers, one writer, 2048-byte transfers, 16 entries per generation-checked directory page; 32 MiB mutable-data quota and explicit SDK per-file USB import/export; The current macOS storage bundle passes frozen listing, usage, import/export and interruption journeys. Broader damaged-media recovery and physical durability remain |
| Whole-app archives | Local signed export/restore, current and pending recovery pairs, exclusive USB session, CLI, atomic host output, explicit fresh recovery-pair consent and exact-identity unreadable-code repair; FILE5 replicated roots and negotiated health inspection; [archive guide](../sdk/ARCHIVES.md) | One surviving root copy can preserve ownership/history through explicit archive repair; both copies lost, unreadable metadata, broader resources and host/physical qualification remain; exact evidence is in the ledger |
| Source/ARM preview | Actual ARM frames and layout inspection, input-readiness synchronization, incremental source watching, retained committed files/private bytes, nested fixtures and explicit reset/disposable modes | Local candidate; failed runs preserve the previous checkpoint. A populated local profile improved from 109.5 to 19.1 seconds with identical frames; the current local macOS bundle passes editing/save/cold-preview journeys, while clean-host release qualification and latency budgets remain open. See [UI guide](../sdk/UI.md) |
| Persistent development | `--workspace NAME`, clone/export/restore/reset | Synthetic NAND, normal signed USB app install and normal loader; no hardware access |
| Debugging | `debug`, `symbolize`, matching symbols | Local GDB session; fault address unavailable; no physical debug interface |
| Private installation | Local `keys generate`/`sign`, OS-approved developer-key enrollment/revocation, unused revoked-key removal, retained-key catalog/export, signed SDK install, per-app lost-key replacement, readable-corrupt repair and partial-backup repair of unreadable registry payload | Local macOS bundle passes 36 actual CLI steps across six ARM sessions, including canceled/approved consent, signed Notebook installation, signer replacement, readable-corrupt repair, partial backups/fresh-scan repair under unreadable payload faults and cold data preservation. Unreadable ownership/metadata, broader resources, remaining/clean native hosts and physical qualification remain; see [private keys](../sdk/KEYS.md) and the ledger |
| Testing | Startup plus bounded JSON keypad/Goodix replays; bounded emulator stderr/UART diagnostics with input identities and process outcomes | Startup/replay attempts replace earlier success; incomplete reports distinguish running, cancelled and not-run cases. The current macOS replay candidate passes 12 CLI commands covering interruption, cold data and cancelled publication preparation. Preview retains its frame/data through failures. No claim of independent or physical validation; exact artifacts are in the ledger |
| Store | Browser package/source submission and updates/withdrawal; local SDK GitHub login/logout, scoped sessions, owned-app pagination/history, project links, offline `publish --dry-run`, folder publication/update and saved-attempt status/resume/cancellation; listing snapshots, browser conflict review, SDK pull/merge, metadata-only edits and SDK withdrawal candidate; parent-enforced HTTPS deadlines and cancellation | Frozen macOS account/deadline and 37-step publication journeys against actual local Worker handlers pass, including exact signed ARM download/launch. Real GitHub authorization with the source SDK/native macOS Keychain, production migration/initial inventory, SDK Counter publication, exact download/source rebuild and signed ARM launch also pass. Native clean hosts, complete release integration and broader live lifecycle/capacity coverage remain; consult the ledger for exact evidence |
| System services | API 10 candidate: clock/battery validity, OS palette/locale/math preferences, temporary brightness and user-initiated clipboard; Notebook consumes palette/preferences/clipboard | Local ARM boundary/lifecycle and document integration evidence; physical accuracy remains; no timezone/trust persistence or unrestricted clipboard access |
| Connectivity | API 11 app USB channel, OS consent, bounded HTTPS bridge, `companion` command and Link Gallery cache/reconnect example | The current source fixes late-fragment session loss after DONE/ERROR, with ARM cache/refresh and host protocol evidence. A retained local macOS bundle passes eleven companion/model-USB cases, including late delivery and same-session requests; the later paragraph bundle has separate offline UI qualification. Published downloads, remaining supported hosts, broader resources and physical USB acceptance remain |

Source: [headers](../sdk/include/lefony/app.h),
[extensions](../sdk/include/lefony/extensions.h), [runtime helpers](../sdk/include/lefony/runtime.h),
[numeric subset](../sdk/include/lefony/numeric.h), [expression subset](../sdk/include/lefony/expression.h), [CLI](../sdk/tools/cli.py),
[loader/services](../ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp).

The [C library matrix](../sdk/C-LIBRARY.md) now has local ARM conformance evidence
for allocation/exhaustion, strings, 64-bit/C99 formatting/scanning, selected math,
stream/descriptor errors, cold committed data and exit. A checked newlib source
adjustment preserves full 31-bit file handles without reusing stale ones;
synthetic counter-boundary cases pass beyond 32,767 and near `INT_MAX`. This
requires matching rebuilt newlib and app objects. It does not qualify every
exported library function or physical endurance.
Four further buffered-stream cases pass in debug and release, including cold
public readback, on the current VM and retained media-I/O candidate. They cover
262,175-byte random updates across storage chunks, append after seek and repeated
sync, reader snapshots across replacement/rename, and zero-filled seek gaps with
pushback/position restoration. Exact candidates and all 32 ARM phases are recorded
in the ledger; the SDK executable inputs are unchanged.
The [completed library comparison](NATIVE-APP-C-LIBRARY-COMPARISON.md) keeps
newlib after 23 expanded ARM phases pass. Both Picolibc buffering variants are
smaller but fail four selected stream/cleanup cases. Full runtime qualification
remains separate from this selection.

The later store backend adds managed account/global storage admission, unique
artifact stages, transactional release/listing retention and bounded cleanup of
abandoned and late-written objects. The CLI/ARM publication journey preserves
accepted history through the actual scheduled handler in local tests. The
deployed website now implements incremental legacy-object
inventory/owner charges and independently gated source/package cleanup, with
local retention, pagination and failed-delete coverage. Production migrations and
initial namespace/owner inventory now pass; submissions are enabled with the default
capacity policies. Both legacy deletion gates remain NULL. Broader capacity/load
and destructive cleanup cutover remain separate acceptance work. They do not change app file quotas,
firmware storage geometry or the SDK executable identity.

The [FILE5 recovery candidate](NATIVE-APP-ROOT-RECOVERY.md) retains canonical
ownership, both package/data pairs and version history in separate data and
metadata copies. Both targets compile. Six ARM SDK cases cover inspection,
exact export, downgrade rejection, cancelled repair, explicit restore and cold
Notebook reopening with a modeled unreadable payload. New saves/restores migrate
healthy older roots; older firmware rejects FILE5. The payload adds one 128 KiB
block per protected root plus metadata. It cannot recover already-lost legacy
roots or an unmountable volume, and has not qualified physical storage.

## Frozen limits and independent versions

The current public macOS ARM64 and Linux x86-64 SDK candidates include the
browser emulator, all 50 clickable Prime keys and larger selectable touchscreen.
Frozen commands, normal KPP/Goodix input, saved/cold Notebook, complete archive
and matching source checks, R2 readback, public binary/source-kit hashes and
corresponding-source route checks pass. See the
[current release record](SDK-EMULATOR-RELEASE.md) for exact artifacts and evidence.
Current developer trials are scoped to maintainer macOS feedback; clean hosts,
Developer ID/notarization, native Linux/Windows, independent feedback and
physical qualification remain open. Windows source inputs are refreshed locally;
a complete Windows executable remains unavailable.

The machine-readable [SDK contract](../sdk/contract.json) records current limits;
host tests check it against the parser, linker and authoritative Prime key map.
The application code window is `0x10000000`–`0x10100000` (1 MiB), writable data
is `0x10201000`–`0x102ef000`, and the separate 64 KiB stack is
`0x102f0000`–`0x10300000`. Guards remain unmapped. The private OS composition
surface costs 153600 bytes. Arenas consume app static data; they do not enlarge
the loader reservation. Reports separate static data from the reserved stack;
exact stack peaks remain **unmeasured**, not zero. The opt-in
[`test --measure-resources`](../sdk/TESTING.md#observing-app-resources) VM candidate
reports package-bound stack-write and sampled-SP extents across relaunches,
plus reservations and execution counters. Those observations do not establish
worst-case stack headroom. An explicit `LEFONY_PROFILE_HEAP=1` newlib project
build also reports allocated-chunk and arena observations with matching VM
firmware; see [heap diagnostics](../sdk/TESTING.md#observing-newlib-allocations).
These include allocator padding/metadata, exclude static buffers and custom
suballocator usage, and add scanning overhead. Unobserved or incomplete records
remain distinct from measured zero; neither stack nor heap observations prove
a worst-case bound or physical performance.

ABI 1 service/event numbers and original structs stay frozen. Package schemas 0 and 1
(`LFAPP0`) is wrapped by signed envelope 1 (`LFAPP1`). Shared storage profile 2
and USB protocol 2 retain profile/protocol 1 compatibility. The app region is
still 64 MiB. API 7 adds a [32 MiB mutable-data quota](../sdk/FILES.md#per-app-quota-policy)
with preservation of existing oversized roots; geometry, firmware identity and
anti-downgrade policies are unchanged. Device-reported allocated/free flash differs from
the package download size.

The qualified API 8 candidate adds [private-data checkpoints and explicit app
migrations](../sdk/DATA.md), using capability 512 and service 14. API 9 typography uses capability 1024 and service 15, bringing the current
feature mask to 2047. The API 10 [system-service candidate](../sdk/SYSTEM.md)
adds capability 2048/service 16, taking the current feature mask to 4095.
The API 11 [channel candidate](../sdk/CHANNEL.md) adds capability 4096/service 17;
that checkpoint advertises API 11 and feature mask 8191. The USB/HTTPS bridge
and companion command are implemented and have local ARM/TLS evidence;
their downloadable host bundles and physical operation remain unqualified.
The current source advertises API 12 and feature mask 16383, adding capability
8192 and file operation 15 for [explicit writer discard](../sdk/FILES.md#explicit-writer-cancellation).
Basic signed ARM cancellation, cold reopening, denial and older-firmware fallback
pass, along with Notebook 0.6/Link Gallery 0.2 full-quota replacement, rejected
growth/content, cancellation and cold reopening. Resource/physical qualification
remains separate from these local journeys.
Minigzip 0.2 also uses API 12 for checked direct output commits and error-path
discard. Its 15 public-file workloads / 40 ARM phases cover quota replacement,
failed growth and repaired-input retries, empty files, heap exhaustion, Home and
cold reopening. A separate 23-phase ARM media matrix covers modeled corrected
and uncorrectable reads, shared-volume exhaustion, preserved input/output and
retry. Broader damaged-media recovery and physical qualification remain separate.
Doom 0.2.1 has additional signed ARM evidence for abrupt stops during save staging,
reference verification and either side of the commit rename. Cold boots inspect
the existing installation without reinstalling; old/new save selection, exact
restored player state, retry, unchanged settings and full WAD export pass.
The final observer requires an open, partly read reference file for its
verification cut. The later interrupted-update matrix passes 17 ARM phases:
partial upload/package writes, cuts around the root rename, public rollback,
retired-version rejection, higher-version retry, acceptance and cold recovery.
Three additional quick-slot sessions cover selection, overwrite, cancellation,
quick load and cold named-slot recovery while preserving existing saves/settings.
All five final WAD exports match the pin. Update fixtures change manifest versions
only, with identical executable bytes. Changed-engine/data-format upgrades,
broader workloads, torn physical programming and physical power-loss behavior
remain separate qualification; see the ledger.
See the [UI guide](../sdk/UI.md) for its local preview candidate. Existing package/ABI/storage formats retain their meanings;
the [implementation ledger](NATIVE-APP-SDK-1.0-PROGRESS.md) records qualification.

The additive [host data-recovery extension](../sdk/DATA-RECOVERY.md) uses app hello
flag 128. It adds no app API revision, package schema or storage layout. Current
source is a local candidate; consult the ledger for exact host/ARM evidence.

The host archive extension uses hello flag 1024 and commands `0x90`–`0x95`.
That flag belongs to USB discovery, separately from app capability bits. It
introduced no app API change and preserves ABI 1 and the existing package/storage geometry.

Discovery service 6, batch service 7, input snapshot service 8 and Back-depth
service 9 are experimental additive extensions.
Older firmware returns `-3`; schema-0 applications must fall back to original services.
The explicit schema-1 package extension can declare required features; schema 0
retains its exact five-field manifest. New readers are local candidates pending
coordinated deployment; old readers reject schema 1. Discovery requires
size 48, version 1 and zero reserved bits, and reports the supported limits.
Batch requires size 20, version 1, zero reserved bits, 1–64 rectangles, and no
more than 76800 total pixels. The runtime validates and copies all descriptors
before drawing; malformed batches draw nothing. Presentation stays OS-owned.
Input snapshots use one 128-byte size/version-tagged copied response; base ABI 1
callbacks are unchanged. The wire header is copied from SDK source by the build
script so SDK and firmware use the same definition.
Navigation accepts depth 0–8; only nonzero depth lets the app handle Back.
Home/Apps/power remain OS-owned. Old firmware needs software Back controls.

Proposed stable compatibility policy: retain stable interfaces throughout an
SDK major line, give at least two stable releases of migration guidance before
removal, and change the major ABI for incompatible removal. SDK 1.0 has not
frozen an expanded stable API. Security exceptions require an incident/recovery
record. Released ABI 1 corpus qualification remains a separate release gate.

## Host matrix

| Host | Current source/tool path | Qualification |
| --- | --- | --- |
| macOS ARM64 | Pinned GCC/newlib/GDB, Python, custom QEMU and libusb desktop candidate; selected Pillow wheel/source inventory | Current storage bundle: 91 CLI steps across eight ARM sessions, including in-transfer cancellation, accepted commits, cold recovery and damaged-object repair; all eight offline templates, GDB/CMake, workspace restore, Notebook editing/save/cold-preview and both paragraph previews pass. The preceding private-signing bundle retains eight offline templates, GDB/CMake, Notebook touch editing/save/cold-preview, two paragraph previews and 36 key-recovery CLI steps across six ARM sessions. An earlier bundle retains eight native-TLS, eleven companion/model-USB, fifteen account, seven deadline and 37 publication-step passes; those matrices were not rerun on this bundle. Real GitHub OAuth/store publication now passes separately with the source SDK and native Keychain. Clean-host and complete release-source qualification remain |
| macOS x86-64 | Source tooling path | Unqualified; no ARM64 download substitution |
| Linux x86-64 | Cross-built GCC 16.2/binutils 2.47, GDB 17.2, full QEMU 11.1.1/r70 build and complete frozen store-enabled archive | The full packager passes firmware-trust/project-source gates. Fresh extractions pass 59 minimal-Ubuntu commands under explicit ARM-host emulation: eight templates, warm/cold starts, source exports, workspace recovery, private signing, reviewed Notebook/Gallery previews and unchanged published Surface 3D launches with default firmware. GDB/CMake, all eleven isolated companion cases and restrictive doctor/negative controls pass. All 5,510 listed files remain unchanged; archive validation also covers SHA256SUMS and 13 symlinks. The 160-ELF audit binds 159 native and 1,101 target inputs; fresh source groups verify 4,287 payload files plus manifests across 82 components and explicit project sources. All 4,399 prepared VM members retain exact rebuild evidence. Twenty actual frozen account commands also pass with GNOME Keyring Secret Service, encrypted persistence through daemon restart, locked/missing-bus failures, revocation and cleanup. All 37 frozen publication steps pass against actual local Worker/D1/R2 handlers, including upload/listing recovery, conflicts, withdrawal/republication, artifact cleanup and signed download/ARM launch with the explicit emulator fixture public key. Native/graphical hosts, interactive credential prompts, real OAuth/production publication, physical USB, upstream rebuilds and coordinated release qualification remain open; see the SDK ledger |
| Windows x86-64 | WSL2 interim path; native private-socket adapter and PE/DLL-checked desktop packaging candidates; cross-built GCC 16.2/binutils 2.47, GDB 17.2, Prime QEMU 11.1.1/r70, libusb and OpenSSL component archives with retained sources/notices; all 39 ARM compiler runtime variants and QEMU's nine dependency libraries audited; OpenSSL resource relocation, 14 reviewed Python wheels, full CPython runtime/source/notice inputs, separate QEMU DLL scope and a 22-component source assembly binding 1,702 installed tool files and 139 newlib files; exact newlib rebuild and project/VM source correspondence gates; refreshed project sources select the store-enabled VM used by Linux, with 4,399 firmware source members, 351 current SDK/recipe inputs and all three source archives verified | No complete native bundle has been built/executed; frozen packaging, native compiler/QEMU/debugger/USB/Credential Manager and clean-host qualification remain open |
| Linux ARM64 | Source tooling path | Separate support/qualification decision pending |

The production Linux archive now includes the launcher's relative library path,
current companion shutdown handling and QEMU control-endpoint stalls previously
validated in a diagnostic bundle. Its updated native source correspondence and
all three source groups are checked. Earlier diagnostic/recovered archives keep
their original evidence; see the [SDK ledger](NATIVE-APP-SDK-1.0-PROGRESS.md).

`doctor` reports compiler/runtime availability separately from device and host
qualification. It never probes hardware or claims an attached calculator was
checked. Physical installation support means the host implements the protocol;
it does not mean migration/endurance/recovery have passed physical acceptance.

Earlier desktop candidates lacked compiled store keys. The complete new Linux
archive now includes the reproducible configured VM and matching sources, with
exact SDK/VM trust gates and unchanged published Surface 3D execution using its
default firmware. Earlier artifacts retain their original scope; store-app
compatibility must be qualified for each exact host bundle. Real OAuth/publication
now passes separately with the source SDK on macOS; other desktop reassemblies,
clean hosts, release integration and physical acceptance remain open.
