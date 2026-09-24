# SPDX-License-Identifier: GPL-3.0-or-later
"""Inert publication metadata and PNG validation; mirrored by the store contract."""
import hashlib
import json
import re
import struct
from urllib.parse import urlsplit
import zlib

SHORT_DESCRIPTION_LIMIT = 120
DESCRIPTION_LIMIT = 2000
NOTES_LIMIT = 4000
MEDIA_LIMITS = {'icon': 262144, 'screenshot': 1048576}
SIGNATURE = b'\x89PNG\r\n\x1a\n'
# ECMAScript trim, kept explicit so Python and the browser agree on text limits.
TRIM = '\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def parse_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON field: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Invalid JSON number: ' + value)
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid)


def text(value, maximum, label, required=False):
    require(isinstance(value, str), label + ': expected UTF-8 text')
    require(not any(0xd800 <= ord(c) <= 0xdfff for c in value), label + ': invalid Unicode')
    value = value.strip(TRIM)
    require('\0' not in value and len(value.encode('utf-16-le')) // 2 <= maximum,
            f'{label}: use at most {maximum} UTF-16 code units without NUL')
    require(not required or value, label + ': add a description before publishing')
    return value



def short_description(value):
    value = text(value, SHORT_DESCRIPTION_LIMIT, 'Short description', True)
    require(not any(c in value for c in '\r\n\u2028\u2029'), 'Short description: use one line')
    return value


def short_description_fallback(description):
    line = re.split(r'(?<=[.!?]) ', re.sub('[' + TRIM + ']+', ' ', description.strip(TRIM)))[0]
    if len(line.encode('utf-16-le')) // 2 <= SHORT_DESCRIPTION_LIMIT:
        return line
    result = ''
    for character in line:
        if len((result + character).encode('utf-16-le')) // 2 > SHORT_DESCRIPTION_LIMIT - 1:
            break
        result += character
    return result.rstrip(TRIM) + '…'


def repository_url(value):
    # An inert link, never fetched by publication. Deliberately excludes userinfo,
    # queries, fragments, percent escapes and alternate URL-parser spellings.
    require(isinstance(value, str) and len(value) <= 2048 and
            re.fullmatch(r'https://[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?(?::[0-9]{1,5})?(?:/[A-Za-z0-9._~/-]*)?', value),
            'store/listing.json: repository_url must be an HTTPS repository link without credentials, query or fragment')
    parsed = urlsplit(value)
    require(parsed.hostname and '.' in parsed.hostname and
            all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?', p) for p in parsed.hostname.split('.')),
            'store/listing.json: invalid repository hostname')
    try:
        require(parsed.port is None or 1 <= parsed.port <= 65535, 'store/listing.json: invalid repository port')
    except ValueError:
        raise ValueError('store/listing.json: invalid repository port') from None
    return value


def listing(value, description, release_notes):
    require(isinstance(value, dict) and {'schema', 'publish_source'} <= set(value) and
            set(value) <= {'schema', 'publish_source', 'repository_url', 'short_description'} and
            type(value['schema']) is int and value['schema'] == 1,
            'store/listing.json: expected schema 1, publish_source and optional repository_url; identity comes from app.json')
    require(value['publish_source'] is True,
            'store/listing.json: set publish_source to true to include your source with the release')
    result = {'schema': 1, 'publish_source': True,
              'description': text(description, DESCRIPTION_LIMIT, 'store/description.md', True),
              'release_notes': text(release_notes, NOTES_LIMIT, 'store/release-notes.md')}
    if 'short_description' in value:
        result['short_description'] = short_description(value['short_description'])
    if 'repository_url' in value:
        result['repository_url'] = repository_url(value['repository_url'])
    return result


def submission_content(submission):
    """Content at the accepted release revision, never a later live listing."""
    metadata = submission['listing']
    media = [{key: file[key] for key in ('sha256', 'bytes', 'width', 'height')}
             for file in submission['files'][3:]
             if file['path'] == 'icon.png' or file['path'].startswith('screenshots/')]
    return {'name': submission['app']['name'], 'short_description': metadata.get('short_description', short_description_fallback(metadata['description'])), 'description': metadata['description'],
            'release_notes': metadata['release_notes'], 'repository_url': metadata.get('repository_url'),
            'icon': media[0], 'screenshots': media[1:]}


def image(data, kind):
    """Validate bounded PNG pixels and strip metadata exactly as store-media.ts."""
    require(kind in MEDIA_LIMITS, 'Unknown listing image kind')
    require(len(data) <= MEDIA_LIMITS[kind], f'{kind}: PNG exceeds {MEDIA_LIMITS[kind]} bytes')
    require(len(data) >= 57 and data.startswith(SIGNATURE), f'{kind}: use a PNG image')
    kept, compressed = [SIGNATURE], []
    offset = 8
    width = height = channels = chunks = 0
    ended = data_ended = seen_data = seen_transparency = False
    while offset < len(data):
        chunks += 1
        require(chunks <= 1024 and len(data) - offset >= 12, 'Malformed PNG chunks')
        size = struct.unpack_from('>I', data, offset)[0]
        end = offset + 12 + size
        require(end <= len(data), 'Truncated PNG image')
        kind_bytes = data[offset + 4:offset + 8]
        require(re.fullmatch(rb'[A-Za-z]{2}[A-Z][A-Za-z]', kind_bytes) and
                zlib.crc32(data[offset + 4:end - 4]) == struct.unpack_from('>I', data, end - 4)[0],
                'Invalid PNG chunk checksum or type')
        chunk = kind_bytes.decode('ascii')
        require(offset != 8 or chunk == 'IHDR', 'Missing PNG header')
        if chunk == 'IHDR':
            require(offset == 8 and size == 13, 'Invalid PNG header')
            width, height, depth, color, compression, filtering, interlace = struct.unpack_from('>IIBBBBB', data, offset + 8)
            require(depth == 8 and color in (2, 6) and compression == filtering == interlace == 0,
                    'Use a static, non-interlaced RGB or RGBA PNG')
            channels = 3 if color == 2 else 4
            require((width == height and 64 <= width <= 512) if kind == 'icon' else
                    (160 <= width <= 1280 and 120 <= height <= 960),
                    'App icon must be square, 64–512 pixels' if kind == 'icon' else
                    'Screenshots must be 160 × 120 to 1280 × 960 pixels')
            kept.append(data[offset:end])
        elif chunk == 'IDAT':
            require(not data_ended, 'PNG image data must be consecutive')
            seen_data = True
            compressed.append(data[offset + 8:end - 4])
            kept.append(data[offset:end])
        elif chunk == 'IEND':
            require(size == 0 and seen_data and end == len(data), 'Invalid PNG end marker')
            ended = True
            kept.append(data[offset:end])
        else:
            if seen_data:
                data_ended = True
            if chunk == 'tRNS':
                require(not seen_transparency and not seen_data and channels == 3 and size == 6 and
                        all(n <= 255 for n in struct.unpack_from('>HHH', data, offset + 8)), 'Invalid PNG transparency')
                seen_transparency = True
                kept.append(data[offset:end])
            elif chunk == 'PLTE':
                require(not seen_data and 3 <= size <= 768 and size % 3 == 0, 'Invalid PNG palette')
            else:
                require(chunk not in ('acTL', 'fcTL', 'fdAT') and chunk[0].islower(), 'Unsupported PNG image chunk')
        offset = end
    require(ended, 'Incomplete PNG image')
    stride = width * channels + 1
    expected = stride * height
    decoder = zlib.decompressobj()
    try:
        pixels = decoder.decompress(b''.join(compressed), expected + 1)
    except zlib.error:
        raise ValueError('Invalid compressed PNG image data') from None
    require(len(pixels) == expected and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
            'PNG pixel data is incomplete, oversized or has trailing compressed data')
    require(all(pixels[i] <= 4 for i in range(0, expected, stride)), 'Invalid PNG scanline filter')
    clean = b''.join(kept)
    return clean, {'width': width, 'height': height, 'bytes': len(clean), 'sha256': hashlib.sha256(clean).hexdigest()}
