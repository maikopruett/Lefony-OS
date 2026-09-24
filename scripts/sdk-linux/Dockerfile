# SPDX-License-Identifier: GPL-3.0-or-later
# Native Linux build dependencies. Supply an Ubuntu 24.04 image pinned by digest.
# Compiler/QEMU build outputs live in the caller's dedicated mounted work folder.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl git ninja-build pkg-config python3 python3-venv \
    python3-setuptools python3-wheel \
    libgmp-dev libmpfr-dev libmpc-dev libisl-dev zlib1g-dev libzstd-dev \
    libglib2.0-dev libpixman-1-dev libsdl2-dev libexpat1-dev libusb-1.0-0-dev \
    bzip2 xz-utils texinfo cmake \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
