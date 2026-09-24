# Foreground input stream

The working-tree SDK adds a C/C++ input stream with API revision 4 and explicitly
declared capability **32**. A conventional main app normally requires mask **48**
(foreground plus input), or **52** when it requests app-owned Back navigation.
Existing ABI 1 callback values and the 128-byte service-8 snapshot are unchanged.
This candidate requires matching firmware and SDK/website readers; physical
input timing and touch feel remain unqualified.

Include `<lefony/input_stream.h>` and call `lefony_read_input_stream(&state)`
from the foreground loop. The caller supplies a writable `LefonyInputStream`;
the helper initializes its request header. Success returns zero. Unsupported or
undeclared capability returns `-3`; invalid size, version, reserved word or
address returns `-4` without consuming any events. No device pointer is exposed.

```c
LefonyInputStream input;
if (lefony_read_input_stream(&input) == 0) {
  if (input.flags & (LEFONY_INPUT_OVERFLOW | LEFONY_INPUT_FOCUS_RESET)) {
    /* Replace local key/contact state from the snapshot; cancel old gestures. */
  }
  for (uint32_t i = 0; i < input.count; ++i) {
    const LefonyStreamEvent *event = &input.events[i];
    if (event->kind == LEFONY_INPUT_KEYS) {
      if (lefony_input_key_held(event->data.keys.down, LEFONY_PHYSICAL_LEFT)) {
        /* A new left press. The up mask reports releases. */
      }
    }
  }
  /* Use input.held for continuous movement, including simultaneous keys. */
}
```

## State and ordered events

The fixed-width request/reply is **480 bytes**, with up to eight 48-byte events.
The OS retains at most 32 events, ordered across key and touch dispatch. `count`
is the number removed by this call; `pending` is the remaining queue length.
Drain it in a bounded loop or on subsequent frames. The snapshot describes the
latest observed state, which may be newer than a partial batch's last event.
Choose either event replay or the live snapshot deliberately when updating local
state, to avoid applying old transitions after a newer snapshot.

Each event has a sequence number and a 32-bit OS millisecond timestamp. Sequence
and time wrap modulo 2³². `sequence` in the reply is the latest produced sequence;
the first event in a fresh focus session is 1. `generation` changes whenever focus
is reset. Reserved outputs and unused event slots are zero.

Key events contain `down`, `up` and resulting `held` masks, plus modifier flags.
Each mask is two uint32 words indexed by **physical row × 8 + column**, with
word 0 containing positions 0–31. Use `LEFONY_PHYSICAL_*` constants, checked
against the [authoritative key map](contracts/keys.json). These are independent
of service 8's logical key tokens and text. Shift, Alpha and Alpha-lock state
appear in the modifier flags; physical Shift/Alpha also have ordinary held bits.

The stream observes the normal OS matrix scan before logical dispatch selects
one key from a chord. A changed key must remain observed in its new state for
at least **10 ms** before a down/up transition is emitted. Debouncing is per key;
a bouncing key does not delay a different key. Repeated scans of a held key
produce no extra down events. Apps implement repeat/movement from held state and
time; legacy logical navigation and editing-repeat policies remain unchanged.
Transitions entirely between scans or shorter than the stability interval can
be missed. This is a sampled input contract, not an electrical edge recorder.

Touch events retain normal Goodix dispatch, two stable IDs, coordinates, phase
(`0` down, `1` move, `2` up, `3` cancel) and the contacts-changed flag. The event
retains release coordinates; the current snapshot clears contacts on up/cancel.
Keys do not overwrite the current touch state. Text and expression editing still
use the [service-8 snapshot](API.md); the stream does
not add a text composition or IME protocol.

## Overflow, focus and OS ownership

If the app stops draining the queue, its next read sets `LEFONY_INPUT_OVERFLOW`,
returns the current state with **zero events**, and discards the unusable backlog.
`dropped` counts all discarded events, saturating at uint32 maximum. It is zero
on the following read unless another overflow occurred. Replace locally held
keys/contacts, cancel incomplete gestures and restart event processing; replaying
a suffix after a missing press/release could leave a game control stuck.

Loading, unloading, faults and focus changes clear the session's queue and touch
state. The first read sets `LEFONY_INPUT_FOCUS_RESET`. Keys already held when an
app gains focus stay suppressed until release and a fresh press, preventing the
launcher key or a previous app's controls from becoming a new app action.
Sleeping and CPU preemption retain the queue and execution stack; they do not
stop OS input processing or make an input event shorten an explicit sleep.

Home, Apps and the dedicated power key stay OS-owned and never appear in held
masks. Shift+Home (Setup) and Shift+Apps (Info) also remain OS navigation: they
leave the native app for Settings, including while an approval screen is open.
Navigation dismisses pending approval and releases the app's input state.
Back exits by default. Existing service 9 can opt into Back delivery with
navigation depth 1–8; depth zero restores normal OS navigation. A Back key already
held when opting in must be released before it produces a new app press.

## Validation

`vm/test-sdk-input-stream.py` builds an external ordinary C app, installs a signed
package into synthetic storage and drives KPP/Goodix through normal OS dispatch.
It covers chords, held state without extra downs, releases, modifiers, Back,
two contacts, up/cancel, overflow during sleep, Home, focus reset and a fresh
press after relaunch. Its undeclared-capability probe and malformed requests
exercise the real SVC boundary. `tests/test_sdk_input_stream.py` also checks
ordered partial reads, bounce suppression, clock wraparound, randomized chords,
focus isolation and overflow under host sanitizers. Exact candidate results are
recorded in the OS repository's `docs/NATIVE-APP-SDK-1.0-PROGRESS.md` ledger.

SDK replay supports `{"keys":["left","shift"]}` to set the currently held
matrix keys and `{"keys":[]}` to release them. Follow state changes with explicit
`wait_ms` steps when testing duration. Held keys and touch contacts are released
when a replay closes, including after an assertion fails.
