# SPDX-License-Identifier: GPL-3.0-or-later
"""Host access controls for trusted frozen-SDK integration checks.

Linux requires a native launcher even when the tested x86-64 tools use an
explicit interpreter. No fallback runs a command without the requested policy.
Network isolation belongs to the calling container; local fixture TLS is allowed.
"""
import json
from contextlib import contextmanager
from pathlib import Path
import platform
import subprocess
import sys


def linux_processes():
    pairs = {}
    for directory in Path('/proc').iterdir():
        if not directory.name.isdecimal():
            continue
        try:
            # comm can contain spaces and parentheses; ppid follows state.
            fields = (directory / 'stat').read_text().rsplit(')', 1)[1].split()
            pairs[int(directory.name)] = int(fields[1])
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return pairs


@contextmanager
def interpreted_qemu(qemu, interpreter):
    """Add only a host interpreter to the source harness's actual QEMU exec.

    This leaves SDK/runtime input hashes referring to the real QEMU binary.
    Frozen CLI processes use command_prefix separately and are never replaced
    by in-process CLI calls. Record the interpreter identity in the run report.
    """
    if interpreter is None:
        yield
        return
    import runner
    original = runner.subprocess

    class Launch:
        PIPE = original.PIPE
        DEVNULL = original.DEVNULL

        @staticmethod
        def Popen(command, *args, **kwargs):
            if not command or command[0] != str(qemu):
                raise ValueError('Unexpected command in interpreted QEMU harness')
            return original.Popen([str(interpreter.resolve()), *command], *args, **kwargs)

    runner.subprocess = Launch
    try:
        yield
    finally:
        runner.subprocess = original


def command_prefix(root, bundle, work, *, launcher=None, interpreter=None):
    system = platform.system()
    if system == 'Darwin':
        if launcher or interpreter:
            raise ValueError('Linux launcher/interpreter options do not apply to macOS')
        profile = ('(version 1)(allow default)(deny file-read* (subpath "/opt/homebrew"))'
                   '(deny process-exec (subpath "/opt/homebrew"))'
                   f'(deny file-read* (subpath {json.dumps(str(root))}))')
        return ['/usr/bin/sandbox-exec', '-p', profile], {'method': 'macOS sandbox-exec'}
    if system != 'Linux' or launcher is None:
        raise ValueError('Linux qualification requires --access-launcher; this host has no implicit fallback')
    launcher = launcher.resolve(strict=True)
    probe = json.loads(subprocess.check_output([str(launcher), '--probe'], text=True, timeout=10))
    if probe['landlock_abi'] < 3:
        raise ValueError('Linux qualification requires Landlock ABI 3 or newer')
    prefix = [str(launcher), '--exec', str(bundle), '--work', str(work), '--work', '/tmp']
    for name in ('/etc', '/proc', '/sys/devices/system'):
        if Path(name).exists():
            prefix += ['--read', name]
    prefix += ['--work', '/dev/null', '--read', '/dev/urandom', '--read', '/dev/random']
    # Permit only the declared system glibc/loader boundary. Other libraries
    # must come from the tested SDK, including dynamically loaded libraries.
    for directory in (Path('/lib/x86_64-linux-gnu'), Path('/lib64'), Path('/lib/aarch64-linux-gnu')):
        for name in ('ld-linux-x86-64.so.2', 'ld-linux-aarch64.so.1', 'libc.so.6', 'libm.so.6',
                     'libpthread.so.0', 'libdl.so.2', 'librt.so.1', 'libresolv.so.2',
                     'libnss_dns.so.2', 'libnss_files.so.2'):
            path = directory / name
            if path.exists():
                prefix += ['--exec', str(path.resolve())]
    if interpreter:
        interpreter = interpreter.resolve(strict=True)
        prefix += ['--exec', str(interpreter)]
    controls = [root / 'sdk/contract.json', Path(sys.executable).resolve()]
    for path in controls:
        prefix += ['--expect-denied', str(path)]
    prefix += ['--']
    if interpreter:
        prefix += [str(interpreter)]
    return prefix, {'method': 'Linux Landlock', **probe,
                    'interpreter': str(interpreter) if interpreter else None,
                    'negative_controls': list(map(str, controls)),
                    'system_libraries': 'glibc/loader only; other libraries must be bundled'}
