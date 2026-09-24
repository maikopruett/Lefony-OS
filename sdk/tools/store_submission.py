# SPDX-License-Identifier: GPL-3.0-or-later
"""Version 1 exact-byte publication manifest, mirrored by the website parser."""
import re
from lfapp import manifest, compatible
from store_listing import canonical, listing, require


def submission_manifest(value):
    require(isinstance(value, dict) and set(value) == ({'schema', 'app', 'listing', 'inputs_sha256', 'files'} | ({'data'} if value.get('schema') == 2 else set())) and
            type(value['schema']) is int and value['schema'] in (1, 2), 'Invalid publication manifest schema')
    app = manifest(value['app'])
    require(app['abi'] == 1, 'Publication requires ABI 1')
    compatible(app)
    metadata = value['listing']
    require(isinstance(metadata, dict) and {'description', 'release_notes'} <= set(metadata), 'Invalid publication listing')
    config = {key: item for key, item in metadata.items() if key not in ('description', 'release_notes')}
    require(listing(config, metadata['description'], metadata['release_notes']) == metadata, 'Listing text must be normalized')
    require(isinstance(value['inputs_sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', value['inputs_sha256']), 'Invalid input manifest digest')
    files = value['files']
    bundled = value['schema'] == 2
    if bundled:
        from bundled_data import descriptor
        descriptor(value['data'])
    data_count = sum(1 for f in files if isinstance(f, dict) and str(f.get('path', '')).startswith('data/')) if isinstance(files, list) else 0
    require((1 <= data_count <= 2) if bundled else data_count == 0, 'Invalid bundled data parts')
    require(isinstance(files, list) and 5 <= len(files) <= 9, 'Publication requires source, package, report, icon and 1–5 screenshots')
    names = ['source.lfsrc', 'package.lfapp', 'report.json', 'icon.png'] + [f'screenshots/{i:02d}.png' for i in range(1, len(files) - data_count - 3)]
    names += [f'data/{i:02d}.gzpart' for i in range(data_count)]
    require(1 <= len(files) - data_count - 4 <= 5, 'Publication exceeds file/byte budget')
    for index, (item, name) in enumerate(zip(files, names)):
        keys = {'path', 'sha256', 'bytes'} | ({'width', 'height'} if 3 <= index < len(files) - data_count else set())
        require(isinstance(item, dict) and set(item) == keys and item['path'] == name, 'Unexpected publication file or order')
        maximum = (8388608, 2101312, 65536, 262144)[index] if index < 4 else (8388608 if name.startswith('data/') else 1048576)
        require(type(item['bytes']) is int and 1 <= item['bytes'] <= maximum and
                isinstance(item['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', item['sha256']), 'Invalid publication file size or digest')
        if 3 <= index < len(files) - data_count:
            w, h = item['width'], item['height']
            require(type(w) is int and type(h) is int and
                    ((w == h and 64 <= w <= 512) if index == 3 else (160 <= w <= 1280 and 120 <= h <= 960)),
                    'Invalid publication image dimensions')
    require(sum(f['bytes'] for f in files) <= (16710000 if bundled else 16777216), 'Publication exceeds byte budget')
    require(sum(f['bytes'] for f in files if f['path'].startswith('data/')) <= 12582912, 'Compressed bundled data exceeds limit')
    require(len(canonical(value)) <= 65536, 'Publication manifest exceeds 64 KiB')
    return value
