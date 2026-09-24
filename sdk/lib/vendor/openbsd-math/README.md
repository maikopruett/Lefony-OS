# App-side numeric library source

These files are exact git-object extracts from the pinned Upsilon revision in
`manifest.json`, under `liba/src/external/openbsd/`. The upstream inventory calls
this an OpenBSD 4.9-derived fdlibm collection; individual file revisions can be
newer. The exact manifest hashes, not that general version label, identify this
subset. Every original file-level copyright/license notice is retained. They
include Sun Microsystems' permission notices and any other terms printed in
the actual files; do not replace them with the OS's or SDK's blanket license.

`scripts/vendor_sdk_math.py` regenerates the extracts from the already pinned
public checkout and refuses to overwrite differing files. It does not fetch or
change an upstream revision. The adjacent original Lefony `math_compat/` headers
adapt fixed-width types and namespace the exported C symbols. No host I/O,
allocator, global calculator variables or privileged OS math call is included.

The experimental SDK runs 760 finite known-answer cases against mpmath 1.3.0
at 400 decimal digits, with an eight-ULP acceptance tolerance, plus signed-zero,
NaN/infinity, domain and helper cases. Host ASan/UBSan and the same corpus inside
a protected ARM app pass. This is a specified corpus, not an exhaustive error
bound, correct-rounding guarantee or physical performance qualification.
