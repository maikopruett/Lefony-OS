# Frame-boundary presentation for touch scrolling

Candidate `260909-055828-24cb13`, capsule SHA-256
`e498606c8c4195dd969764021910696d7e9e481db09ba664d2690f419e0a9c25`.
Prepared for installer selection; not flashed during this change. Physical
scrolling/tear-free output remains to be confirmed by the user. U-Boot, panel
timings, pixel clock, touch mapping, and NAND layout are unchanged.

## Cause

The user confirmed coordinate touch works on the calculator but reported bad
tearing while scrolling. Previously every `pushRect` wrote into the active
LCDIF scanout buffer, including the intermediate stages of a window redraw.
The physical `waitForVBlank()` did nothing. This allows the panel to consume
part-old, part-new frames; it is a concrete tearing mechanism, not evidence of
a touch-coordinate regression.

The Prime Linux `mxsfb_pan_display` path in
`build/raymii-prinux-linux/drivers/video/fbdev/mxsfb.c` writes NEXT_BUF to request
a VSYNC-bound flip and waits for completion. This does not require a separate
panel TE pin. The upstream [Linux mxsfb driver](https://code.googlesource.com/linux/torvalds/linux/+/7b1b868e1d9156484ccce9bf11122c053de82617/drivers/gpu/drm/mxsfb/mxsfb_kms.c)
also uses the LCD controller's next-buffer mechanism.

## Implementation

- Retain one logical drawing/readback buffer and allocate two guarded LCD
  scanout buffers. Total reserved storage is 921,984 bytes, within the existing
  1 MiB non-cacheable framebuffer region; no linker-map expansion is required.
- Bracket the complete `Window::redraw` view traversal in a frame transaction.
  Copy the finished logical image into the free scanout buffer, publish memory,
  write LCDIF NEXT_BUF, and wait for CUR_BUF to acknowledge the swap.
- Never write the currently scanned or pending buffer. If a swap times out,
  preserve ownership, keep rendering into the logical image, and retry later.
  Even small partial redraws preserve all unchanged pixels in the next frame.
- Bound acknowledgment polling to 500 iterations. Physical delays use a finite
  instruction loop, independent of GPT state, including early boot. The VM
  uses its modeled timer. No live CUR_BUF writes or controller resets per frame.
- Clear stale frame-done status when submitting; ownership uses CUR_BUF, not
  a completion flag that could belong to an earlier frame. No IRQ is enabled.
- Frames with no changed pixels do not copy or swap. Outside a window
  transaction, direct pixel operations still present (potentially more slowly
  for workloads that issue many individual pixel calls).
- Initialize/resume scanout from the retained logical image. Batch display
  self-tests, check all three buffers' guards, and finish the first frame before
  the existing backlight reveal. Abort/exception screens cancel an interrupted
  frame transaction; Poincare's longjmp recovery also clears transaction depth.
- USB event diagnostics report `FRAME_SWAP_TIMEOUT` / `FRAME_SWAP_RECOVERED`
  with CUR, NEXT, and timeout count, only on fault-state transitions. Existing
  snapshot pixel samples now use the actual logical-buffer pointer, not the old
  hardcoded address. VM control exposes `DISPLAY FRAMES` / `DISPLAY TIMEOUTS`.

`scripts/prepare_prime_display.py` is checked and idempotent; the regular native
build pipeline invokes it. It edits only the prepared window/error hooks and
copies the frame wrapper, without resetting a checkout.

## Verification

- 126 targeted tests passed, including compiled C++11 ownership tests for clean
  frames, partial redraw, publication ordering, repeated timeout while both DMA
  buffers are owned, delayed completion, resume, and unexpected CUR addresses.
- Native and VM builds completed; the real Shift/event-table test passed.
- The coordinate-touch UI test exercises launcher and toolbox scrolling,
  repeated row recycling, tap activation, palette insertion (`3² = 9`), and
  cancellation. Frame counts advance with zero timeouts during normal operation;
  framebuffer guards remain intact. Screenshots were inspected.
- The same test stops LCDIF RUN during scrolling, confirms bounded failures
  without losing input responsiveness, restores RUN, and checks swap recovery.
- The final physical-target capsule boots through the emulated NAND path.
  Main/elapsed timer checks and the stopped-GPT, unplugged full-battery, and
  two-day elapsed-gap USB battery checks pass.
  One timer run concurrent with the other VM tests exceeded the elapsed/RTC
  comparison tolerance: 1120 ms versus 1084.72 ms, sampled through separate USB
  requests. An unchanged isolated rerun passed all ten comparisons. This is
  consistent with sampling skew under contention; no timer code or test
  tolerances were changed. Both logs remain at
  `/tmp/lefony-tearing-timer-final.log` and
  `/tmp/lefony-tearing-timer-recheck.log` for this session.

The emulator models frame-boundary buffer latching, not the panel's scanline-
by-scanline optical output. These checks validate buffer ownership and recovery;
only a physical scrolling test can establish that visible tearing is resolved.
