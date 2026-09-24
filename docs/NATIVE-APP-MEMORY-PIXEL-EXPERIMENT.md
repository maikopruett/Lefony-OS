# Larger memory and copied-pixel architecture proof

This extends the [R0 execution experiment](NATIVE-APP-EXECUTION-EXPERIMENT.md)
using emulator-only, explicitly negotiated services. ABI 1's public memory
limits, package schemas, discovery bits and physical services remain unchanged.
The experiment is not a new supported ABI or a completed Doom port.

The [pinned Doom workload](../sdk/ports/doom/README.md) requires a default 6 MiB
zone allocation plus pixel buffers and other state. Its portable ARM engine
object uses about 274 KiB of code/constants and 304 KiB of static data before
dead-code removal. This motivates testing additional heap capacity separately
from the existing code/static-data regions.

## Candidate mapping and services

The VM reserves 8 MiB of physical BSS and eight short-descriptor page tables.
Virtual space `0x11000000..0x11800000` contains an unmapped first and last 4 KiB
page. Its usable user RW+XN range is `0x11001000..0x117ff000`, **8,380,416
bytes**. The normal 952 KiB data region and 64 KiB stack remain as before.
The extra reservation reduces the kernel heap in the same fixed 48 MiB image
region; the test checks remaining kernel headroom and records the exact value.
This is one candidate budget for measurement, not a menu of promised profiles.

After the execution opt-in, experimental service `0x7fff0003` takes six
32-bit words. Input begins with size 24 and version 1; output returns those,
the usable heap base/capacity, kernel heap reservation and app stack capacity.
The first call clears/maps the heap; subsequent queries preserve live data.
Normal legacy apps cannot access it. Fault/unload removes the mapping and
saved context. Cache maintenance precedes unmapping; the next allocation clears
the reservation. QEMU does not qualify physical cache behavior or latency.

The shared [newlib adapter](../sdk/experiments/newlib_os.c) implements bounded
`_sbrk`, including valid shrink requests and exhaustion. The kernel-heap mode
obtains this candidate memory; the original libc proof still uses its 256 KiB
local heap. No general file/process facilities are advertised: their hooks
continue to fail explicitly until actual OS implementations exist.

Experimental service `0x7fff0004` takes ten 32-bit words: size 40, version 1,
reserved zero, x/y, width/height, source stride in pixels, source pointer, and
exact readable byte length. It copies little-endian RGB565 into the OS-owned
surface. All geometry, stride, length, alignment and address checks precede any
drawing. At most 320 × 240 pixels are copied; stride is bounded to 320 pixels.
The app retains no LCD/DMA access and cannot change the copied frame by editing
its source buffer. Presentation still uses the prototype's existing scheduler.

## Validation

```sh
make firmware-vm
.venv/bin/python vm/test-sdk-memory-pixels.py
.venv/bin/python vm/test-sdk-libc.py
make firmware
```

The installed ARM workload allocates/initializes 6 MiB with newlib, checks
contents across a yield and repeated heap queries, verifies failed-realloc
preservation, copies a full frame from another allocation, and checks malformed
draw requests leave that frame intact. Existing checked save/read services
transfer data from the negotiated heap. Same-OS Home/relaunch checks heap
clearing and saved data. Separate programs verify unnegotiated access, both
guard pages and heap execution fault while the OS remains responsive.

The test records compiled probe and firmware identities, app code/static data,
kernel reservation, heap setup duration in the model, normal rendered frames
and isolation outcomes in `build/sdk-memory-pixels/report.json`. VM diagnostic
indices 16–18 expose setup milliseconds, mapped heap bytes and kernel heap
reservation for that evidence. They are not physical/public controls.

Remaining work includes a supported negotiated runtime/library profile,
larger-source project/package/website contracts, input queues and frame
scheduling, streamed files and real stdio, and integration of the actual Doom
workload. Physical memory/cache/stack peaks and performance need qualification
before promoting this candidate into the public runtime.
