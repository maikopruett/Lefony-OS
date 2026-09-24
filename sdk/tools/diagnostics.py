# SPDX-License-Identifier: GPL-3.0-or-later
"""Local symbol matching and debugger configuration. No user data collection."""
import json
from pathlib import Path
import shutil
import subprocess
from build import digest
from lfapp import unpack
from gdb_transport import gdb_quote, remote_command


def matching_symbols(project, package):
    output = project / 'build'
    report = json.loads((output / 'build.json').read_text(encoding='utf-8'))
    debug = output / 'app-debug.elf'
    _, image = unpack(package.read_bytes())
    import hashlib
    if report['debug_sha256'] != digest(debug) or report['image_sha256'] != hashlib.sha256(image).hexdigest():
        raise ValueError('debug symbols do not match this package; rebuild or restore matching build products')
    return debug


def symbolize(project, package, pc):
    debug = matching_symbols(project, package)
    program = shutil.which('arm-none-eabi-addr2line')
    if not program:
        raise ValueError('arm-none-eabi-addr2line is required')
    if not isinstance(pc, int) or not 0x10000000 <= pc < 0x10100000:
        raise ValueError('program counter is outside the app code reservation')
    value = subprocess.check_output([program, '-e', str(debug), '-f', '-C', hex(pc)], text=True, encoding='utf-8', errors='replace', timeout=10)
    return {'pc': pc, 'symbol': value.strip().splitlines(), 'debug_sha256': digest(debug)}


def gdb_script(project, package, endpoint):
    debug = matching_symbols(project, package)
    report = json.loads((project / 'build/build.json').read_text(encoding='utf-8'))
    entry = 'main' if (report.get('runtime') or {}).get('name') == 'foreground-newlib-1' else 'lefony_event'
    path = project / 'build/debug.gdb'
    path.write_text('set pagination off\nset confirm off\nfile ' + gdb_quote(debug) + '\n'
                    'set substitute-path . ' + gdb_quote(project) + '\n'
                    + remote_command(endpoint) + '\n'
                    'hbreak ' + entry + '\ncontinue\n', encoding='utf-8', newline='\n')
    return path
