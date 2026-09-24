# SPDX-License-Identifier: GPL-3.0-or-later
"""Check compiled VM app keys against the SDK's explicitly selected public keys.

This checks initialized ELF objects, not signature execution or physical trust.
The pinned firmware compiler retains local object symbols in the VM ELF.
"""
import hashlib
import struct

STORE_SYMBOL = b'_ZL19LefonyAppTrustRoots'
EMULATOR_SYMBOL = b'_ZL20LefonyEmulatorAppKey'
SPKI_PREFIX = bytes.fromhex('30820122300d06092a864886f70d01010105000382010f003082010a0282010100')
SPKI_SUFFIX = bytes.fromhex('0203010001')
RECORD_BYTES = 32 + 256


def require(condition, message):
    if not condition:
        raise ValueError('SDK VM trust: ' + message)


def key_record(der):
    require(len(der) == len(SPKI_PREFIX) + 256 + len(SPKI_SUFFIX)
            and der.startswith(SPKI_PREFIX) and der.endswith(SPKI_SUFFIX),
            'expected RSA-2048/e=65537 public key')
    modulus = der[len(SPKI_PREFIX):-len(SPKI_SUFFIX)]
    require(modulus[0] & 128 and modulus[-1] & 1, 'invalid public modulus')
    return hashlib.sha256(der).digest() + modulus


def compiled_tables(image):
    require(52 <= len(image) <= 64 * 1024**2 and image[:7] == b'\x7fELF\x01\x01\x01',
            'expected an unstripped ARM ELF32 image')
    kind, machine, version = struct.unpack_from('<HHI', image, 16)
    phoff, shoff = struct.unpack_from('<II', image, 28)
    ehsize, phsize, phcount, shsize, shcount = struct.unpack_from('<5H', image, 40)
    require((kind, machine, version, ehsize, phsize, shsize) == (2, 40, 1, 52, 32, 40)
            and 0 < phcount <= 128 and 0 < shcount <= 1024
            and phoff >= 52 and phoff + phsize * phcount <= len(image)
            and shoff >= 52 and shoff + shsize * shcount <= len(image), 'invalid ELF tables')
    programs = [struct.unpack_from('<8I', image, phoff + i * phsize) for i in range(phcount)]
    sections = [struct.unpack_from('<10I', image, shoff + i * shsize) for i in range(shcount)]

    def section_data(section):
        offset, size = section[4:6]
        require(section[1] != 8 and offset + size <= len(image), 'invalid initialized section')
        return image[offset:offset + size]

    symtabs = [section for section in sections if section[1] == 2]
    require(len(symtabs) == 1, 'retain the VM ELF symbol table for app-key verification')
    symtab = symtabs[0]
    require(symtab[9] == 16 and symtab[5] % 16 == 0 and symtab[5] <= 8 * 1024**2
            and 0 < symtab[6] < shcount, 'invalid symbol table')
    strings = sections[symtab[6]]
    require(strings[1] == 3, 'invalid symbol names')
    names = section_data(strings)
    tables = {STORE_SYMBOL: [], EMULATOR_SYMBOL: []}
    for name, address, size, info, other, index in struct.iter_unpack('<IIIBBH', section_data(symtab)):
        require(name < len(names), 'invalid symbol name offset')
        end = names.find(b'\0', name)
        require(end >= 0, 'unterminated symbol name')
        symbol = names[name:end]
        if symbol not in tables:
            continue
        require(info & 15 == 1 and other == 0 and 0 < index < shcount
                and RECORD_BYTES <= size <= 4 * RECORD_BYTES and size % RECORD_BYTES == 0,
                'invalid compiled app-key object')
        section = sections[index]
        require(section[1] == 1 and section[2] & 3 == 2 and address >= section[3]
                and address + size <= section[3] + section[5], 'app-key object is outside read-only data')
        offset = section[4] + address - section[3]
        require(offset + size <= len(image) and any(
            typ == 1 and flags & 4 and filesz <= memsz and start + filesz <= len(image)
            and virtual <= address and address + size <= virtual + filesz
            and start + address - virtual == offset
            for typ, start, virtual, physical, filesz, memsz, flags, alignment in programs),
            'app-key object is not mapped from initialized firmware bytes')
        tables[symbol].append(image[offset:offset + size])
        require(len(tables[symbol]) <= 16, 'too many app-key table copies')
    return tables


def verify_trust(firmware, store_public_der, emulator_public_der):
    require(firmware.stat().st_size <= 64 * 1024**2, 'firmware exceeds size bound')
    image = firmware.read_bytes()
    selected = [key_record(der) for der in store_public_der]
    require(1 <= len(selected) <= 4 and len(set(selected)) == len(selected),
            'select one to four distinct store public keys')
    emulator = key_record(emulator_public_der)
    require(emulator not in selected, 'the emulator fixture must not be a store trust root')
    tables = compiled_tables(image)
    require(tables[STORE_SYMBOL],
            'no compiled store keys; build the VM with explicit LEFONY_APP_PUBLIC_KEYS matching --public-key')
    for table in tables[STORE_SYMBOL]:
        records = [table[i:i + RECORD_BYTES] for i in range(0, len(table), RECORD_BYTES)]
        require(len(records) == len(selected) and set(records) == set(selected),
                'compiled store keys differ from --public-key')
    require(tables[EMULATOR_SYMBOL] and all(table == emulator for table in tables[EMULATOR_SYMBOL]),
            'VM emulator key differs from the public synthetic-workspace fixture')
    return {'schema': 1, 'firmware_sha256': hashlib.sha256(image).hexdigest(),
            'store_key_ids': sorted(record[:32].hex() for record in selected),
            'emulator_key_id': emulator[:32].hex(),
            'store_table_copies': len(tables[STORE_SYMBOL]),
            'emulator_table_copies': len(tables[EMULATOR_SYMBOL]),
            'method': 'initialized-ELF-app-key-objects', 'signature_execution_qualified': False,
            'physical_qualified': False}
