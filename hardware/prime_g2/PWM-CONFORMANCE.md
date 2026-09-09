# PWM7 FIFO and interrupt conformance work

Status: **nominal FIFO, compare/rollover interrupts and 32-bit sample swapping
implemented through r61;
physical parity unverified**.
Capacity, overflow, read-only occupancy, W1C access, period-boundary sample
consumption, repeats, reset and migration are modeled. FIFO watermark,
output waveform and exact silicon
update edges remain incomplete.

## r60 timed events

Compare and rollover latch status even when masked. Enabled events have a
virtual-clock deadline and drive a separate PWM IRQ without software polling.
Late enable, selective W1C, gate pauses, reset and active/pending/gated
migration are covered. The timer deadline and output are derived on load
from saved register, clock and phase state. Twelve tests in
`vm/test-prime-g2-pwm-irq.py` pass, including observation at GIC SPI input 116.

That routing test is not CPU interrupt-handler qualification. An initial
acknowledge/EOI audit failed because qtest's non-secure MMIO cannot configure
the GIC's reset Group0 interrupts or priority mask. Its failed evidence is
preserved under `build/prime-g2-emulator-qualification/r60-gic-nonsecure-audit-20260907/`.
The replacement routing test observes the actual GIC input without disabling
security extensions. A separate `vm/test-prime-g2-pwm-cpu-irq.py` now executes
a small secure ARM-state program under TCG: it configures the real GIC,
receives architectural ID 148, enters the IRQ vector, clears PWM, performs
EOI and returns to the interrupted supervisor-mode program. It passes with
the unchanged r60 binary. This nominal integration check does not establish
latency or physical clock accuracy. FE watermark latch/reassertion behavior,
physical event edges and output waveforms remain separate open requirements.

## Evidence and scope

### Follow-up watermark and sample-order audits

The r60 watermark audit (`vm/test-prime-g2-pwm-watermark.py`) fails all eight
cases: four empty-slot thresholds, with IRQ enabled or masked. FIFO occupancy
drains correctly, but FE and its IRQ never assert. Audit evidence is under
`build/prime-g2-emulator-qualification/r60-pwm-watermark-audit-20260907/`.
The test does not prescribe W1C reassertion or first-enable/reset behavior.
The available SDK and firmware guide establish thresholds and clearing,
but are not sufficient to settle those edge semantics. No invented latch
policy has been added merely to turn the threshold test green.

The sample-order audit (`vm/test-prime-g2-pwm-swap.py`) passes only the two
no-swap cases in r60. All six cases with HCTR, BCTR or both fail: writes are
discarded, leaving the queue empty. Evidence is under
`build/prime-g2-emulator-qualification/r60-pwm-swap-audit-20260907/`.
The implementation work uses HCTR bit 20 and BCTR bit 21, as defined by the
[Linux driver](https://github.com/torvalds/linux/blob/master/drivers/pwm/pwm-imx27.c).
The [NXP SDK](https://mcuxpresso.nxp.com/api_doc/dev/1244/group__pwm__driver.html)
defines half-word swapping on the write bus and byte swapping on the
16-bit FIFO input. Tests cover aligned 32-bit writes only: transformed
samples must remain unchanged when control bits change after insertion,
including across migration. Narrow MMIO accesses remain unqualified.

r61 corrects the sample path. HCTR selects the upper rather than lower
16 bus bits; BCTR reverses the selected two bytes before FIFO insertion.
Overflow still rejects the new sample and latches FWE. All eight swap tests
pass, including all four combinations through migration and post-insertion
control changes. This does not resolve the separate watermark audit.


[NXP's PWM SDK reference](https://mcuxpresso.nxp.com/api_doc/dev/4162/a00131.html)
distinguishes occupied FIFO entries from its empty-slot watermark. Capacity
is four samples; repeat settings use each sample 1/2/4/8 times. Status bits
are FE=3, ROV=4, CMP=5 and FWE=6; interrupt enables are FE=0, ROV=1 and
CMP=2. FWE records a write attempted while full. Watermark encodings 0..3
mean at least 1..4 empty slots, respectively. These shared-IP definitions
still need a physical i.MX6ULL differential.

The local calculator Linux 4.14 `drivers/pwm/pwm-imx.c` waits when FIFOAV
equals four and resets the FIFO before enabling a previously disabled PWM.
The [current Linux driver](https://github.com/torvalds/linux/blob/master/drivers/pwm/pwm-imx27.c)
also distinguishes disabled sample readback and includes an ERR051198
empty-FIFO update workaround. A read of PWMSAR must not be assumed to mean
the last bus write in every state.

The [i.MX6ULL errata PDF](https://www.nxp.com/docs/en/errata/IMX6ULLCE.pdf)
retrieved for this audit identifies itself as revision 2, October 2019, and
does not list PWM or ERR051198. That absence does **not** prove the silicon
is unaffected. Do not automatically copy another chip's glitch behavior,
or assume an idealized period-boundary update is the exact Prime behavior.

## Reproduced r58 failures

`vm/test-prime-g2-pwm-fifo.py` keeps the peripheral gate open, enables PWM
with its counter source disconnected, and performs no virtual clock steps.
This isolates bus-side occupancy and access semantics from uncertain FIFO
consumption timing.

| Contract | Expected | Observed r58 |
| --- | --- | --- |
| Four sample writes | Occupancy 1, 2, 3, 4 | Always zero |
| Fifth write to full FIFO | Count stays four, FWE set | Zero status |
| Write FIFOAV bits | Occupancy unchanged | Becomes seven |
| Write ones to W1C flags | No new events created | Flags become set |

The JSON audit is saved under
`build/prime-g2-emulator-qualification/r58-pwm-fifo-audit-20260907/`.
Audit mode records failures and exits normally; ordinary test mode fails.
Neither a completed audit nor prior green boot suites establish FIFO parity.

## Implementation and proof requirements

The r59 tests cover four access/occupancy contracts plus consumption, clock
gating, reset, migration and ring refill for all four repeat counts. The
active sample is separate from queued samples; overflow discards the new
write and latches FWE. First consumption is provisionally at a period
boundary. This is a nominal timing model, not proof of the first-enable or
empty-FIFO silicon behavior. r61 subsequently adds the aligned 32-bit swap
path described above. Remaining requirements follow.

Maintain separate queued samples, active compare sample, repeat progress,
counter/phase, status and IRQ state. A four-word queue cannot be replaced
by a last-written-value register. Overflow must not silently replace a
queued value. Define 16/32-bit access and swap controls from register-level
evidence before claiming those cases.

Consume samples through counter events, not host render calls or status
reads. Account for multiple elapsed periods, periods with an empty queue,
clock gating, repeat progress and zero/maximum sample values. Preserve the
queue and active sample independently across migration. Reset must clear
the FIFO and pending events without a later stale callback.

Schedule compare/rollover and FIFO watermark events even when masked; wire
the derived PWM IRQ separately from LCDIF IRQ to GIC SPI 116, as specified
by the existing i.MX6UL board definitions. Test masking, late enabling,
selective acknowledgement, overflow, reset and migration. Establish the
watermark's latch/reassertion rules before treating FE as a generic sticky
edge or level flag.

Finally observe the output pin for normal/inverted/disconnected modes,
first enable, FIFO exhaustion, mid-period writes, gate changes and disable.
Only then connect the resulting waveform/average optical output to the
backlight. Test boot and repeated brightness changes, not merely a nonblank
first frame. Physical electrical timing and empty-FIFO erratum applicability
remain independent qualification gates.
