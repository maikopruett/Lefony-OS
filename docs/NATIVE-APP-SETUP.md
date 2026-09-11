# Native SDK and store setup

The SDK now supports signed ABI 1 packages, a launcher, private app data and
separate USB installation commands. The website is deployed at **https://lefony.com**.
GitHub OAuth and an always-on dedicated validator are the remaining account/host
setup. Physical storage migration and recovery still require hardware testing;
no calculator was written during this implementation.

## Already provisioned in this workspace

- Independent app public key: `ports/lefony-prime-g2/app-signing.pub`.
- Private signer: ignored `build/lefony-app-signing/app-private.pem` in the OS
  repository. Back it up privately before moving or cleaning this checkout.
- Public guest-key list: `ports/lefony-prime-g2/app-trust-roots.json`.
- Cloudflare D1 `lefony-app-store`, with website migrations 0001–0004.
- Private R2 `lefony-app-artifacts`; no public bucket access is needed.
- Worker `STORE_BUILDER_TOKEN` secret. Its matching private local copy is
  `.local/store-builder-token` in the website repository.
- The website configuration contains the app public key and D1 identifier.

The app signer is a new identity, independent of the existing firmware signer.
Never replace either identity implicitly. No calculator has been flashed.

## 1. Configure GitHub login

In GitHub **Settings → Developer settings → OAuth Apps → New OAuth App**, create
an app for the deployed website. For the current production domain, set:

- Homepage URL: `https://lefony.com`.
- Authorization callback URL: `https://lefony.com/api/store/auth/callback`.

Use a separate OAuth app and the matching origin for staging.

In the **website repository**, set `GITHUB_CLIENT_ID` in `wrangler.jsonc` to its
client ID, then enter the secret through Wrangler's hidden prompt:

```sh
npx wrangler secret put GITHUB_CLIENT_SECRET
```

Do not put the secret in `wrangler.jsonc`, public assets, screenshots, or Git.
No repository-access permission is required for users. Test sign-in, logout,
cancelled login and an expired login before enabling submissions.

`node scripts/deploy-store-preview.mjs` in the website repository can publish
read-only store/developer pages before OAuth exists. It generates an ignored
config that forces submissions off and does not require a fake OAuth secret.
Normal `npx wrangler deploy` retains the full OAuth-secret requirement.

## 2. Build and qualify the Linux validator

Use a dedicated Linux Docker host, separate from unrelated services and secrets.
Docker controls the host kernel; the restricted container is one boundary, not
a substitute for host isolation.

The repository includes a toolchain base Dockerfile. It downloads checksum-pinned
GCC 16.2.0/binutils 2.47 and builds the pinned custom QEMU. Obtain an Ubuntu 24.04
image through your registry, inspect its real digest, and substitute it below:

```sh
docker build -f sdk/publisher/Dockerfile.toolchain \
  --build-arg BASE_IMAGE=ubuntu@sha256:ACTUAL_BASE_DIGEST \
  --build-arg JOBS=2 -t lefony-sdk-toolchain:candidate .
```

Build the VM with the explicitly configured app public keys:

```sh
LEFONY_APP_PUBLIC_KEYS="$PWD/ports/lefony-prime-g2/app-trust-roots.json" make firmware-vm
```

Push the trusted base to your registry and use its immutable manifest digest for
the final validator image:

```sh
docker build -f sdk/publisher/Dockerfile \
  --build-arg VALIDATOR_BASE=YOUR_REGISTRY/lefony-sdk-toolchain@sha256:ACTUAL_DIGEST \
  -t lefony-validator:candidate .
```

The source submission never enters image construction. Preserve the compiler
source archives and patched QEMU source retained under
`/usr/share/lefony-sources` when distributing these binaries.

Before starting the public consumer, exercise the exact final image with the
counter, compile-error, infinite-loop and malformed-source fixtures. A passing
case must build identically twice, return from every callback and leave the OS
responsive; each failing case must produce a failed result without publication.
Run the executable qualification gate and retain its report:

```sh
python3 sdk/publisher/qualify.py --image sha256:ACTUAL_IMAGE_ID --output build/validator-qualification.json
```

The consumer requires this passed report for the exact configured image.
The local candidate has passed all five qualification cases in the isolated
`colima-lefony-sdk` Docker context. Its immutable ID is
`sha256:5585bc06476d05efb819b47221924e0ba663f5f20d80ad7d0958de4dbb50ea91`.
The report is `build/validator-qualification.json`. You can export the image
with `docker --context colima-lefony-sdk save lefony-validator:candidate` and
load it on a compatible ARM64 dedicated Linux host. Qualify it again on that
host and use the exact image ID reported there. Do not assume this ARM64 image
runs natively on an x86 host.

## 3. Run the consumer continuously

Install the checked-out SDK under `/opt/lefony` on the dedicated host. Copy the
app private key to `/etc/lefony-app-signing/app-private.pem`, readable only by
`lefony-builder`. Set `/etc/lefony-validator.env` (mode 0600) with:

```text
LEFONY_STORE_ORIGIN=https://YOUR_EXACT_SITE_ORIGIN
LEFONY_STORE_BUILDER_TOKEN=YOUR_EXISTING_PRIVATE_BUILDER_TOKEN
LEFONY_VALIDATOR_IMAGE=YOUR_REGISTRY/lefony-validator@sha256:ACTUAL_DIGEST
```

An immutable local `sha256:IMAGE_ID` from `docker image inspect` is also accepted
for a preloaded image. Mutable tags are rejected by the consumer.

Copy the passed report to `/etc/lefony-validator-qualification.json`, readable by
the service account. Install the supplied `sdk/publisher/lefony-validator.service` and `.timer` under
`/etc/systemd/system/`. Create the `lefony-builder` service account, grant it
access to this dedicated host's Docker socket, then run:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now lefony-validator.timer
sudo journalctl -u lefony-validator.service
```

The timer runs one consumer at a time. Private credentials remain on the host,
with no network, credentials or host mounts inside source-validation containers.
Reports omit private paths and raw logs. Do not run public untrusted builds on a
personal workstation simply because Docker is available there.

## 4. Open the store after end-to-end qualification

In a separate staging deployment, verify a complete GitHub login → required
listing fields → queued build → signed download → emulator launch → vote/comment
flow. Include malformed input, a hanging app, a failed build, lease expiry,
revoked signing key and hidden app checks. Do not seed fake accounts or reviews
into production as test data.

Set `STORE_SUBMISSIONS_ENABLED` to `"true"` only for the deployment whose
validator is running and qualified. Then, from the website repository:

```sh
npm run build
npm run lint
npm test -- --maxWorkers=2
npm run test:e2e
npx wrangler d1 migrations apply STORE_DB --remote
npx wrangler deploy
```

There is no manual app approval step. Each submission requires a matching app
name, description, icon, one to five screenshots and permission to publish its
source. The automated signing/publication pipeline handles passing builds.

## 5. Desktop downloads

The Developers page offers a macOS ARM64 candidate and three corresponding-source
archives with checksums. A replacement candidate can be built with the frozen Python launcher, compiler,
QEMU and all linked runtime libraries. From the OS repository:

```sh
.venv/bin/python -m pip install -r sdk/requirements-desktop.txt
PRIME_G2_QEMU_SOURCE_DIR=/tmp/lefony-sdk-qemu-source \
PRIME_G2_QEMU_RUNTIME_ROOT=/tmp/lefony-sdk-qemu \
PRIME_G2_QEMU_OUTPUT="$PWD/build/qemu-prime-g2-public/qemu-system-arm" make emulator
.venv/bin/python scripts/package_native_desktop.py \
  --qemu build/qemu-prime-g2-public/qemu-system-arm \
  --toolchain "$(brew --prefix arm-none-eabi-gcc)" \
  --binutils "$(brew --prefix arm-none-eabi-binutils)" \
  --public-key ports/lefony-prime-g2/app-signing.pub \
  --runtime-library "$(brew --prefix sdl3)/lib/libSDL3.dylib" \
  --openssl "$(brew --prefix openssl@3)/bin/openssl" \
  --source-materials build/sdk-desktop-sources \
  --output build/sdk-desktop-release-candidate
```

To refresh source materials from an existing matching bundle, run from the OS root:

```sh
.venv/bin/python scripts/collect_native_desktop_sources.py \
  --bundle build/sdk-desktop-candidate3/lefony-sdk \
  --output build/sdk-desktop-sources
.venv/bin/python scripts/package_native_desktop_sources.py \
  --materials build/sdk-desktop-sources --output build/sdk-public-sources
```

Preserve the checked sources, recipes, patches, notices and manifest when
rebuilding. The collector uses installed Homebrew recipes; its `--prefix`
option selects the installation. A first build needs those dependency materials
prepared before final packaging. The existing candidate and collected materials
are available in this workspace.

Build QEMU from neutral source/build paths as above; the packager rejects
binaries embedding the current user’s home path. The output directory must be new. The SDL3 argument supplies the dynamically
loaded dependency of Homebrew's SDL2 compatibility library. Test a moved copy
with spaces in its path and without Homebrew/Python on `PATH`, then test on a
clean supported OS. The downloadable macOS bundle is an unsigned development
candidate, accompanied by checksums, notices and corresponding source. For a
normal macOS release, sign/notarize with your Developer ID. The local tests
deny all reads and execution under Homebrew while building and running apps;
they do not replace a clean-machine or Windows/Linux desktop qualification.

The script also supports a native Linux build, which needs independent
qualification against its supported glibc/desktop environment. Windows is not
supported by the current Unix-socket runner. A macOS local test does not qualify
Linux or Windows downloads.

## 6. Build compatible firmware and set up app storage

Both firmware targets include the isolated runtime and Native apps launcher.
Build with the **existing firmware key** and the independent app public-key
list; never regenerate an installed device's firmware identity:

```sh
LEFONY_UPDATE_PUBLIC_KEY="$PWD/ports/lefony-prime-g2/release-signing.pub" \
LEFONY_APP_PUBLIC_KEYS="$PWD/ports/lefony-prime-g2/app-trust-roots.json" make firmware
```

Install that candidate only through the existing firmware installer and its
applicable recovery/backup checks. Building or deploying the website does not
update a calculator. No physical flash is performed by this runbook's build.

On a compatible running calculator, the app store's **Connect calculator**
button reads its app protocol. An unprovisioned calculator offers **Save backup
and set up app storage**, with explicit consent to retire the stock HP
filesystem. The browser saves and rereads the backup before provisioning.
Afterward, **Install app** verifies the signature, writes the inactive app bank,
commits it, and reads the installed bytes back. Open **Native apps** on the
calculator to select the app. The native counter demonstrates persisted data.

The OS checkout also provides a command-line path (these commands operate on
an attached device only when you explicitly run them):

```sh
.venv/bin/python scripts/lefony_app_installer.py status
.venv/bin/python scripts/lefony_app_installer.py migrate-storage \
  --backup build/private-app-backup --retire-stock-filesystem
.venv/bin/python scripts/lefony_app_installer.py list
.venv/bin/python scripts/lefony_app_installer.py install downloaded.lfapp
.venv/bin/python scripts/lefony_app_installer.py remove APP_ID
```

Keep backups and signing keys outside public Git history. See
[NATIVE-APP-STORAGE.md](NATIVE-APP-STORAGE.md) for exact layout, protocol,
interruption behavior and recovery limitations. The A/B migration flag remains
unchanged. The new migration deliberately reserves only 432–496 MiB.

Before a public physical release, test a recoverable calculator: full raw backup,
restore procedure, migration, install/update/remove, cold boot, data persistence,
real power-loss recovery, bad blocks and touch/key response. Record candidate
hashes. Emulator tests establish code behavior, not electrical or endurance
qualification. The backup restore procedure remains a separate hardware task.

## 7. Publish source changes and operate the store

The working trees have not been committed or pushed. Review the OS and website
diffs, commit them, and publish a firmware/SDK release through the existing
release process when ready. The deployed website already has D1/R2 and the
independent app key; it does not need replacement resources.

Back up D1 and private signing credentials, keep the validator host patched,
and run `sdk/publisher/health.py --store https://lefony.com` with the private
builder token to inspect queue age and accepted key IDs. Configure GitHub OAuth,
install the dedicated validator service, exercise staging, then enable public
submissions. Routine apps are never sent to a manual approval queue.
