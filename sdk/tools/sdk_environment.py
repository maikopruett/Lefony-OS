# SPDX-License-Identifier: GPL-3.0-or-later
"""One resource root for source and frozen SDK installations."""
from pathlib import Path
import os
import sys

SDK = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2])) / 'sdk'


def openssl_environment(runtime=None, environment=None):
    """Relocate OpenSSL's data paths for one child, without changing Python TLS.

    Source installations keep their host configuration. Frozen Windows builds
    always use the configuration, providers and engines shipped with the SDK.
    An explicit runtime is used during packaging before the entry point exists.
    """
    result = dict(os.environ if environment is None else environment)
    if runtime is None:
        if not (getattr(sys, 'frozen', False) and sys.platform == 'win32'):
            return result
        runtime = Path(sys._MEIPASS) / 'openssl'
    runtime = Path(runtime).resolve()
    paths = {'OPENSSL_CONF': runtime/'ssl/openssl.cnf',
             'OPENSSL_CONF_INCLUDE': runtime/'ssl',
             'OPENSSL_MODULES': runtime/'lib/ossl-modules',
             'OPENSSL_ENGINES': runtime/'lib/engines-3'}
    for name, path in paths.items():
        if not (path.is_file() if name == 'OPENSSL_CONF' else path.is_dir()):
            raise ValueError('Missing bundled OpenSSL resource: ' + str(path))
    # Environment names are case insensitive on Windows, including when a
    # caller supplied an ordinary dict instead of os.environ.
    result = {key: value for key, value in result.items() if key.upper() not in paths}
    result.update({name: str(path) for name, path in paths.items()})
    return result


def configure_output():
    """CLI pipes/files use UTF-8; interactive consoles keep their native setup.

    Call only at executable entry points, not when importing SDK helpers or
    entering the binary GDB relay. Replacement escapes prevent a diagnostic
    containing an unpaired surrogate from masking the original failure.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure') and not stream.isatty():
            stream.reconfigure(encoding='utf-8', errors='backslashreplace', newline='\n')


def cli_command():
    """A frozen SDK executable dispatches CLI arguments, not Python filenames."""
    return [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, str(SDK / 'tools/cli.py')]
