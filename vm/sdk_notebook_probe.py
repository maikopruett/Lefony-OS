# SPDX-License-Identifier: GPL-3.0-or-later
"""Observe Notebook's rendered readiness without writing app or OS state."""
from pathlib import Path
import tempfile
import time
from PIL import Image


def wait_notebook(normal,records,*,timeout=15,observe=None):
    # Opening/saving/exporting draws a dedicated busy screen without the title
    # underline. Wait for a complete stable ordinary screen before the next
    # gesture; fixed wall sleeps can expire while NAND/model work is pending.
    started=time.monotonic();deadline=started+timeout;previous=None;stable_since=None;observed=started
    with tempfile.TemporaryDirectory(prefix='notebook-frame-') as temp:
        path=Path(temp)/'frame.ppm'
        while time.monotonic()<deadline:
            normal.execute('screendump',{'filename':str(path)})
            with Image.open(path) as frame:
                ready=frame.size==(320,240) and frame.getpixel((12,36))!=frame.getpixel((0,0))
                pixels=frame.tobytes()
            now=time.monotonic()
            if ready and pixels==previous:
                if stable_since is not None and now-stable_since>=.15:
                    records.append({'action':'await-notebook-screen','status':'passed','elapsed_seconds':round(now-started,3),'timeout_seconds':timeout});return
            else:stable_since=now if ready else None
            if observe and now-observed>=15:
                observe(round(now-started,3));observed=time.monotonic()
            previous=pixels;time.sleep(.05)
        (normal.output/'readiness-failure.ppm').write_bytes(path.read_bytes())
    state=normal.channel.command('STATE')
    fault=normal.channel.command('APP DIAG 9')
    raise AssertionError(f'Notebook did not leave its busy screen within {timeout} seconds: {state}; fault {fault}')
