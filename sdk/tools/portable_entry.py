# SPDX-License-Identifier: GPL-3.0-or-later
"""Frozen desktop entry point; resolves its tools relative to the bundle."""
import os
from pathlib import Path
import sys

if getattr(sys, 'frozen', False):
    root = Path(sys._MEIPASS)
    toolchain = root / 'toolchain'
    paths = [str(toolchain/'bin')]
    if os.name == 'nt':
        # Also serves child tools (GCC's cc1, OpenSSL, GDB and QEMU). Their
        # imported DLL closure is checked by the native Windows packager.
        paths.append(str(root))
    os.environ['PATH'] = os.pathsep.join([*paths, os.environ.get('PATH', '')])
    # GCC must discover its relocated cc1plus, startup headers and libgcc.
    os.environ.pop('GCC_EXEC_PREFIX', None)
    os.environ.pop('COMPILER_PATH', None)
    os.environ.pop('LIBRARY_PATH', None)
if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    if sys.argv[1:2] == ['--internal-gdb-relay']:
        from gdb_transport import main
        raise SystemExit(main(sys.argv[2:]))
    else:
        from sdk_environment import configure_output
        configure_output()
        from cli import main
        raise SystemExit(main())
