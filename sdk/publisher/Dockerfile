# SPDX-License-Identifier: GPL-3.0-or-later
# Supply a separately built base containing GCC 16.2.0, Python 3.11+, the
# Prime-specific QEMU at /opt/runtime/qemu-system-arm and its shared libraries.
# Use the repository root as context. No source submissions enter image builds.
ARG VALIDATOR_BASE
FROM ${VALIDATOR_BASE}
COPY sdk /opt/sdk
COPY dist/lefony-os-prime-g2-vm-native.elf /opt/runtime/firmware.elf
RUN test "$(arm-none-eabi-g++ -dumpfullversion)" = 16.2.0 && /opt/runtime/qemu-system-arm --version && python3 --version
USER 65534:65534
WORKDIR /tmp
ENTRYPOINT ["python3", "-B", "/opt/sdk/publisher/validate.py"]
