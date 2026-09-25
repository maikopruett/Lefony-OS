# SPDX-License-Identifier: GPL-3.0-or-later
"""Load the bundled Prime skins, with an explicit custom-directory override."""
import math
import os
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image
from sdk_environment import SDK


ALIASES = {
    'esc': 'back', 'views': 'view', 'vars': 'var', 'math': 'toolbox',
    'templ': 'units', 'xttn': 'xnt', 'frac': 'fraction', 'bksp': 'backspace',
    '^': 'power', 'sq': 'square', 'chs': 'plusminus', 'paren': 'parenthesis',
    'comma)': 'comma', 'enter': 'ok', 'eex': 'ee', 'div': 'divide',
    'mult': 'multiply', 'on': 'onoff',
    **dict(zip('0123456789', ('zero', 'one', 'two', 'three', 'four', 'five',
                              'six', 'seven', 'eight', 'nine'))),
}


def load_skins(directory=None):
    directory = directory or os.environ.get('LEFONY_EMULATOR_ASSETS') or SDK / 'assets/prime'
    base = Path(directory).expanduser().resolve()
    files = sorted((base / 'skins').glob('*.primeskin'))
    if not 1 <= len(files) <= 20:
        raise ValueError('Skin directory must contain 1–20 skins/*.primeskin files')
    catalog, assets = [], {}
    for index, path in enumerate(files):
        if path.stat().st_size > 131072:
            raise ValueError('Skin definition is too large')
        root = ET.fromstring(path.read_bytes())
        images = {}
        dimensions = None
        for state, tag in (('normal', 'picture'), ('hover', 'picture_hover'),
                           ('pressed', 'picture_pressed')):
            name = root.find(tag).get('file')
            image = (base / 'images' / name).resolve()
            if image.parent != base / 'images' or image.stat().st_size > 16000000:
                raise ValueError('Skin image must be a local image in images/')
            with Image.open(image) as bitmap:
                if bitmap.format != 'PNG' or not all(1 <= n <= 4096 for n in bitmap.size):
                    raise ValueError('Invalid skin PNG')
                if dimensions is not None and dimensions != bitmap.size:
                    raise ValueError('Skin state images must have matching dimensions')
                dimensions = bitmap.size
                bitmap.verify()
            route = f'skin/{index}/{state}.png'
            assets[route] = image.read_bytes()
            images[state] = route
        width, height = dimensions

        def number(element, name, default=None):
            value = float(element.get(name, default))
            if not math.isfinite(value):
                raise ValueError('Non-finite skin coordinate')
            return value

        def rectangle(x, y, w, h):
            if x < 0 or y < 0 or w <= 0 or h <= 0 or x+w > width+1 or y+h > height+1:
                raise ValueError('Skin rectangle is outside its image')
            return dict(x=x, y=y, width=w, height=h)

        screen = root.find('screen')
        screen = rectangle(*(number(screen, n) for n in ('x', 'y', 'width', 'height')))
        if abs(screen['width'] / screen['height'] - 4/3) > .001:
            raise ValueError('Prime display must have a 4:3 aspect ratio')
        group = root.find('keys')
        sx, sy = (number(group, n, '1') for n in ('xscale', 'yscale'))
        ox, oy = (number(group, n, '0') for n in ('xoffset', 'yoffset'))
        keys = []
        for key in group.findall('key'):
            x, y, x2, y2 = (number(key, n) for n in ('x', 'y', 'x2', 'y2'))
            left, top = min(x, x2)*sx+ox, min(y, y2)*sy+oy
            note = key.get('note', '')
            keys.append(dict(name=ALIASES.get(note, note), label=note,
                             **rectangle(left, top, abs(x2-x)*sx, abs(y2-y)*sy)))
        if len(keys) != 51 or len({key['name'] for key in keys}) != 51:
            raise ValueError('Prime skin must define 51 distinct keys')
        title = next((t.get('id') for t in root.findall('trans') if t.get('lang') == 'EN'), path.stem)
        catalog.append(dict(id=index, title=title, width=width, height=height,
                            screen=screen, keys=keys, images=images))
    return catalog, assets
