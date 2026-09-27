#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned Phase 5 layout and release-authenticated boot descriptor.

This module has no USB or write-to-device entry point. Layout 5 is distinct
from legacy NAND/A-B/app profiles. A physical migration remains unavailable.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import zlib

from prime_g2_update_capsule import sign_prefix, verify_signature
from prime_hp_confinement import PROFILE
from analyze_hp_prime_compatibility import INPUTS

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / 'native/prime_g2/dual_boot_layout.json'
PAGE, ERASE, BLOCKS, RAW_PAGE = 2048, 131072, 4096, 2112
LAYOUT_ID = 5
DESCRIPTOR_BYTES = 512
PREFIX_BYTES = 256
COMPONENTS = ('hp_image', 'lefony_image', 'lefony_dtb', 'rescue')


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def sha(data):
    return hashlib.sha256(data).digest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


@dataclass(frozen=True)
class Region:
    name: str
    first: int
    count: int
    encoding: str
    owner: str

    @property
    def end(self):
        return self.first + self.count

    def contains(self, block):
        return self.first <= block < self.end


def load_layout(path=LAYOUT):
    doc = json.loads(Path(path).read_text())
    require(doc['schema'] == 1 and doc['layout_id'] == LAYOUT_ID, 'unknown layout')
    require(doc['physical_migration_allowed'] is False, 'physical migration is not qualified')
    require(doc['geometry'] == dict(total_bytes=BLOCKS*ERASE, page_bytes=PAGE,
                                   oob_bytes=64, erase_block_bytes=ERASE), 'wrong NAND geometry')
    require(doc['hp_profile'] == PROFILE, 'unqualified HP confinement profile')
    regions = {}
    cursor = 0
    for entry in doc['regions']:
        region = Region(**entry)
        require(type(region.first) is int and type(region.count) is int and
                region.first == cursor and region.count > 0 and region.end <= BLOCKS,
                'layout has a gap, overlap or invalid range')
        require(region.name not in regions, 'duplicate region')
        regions[region.name] = region
        cursor = region.end
    require(cursor == BLOCKS, 'incomplete layout')
    require((regions['hp_filesystem'].first, regions['hp_filesystem'].end) == (392, 2048),
            'filesystem disagrees with HP confinement')
    require((regions['lefony_apps'].first, regions['lefony_apps'].count) == (3456, 512),
            'app storage requires an explicit migration contract')
    return doc, regions


def layout_digest():
    doc, _ = load_layout()
    return sha(canonical(doc))


def capacity(name, length, bad_blocks):
    doc, regions = load_layout()
    require(name in doc['minimum_spare_blocks'], 'region is not an image slot')
    r = regions[name]
    require(all(type(b) is int and 0 <= b < BLOCKS for b in bad_blocks), 'invalid bad-block map')
    good = [b for b in range(r.first, r.end) if b not in bad_blocks]
    needed = (length + ERASE - 1)//ERASE
    require(0 < length <= doc['maximum_image_bytes'].get(name, r.count*ERASE), 'image size outside policy')
    require(needed + doc['minimum_spare_blocks'][name] <= len(good), 'insufficient good blocks and spare reserve')
    return good[:needed]


def descriptor_prefix(images, release):
    """Authenticate all four payloads and the exact layout/profile together."""
    require(set(images) == set(COMPONENTS), 'missing or unexpected component')
    require(type(release) is int and 0 < release < 2**32, 'invalid release generation')
    doc, _ = load_layout()
    data = bytearray(PREFIX_BYTES)
    struct.pack_into('<4s7I', data, 0, b'LFD5', 1, LAYOUT_ID, 0x32475048,
                     release, 4, 1, 0)  # profile v4, handoff v1, reserved
    data[32:64] = layout_digest()
    data[64:96] = sha(PROFILE.encode())
    for i, name in enumerate(COMPONENTS):
        payload = images[name]
        require(0 < len(payload) <= doc['maximum_image_bytes'][name], 'invalid '+name+' length')
        if name in ('lefony_image', 'rescue'):
            require(len(payload) >= 64 and payload[0x30:0x40] == struct.pack('<4s3I', b'LFL5', 5, 1, 0),
                    'legacy firmware is incompatible with the dual layout')
        struct.pack_into('<I', data, 96+36*i, len(payload))
        data[100+36*i:132+36*i] = sha(payload)
    require((len(images['hp_image']), sha(images['hp_image']).hex()) == INPUTS['HPPrime.img'],
            'unsupported exact HP image')
    return bytes(data)


def sign_descriptor(images, release, private_key):
    prefix = descriptor_prefix(images, release)
    return prefix + sign_prefix(prefix, private_key)


def verify_descriptor(data, public_key, images=None):
    require(len(data) == DESCRIPTOR_BYTES, 'incorrect descriptor length')
    prefix = data[:PREFIX_BYTES]
    magic, schema, layout, model, release, profile, handoff, reserved = struct.unpack_from('<4s7I', prefix)
    require((magic, schema, layout, model, profile, handoff, reserved) ==
            (b'LFD5', 1, LAYOUT_ID, 0x32475048, 4, 1, 0) and release > 0,
            'unsupported descriptor contract')
    require(prefix[32:64] == layout_digest() and prefix[64:96] == sha(PROFILE.encode()),
            'layout/profile identity mismatch')
    require(prefix[240:] == bytes(16), 'nonzero reserved descriptor fields')
    verify_signature(prefix, data[PREFIX_BYTES:], public_key)
    doc, _ = load_layout()
    result = {'release': release, 'images': {}}
    for i, name in enumerate(COMPONENTS):
        size, = struct.unpack_from('<I', prefix, 96+36*i)
        digest = prefix[100+36*i:132+36*i]
        require(0 < size <= doc['maximum_image_bytes'][name], 'invalid signed '+name+' size')
        result['images'][name] = (size, digest.hex())
    require(result['images']['hp_image'] == INPUTS['HPPrime.img'], 'unsupported signed HP identity')
    if images is not None:
        require(descriptor_prefix(images, release) == prefix, 'payload does not match signed descriptor')
    return result


def record(generation, state, transaction, descriptor=b''):
    """Redundant layout record; signature authorizes payload, CRC detects tears."""
    require(type(generation) is int and 0 < generation < 2**32, 'invalid generation')
    require(state in ('recovery', 'committed'), 'unknown boot state')
    require(len(transaction) == 32 and transaction != bytes(32), 'invalid transaction identity')
    require(len(descriptor) == (DESCRIPTOR_BYTES if state == 'committed' else 0), 'invalid state descriptor')
    page = bytearray(b'\xff'*PAGE)
    struct.pack_into('<4s4I', page, 0, b'LFC5', 1, LAYOUT_ID, generation, state == 'committed')
    page[20:52] = transaction
    page[52:64] = bytes(12)
    page[64:64+len(descriptor)] = descriptor
    struct.pack_into('<I', page, PAGE-4, zlib.crc32(page[:PAGE-4]))
    return bytes(page)


def decode_record(page):
    require(len(page) == PAGE, 'short layout record')
    magic, schema, layout, generation, state = struct.unpack_from('<4s4I', page)
    require((magic, schema, layout) == (b'LFC5', 1, LAYOUT_ID) and generation and state in (0, 1),
            'invalid layout record')
    require(page[20:52] != bytes(32) and page[52:64] == bytes(12), 'invalid record fields')
    end = 64 + DESCRIPTOR_BYTES if state else 64
    require(page[end:PAGE-4] == b'\xff'*(PAGE-4-end), 'unknown record extensions')
    require(struct.unpack_from('<I', page, PAGE-4)[0] == zlib.crc32(page[:PAGE-4]), 'torn layout record')
    return {'generation': generation, 'state': 'committed' if state else 'recovery',
            'transaction': page[20:52], 'descriptor': page[64:end]}


def select_record(pages):
    require(len(pages) == 2, 'two layout copies required')
    valid = []
    for slot, page in enumerate(pages):
        try:
            decoded = decode_record(page)
        except ContractError:
            continue
        valid.append((decoded['generation'], slot, decoded))
    require(valid, 'no valid layout; recovery required')
    if len(valid) == 2:
        require(valid[0][2]['transaction'] == valid[1][2]['transaction'], 'conflicting transactions')
        require(valid[0][0] != valid[1][0] or pages[0] == pages[1], 'conflicting layout generations')
    return max(valid, key=lambda item:item[:2])[2]
