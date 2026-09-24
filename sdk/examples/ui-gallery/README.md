# UI Gallery

This C++ example uses the public widgets, menu model, confirmation layout and
normal input services. It needs API 9 and the ordinary foreground runtime.
It keeps demonstration state in memory and performs no file or network writes.

Up/Down selects controls and OK activates. With the field focused, OK selects
all its text. Tap to place the caret, drag to select rendered cells, or move with
Left/Right. Cancelled touch restores the original selection; combining accents
stay with their base during touch selection. The checkbox disables the field, reset
button and slider. Slider drags cancel outside their control or on interrupted
contact. Reset opens a confirmation with Cancel selected by default.

Actions opens a scrolling menu with an unavailable entry. Menu arrows skip
disabled actions; touch can scroll across them without activating them. The
actions demonstrate a custom theme, a 1023-byte field, empty text, four OS fonts,
and empty/loading/ready menu states. Loading is a three-second local simulation.
Back, or the header Back button, returns. Home remains owned by the OS.

Version 0.1.2 adds Wrapped text at the end of Actions. It demonstrates the shared
paragraph widget with word wrapping, combining accents, a long unbroken word,
explicit blank lines and disabled/invalid colors. The app checks that all three
paragraphs fit their assigned layout boxes.

```sh
lefony-sdk new ./my-gallery --template ui-gallery
lefony-sdk --project ./my-gallery preview --once --scenario tests/startup.json
```

Read `UI.md` in the SDK distribution for limits, font policy and layout inspection.
