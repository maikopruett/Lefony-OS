# Listing files

Write the description in `description.md` and changes in `release-notes.md`.
These files display as plain text; Markdown and HTML are not executed. Description
is required (at most 2,000 UTF-16 code units); notes may be empty (at most 4,000).
The app ID, name, version, ABI and license come only from `app.json`.

Add a square 64–512 pixel `icon.png` and 1–5 images under `screenshots/`, each
160–1280 pixels wide and 120–960 high. Use static non-interlaced 8-bit RGB/RGBA
PNGs. Icon size is limited to 256 KiB, each screenshot to 1 MiB. Screenshot names
use ASCII letters, numbers, hyphens and underscores; filename order is display
order (for example `01-main.png`, `02-options.png`). Capture the real app UI.

Set `publish_source` to `true` in `listing.json` when you intend to distribute the
source with the release. An optional `repository_url` is an HTTPS repository
link without credentials, query or fragment. It is never fetched automatically.

Run `lefony-sdk publish --dry-run` with matching SDK runtime dependencies. It
snapshots source and these files, builds a release package, runs all JSON replays
under `tests/` in the ARM emulator and writes a local listing preview and exact
upload manifest beneath `.lefony/publish/`. Later source edits belong to a new
attempt. The dry run does not sign in or upload. With the matching store backend,
`lefony-sdk login` and `lefony-sdk publish` build/test and publish the folder.
Use `publish --resume ATTEMPT_ID` to upload a prepared attempt or recover an
interruption; `--status` queries progress and `--cancel` cancels staging.
Updates need a higher immutable version. A website revision conflict requires
reviewing and reconciling the changes. Use `listing pull --dry-run` to save a
local/store comparison, then `listing pull --plan PLAN_ID` with explicit
`--take-local FIELD` or `--take-remote FIELD` choices for conflicts. Pull preserves
source-sharing permission. Read SDK `PUBLISHING.md` before publishing.

Write one brief sentence in `listing.json` → `short_description` (1–120 UTF-16
code units). It appears in the app list. Put detailed instructions, requirements
and limitations in `description.md` (up to 2,000 units) for the app detail page.
