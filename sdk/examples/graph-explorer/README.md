# Graph Explorer

An experimental public-API graph app with Cartesian sine and reciprocal curves,
a parametric unit circle, adaptive sampling, clipped raster drawing, axes,
trace, pan and zoom. Press OK to cycle curves, arrows to pan and +/− to zoom.
Touch buttons provide the same actions. Drag within the plot to pan, pinch to
zoom, tap to trace a point, or hold one finger still for half a second to reset.

Sampling runs in batches of at most 64 function evaluations per callback, with
a fixed depth-first stack and a 4096-evaluation ceiling. Invalid or unresolved
segments become visible gaps; the sampler never proves continuity or that every
narrow feature was found. The screen adapter batches/coalesces spans and falls
back to original ABI 1 fills on unsupported older firmware. No framebuffer or
privileged math access is used. The two-contact gestures need input service 8.

The view resets on launch; this example does not save documents. The current
curve set is fixed, and it is not a general expression graph editor. Physical
latency/frame rate and touch feel remain unqualified. Use the public replay
with `lefony-sdk test --workspace graph-test` and inspect its captured frames.
