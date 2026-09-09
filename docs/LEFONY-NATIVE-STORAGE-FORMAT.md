# Upsilon native storage format v1

## Scope

The Prime G2 native VM persists Upsilon's canonical `Ion::Storage` record
buffer on the same emulated SD medium that U-Boot reads. The generated raw
image remains immutable; normal VM runs write to a QCOW2 overlay. Physical
Prime builds continue to use RAM-only storage until the real device's
nonvolatile medium and write-protection policy are implemented and tested.

Calculation history is intentionally not part of this format. Epsilon keeps
that application's history in session RAM, so clearing it across a cold boot
matches the upstream calculator behavior. Variables, functions, sequences,
lists, matrices, statistics/regression records, and Python scripts are Ion
records and share the persistent payload described here. Global preferences
and the Statistics/Regression stores are serialized into dedicated Ion records
inside the same atomic payload.

## Media map

All block numbers are zero-based 512-byte logical blocks.

| Region | First block | Last block | Size |
| --- | ---: | ---: | ---: |
| MBR and pre-partition gap | 0 | 2047 | 1 MiB |
| FAT32 U-Boot partition | 2048 | 131071 | 63 MiB |
| Persistence slot 0 | 131072 | 132095 | 512 KiB |
| Persistence slot 1 | 132096 | 133119 | 512 KiB |
| Reserved for future use | 133120 | 262143 | 63 MiB |

Each persistence slot contains one 512-byte header block, followed by 65,012
payload bytes rounded up to 127 blocks. The rest of the slot is reserved and
must not be interpreted by version 1 readers.

## Header

The header is little-endian and occupies the first 64 bytes of its block. All
unused bytes in the 512-byte block are zero when written.

| Offset | Size | Field | Version 1 value |
| ---: | ---: | --- | --- |
| 0 | 8 | magic | bytes `MHLSTGR1` |
| 8 | 4 | version | `1` |
| 12 | 4 | header size | `64` |
| 16 | 8 | generation | monotonically increasing unsigned integer |
| 24 | 4 | payload length | `65012` |
| 28 | 4 | payload CRC-32 | Ion CRC-32 over all payload bytes |
| 32 | 4 | header CRC-32 | Ion CRC-32 over the 64-byte header with this field zero |
| 36 | 4 | flags | `1` means committed |
| 40 | 24 | compatible extension fields | opaque to version 1 and preserved across commits |

A slot is usable only when its magic, exact version, header size, committed
flag, payload length, header checksum, payload checksum, and internal record
layout all validate. Version 1 rejects unknown versions. It retains all six
compatible extension words when rewriting a valid version-1 generation, so a
newer compatible writer does not lose fields unknown to this implementation.

## Payload and limits

The payload is the existing Upsilon `InternalStorage::m_buffer`, not a second
record representation. Each record begins with a little-endian 16-bit total
record size, followed by a NUL-terminated `base.extension` name and the opaque
record value. A zero record size terminates the used record sequence.

Version 1 additionally enforces these defensive limits while loading:

- total payload capacity: 65,012 bytes;
- maximum records: 1,024;
- maximum full-name length: 255 bytes, excluding NUL;
- exactly one dot in every full name;
- maximum absolute record value: 65,006 bytes for the shortest compliant
  name, with the actual limit reduced by the name length and other records;
- every record and the final two-byte terminator must remain inside the
  payload.

The loader validates these bounds before copying the payload into Ion storage,
so corrupt sizes and missing terminators cannot make Ion iterate outside its
storage region.

## Native records

`mahalo.preferences` contains a packed, 29-byte `PRF1` version-1 object. It
stores language, country, UI flags, brightness and idle policy, and Poincare's
angle, display, edition, complex, significant-digit, symbol, and Python-font
preferences. The object carries its own size, version, and CRC-32. Every enum
and numeric field is range-checked before it is applied.

`mahalo.statistics` and `mahalo.regression` each contain a `DAT1` version-1
object with a CRC-32. Each object holds all three series, both columns, up to
100 double-precision pairs per series, and pair counts. The Statistics object
also keeps histogram width/origin; the Regression object keeps the selected
model for each series. Kind, size, counts, and model identifiers are validated
before the application stores are changed.

An intentional factory reset destroys all user records, reconstructs compiled
preference defaults, clears both dataset stores, and commits both slots. The
user-facing VM protocol requires Shift+Alpha+Backspace to be held with the
`STORAGE RESET` request; an unqualified request is rejected. The literal
`STORAGE RESET CONFIRM` form remains available only for bounded internal test
automation.

## Commit and recovery

To commit generation `N + 1`, firmware chooses the inactive slot and performs
these operations in order:

1. write a zero header block, invalidating the target slot;
2. write the complete payload;
3. flush the controller/device path;
4. write the committed header, including payload and header checksums;
5. flush again, then make the new generation active in RAM.

The previous slot is never modified during this sequence. After interruption,
startup validates both slots and loads the valid slot with the largest
generation. If only one is valid it is used as the recovery copy. If neither
is valid, Upsilon starts from its compiled empty/default RAM state.

VM mode `persistent` uses a reusable QCOW2 overlay. Mode `ephemeral` uses a
throwaway QEMU snapshot. Because QEMU rejects a read-only SD drive, mode
`readonly` combines a throwaway snapshot with a private QCOW2 overlay whose
first reserved block after the persistence region is filled with `0xA5`. The
native block layer recognizes that marker and refuses every write before
issuing an SD command.
Direct ELF boot has no initialized SD controller and therefore remains an
explicit RAM-only recovery path.

## Validation

The automated storage suite covers record capacity boundaries, 500+ malformed
payload cases, both-slot corruption, reserved-field preservation, abrupt VM
termination and reboot, preference/dataset reset, read-only rescue mode, and
interruption after each of the four commit phases. It can be run alone with
`./vm/test-native-comprehensive.sh storage`; the fault phase is run with
`./vm/test-native-comprehensive.sh fault`.
