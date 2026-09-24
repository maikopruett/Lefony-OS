# SPDX-License-Identifier: GPL-3.0-or-later
"""Desktop packaging must retain matching compiled store and VM fixture keys."""
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import native_desktop_firmware as trust


def public(seed):
    return trust.SPKI_PREFIX + bytes([0x80 | seed]) + bytes([seed]) * 254 + b'\x01' + trust.SPKI_SUFFIX


STORE, OTHER, EMULATOR = public(2), public(3), public(4)


def elf(tables=None):
    if tables is None:
        tables = [(trust.STORE_SYMBOL, trust.key_record(STORE)),
                  (trust.STORE_SYMBOL, trust.key_record(STORE)),
                  (trust.EMULATOR_SYMBOL, trust.key_record(EMULATOR))]
    data = bytearray(256)
    names = bytearray(b'\0')
    symbols = bytearray(16)
    for name, value in tables:
        offset = len(data)
        data.extend(value)
        symbols.extend(struct.pack('<IIIBBH', len(names), 0x82000000 + offset - 256,
                                   len(value), 1, 0, 1))
        names.extend(name + b'\0')
    data_size = len(data) - 256
    strings_offset = len(data)
    data.extend(names)
    symbols_offset = len(data)
    data.extend(symbols)
    sections_offset = len(data)
    for section in [(0,) * 10,
                    (0, 1, 2, 0x82000000, 256, data_size, 0, 0, 1, 0),
                    (0, 3, 0, 0, strings_offset, len(names), 0, 0, 1, 0),
                    (0, 2, 0, 0, symbols_offset, len(symbols), 2, 0, 4, 16)]:
        data.extend(struct.pack('<10I', *section))
    data[:16] = b'\x7fELF\x01\x01\x01' + bytes(9)
    struct.pack_into('<HHIIIIIHHHHHH', data, 16, 2, 40, 1, 0x82000000,
                     52, sections_offset, 0, 52, 32, 1, 40, 4, 0)
    # Firmware uses one RWE load segment; .rodata itself is read-only.
    struct.pack_into('<8I', data, 52, 1, 256, 0x82000000, 0x82000000,
                     data_size, data_size, 7, 1)
    return data


def verify(tmp_path, image, keys=(STORE,), emulator=EMULATOR):
    path = tmp_path / 'vm.elf'
    path.write_bytes(image)
    return trust.verify_trust(path, keys, emulator)


def test_matching_compiled_copies_and_fixture(tmp_path):
    record = verify(tmp_path, elf())
    assert record['store_table_copies'] == 2 and record['emulator_table_copies'] == 1
    assert not record['signature_execution_qualified'] and not record['physical_qualified']
    assert record['store_key_ids'] == [trust.key_record(STORE)[:32].hex()]


def test_key_order_does_not_change_selected_trust(tmp_path):
    image = elf([(trust.STORE_SYMBOL, trust.key_record(STORE) + trust.key_record(OTHER)),
                 (trust.EMULATOR_SYMBOL, trust.key_record(EMULATOR))])
    assert len(verify(tmp_path, image, (OTHER, STORE))['store_key_ids']) == 2


@pytest.mark.parametrize('kind', ['missing', 'changed_copy', 'wrong_modulus', 'extra_key',
                                 'missing_fixture', 'changed_fixture', 'fixture_as_store'])
def test_mismatched_compiled_trust_rejected(tmp_path, kind):
    store = trust.key_record(STORE)
    fixture = trust.key_record(EMULATOR)
    tables = [(trust.STORE_SYMBOL, store), (trust.STORE_SYMBOL, store),
              (trust.EMULATOR_SYMBOL, fixture)]
    if kind == 'missing': tables = tables[2:]
    elif kind == 'changed_copy': tables[1] = (trust.STORE_SYMBOL, trust.key_record(OTHER))
    elif kind == 'wrong_modulus': tables[1] = (trust.STORE_SYMBOL, store[:32] + fixture[32:])
    elif kind == 'extra_key': tables[1] = (trust.STORE_SYMBOL, store + trust.key_record(OTHER))
    elif kind == 'missing_fixture': tables = tables[:2]
    elif kind == 'changed_fixture': tables[2] = (trust.EMULATOR_SYMBOL, store)
    else: tables[0] = (trust.STORE_SYMBOL, store + fixture)
    with pytest.raises(ValueError, match='SDK VM trust'):
        verify(tmp_path, elf(tables))


@pytest.mark.parametrize('keys', [(), (STORE, STORE), (STORE, EMULATOR), (OTHER,), (STORE,) * 5])
def test_invalid_selected_store_keys_rejected(tmp_path, keys):
    with pytest.raises(ValueError, match='SDK VM trust'):
        verify(tmp_path, elf(), keys)


@pytest.mark.parametrize('kind', ['header', 'architecture', 'section_table', 'stripped',
                                 'name_offset', 'object_size', 'object_section', 'object_type',
                                 'writable', 'unallocated', 'unmapped', 'truncated_load', 'section_offset'])
def test_malformed_or_unmapped_key_objects_rejected(tmp_path, kind):
    image = elf()
    sections = struct.unpack_from('<I', image, 32)[0]
    symbols = struct.unpack_from('<I', image, sections + 3 * 40 + 16)[0]
    if kind == 'header': image[4] = 2
    elif kind == 'architecture': struct.pack_into('<H', image, 18, 62)
    elif kind == 'section_table': struct.pack_into('<I', image, 32, len(image))
    elif kind == 'stripped': struct.pack_into('<I', image, sections + 3 * 40 + 4, 0)
    elif kind == 'name_offset': struct.pack_into('<I', image, symbols + 16, len(image))
    elif kind == 'object_size': struct.pack_into('<I', image, symbols + 16 + 8, 289)
    elif kind == 'object_section': struct.pack_into('<H', image, symbols + 16 + 14, 0)
    elif kind == 'object_type': image[symbols + 16 + 12] = 2
    elif kind == 'writable': struct.pack_into('<I', image, sections + 40 + 8, 3)
    elif kind == 'unallocated': struct.pack_into('<I', image, sections + 40 + 8, 0)
    elif kind == 'unmapped': struct.pack_into('<I', image, 52 + 8, 0x81000000)
    elif kind == 'truncated_load': struct.pack_into('<I', image, 52 + 16, 1)
    else: struct.pack_into('<I', image, sections + 40 + 16, len(image))
    with pytest.raises(ValueError, match='SDK VM trust'):
        verify(tmp_path, image)


def test_raw_public_key_bytes_do_not_replace_compiled_objects(tmp_path):
    image = elf([(trust.EMULATOR_SYMBOL, trust.key_record(EMULATOR))])
    image.extend(trust.key_record(STORE))
    with pytest.raises(ValueError, match='no compiled store keys'):
        verify(tmp_path, image)
