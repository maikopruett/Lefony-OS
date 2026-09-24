# Native SDK and store setup

The supported publication mode is **local SDK validation**. Developers build
and test ARM packages on their computers. The website checks identity,
ownership, package structure, integrity and required listing media, then signs
the accepted bytes. It does not rebuild or execute community submissions.
Reports are developer-supplied evidence, never independent certification.

The earlier validator/consumer configuration is archived in
[the historical runbook](NATIVE-APP-SETUP-LEGACY.md). No hosted validator,
GitHub Actions submission job or manual approval is required for this flow.

## Developer journey

Install an experimental SDK artifact from the website's Developers page, or follow
[the source SDK quick start](../sdk/README.md). The 0.2.0-dev release is experimental and does not complete
the maturity roadmap. Consult [the capability matrix](NATIVE-APP-CAPABILITIES.md) for limits,
host support and the difference between preview and installed VM workspaces.

```sh
lefony-sdk doctor
lefony-sdk new my-app --template pocket-lab
cd my-app
lefony-sdk build
lefony-sdk test
lefony-sdk test --workspace development
lefony-sdk package
lefony-sdk source
```

Sign in with GitHub on the Developers page. Supply the matching source bundle
and package, app name, description, icon and one to five screenshots. Confirm
permission to publish the source and that you tested the exact package locally.
The listing labels these bytes **Developer tested locally**. Source disclosure
does not prove binary/source correspondence. App signatures authenticate bytes,
not calculation quality, isolation correctness or physical qualification.

Versions are immutable. A changed package needs a new version. Owners can
withdraw their app from their developer account; downloads stop while already
installed copies and ownership/review history are retained. A later new version
can be published again. CLI OAuth/publish/withdraw commands remain unimplemented;
use the browser flow rather than copying browser credentials into scripts.

## Maintainer configuration and release order

The website is a sibling repository; its account, schema and deployment tests
are separate from this SDK's local checks. Preserve the existing app signing
identity and the separate firmware trust root. Private keys stay in ignored
local storage or secret bindings, never in SDK projects, bundles or test reports.

The current website supports `STORE_PUBLICATION_MODE=local-sdk`, GitHub OAuth,
private app signing, D1 metadata and R2 artifacts. Configure account credentials
through its secret-management workflow. Do not put secrets in `wrangler.jsonc`
or source control. Public-key metadata is public release data.

ABI 1's five-field manifest and source format 0 remain strict. The SDK also
supports explicit schema-1 manifests and `source --format 1` for projects with
assets. The bundled emulator and updated website understand these contracts.
Older physical firmware rejects required new capabilities; update to compatible
firmware before installing those apps. The SDK release does not update firmware
on a calculator. See [contract extensions](NATIVE-APP-CONTRACT-EXTENSIONS.md).

Before deployment, run the website build, lint, unit/integration and browser
tests according to its `AGENTS.md`, then exercise staging login, publication,
exact-byte download verification, a data-preserving update and owner withdrawal.
Never create fake production reviews/accounts as fixtures. A passing OS host
suite alone does not qualify a website deployment or SDK download.

## Calculator storage and installation

Lefony reserves its fixed 64 MiB app region at OS startup. The browser reads
inventory/capacity and installs, updates or removes an app when requested.
Ordinary app installation does not run browser provisioning or require a
storage backup. Apps appear as individual tiles in the main menu.

Physical firmware accepts signed ABI 1 packages and verifies installed bytes.
SDK `run`, `test`, `debug`, `build` and `package` do not contact a calculator.
Workspace media and its deliberately public emulator signing fixture are
synthetic; the fixture is compiled out of physical firmware.

The older explicit `scripts/lefony_app_installer.py migrate-storage` command is
retained for legacy tools. Firmware update/recovery backups and protections
remain separate. See [storage/recovery contracts](NATIVE-APP-STORAGE.md).
Physical power loss, restore, migration, endurance and input feel require their
own exact-candidate qualification before a stable durability claim.

## Downloads

`scripts/package_native_sdk.py` creates a deterministic standalone source kit.
`scripts/package_native_desktop.py` packages compiler, newlib, GDB, Python, QEMU,
USB dependencies and notices for host-specific candidates. The current recipe
requires `--newlib`, `--gdb-runtime`, `--libusb` and `--project-sources` on every
supported packaging host; see the
[native host guide](../sdk/HOSTS.md). Corresponding source must match every bundled
binary. Rebuild and qualify relocated/offline bundles after SDK changes;
historical hashes do not qualify new candidates.

The maintainer authorized publishing 0.2.0-dev with native Windows and physical
qualification pending. macOS ARM64 is locally tested; clean-host Linux/WSL, native
Windows, macOS signing/notarization and physical qualification remain required
for broader support or stable-release claims. The full requirements remain in
[the maturity roadmap](NATIVE-APP-SDK-MATURITY-PLAN.md).
