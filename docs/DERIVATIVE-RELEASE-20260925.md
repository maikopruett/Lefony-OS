# Calculator derivative release

Published development version `1.0.0+1790349064` on September 25, 2026:
[GitHub release](https://github.com/maikopruett/Lefony-OS/releases/tag/build-20260925-1790349064).
The live [Lefony website](https://lefony.com) selects this release. Its latest
manifest returned the expected version, tag and all 14 artifact descriptors;
the website release checker downloaded and verified the capsule and signature.

The [derivative layout](CALCULATOR-DERIVATIVE-LAYOUT.md) adds the centered `d/dx`
button, editable expression placeholder, changeable variable and typeset
editor/history/recall. Evaluated derivatives show their evaluation point.
Integral templates and math-engine differentiation rules are unchanged.

## Exact artifacts

| Artifact / target | SHA-256 |
| --- | --- |
| Physical HP Prime G2 `prime_g2` binary | `584ef3f8feba18c18fbc9fa5ae9aad49c773104776a769f77cdd7a73b4c45c1c` |
| Emulator `prime_g2_vm` ELF | `8926e6bcad665887b0b99f959f94e4c5c85a8b13a83457008fff12048bf2144d` |
| Signed LFU1 capsule | `5ece7bf4f461fcf7e3a653b442caad005d5941c77fb669921fb7a50535a8b1f9` |
| Corresponding-source archive | `1b062af0b2fffddddb22a5eb6626fead55873bfe328744c0920358fa173b4b6b` |

The working-tree source archive contains the audited public sources and the
prepared physical firmware sources. Base revision
`c45297de4ea5598af0cb408f77b074ba2b949dfd` identifies the starting commit;
the manifest's `sourceState` binds the exact distributed archive. No branch
commit or push was made. This publication record and the status-document
follow-up were written after publication and are not in that snapshot.

## Validation

Both targets were rebuilt with `LEFONY_RELEASE_VERSION=1.0.0+1790349064`,
`LEFONY_APP_PUBLIC_KEYS=ports/lefony-prime-g2/app-trust-roots.json` and the
existing `LEFONY_UPDATE_PUBLIC_KEY=ports/lefony-prime-g2/release-signing.pub`.
The signing key matched that checked-in public identity. Recovery assets match
the existing public pin; no trust roots or recovery policies changed.

- `make firmware-vm` and `make firmware`: passed; the physical source was
  captured after its build, including compiler/version/build inputs.
- `make test`: **1,983 passed, two expected private DTB/DTS skips**. The stale
  Settings fixture was updated to include the existing contributors declarations
  and assert idempotence; no Settings firmware behavior changed.
- `vm/test-prime-coordinate-touch.py --derivative` and
  `--calculation-history`, using the release ELF: passed. The derivative journey
  uses brief normal KPP presses to avoid Backspace autorepeat under host load;
  Goodix taps, editable variables, symbolic/numeric results and recall are covered.
- `vm/test-sdk-contracts.py --firmware <release-elf>`: all 12 cases passed.
- `vm/native-suite.py --suite smoke`: all four checks passed.
- Public-tree, whitespace, source archive, capsule signature, ZIP and all
  artifact length/hash checks passed.
- Website `npm run release:validate-browser -- <manifest> <release-directory>`:
  recovery signature, baseline, RAM layout and exit-plan checks passed.
- All 16 uploaded files were downloaded from the draft and verified before
  publication. Website `npm run release:check-latest` and a separate live
  latest-manifest comparison passed after publication.

Evidence is retained under ignored `build/derivative-release-20260925/`.
No calculator was accessed or flashed. This remains a build-tested development
release; physical touch/keypad acceptance, power-loss behavior and endurance
are not established by these emulator and package checks.
