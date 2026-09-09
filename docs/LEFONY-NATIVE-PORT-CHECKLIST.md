# HP Prime G2 native Upsilon full-port checklist

This is the authoritative engineering checklist for running Upsilon directly
on the HP Prime G2's i.MX6ULL Cortex-A7 without Linux. Development is
emulator-first, but the final target is a reliable native calculator whose
behavior is validated in the emulator and, where QEMU cannot model the
hardware, confirmed on a recoverable physical Prime G2.

The checklist covers the native Upsilon/Ion port, its U-Boot boot path, the
Prime G2 QEMU environment, application behavior, persistence, reliability,
recovery, documentation, and eventual physical-hardware parity.

## Status and completion rules

- `[x]` means implemented and verified at the level stated by the item.
- `[ ]` means incomplete, even if an experiment or partial implementation
  exists.
- **VM substitute** means the emulator uses a deliberate interface in place
  of hardware that upstream QEMU does not model. It does not prove the
  corresponding physical driver.
- **Physical gate** means emulator work can prepare and test the surrounding
  software, but final completion requires a recoverable hardware test.
- An item is not complete merely because the OS boots or a screen appears.
  Its acceptance test must also pass.
- Automated tests must start from a clean, cold VM unless a test explicitly
  covers resume or retained state.
- Generated files belong under `build/` or `dist/`; source directories must
  remain reproducible from pinned inputs.
- Native bring-up must not write the calculator's NAND until the boot,
  recovery, image-layout, and power-loss tests in this document are complete.

### Last clean emulator run

On 2026-08-31, `./vm/test-native-comprehensive.sh` passed all 32 stages from
clean physical and VM builds: host units, the complete pinned upstream unit
binary, pinned U-Boot and reproducible boot media, SBOM generation, smoke and
semantic protocol tests, runtime hardware checks, the exhaustive 39-key/modifier
matrix, Goodix I2C touch navigation, display and electrical-fidelity fault
injection, PF1550/
RTC/power-service diagnostics, modeled USB enumeration and transfers, all 11
enabled app launches and 22 calculation workflows, protocol and update-capsule
fuzzing, storage boundaries/fuzzing/persistence/preferences/read-only rescue,
every simulated commit interruption, four safe exception classes, watchdog
cold reset, corrupt-boot recovery, performance budgets, 25 consecutive cold
boots, and 24 hours of accelerated virtual-time activity.
The machine-readable result is retained at
`build/prime-g2-native-suite-20260831-220308/summary.json`.

This is the completed emulator-solvable items 1–9 baseline, not a declaration
that the physical gates or every release/product item in P1–P3 is complete.

### Completed emulator work packages 1–9

1. [x] Native KPP matrix scanning, IRQ wake, debounce, repeat, modifiers, and
   exhaustive key-map tests.
2. [x] Native USBOTG device/EP0 path, modeled host enumeration and transfers,
   reconnect/suspend/error cases, and RAM-only recovery capsule staging.
3. [x] PF1550/SNVS power state, RTC, battery UI, idle dim/suspend/resume, and
   deterministic power lifecycle tests.
4. [x] Native Goodix I2C report parsing, IRQ/reset behavior, taps, swipes,
   navigation, and malformed/missing-device tests.
5. [x] Pinned U-Boot media boot plus modeled NAND/BCH, atomic A/B update,
   readback verification, rollback, bad-block faults, and read-only rescue.
6. [x] ARMv7 MMU/cache regions, DMA ownership, GIC dispatch,
   interrupt-backed timing, latency accounting, and safe exception handling.
7. [x] Health-checked watchdog feeding after the first live event-loop poll,
   reset-reason persistence, startup-loop prevention, and forced hang/reset
   tests.
8. [x] Representative native UI workflows for all 11 enabled applications,
   including 22 calculation workflows and frame/state assertions.
9. [x] Storage/update/USB/control-protocol fuzzing, resource and latency
   budgets, leak checks, 25 cold boots, accelerated 24-hour soak, and current
   developer/checklist documentation.

### Explicit emulator non-claims

The current green test run must not be interpreted as completion of these
hardware-parity items. They remain explicitly unchecked below:

- Physical USB PHY/electrical behavior and interoperability with real macOS,
  Linux, and Windows host controllers. The modeled bus now covers native EP0
  enumeration, reconnect, suspend/resume, malformed traffic, and recovery.
- Physical KPP debounce timing and electrical measurements. VM keys now enter
  the QEMU KPP matrix at its hardware boundary rather than through guest UART.
- Deep suspend, clock/peripheral reconstruction, physical wake, and measured
  power consumption.
- Analog panel signal integrity; calibrated battery telemetry; NAND ECC error
  correction, endurance, and wear behavior.
- Target validation of Goodix touch, PF1550/on-key, SNVS power-off/wake, and
  RTC retention across reset and loss of main power.

## Priority order

1. **P0 — self-contained and testable virtual calculator:** boot from emulated
   media, persistent storage, deterministic test control, and broad application
   regression coverage.
2. **P1 — complete native OS behavior:** runtime hardening, display and input
   correctness, full application workflows, power lifecycle, and removal of
   user-visible dummy services.
3. **P2 — Prime G2 hardware and QEMU fidelity:** Prime-specific device models,
   physical drivers, USB/recovery, power, battery, NAND, and hardware parity.
4. **P3 — release readiness:** updates, compatibility, performance, long-run
   reliability, documentation, licensing, and distributable images.

Do not start destructive installation work merely because a lower-level item
is ready. Complete the P0 recovery and test gates first.

## Verified baseline

### Source, build, and artifacts

- [x] Pin the Upsilon repository and exact upstream commit in
  `ports/lefony-prime-g2/UPSTREAM`.
- [x] Keep native platform code as an overlay rather than modifying the
  generated upstream checkout by hand.
- [x] Provide an ARMv7-A bare-metal cross-build container.
- [x] Build a physical native target with `PLATFORM=prime_g2`.
- [x] Build an emulator target with `PLATFORM=prime_g2_vm`.
- [x] Produce a compact U-Boot ELF, a debug ELF, and a flat binary.
- [x] Keep VM-only compiler and peripheral substitutions out of the physical
  target.
- [x] Pin a known U-Boot revision for the native VM.
- [x] Build U-Boot reproducibly with the repository script and container.

### CPU startup and memory

- [x] Install ARM exception vectors at the native image vector address.
- [x] Establish a dedicated native stack before entering C++.
- [x] clear `.bss` and execute the C++ constructor array.
- [x] Enable the VFP/NEON register file before floating-point code runs.
- [x] Normalize the U-Boot handoff to MMU-off and cache-off operation.
- [x] Link the image at `0x82000000` with entry point `0x82000020`.
- [x] Reserve a separate framebuffer region at `0x8f000000`.
- [x] Assert image heap and framebuffer bounds at link time.
- [x] Avoid the unaligned-access abort seen during initial QEMU bring-up.

### Current native services

- [x] Initialize UART1 and emit a native-entry diagnostic marker.
- [x] Initialize GPT1 and expose monotonic millisecond and sleep functions.
- [x] Render the Upsilon 320x240 framebuffer through LCDIF in QEMU.
- [x] Implement the physical-target LCDIF serial-RGB configuration and ILI9322
  initialization sequence in source.
- [x] Implement a physical-target PWM7/backlight initialization path in
  source.
- [x] Implement a physical-target 8x8 KPP polling path and Prime-to-Ion key
  map in source.
- [x] Isolate QEMU's parallel LCDIF, GPT clock, and UART input substitutions
  behind `PRIME_G2_EMULATOR`.
- [x] Start Upsilon at its normal home screen with Calculation selected.
- [x] Start with compiled default preferences and volatile RAM storage.

### Current emulator validation

- [x] Start U-Boot before native Upsilon in QEMU.
- [x] Hand off from the U-Boot prompt to the preloaded native entry point.
- [x] Provide a UART control bridge for deterministic key and gesture input.
- [x] Provide a QMP framebuffer capture helper.
- [x] Verify UART `PING`/`PONG` after native startup.
- [x] Verify that a D-pad event visibly changes the selected home application.
- [x] Verify that OK opens Calculation.
- [x] Verify that entering `1+2` visibly produces `3`.
- [x] Verify that a touch command reaches the native VM bridge.
- [x] Retain smoke-test logs and framebuffer captures under `build/`.
- [x] Stop QEMU and helper processes cleanly after the smoke test.

## P0 — highest priority now

P0 turns the current RAM-preloaded demonstration into a self-contained,
repeatable virtual calculator. These tasks should be completed before adding
large amounts of optional hardware functionality.

### P0.1 — real U-Boot boot from emulated media

- [x] Select the first native boot medium for the VM. Prefer emulated SD/eMMC
  through USDHC because it is simpler and safer than raw NAND for this phase.
- [x] Document the chosen virtual-media geometry, partition table, filesystem,
  load address, maximum image size, and ownership of every region.
- [x] Add a deterministic script that creates the complete blank media image.
- [x] Add the Upsilon ELF or packaged payload to that image without requiring
  manual mounting.
- [x] Attach the image to the QEMU i.MX6ULL machine through a modeled controller.
- [x] Confirm that U-Boot detects the controller and media after a cold boot.
- [x] Configure U-Boot to load Upsilon from the media into a staging address.
- [x] Verify that the staging range cannot overlap U-Boot, the linked native
  image, its heap/stack, or the framebuffer.
- [x] Verify the payload length before executing it.
- [x] Verify a payload checksum or cryptographic digest before executing it.
- [x] Replace the host-side `go 82000020` helper with a U-Boot boot command.
- [x] Remove QEMU generic-loader injection of the native payload from the
  normal end-to-end boot test.
- [x] Keep direct ELF boot as an explicitly named developer fast path.
- [x] Add a boot timeout and a clear UART failure message when the payload is
  missing, corrupt, or too large.
- [x] Provide a non-destructive U-Boot recovery prompt after boot failure.
- [x] Test a missing payload.
- [x] Test a truncated payload.
- [x] Test a payload with a deliberately incorrect checksum.
- [x] Test an ELF with an invalid or overlapping load segment.
- [x] Test 25 consecutive cold boots from the generated image.
- [x] Make the media build reproducible: identical inputs must produce the
  same payload contents and partition layout.

**P0.1 acceptance gate:** `run-native-vm.sh --u-boot` cold-boots Upsilon from
the attached media with no native-payload loader device and no helper typing a
`go` command. Corrupt-media tests must remain at a recoverable U-Boot prompt.

### P0.2 — persistent Ion storage and preferences

- [x] Choose whether the first persistent backend is a raw reserved partition,
  a small filesystem file, or a dedicated emulated block/NOR device.
- [x] Write a storage-format specification with magic, version, length,
  generation counter, and checksum fields.
- [x] Reserve two independent metadata/data copies for atomic updates.
- [x] Define maximum record count, name length, payload size, and total storage
  capacity.
- [x] Add a native block-storage abstraction below `Ion::Storage`.
- [x] Keep the existing RAM storage available as an explicit recovery mode.
- [x] Load valid records during startup before Upsilon opens the home screen.
- [x] Initialize empty storage to Upsilon defaults on the first boot.
- [x] Persist calculator variables and function definitions.
- [x] Persist Python scripts.
- [x] Persist lists, matrices, statistics data, and regression data.
- [x] Persist settings that Upsilon expects to survive reboot.
- [x] Decide whether calculation history should persist and document the
  decision.
- [x] Commit updates atomically so either the old or the new generation remains
  usable after interruption.
- [x] Flush controller and device caches before declaring a commit complete.
- [x] Reject corrupt metadata without reading outside the storage region.
- [x] Recover the newest valid generation when one copy is corrupt.
- [x] Fall back to empty/default storage when both copies are corrupt.
- [x] Preserve unknown compatible fields across a format upgrade.
- [x] Provide an intentional factory-reset operation.
- [x] Require a confirmation gesture for factory reset.
- [x] Provide a read-only rescue boot that never writes the storage medium.
- [x] Add capacity-boundary tests for zero-length, maximum-size, duplicate,
  rename, delete, and out-of-space operations.
- [x] Add fuzz tests for malformed metadata, record names, sizes, and checksums.
- [x] Add simulated power-loss tests at every storage commit phase.
- [x] Add reboot tests proving that records and preferences survive.
- [x] Add reset tests proving that factory reset restores compiled defaults.
- [x] Remove `PRIME_G2_READ_ONLY_STORAGE=1` only after all persistence tests
  pass.

**P0.2 acceptance gate:** create representative records and settings, stop the
VM without a graceful guest shutdown, restart it, and recover either the last
completed generation or the prior valid generation with no storage corruption.

### P0.3 — deterministic guest test protocol

- [x] Version the UART test/control protocol.
- [x] Use structured request identifiers so responses can be matched to
  commands.
- [x] Separate diagnostic log output from machine-readable test responses.
- [x] Add a command that reports firmware version, build ID, platform, and
  storage-format version.
- [x] Add a command that reports the active application and controller state.
- [x] Add a command that reports focused/selected rows, cells, or home apps.
- [x] Add a command that returns exact expression/result text for test builds.
- [x] Add commands for cold reset, warm reset, storage reset, and fault
  injection.
- [x] Add commands to advance or control virtual time deterministically.
- [x] Add a command to query key state and pending events.
- [x] Reject malformed, oversized, and unknown protocol commands safely.
- [x] Add protocol unit tests that do not require QEMU.
- [x] Add protocol integration tests through the VM UART.
- [x] Ensure protocol support can be disabled in release images.
- [x] Ensure test commands cannot alter physical production builds.

**P0.3 acceptance gate:** application tests can assert semantic guest state,
not only that two screenshots differ.

### P0.4 — complete keypad regression coverage

- [x] Create one source-of-truth table for HP key position, evdev code, Ion key,
  native KPP row/column, and test name.
- [x] Verify every digit key.
- [x] Verify decimal point, comma, EE, and parentheses.
- [x] Verify add, subtract, multiply, divide, and power.
- [x] Verify sine, cosine, tangent, logarithm, natural logarithm, and square.
- [x] Verify XNT, Var, Toolbox, Home, Back, Backspace, and OK.
- [x] Map and verify the Prime-only Symb, Plot, Num, Help, View, and Menu
  keys instead of silently dropping their matrix positions.
- [x] Verify all four D-pad directions.
- [x] Verify Shift and Alpha as modifiers.
- [x] Verify every printed blue Shift action, including Shift+5 brackets,
  braces, lists, matrices, roots, inverse functions, Delete/Clear,
  Copy/Paste, Eval, Memory, Setup, Program, Base, and Notes. Where Lefony has
  no separate HP application, route the key to the closest native facility
  (Graph, Code, Settings, or the math toolbox) without NumWorks launcher
  shortcuts leaking through.
- [x] Verify the HP Prime's complete printed Alpha layout: `A`–`Z`,
  Shift+Alpha uppercase, `#`, `:`, `\"`, `;`, and space. This includes the
  Units/C, fraction/E, and plus-minus/M matrix positions omitted by the
  original NumWorks-oriented mapping.
- [x] Verify modifier lock, clear, and cancellation behavior.
- [x] Verify a short press and release.
- [x] Verify a held key and key-repeat delay/rate.
- [x] Verify simultaneous key chords that Upsilon supports.
- [x] Verify rapid alternating keys without dropped releases.
- [x] Verify that an unknown key code changes no state.
- [x] Verify that reset during a held key does not leave a stuck key.
- [x] Verify the On/Off key separately from ordinary event handling.
- [x] Add a visual keyboard-map diagnostic available only in test builds.

**P0.4 acceptance gate:** the automated native-VM matrix test covers all 51
physical keys, exact Alpha and Shift legends, every supported modifier
combination, and lifecycle/repeat behavior without a stuck, duplicated, or
dropped event.

### P0.5 — application launch and core workflow suite

The complete pinned upstream unit binary supplies engine/controller evidence
for checked computational items below; the native VM separately proves that
every enabled snapshot launches and processes events. Items that explicitly
require editing, navigation, rendering, or persistence remain unchecked until
that workflow is driven end to end through the native UI.

#### Home and shared UI

- [x] Verify the exact default home ordering and initially selected app.
- [x] Navigate to every home application with D-pad input.
- [x] Open every enabled application and return Home.
- [x] Verify title bar, angle mode, calibrated battery percentage/state, and
  clock region.
- [ ] Verify modal dialogs, pop-ups, list scrolling, tabs, and breadcrumbs.
- [ ] Verify text fields, cursor motion, selection, cut/copy/paste policy, and
  deletion.
- [ ] Verify Shift/Alpha indicators and modifier clearing.
- [ ] Verify low-memory error paths without crashing.

#### Calculation

- [x] Verify basic integer addition (`1+2=3`).
- [x] Verify subtraction, multiplication, division, powers, roots, and
  parentheses.
- [x] Verify exact and approximate results.
- [x] Verify fractions, mixed signs, scientific notation, and complex values.
- [x] Verify degree, radian, and gradian trigonometry.
- [ ] Verify undefined, overflow, syntax-error, and domain-error results.
- [ ] Verify calculation-history navigation and deletion.
- [x] Verify Ans and variable substitution.

#### Functions and Graph

- [ ] Create, edit, enable, disable, rename, and delete a function.
- [ ] Plot Cartesian, polar, and parametric functions supported by the build.
- [ ] Verify axes, grid, labels, zoom, pan, trace, and automatic range.
- [ ] Verify intersections, roots, extrema, tangents, and integrals.
- [ ] Verify discontinuities and values outside the visible range.
- [ ] Verify graph rendering after repeated application switching.

#### Python

- [ ] Open the script list and console.
- [ ] Create, edit, rename, execute, and delete a script.
- [ ] Verify indentation, syntax highlighting, autocomplete, and history.
- [ ] Verify arithmetic, loops, functions, imports, exceptions, and interrupts.
- [ ] Verify output scrolling and long-line behavior.
- [x] Verify script persistence after reboot.
- [ ] Verify memory exhaustion produces a controlled error.

#### Statistics and Regression

- [ ] Enter and edit one-variable and two-variable data.
- [ ] Verify table navigation, column formulas, sorting, and clearing.
- [x] Verify summary statistics and expected rounding.
- [ ] Verify histograms, box plots, scatter plots, and regression curves.
- [x] Verify each supported regression model.
- [ ] Verify empty, singular, and invalid datasets.
- [x] Verify dataset persistence after reboot.

#### Probability

- [ ] Exercise every included distribution.
- [ ] Verify parameter editing and validation.
- [ ] Verify left-tail, interval, and right-tail calculations.
- [ ] Verify graph shading and numerical results.
- [ ] Verify extreme probabilities and invalid parameter boundaries.

#### Solver

- [x] Solve linear, polynomial, and supported nonlinear equations.
- [x] Verify real, complex, exact, and approximate solutions.
- [x] Verify no-solution, infinite-solution, and invalid-equation cases.
- [ ] Verify interval/root-guess editing and navigation.

#### Sequences

- [x] Create explicit and recursive sequences.
- [x] Verify initial conditions and index bounds.
- [ ] Verify value tables and plots.
- [x] Verify undefined and recursive-dependency errors.
- [ ] Verify sequence persistence after reboot.

#### RPN

- [ ] Verify stack entry, lift, drop, swap, clear, and undo behavior.
- [ ] Verify arithmetic, functions, complex values, and stack overflow handling.
- [ ] Verify switching between RPN and standard Calculation safely.

#### Atomic

- [ ] Navigate the periodic table with keys.
- [ ] Verify element details, search, labels, and scrolling.
- [ ] Verify the app does not allocate or retain unbounded memory.

#### Settings

- [ ] Verify language and country selection.
- [ ] Verify angle, display, complex, and significant-digit preferences.
- [ ] Verify brightness controls and shortcuts.
- [x] Verify font and editor preferences included by Upsilon.
- [ ] Verify idle dim and suspend settings.
- [x] Verify preferences survive reboot after persistence is enabled.
- [x] Verify factory reset restores every default.

#### Optional upstream applications

- [x] Decide whether Reader is part of the supported native product.
- [x] Decide whether External apps are part of the supported native product.
- [x] Document excluded applications and the technical or licensing reason.
- [ ] If enabled, add storage, loading, sandboxing, crash isolation, and
  application-specific tests before release.

**P0.5 acceptance gate:** every enabled home application has at least one
automated launch test and one representative end-to-end workflow, with no
abort, exception, or framebuffer corruption.

### P0.6 — automated test runner and CI readiness

- [x] Split smoke, application, storage, fault, and long-run tests into named
  suites.
- [x] Allow every suite to run headlessly.
- [x] Give every test a bounded timeout and useful failure diagnostics.
- [x] Capture UART, QEMU diagnostics, guest state, and framebuffer on failure.
- [x] Save the exact build IDs and commands used for each test run.
- [x] Prevent parallel test runs from sharing sockets or media images.
- [x] Start each destructive storage test from a private media copy.
- [x] Make framebuffer comparisons tolerant only where virtual time changes.
- [x] Mask or control the clock/battery regions for deterministic screenshots.
- [x] Add a clean-build test for both `prime_g2` and `prime_g2_vm`.
- [x] Add a U-Boot build test using the pinned revision.
- [x] Add an emulator cold-boot smoke test to CI.
- [x] Add application tests to CI in dependency-based groups.
- [x] Add storage corruption and recovery tests to CI.
- [x] Publish compact failure artifacts without committing generated images.
- [x] Ensure all emulator processes are reaped after success, failure, timeout,
  or interruption.

**P0.6 acceptance gate:** a clean checkout can build and run the complete P0
suite with one documented command and no physical calculator.

## P1 — native correctness and reliability

### P1.1 — exception handling and diagnostics

- [x] Give undefined, SVC, prefetch-abort, data-abort, IRQ, and FIQ distinct
  vector handlers.
- [x] Preserve registers before diagnostic code modifies them.
- [x] Report exception type, PC, LR, SP, CPSR, fault address, and fault status
  over UART.
- [x] Detect and report recursive faults in the exception reporter.
- [x] Draw a minimal crash screen when LCDIF remains usable.
- [x] Add a deterministic test trigger for every exception class that can be
  safely generated.
- [x] Decide and document whether release builds halt, reset, or return to
  U-Boot after a fatal exception.
- [x] Add a crash counter or reason record without risking storage corruption.

### P1.2 — MMU, caches, and memory protection

- [x] Document the complete physical and virtual memory map.
- [x] Create first-level translation tables with explicit attributes.
- [x] Map executable code read-only where practical.
- [x] Map data/heap/stack read-write and non-executable where supported.
- [x] Map peripheral registers as strongly ordered/device memory.
- [x] Map framebuffer memory with attributes compatible with LCDIF DMA.
- [x] Enable branch prediction, instruction cache, data cache, and MMU in a
  controlled startup sequence.
- [x] Add cache clean/invalidate operations for DMA-visible framebuffer and
  storage buffers.
- [x] Add required barriers around peripheral and DMA ownership changes.
- [x] Add stack guard regions or canaries.
- [x] Track maximum stack and heap usage during the application suite.
- [x] Add allocator exhaustion and fragmentation tests.
- [x] Test warm reboot after caches and MMU have been enabled.

### P1.3 — interrupts and timing

- [x] Initialize the Cortex-A7 GIC distributor and CPU interface.
- [x] Add a safe IRQ registration/dispatch layer.
- [x] Add spurious and unhandled interrupt diagnostics.
- [x] Convert the monotonic timer to an interrupt-backed design or prove that
  polling meets all Upsilon timing requirements.
- [x] Convert keypad wake/event detection to interrupts while retaining a
  debounced scan.
- [x] Add interrupt-safe synchronization around shared input state.
- [x] Test 32-bit GPT rollover explicitly.
- [x] Test millisecond monotonicity for at least two rollover intervals in
  accelerated virtual time.
- [ ] Verify delays at multiple CPU/bus clock configurations.
- [x] Define and test the behavior of timers across suspend/resume.
- [x] Add event-loop latency and missed-frame measurements.

### P1.4 — display correctness

- [x] Document LCDIF timing, bus width, pixel format, clock tree, and panel
  initialization values with their hardware sources.
- [x] Verify RGB565-to-XRGB8888 conversion exhaustively.
- [x] Verify black, white, primary colors, grayscale, and gradients.
- [x] Add bounds assertions or clipping tests for every display rectangle API.
- [x] Implement a meaningful `waitForVBlank()`.
- [x] Decide whether single buffering is sufficient or implement safe double
  buffering.
- [x] Detect and recover from LCDIF underflow; verify a modeled underflow
  raises LCDIF status, blanks one scanout, and restores the next scanout.
- [x] Detect a stopped pixel clock or DMA engine.
- [x] Verify frame output after warm reboot and suspend/resume.
- [x] Implement and test brightness updates across the full supported range.
- [x] Test dimming, restore, minimum visible level, and backlight shutdown.
- [x] Eliminate cold-boot artifacts by clearing the framebuffer to black,
  keeping PWM7 and the backlight-enable pin optically gated through redundant
  upstream initialization, and revealing only after the first complete window
  redraw plus one panel scan interval. Keep colored milestone squares opt-in.
- [x] Measure redraw rate for representative home/list/application output; keep
  graph and Python microprofiles in the release-candidate performance pass.
- [x] Add framebuffer-integrity guards around its reserved memory region.
- [x] Enforce the Prime G2 LCD IOMUXC mux and pad-control values in QEMU.
- [x] Enforce pixel-clock, sync/porch, polarity, digital-edge, and panel
  power/reset timing limits with independent fault injection.
- [ ] Measure pixel-clock/data rise and fall time, voltage levels, ringing,
  setup/hold margin, and polarity on the physical panel interface. **Physical
  gate; digital QEMU timing does not prove analog signal integrity.**
- [ ] Complete a physical-panel color, timing, tearing, and reset test.
  **Physical gate.**

### P1.5 — touchscreen and pointer semantics

- [x] Decide whether native Upsilon will be key-only or expose Prime touch as a
  supported first-class input method.
- [x] If touch is supported, define the Ion-facing event/gesture contract.
- [x] Preserve actual tap coordinates, release coordinates, duration, and
  sequence instead of converting every tap blindly to OK.
- [x] Define the supported navigation hit zones for Back, Home, Left, Right,
  and OK; arbitrary widget-level pointer dispatch is explicitly unsupported.
- [x] Define tap, hold, swipe, release, and cancellation thresholds; continuous
  drag/drawing and multitouch are explicitly unsupported.
- [x] Reject out-of-range coordinates and multi-contact reports.
- [ ] Add orientation and coordinate-calibration support.
- [x] Add multi-report gesture sequencing and release semantics.
- [x] Verify that simultaneous keypad and touch input cannot leave stuck state.
- [x] Add deterministic touch tests for every advertised navigation pattern.
- [x] Implement the native I2C/GPIO touchscreen driver. **Physical gate unless
  its device model is completed first.**
- [ ] Validate the Goodix/Ilitek model and exact controller variant on target
  hardware. **Physical gate.**

### P1.6 — power button, suspend, resume, and shutdown

- [x] Replace the dummy `Ion::Power` implementation.
- [x] Define and test short-press suspend/wake, 2-second orderly off, and
  8-second forced-off behavior.
- [x] Ensure On/Off cannot be confused with an ordinary calculator key.
- [x] Stop or quiesce LCDIF before deep suspend where required.
- [x] Dim and disable the backlight in the correct order.
- [x] Flush persistent storage before entering a power state that can lose RAM.
- [x] Route normal suspend wake through both the SNVS power-button interrupt
  and the PF1550 GPIO5 interrupt, with WFI instead of ON-key polling.
- [x] Put ILI9322 into display-off/standby before stopping LCDIF, force PWM7
  duty/output and its enable GPIO low, and reverse the sequence after wake.
- [x] Configure PF1550 PWRON reset/restart, ONKEY reset, and CORE_OFF wake
  controls before the non-returning SNVS `TOP` full-shutdown command.
- [x] Configure and read-back verify the LCD's PF1550 LDO1 supply at 3.3 V
  before panel reset, including a battery-cold emulator start with the rail
  initially disabled.
- [x] Preserve RAM and reconstruct display, panel, backlight, USB, touch, and
  modeled regulator state after resume.
- [x] Reinitialize the panel without erasing the retained framebuffer.
- [x] Keep monotonic time advancing across modeled suspend and document it.
- [x] Add rapid suspend/resume and repeated On/Off tests.
- [x] Add suspend during storage activity tests.
- [x] Add suspend from every enabled application.
- [x] Add idle-dimming and idle-suspend tests using virtual time.
- [x] Model battery drain, regulator/power-domain state, and suspend/resume
  energy transitions in QEMU.
- [ ] Measure normal-suspend current and validate both SNVS and PF1550 wake
  sources plus full rail-off/reboot on the target. **Physical gate.**

### P1.7 — watchdog and recovery behavior

- [x] Decide which i.MX watchdog instance is owned by native Upsilon.
- [x] Start the watchdog only after clocks and diagnostics are ready.
- [x] Feed it from a health-checked event-loop path, not an unconditional timer.
- [x] Preserve a watchdog reset reason for the next boot.
- [x] Test event-loop deadlock, IRQ storm, and deliberate infinite-loop resets.
- [x] Ensure repeated crashes fall back to U-Boot or a read-only recovery mode.
- [x] Ensure watchdog reset cannot interrupt storage commits indefinitely.

## P2 — Prime hardware and emulator fidelity

These tasks are required before emulator success can be treated as proof of a
complete HP Prime G2 port. The physical Linux evidence, exact DTB, decoded
keypad matrix, and live register snapshots are maintained in
`hardware/prime_g2/`; `hardware/prime_g2/EMULATOR-PARITY.md` is the detailed
component-by-component implementation ledger.

### P2.1 — Prime-specific QEMU machine definition

- [ ] Decide whether to extend `mcimx6ul-evk` or add a distinct HP Prime G2
  QEMU machine.
- [ ] Encode the Prime's RAM size, memory map, interrupt routing, clocks, and
  attached devices in the machine definition.
- [ ] Add a maintained machine-level test that instantiates every modeled
  device.
- [ ] Keep the machine model compatible with repository-pinned QEMU versions.
- [ ] Document every register or electrical behavior that remains substituted.
- [ ] Remove VM substitutions from native Upsilon as corresponding device
  models become available.

### P2.2 — KPP keypad model

- [x] Model KPP row/column registers used by the native driver.
- [x] Model matrix scanning and active row/column electrical behavior.
- [x] Model status bits, scan-settle behavior, and interrupt delivery.
- [x] Connect host key/control commands to matrix positions, not Ion key codes.
- [x] Test ghosting and rollover behavior expected from the real matrix.
- [x] Run the same native KPP scan routine in the VM and physical build.
- [ ] Validate KPP debounce timing and IRQ wake behavior on hardware.
  **Physical gate.**
- [x] Remove the UART keypad-state VM substitute.

### P2.3 — touchscreen controller model

- [x] Identify the fitted controller: live Linux reports Goodix ID 5688,
  version 0200 at I2C1 address `0x14` (the DT's `goodix,gt928` declaration is
  not the fitted-silicon identity).
- [x] Document the captured GT5688 identity/firmware and report protocol
  behavior in `docs/LEFONY-NATIVE-TOUCH.md`.
- [x] Model its I2C address, identification, configuration, coordinate reports,
  interrupt GPIO, and reset GPIO.
- [x] Connect host tap/drag/swipe commands to controller reports.
- [x] Test reset, missing-device, malformed-report, and interrupt-loss paths.
- [x] Run the same native touchscreen driver implementation in the QEMU and
  physical builds.
- [ ] Validate that driver and its calibration on hardware. **Physical gate.**
- [x] Remove the UART gesture VM substitute.

### P2.4 — LCD panel and backlight models

- [x] Model or extend LCDIF support for the Prime's serialized 8-bit RGB path.
- [x] Model the ILI9322 control interface and register initialization.
- [x] Model panel reset, blanking, and invalid initialization sequences.
- [x] Model PWM7 duty cycle and panel/backlight supply enable.
- [x] Expose brightness changes in emulator diagnostics and PWM register state.
- [x] Run identical LCDIF/panel/backlight code in QEMU and on hardware.
- [x] Remove the parallel-LCDIF and backlight no-op VM substitutions.

### P2.5 — PF1550, battery, charger, and on-key

- [x] Document the PF1550 bus/address, declared regulators, charger, interrupt,
  and on-key topology from the exact DTB and live driver bindings.
- [x] Capture and document the separate PF1550 status and i.MX6ULL ADC paths in
  `hardware/prime_g2/BATTERY-CHARGER.md`, including shipping-firmware ADC
  initialization, conversion, filtering, and percentage thresholds.
- [x] Replace the dummy battery implementation with a native service.
- [x] Explicitly enable PF1550 `CHG_OPER` battery mode 2 at cold boot and verify
  it without overwriting OTP charge-current, voltage, thermal, or input limits.
- [x] Report PF1550 external-power, active-charge, complete, present, and fault
  dimensions independently.
- [x] Implement HP's ADC1_IN1 voltage conversion, ten-sample trimmed mean,
  five-level 0/25/50/75/100 estimate, critical threshold, and 30-second hold.
- [ ] Validate ADC voltage and displayed level against a meter across load,
  charging, temperature, and aging. **Physical gate; this is a voltage-derived
  estimate, not a coulomb-counted 1% state of charge.**
- [x] Clamp and filter telemetry values safely.
- [x] Handle missing or faulting power-controller communication.
- [x] Implement charger plug/unplug polling and UI state changes.
- [x] Implement low-battery warning and orderly shutdown policy.
- [x] Model PF1550 reset mode 1, guest mode-2 enable, independent VBUS/charge
  state, and ADC1 conversion/calibration behavior in QEMU.
- [ ] Validate regulator, charger, and on-key behavior. **Physical gate.**

### P2.6 — RTC

- [x] Identify the authoritative Prime RTC source (the i.MX6ULL SNVS LP secure
  RTC counter captured in the Prime device tree).
- [x] Replace the fixed dummy date/time.
- [x] Read, validate, and set date/time.
- [x] Define timezone policy; store only what the hardware/OS can represent.
- [ ] Handle oscillator loss and invalid RTC contents.
- [x] Test leap years, month boundaries, and invalid values.
- [ ] Preserve time across reset and power loss. **Physical gate.**
- [x] Add a deterministic virtual RTC mode for screenshot tests.

### P2.7 — LED and exam mode

- [ ] Identify the Prime indicator hardware available to native Upsilon.
- [x] Replace dummy LED color and blink functions or document an intentional
  hardware limitation.
- [ ] Define exam-mode persistence independently of ordinary user storage.
- [ ] Make exam-mode state resistant to ordinary reset and storage deletion as
  required by the chosen policy.
- [ ] Verify exam restrictions in every affected application.
- [ ] Verify indication across boot, suspend, charging, and fault states.
- [ ] Complete policy/compliance review before calling exam mode supported.

### P2.8 — USB device, transfer, and DFU/recovery

- [x] Document the i.MX USB controller instance, PHY, clocks, pins, and VBUS
  detection used by the Prime.
- [x] Replace the dummy `Ion::USB` implementation.
- [x] Detect cable insertion and removal.
- [x] Enumerate reliably after cold boot and reconnect in the modeled bus.
- [x] Explicitly leave ordinary calculator record transfer unsupported for the
  first native release; the versioned recovery/diagnostic protocol is the only
  advertised vendor interface.
- [x] Define a native update/recovery protocol separate from normal record
  transfer.
- [x] Ensure a malformed host packet cannot write outside staging storage.
- [x] Authenticate or checksum update payloads according to the release threat
  model.
- [x] Keep ROM SDP or U-Boot recovery reachable even when native USB is broken;
  neither recovery path depends on the native driver or its storage state.
- [x] Model USBOTG controller/endpoint/PHY behavior sufficiently to enumerate
  the native guest over an emulated USB bus, including reset, address,
  configuration, disconnect, reconnect, suspend, and malformed transfers.
- [x] Run automated native recovery enumeration and capsule-transfer tests over
  that emulated USB bus; maintain a mandatory physical USB suite until it is
  complete.
- [ ] Test macOS, Linux, and Windows hosts where product support requires them.
  **Physical gate.**

### P2.9 — NAND/GPMI/BCH and permanent installation

- [ ] Preserve and document a verified full stock NAND backup before any write.
- [x] Document NAND geometry, bad-block handling, ECC layout, partitions, and
  U-Boot expectations.
- [x] Keep the first native release on the verified alternate boot medium;
  permanent NAND remains a separately authorized physical migration because
  the captured stock UBI layout has no safe second slot.
- [x] Defer a production GPMI/BCH writer while NAND installation is gated;
  U-Boot remains the only proposed NAND reader/writer for future migration.
- [x] Never assume erased NAND reads as a stable filesystem abstraction.
- [x] Respect factory bad blocks and newly discovered bad blocks.
- [x] Use redundant metadata and boot slots in the emulator A/B layout.
- [x] Add image-size and partition-overlap guards.
- [x] Add power-loss simulation at every erase/write transition.
- [x] Add bad-block injection and skip/failure tests.
- [x] Model BCH corrected and uncorrectable bit errors and inject them at page,
  OOB, and metadata boundaries.
- [x] Bound partial-page programs and model deterministic erase wear promotion,
  read disturb, retention-style bit faults, corrected/uncorrectable BCH status,
  and bad-block behavior; this remains a fault model, not flash-lifetime proof.
- [x] Add rollback after a corrupt or incomplete update.
- [x] Model page program/read, erase, erased state, bad blocks, and persistent
  GPMI/BCH/NAND state in QEMU; keep the production ECC and physical layout
  migration risk explicitly documented.
- [x] Prove in the emulator manager that a corrupt pending slot rolls back, an
  invalid active slot selects the other verified slot, and two invalid slots
  select read-only rescue.
- [ ] Repeat both-invalid-slot recovery on the final physical layout before
  enabling permanent installation. **Physical gate.**
- [ ] Require a separate explicit user action for the first destructive NAND
  installation. **Physical gate.**

### P2.10 — board identity and remaining Ion services

- [x] Replace dummy serial number with the appropriate hardware-derived value
  or a documented privacy-preserving alternative.
- [ ] Replace dummy PCB version with a validated board revision source.
- [x] Replace dummy FCC ID only if Upsilon actually requires it; otherwise
  document the fixed informational value.
- [x] Implement real stack-bound checking rather than always returning safe.
- [x] Implement console input if required for recovery/debugging.
- [x] Implement clipboard semantics or explicitly disable clipboard-dependent
  features.
- [ ] Audit every Ion API linked by the native build for dummy, stub, constant,
  or silently ignored behavior.
- [ ] Fail clearly for unsupported APIs instead of pretending success where
  silent behavior could lose data.

## P3 — release readiness and long-term maintenance

### P3.1 — update and rollback system

- [ ] Define a versioned native firmware package format.
- [ ] Include product, hardware revision, payload length, load requirements,
  format version, and digest in the manifest.
- [ ] Decide whether releases require signatures and document key management.
- [ ] Use A/B payload slots or an equivalently recoverable update design.
- [ ] Never overwrite the known-good slot before the new slot verifies.
- [ ] Mark a new slot successful only after Upsilon reaches a health checkpoint.
- [ ] Roll back automatically after repeated boot failures.
- [ ] Preserve user storage across compatible firmware updates.
- [ ] Provide explicit migration and rollback rules for incompatible storage
  formats.
- [ ] Add interrupted-download, interrupted-write, corrupt-manifest, wrong-board,
  downgrade, and rollback tests.

### P3.2 — security and robustness review

- [ ] Define the threat model for local records, USB updates, external apps,
  debug UART, and test protocol.
- [x] Disable or restrict emulator/debug control commands in release builds.
- [x] Validate all lengths, addresses, record names, and protocol state before
  memory access.
- [ ] Add compiler warnings-as-errors for native platform code where practical.
- [ ] Enable stack protection and other compatible hardening options, measuring
  their cost.
- [ ] Audit integer overflow in timers, storage offsets, framebuffer math, and
  package parsing.
- [x] Fuzz storage, update, USB, and test-protocol parsers.
- [ ] Document whether secure boot is supported, unsupported, or out of scope.
- [ ] Perform a focused third-party review before a permanent-install release.

### P3.3 — performance and resource budgets

- [ ] Establish cold-boot-to-home, warm-boot, app-open, redraw, calculation,
  Python-start, and graph-render budgets.
- [x] Measure code, mutable data, heap, stack, and framebuffer
  sizes for every release.
- [x] Fail the build when linked regions overlap or exceed agreed budgets.
- [x] Profile expensive display conversion and redraw paths.
- [x] Measure key-to-frame and touch-to-frame latency.
- [x] Measure storage commit latency and worst-case recovery time.
- [x] Run application-switch and calculation loops to detect leaks.
- [x] Run a minimum 24-hour accelerated-virtual-time emulator soak with
  scripted activity. This is 24 modeled hours, not a 24-hour wall-clock claim.
- [ ] Run a minimum 24-hour physical soak before stable release. **Physical
  gate.**

### P3.4 — release test matrix

- [ ] Clean build on every supported development host architecture.
- [x] Direct-ELF developer boot test.
- [x] U-Boot media cold-boot test.
- [x] Default-state first-boot test.
- [x] Persistent-state reboot test.
- [x] Factory-reset test.
- [x] Full key and modifier test.
- [x] Full touch test if touch is supported.
- [x] Every-application representative workflow suite.
- [x] Suspend/resume and power-button suite.
- [x] Storage corruption and power-loss suite.
- [x] Update, rollback, and recovery suite in the emulator A/B layout.
- [x] USB enumeration/transfer/update suite on the modeled USB bus.
- [x] Watchdog and exception suite.
- [x] Performance-budget test.
- [x] Accelerated 24-hour virtual-time emulator soak test.
- [ ] Physical smoke, peripheral, recovery, and soak suites. **Physical gate.**
- [x] Record the exact source revisions, toolchain, test results, and known
  limitations for each release candidate.

### P3.5 — documentation and developer experience

- [x] Keep a one-command clean native VM build documented.
- [x] Keep a one-command complete native VM test documented.
- [x] Document all required host dependencies and tested versions.
- [x] Document the native memory map and linker layout.
- [x] Document U-Boot environment, media layout, and fallback behavior.
- [x] Document the Ion platform architecture and ownership of each service.
- [x] Document the VM substitutions and their hardware-parity implications.
- [x] Document storage format, reset, backup, and migration behavior.
- [x] Document how to collect UART, QEMU, framebuffer, and crash diagnostics.
- [x] Document how to add a new key, gesture, application test, and device model.
- [x] Document safe physical bring-up without NAND writes.
- [x] Document permanent installation only after its recovery gates pass.
- [x] Maintain a known-issues section with severity and workaround.
- [x] Keep this checklist synchronized with implementation changes.

### P3.6 — licensing, attribution, and distribution

- [x] Confirm the pinned Upsilon license and all linked component licenses for
  the intended distribution model.
- [ ] Preserve required Upsilon/Epsilon attribution and source notices.
- [ ] Preserve U-Boot, QEMU, toolchain, library, font, icon, and third-party
  notices as required.
- [x] Document the non-commercial or redistribution restrictions that apply to
  the selected Upsilon revision.
- [x] Ensure no HP or NumWorks proprietary firmware dump, key, or copyrighted
  binary is required or redistributed without permission.
- [ ] Provide corresponding source and modifications where licenses require it.
- [x] Generate a software bill of materials for release artifacts.
- [ ] Review product names, logos, and trademarks used in release packaging.

## Final definition of done

The full port is complete only when all applicable items above are checked and
the following statements are true:

- [x] A clean generated upstream checkout reproducibly builds U-Boot, native
  Upsilon, and a complete
  bootable media image.
- [x] QEMU cold-boots that media through U-Boot to the normal Upsilon home screen
  without preloading the payload or typing a host-assisted jump command.
- [x] Every shipped application completes its automated representative workflows.
- [x] Every supported key, modifier, repeat, chord, and touch action behaves
  deterministically.
- [x] User records and preferences persist atomically across reset and simulated
  power loss, and corrupt storage recovers safely.
- [x] Display, timing, suspend/resume, watchdog, exception, and memory-protection
  tests pass.
- [ ] No shipped feature relies on an unexplained dummy Ion implementation.
- [ ] Unsupported hardware features are visibly disabled and documented rather
  than silently reporting success.
- [ ] The emulator runs the physical driver paths for every Prime device claimed
  as hardware-validated, or the remaining physical-only gates are explicitly
  completed.
- [x] Recovery remains available after a missing, corrupt, or interrupted native
  image/update.
- [ ] The complete automated suite passes from a clean build, followed by the
  required emulator and physical soak tests.
- [ ] Release documentation accurately describes capabilities, limitations,
  licenses, installation risk, backup, recovery, update, and rollback.

## Immediate next execution sequence

The nine emulator-solvable work packages requested for this phase are complete:
KPP input, USB OTG, power/RTC, Goodix touch, NAND/U-Boot recovery, GIC/MMU/cache,
watchdog, representative native UI workflows for every enabled application,
and fuzz/performance/soak/documentation coverage. The next work necessarily
separates physical validation from later release/product scope:

1. Capture and compare PF1550, SNVS, RTC, battery, Goodix, KPP, LCDIF, and USB
   traces on a recoverable calculator; keep every electrical or calibration
   claim gated until the traces agree.
2. Validate physical KPP debounce, touch mapping, suspend/resume, wake sources,
   RTC retention, battery calibration, backlight behavior, and measured current.
3. Exercise physical USB recovery and runtime enumeration against macOS, Linux,
   and Windows hosts, including disconnect, malformed transfer, and suspend.
4. Back up the full device, confirm its NAND/UBI/eraseblock layout, and validate
   ECC, interrupted update, A/B rollback, and rescue before any permanent write.
5. Run physical smoke, peripheral, recovery, and 24-hour soak suites.
6. Complete the remaining unchecked release scope: hardening review, migration
   policy, multi-host builds, attribution/source packaging, and trademark review.
