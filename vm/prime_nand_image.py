"""Convert decoded Prime captures to explicitly re-encoded physical fixtures.

The result is NOT a physical raw NAND acquisition. Payload provenance is
retained, but ordinary ECC codewords are newly generated for qualification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile

from prime_bch import BCH
from prime_bch_native import NativeBCH
from prime_gpmi_bch import Layout, REVERSE

PAGE = 2112
PAGES = 4096 * 64
FCB_PAGES = (0, 64, 128, 192)


def checksum(fcb):
    return (~sum(fcb[4:])) & 0xffffffff


def decode_fcb(physical):
    bch = BCH(13, 40, 0x201b)
    decoded, corrections = bytearray(), []
    if len(physical) != PAGE:
        raise ValueError('incorrect FCB page length')
    for block in range(8):
        chunk = physical[32 + block * 193:32 + (block + 1) * 193]
        data, _, errors = bch.decode(chunk[:128].translate(REVERSE), chunk[128:].translate(REVERSE))
        decoded.extend(data.translate(REVERSE))
        corrections.append(len(errors))
    if (decoded[4:12] != bytes.fromhex('4643422000000001') or
            struct.unpack_from('<I', decoded)[0] != checksum(decoded)):
        raise ValueError('invalid FCB fingerprint/version/checksum')
    return bytes(decoded), corrections


def encode_fcb(fcb):
    if len(fcb) != 1024 or struct.unpack_from('<I', fcb)[0] != checksum(fcb):
        raise ValueError('invalid logical FCB size/checksum')
    bch = BCH(13, 40, 0x201b)
    physical = bytearray(PAGE)
    for block in range(8):
        chunk = fcb[block * 128:(block + 1) * 128]
        start = 32 + block * 193
        physical[start:start + 128] = chunk
        physical[start + 128:start + 193] = bch.encode(chunk.translate(REVERSE)).translate(REVERSE)
    physical[2048:2050] = b'\xff\xff'
    return bytes(physical)


def recover_fcb(record):
    """Invert Linux's raw projection using archived recovery BCH-2 geometry.

    Success requires all eight BCH-40 blocks plus the full FCB checksum;
    a fingerprint at offset 22 alone is insufficient evidence.
    """
    data, oob = record[:2048], record[2048:]
    if len(oob) != 64:
        raise ValueError('short projected FCB')
    word = int.from_bytes(oob[:10], 'little')
    wire, ecc = 80, 80
    for block in range(4):
        word |= int.from_bytes(data[block * 512:(block + 1) * 512], 'little') << wire
        wire += 4096
        word |= ((int.from_bytes(oob, 'little') >> ecc) & ((1 << 26) - 1)) << wire
        wire += 26
        ecc += 26
    physical = bytearray(word.to_bytes(PAGE, 'little'))
    physical[0], physical[2048] = physical[2048], physical[0]
    return decode_fcb(bytes(physical))


def fcb_layout(fcb):
    word = lambda offset: struct.unpack_from('<I', fcb, offset)[0]
    if word(0x14) != 2048 or word(0x18) != 2112 or word(0x1c) != 64:
        raise ValueError('unsupported FCB NAND geometry')
    first, following, ecc0, eccn = word(0x30), word(0x34), word(0x38), word(0x2c)
    if (first & 3 or following & 3 or first > 4092 or following > 4092 or
            ecc0 > 20 or eccn > 20 or word(0x3c) > 255 or word(0x40) > 255 or word(0x88) > 1):
        raise ValueError('unsupported FCB BCH layout')
    gf = word(0x88) << 10
    layout = Layout((word(0x40) << 24) | (word(0x3c) << 16) | (ecc0 << 11) | gf | (first // 4),
                    (2112 << 16) | (eccn << 11) | gf | (following // 4))
    if (word(0xac) or word(0x84) != 2048 or word(0x80) > 7 or
            word(0x7c) * 8 + word(0x80) != layout.marker_payload_bit()):
        raise ValueError('unsupported FCB marker mode/location')
    return layout


def overlay_records(path):
    records = {}
    if path is None:
        return records
    with path.open('rb') as stream:
        if stream.read(8) != b'PG2OVL1\n':
            raise ValueError('expected decoded qualification overlay')
        while header := stream.read(8):
            if len(header) != 8:
                raise ValueError('torn overlay header')
            kind, page = struct.unpack('<B3xI', header)
            if kind != 1 or page >= PAGES:
                raise ValueError('qualification converter accepts page-program overlays only')
            data = stream.read(PAGE)
            if len(data) != PAGE:
                raise ValueError('torn overlay record')
            records[page] = data
    return records


def convert(source, output, overlay=None):
    if output.exists():
        raise ValueError('output already exists; choose a new artifact path')
    if source.stat().st_size != PAGE * PAGES:
        raise ValueError('source is not a complete 512 MiB + OOB capture')
    records = overlay_records(overlay)
    fcb_reports, logical_fcbs = {}, {}
    with source.open('rb') as stream:
        for page in FCB_PAGES:
            stream.seek(page * PAGE)
            record = records.get(page, stream.read(PAGE))
            fcb, corrected = recover_fcb(record)
            logical_fcbs[page] = fcb
            fcb_reports[page] = {'sha256': hashlib.sha256(fcb).hexdigest(), 'corrected_bits': corrected}
    if len(set(logical_fcbs.values())) != 1:
        raise ValueError('FCB copies disagree; select the intended geometry explicitly')
    layout = fcb_layout(logical_fcbs[0])
    digest, source_digest = hashlib.sha256(), hashlib.sha256()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix='physical-nand-', delete=False) as target:
            temporary = Path(target.name)
            with source.open('rb') as stream, NativeBCH() as native:
                for page in range(PAGES):
                    original = stream.read(PAGE)
                    if len(original) != PAGE:
                        raise ValueError('source changed size during conversion')
                    source_digest.update(original)
                    record = records.get(page, original)
                    if page in logical_fcbs:
                        physical = encode_fcb(logical_fcbs[page])
                    elif record == b'\xff' * PAGE:
                        physical = record
                    else:
                        payload, meta = layout.swap_marker(record[:2048], record[2048:2048 + layout.metadata_bytes])
                        physical = layout.encode(payload, meta, native)
                    target.write(physical)
                    digest.update(physical)
                    if page and page % 32768 == 0:
                        print(f'Re-encoded {page}/{PAGES} pages', flush=True)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, output)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink()
    return {'kind': 're-encoded qualification fixture, NOT physical raw capture',
            'source': str(source), 'source_sha256': source_digest.hexdigest(),
            'output': str(output), 'sha256': digest.hexdigest(),
            'overlay': str(overlay) if overlay else None,
            'overlay_sha256': hashlib.sha256(overlay.read_bytes()).hexdigest() if overlay else None,
            'recovered_fcbs': fcb_reports, 'pages': PAGES}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--overlay', type=Path)
    args = parser.parse_args()
    report = convert(args.source.resolve(), args.output.resolve(), args.overlay.resolve() if args.overlay else None)
    args.output.with_suffix(args.output.suffix + '.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
