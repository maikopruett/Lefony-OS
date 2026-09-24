# Notebook

A C++ document/calculator proving app using public SDK APIs and conventional
`main`. See [the UI guide](../../UI.md) for preview, input, storage and limits.
Version 0.6.2 requires local API 12 writer cancellation, API 10 system services,
API 9 typography and API 8 data control. It is not supported by
the earlier published 0.2.0-dev firmware.

```sh
lefony-sdk --project . package --profile debug
lefony-sdk --project . preview --once
lefony-sdk --project . preview --scenario tests/edit.json
```

`tests/edit.json` uses normal keypad and Goodix input. Broader cold persistence,
export, malformed data, format upgrade and release-frame checks live in the
repository's `vm/test-sdk-notebook.py`. No fixture or replay accesses a calculator.
Package upgrades are accepted only after the complete document is readable.
Unsupported schemas and malformed documents retain the previous compatible pair
for explicit host recovery; `vm/test-sdk-notebook-upgrade.py` exercises this
workflow, including cold reopening and rollback.

The empty and damaged-document screens use the shared wrapping paragraph widget.
Recovery instructions fit within the list area and keep the original file intact;
disabled New/Options actions cannot overwrite an unreadable document.

Document saves and exports use the SDK's staged `FileWriter` replacement, so
replacing a file credits its previous length against the app quota. Failed writes
discard staging and keep the editing draft; an uncertain commit asks the user to
reopen and inspect the saved file. Legacy `notebook.tmp` cleanup happens only
after the document is readable and its package/data pair is accepted. The
full-quota workload is `vm/test-sdk-notebook-quota.py`; consult its report and the
ledger before treating the current integration as qualified.

Drag the expression list to scroll by pixels; partially visible rows keep their
text and can be tapped after releasing a drag. The scrollbar shows position.
Keyboard navigation reveals the selected row. A cancelled drag keeps its scroll
position and cannot activate a row or footer control. The shared model and
clipped rendering are exercised through normal Goodix input by
`vm/test-sdk-list-scroll.py`; see the repository's SDK evidence ledger for the
exact candidate and remaining qualification.

Preview keeps committed data between source edits. Use `--reset-data` to start
again from empty data or `--fixture-dir` inputs, and `--fresh-data` for a run
whose output should be discarded. See [preview data policy](../../UI.md).

Options saves angle units, automatic/scientific/engineering notation and 1–14
significant digits with each document. New files start with OS preferences;
existing format 1/2 files preserve their original radians/automatic/9-digit
meaning. Format 3 is written on the next successful save. The light palette
follows the OS, with a separate app dark palette.

Use Shift+View to copy, Shift+OK to cut and Shift+Menu to paste in the expression
field. Tap to place the caret or drag to select text; cancelled/outside or
multi-contact gestures restore the prior selection. Field touch keeps the editor
open. OK or Save commits the expression. Select all and Shift+arrows also select
text. The shared field model is exercised by `vm/test-sdk-text-field.py`.
Supported calculator symbols
normalize to the scalar grammar; an unsupported or oversized paste preserves
the field. Options Cancel/Back and cancelled slider drags discard draft changes.
