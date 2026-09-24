# Historical hosted native app validation

This directory retains the older hosted-validator implementation for historical
reproducibility. It is not required by the current local-SDK publication flow.
Use [the current setup runbook](../../docs/NATIVE-APP-SETUP.md). Developers build
and test locally; the website checks and signs submitted bytes without running
them. The instructions below describe only the earlier deployment model.

`worker.py` consumes one queued source submission from the website, runs a
trusted image without network access, and reports a result. There is no manual
approval state. The validator returns an unsigned **ABI 1** package for the versioned native runtime. The host independently checks it, then wraps it in an LFAPP1 signature using a separate app private key. Neither the key nor the API credential enters the container. This does not qualify a physical app runtime.

The source bundle is bounded JSON with native `.cpp`/`.h` files. Neither the
host nor CI runs an app-provided build script, shell command, workflow or package
manager. The compiler command comes from this SDK. `validate.py` builds twice,
compares the packages, checks the ELF/container, and runs startup, logical input,
timer, touch/cancellation and close callbacks in the real VM guest loader. The
report includes the exact firmware and package hashes. It tests termination and
OS recovery, not the mathematical correctness of arbitrary apps.

## Prepare a validator image

This requires a Linux Docker host. `Dockerfile.toolchain` builds the pinned compiler and custom QEMU from checked sources; see the [setup runbook](../../docs/NATIVE-APP-SETUP.md). Build and qualify a base image containing:

- Python 3.11 or later;
- GCC `arm-none-eabi-g++` 16.2.0 and matching objcopy/libgcc;
- this repository's Prime QEMU at `/opt/runtime/qemu-system-arm`, with its
  runtime libraries (headless display support is sufficient).

Use a base pinned by digest, then build from the OS repository root:

```sh
docker build -f sdk/publisher/Dockerfile \
  --build-arg VALIDATOR_BASE=registry.example/lefony-base@sha256:YOUR_BASE_DIGEST \
  -t lefony-validator:candidate .
```

The example digest/registry must be replaced with a real qualified image. A
prebuilt image is not published by this change. Package only SDK source and the
matching public VM ELF into the build context; `.dockerignore` excludes local
keys, private captures and unrelated generated trees. Retain corresponding
source and notices for redistributed toolchain/QEMU components.

Run the built image against known passing, failing, hanging and malformed
submissions before enabling public consumption. Push/preload it through the
operator's normal registry process and record its immutable manifest digest.

## Consume a job

Set `LEFONY_STORE_BUILDER_TOKEN` in the consumer's private environment, matching
the website's `STORE_BUILDER_TOKEN` secret. It must be at least 32 characters of
high-entropy random data. The token is never supplied to the container.

```sh
python3 sdk/publisher/worker.py \
  --store https://YOUR_STORE_ORIGIN \
  --image registry.example/lefony-validator@sha256:YOUR_VALIDATED_DIGEST \
  --signing-key /etc/lefony-app-signing/app-private.pem \
  --qualification /etc/lefony-validator-qualification.json
```

The supplied `lefony-validator.service` and `.timer` run the consumer on a dedicated Linux host. An immutable local `sha256:IMAGE_ID` is also accepted. Schedule this one-shot command on an isolated build host using the operator's
job scheduler. Start with one consumer. Leases prevent concurrent workers from
publishing the same release; they expire after ten minutes, with at most three
attempts. A validator has a three-minute wall deadline, memory/CPU/process and
output limits, a read-only root filesystem, a bounded temporary directory, no
host volume mounts, no network, no Linux capabilities and a non-root user. No
host Docker socket is mounted into the container. Use an ephemeral build host
for public untrusted code; a Docker container alone is not a separate kernel.

The host independently rechecks source and package hashes, identity and ELF
structure before sending a completion. The API accepts a result only for a
live lease and independently verifies the app signature, key identity, container size and payload digest. Artifacts are
immutable by content hash. A hidden app or blocked account cannot publish.

A failed compiler/emulator check marks the release failed; it does not publish a
partially checked package. Retry with a corrected source and a new version.
Transient worker crashes retry through the bounded lease mechanism. Local
validation can be reproduced with `lefony-sdk build` and `lefony-sdk test`.

## Current qualification boundary

The real guest runtime, host/OpenSSL signing and website/Web Crypto publication
paths have been tested independently. The Linux toolchain image is built from
checksum-pinned compiler archives and the existing pinned QEMU source. Its exact
final image still needs the passing/failing/hanging/malformed fixture gate before
public consumption. Consult the setup/status notes for current build evidence.
Keep submissions disabled until the exact image, queue, OAuth and object storage
pass a staging run. This is deployment qualification, not manual app review.
