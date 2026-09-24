# Foreground execution architecture proof

This is an R0 emulator experiment for the [SDK 1.0 plan](NATIVE-APP-SDK-1.0-PLAN.md),
not a released execution ABI. It keeps the ABI 1 linker, package grammar and
memory limits. Neither experimental service is accepted by physical firmware.
The public discovery feature bits remain unchanged. It is deliberately absent
from the public SDK headers, templates and website publisher.

## Design under test

An application opts in during its first start callback using VM service
`0x7fff0001` with a zero argument. Its callback calls an ordinary C `main` once.
The kernel subsequently resumes the interrupted instruction and original app
stack instead of re-entering the callback. This demonstrates the execution
mechanism before choosing a versioned startup/memory contract. A second opt-in
or nonzero argument is rejected. The application cannot supply privileged
context, a processor status register, or a replacement stack address.

Timer interruptions bound a running slice to the next existing 10 ms timer
deadline. The IRQ handler acknowledges the interrupt through its existing
dispatcher, saves the user context and returns to the OS. A CPU loop with no
services is therefore interruptible. A low-priority `NativeAppResume` event now
resumes the foreground app through normal dispatch, after services, Goodix,
keyboard edges and repeat handling. Loaded apps outside the active native
container cannot receive these wakes. The normal OS still owns Home, Back and
power routing. No public app event or ABI 1 callback value was added.

Autonomous wakes preserve the last real input snapshot, including its sequence;
the 300 ms app UI timer no longer substitutes Tick snapshots into a resumable
program. Repeated reads still return a snapshot, not a complete event queue.
Key repeat uses elapsed time across event-wait boundaries, while the existing
single-step D-pad policy still requires release/repress. UI timers retain their
300 ms interval and include time spent executing/dispatching app work. Overdue
UI ticks after a stall are coalesced into one tick per event-loop step rather
than replayed as an unbounded backlog. Physical power policy remains in its
existing service/driver path.

The runtime tracks writes to its private surface, including text and copied
RGB565 pixels. Autonomous yields/preemptions redraw only when that surface
changed or the app faulted. This prevents a file/timer wait from paying for a
full-screen repaint. It does not yet define frame pacing, a completion/fence
API, or a low-power sleep contract.

VM service `0x7fff0002` with a zero argument yields immediately. This is not a
sleep or blocking-file API. At an expired SVC entry, the kernel has performed no
service side effects: it saves a retry address for that ARM/Thumb instruction.
After a successful service or explicit yield, the saved return address proceeds
past the SVC. Ordinary callback completion remains service 0; in the opt-in
profile it marks execution finished, so later timer/key events do not restart
`main`. OS close discards suspended state without depending on app cooperation.
Load, unload and faults clear saved context. Resource-specific cancellation and
exit handlers still need integration with the future file/USB services.

The privileged context holds 328 bytes: all 32 VFP double registers, FPSCR,
SPSR, r0–r12, the return PC, and banked user SP/LR. IRQ and SVC exception frames
share an exact layout. Kernel integer/VFP state is restored before returning
to the event loop. User SP/LR transfer uses the architecture's separate user
register forms with no base writeback; exception return restores processor
flags and mode. See Arm's
[Armv7 and earlier assembly reference](https://documentation-service.arm.com/static/5e7b6a6216d2907d594035c4).
No new hardware registers, clock settings or interrupt periods are introduced.

## Reproduction and acceptance

```sh
make firmware-vm
.venv/bin/python vm/test-sdk-execution.py
.venv/bin/python vm/test-sdk-scheduling.py
make firmware
.venv/bin/python vm/test-native-app-sdk.py
```

The execution test builds actual C/ARM assembly, signs and installs through
modeled USB into synthetic storage, and launches through the installed app UI.
Its finite workload keeps distinct patterns in every VFP lane, all general
registers, a nondefault FPSCR rounding mode, condition flags around a tight
loop, and nested stack canaries. It must survive involuntary preemption and
explicit yield, finish once, and retain its green result after later input.
A separate infinite CPU workload must yield to the normal Home key and leave
the OS responsive, then relaunch in the same OS instance. VM diagnostic indices 12–15 count preemptions, explicit
yields, resumes and the finished state. Existing indices retain their meaning.
VM-only indices 19 and 20 count foreground wakes and native-container UI timer
ticks. The scheduling test measures 32 guest yields and checks ordinary OK
input across 650 ms of waits, Backspace repeat, held/repressed Right, Goodix
touch, timer progress, Home and same-OS relaunch. It builds with the ordinary
external-project C compiler path. Its timing ceilings detect a regression to
the old timer/repaint behavior; they are not physical frame-rate targets.

The report and captured frame are retained under ignored
`build/sdk-execution-qualification/`, with source and firmware hashes. The
legacy ARM isolation suite must still preserve callback timeout, MMIO/data/code
isolation, stack guards and validated services. Both firmware targets must
compile after changes to the shared exception path.

Repeated installed runs also exposed a pre-existing timeout-boundary input
problem: the upstream keyboard loop forgot observed releases each time its
event wait returned. A press between waits could be ignored for the whole
hold. A checked-in Prime-only patch now retains release history across those
boundaries, consumes an entire observed chord once, and requires release before
a subsequent press. Initial held keys, modifier handling and the separate
repeat policy retain their existing behavior. The host edge test checks every
matrix bit, repeated idle/held samples and chords; installed ARM runs exercise
the real KPP and normal event path. Physical key feel remains unqualified.

This proof does not establish physical latency, a supported conventional
startup profile, sleep/input queues, larger memory, playable frame rates,
allocation/file integration, or complete termination cleanup. Those remain
required implementation and qualification work before the runtime can ship.
