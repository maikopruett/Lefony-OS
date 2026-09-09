"""Install checked, idempotent whole-window frame presentation hooks."""
import argparse
from pathlib import Path
import shutil


def prepare(source):
    root = Path(__file__).resolve().parents[1]
    shutil.copy2(root / "ports/lefony-prime-g2/apps/prime_frame.h",
                 source / "apps/prime_frame.h")
    path = source / "escher/src/window.cpp"
    text = path.read_text()
    changes = [
        ('#include <escher/window.h>',
         '#include <escher/window.h>\n#include <apps/prime_frame.h>'),
        ('  View::redraw(bounds());\n  PrimeG2BootProgress(20);',
         '  {\n    PrimeFrame frame;\n    View::redraw(bounds());\n    PrimeG2BootProgress(20);\n  } // Present the complete frame before revealing the backlight.'),
    ]
    for old, new in changes:
        if new in text:
            continue
        if text.count(old) != 1:
            raise ValueError(f"Unexpected display integration context: {old}")
        text = text.replace(old, new)
    path.write_text(text)
    # Poincare uses longjmp for pool exhaustion, so C++ destructors do not run.
    path = source / "apps/apps_container.cpp"
    text = path.read_text()
    changes = [
        ('#include "prime_g2_boot_progress.h"',
         '#include "prime_g2_boot_progress.h"\n#include <apps/prime_frame.h>'),
        ('    // Exception\n',
         '    // Exception\n    PrimeFrame::cancel(); // longjmp bypasses the frame destructor.\n'),
    ]
    for old, new in changes:
        if new in text:
            continue
        if text.count(old) != 1:
            raise ValueError(f"Unexpected frame recovery context: {old}")
        text = text.replace(old, new)
    path.write_text(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    prepare(parser.parse_args().source.resolve())
