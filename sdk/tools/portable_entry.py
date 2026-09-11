# SPDX-License-Identifier: GPL-3.0-or-later
"""Frozen desktop entry point; resolves its tools relative to the bundle."""
import os
from pathlib import Path
import sys

if getattr(sys, 'frozen', False):
    root = Path(sys._MEIPASS)
    toolchain = root / 'toolchain'
    os.environ['PATH'] = str(toolchain/'bin') + os.pathsep + os.environ.get('PATH', '')
    # GCC must discover its relocated cc1plus, startup headers and libgcc.
    os.environ.pop('GCC_EXEC_PREFIX', None)
    os.environ.pop('COMPILER_PATH', None)
    os.environ.pop('LIBRARY_PATH', None)
from cli import main
raise SystemExit(main())
