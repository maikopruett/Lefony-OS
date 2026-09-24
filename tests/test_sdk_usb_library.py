# SPDX-License-Identifier: GPL-3.0-or-later
"""Desktop USB dependency discovery without enumerating or opening a device."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sdk/tools'))
import usb_files


def test_frozen_usb_loads_only_its_bundled_library(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    monkeypatch.setattr(usb_files.ctypes.util, 'find_library', lambda _: pytest.fail('Host search in frozen bundle'))
    expected = str(tmp_path / 'usb' / usb_files.library_name())
    calls = []
    def loader(path): calls.append(path); return 'loaded'
    name = 'WinDLL' if usb_files.os.name == 'nt' else 'CDLL'
    monkeypatch.setattr(usb_files.ctypes, name, loader)
    assert usb_files.load_library() == 'loaded' and calls == [expected]
    def unavailable(path): calls.append(path); raise OSError('missing dependency')
    monkeypatch.setattr(usb_files.ctypes, name, unavailable)
    with pytest.raises(usb_files.USBError, match='Bundled libusb'):
        usb_files.load_library()
    assert calls == [expected, expected]


def test_source_usb_reports_unavailable_library_without_opening_devices(monkeypatch):
    monkeypatch.setattr(sys, 'frozen', False, raising=False)
    monkeypatch.setattr(usb_files.ctypes.util, 'find_library', lambda _: 'unloadable-libusb')
    def unavailable(path): raise OSError('missing native dependency')
    name = 'WinDLL' if usb_files.os.name == 'nt' else 'CDLL'
    monkeypatch.setattr(usb_files.ctypes, name, unavailable)
    with pytest.raises(usb_files.USBError, match='install the native library'):
        usb_files.load_library()
