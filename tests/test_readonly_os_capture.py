# SPDX-License-Identifier: GPL-3.0-or-later
"""OS captures use only bounded read requests and require two matching reads."""
import json
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prime_g2_readonly_os_capture as capture


class Device:
    def __init__(self, *, size=5000, corrupt_second=False, bad_marker=False,
                 changed_status=False, short_data=False, active_slot=0):
        self.image = bytearray((i % 251 for i in range(max(size, 2048))))
        struct.pack_into('<3I', self.image, 0x24, 0x016f2818, 0, size)
        self.image = bytes(self.image)
        self.page = None
        self.triggers = []
        self.status_reads = 0
        self.corrupt_second = corrupt_second
        self.bad_marker = bad_marker
        self.changed_status = changed_status
        self.short_data = short_data
        self.active_slot = active_slot

    def write(self, request, data, value, index):
        assert request == 0x51 and not data and index == 0
        assert 2048 <= value < 6144
        self.page = value
        self.triggers.append(value)

    def read(self, request, value, index, length):
        if request == 0x48:
            self.status_reads += 1
            state = 1 if self.changed_status and self.status_reads > 2 else 0
            return struct.pack('<16I', 0x31554241, 2, state, 0, self.active_slot, 0xffffffff,
                               0, 3, 1, 0, 0, 10, 0, 0, 0, 512)
        if request == 0x51:
            return struct.pack('<6I', 0x3152504c, self.page, 0, 0,
                               0 if self.bad_marker else 255, 1)
        assert request == 0x52 and length == 512 and index == 0
        offset = (self.page - 2048) * 2048 + value
        data = self.image[offset:offset + 512].ljust(512, b'\xff')
        if self.corrupt_second and len(self.triggers) > 4 and self.page == 2049:
            data = bytes([data[0] ^ 1]) + data[1:]
        return data[:-1] if self.short_data else data


def test_capture_is_private_complete_and_reread_before_publication(tmp_path):
    device = Device()
    output = tmp_path / 'capture'
    observations = []
    def progress(*args):
        observations.append(args)
        assert not output.exists()
    report = capture.capture(device, output, progress=progress)
    assert report['status'] == 'passed' and report['independent_reads_identical']
    assert report['capsule_bytes'] == 5000
    assert (output/'os.zImage').read_bytes() == (output/'verification.zImage').read_bytes() == device.image
    assert device.triggers == [2048, 2048, 2049, 2050, 2048, 2049, 2050]
    assert report['page_read_triggers'] == 7 and len(observations) == 6
    assert output.stat().st_mode & 0o777 == 0o700
    assert (output/'os.zImage').stat().st_mode & 0o777 == 0o600
    assert not output.with_name('capture.partial').exists()
    assert json.loads((output/'report.json').read_text()) == json.loads(json.dumps(report))
    before = list(device.triggers)
    with pytest.raises(ValueError, match='new OS capture'):
        capture.capture(device, output)
    assert device.triggers == before


@pytest.mark.parametrize('options,error', [
    ({'size':4096}, 'header'), ({'size':5001}, 'header'),
    ({'size':8*1024*1024+4}, 'header'), ({'active_slot':1}, 'active slot B'),
    ({'corrupt_second':True}, 'reads differ'), ({'bad_marker':True}, 'bad-block'),
    ({'changed_status':True}, 'Updater state changed'), ({'short_data':True}, 'short NAND'),
])
def test_bad_or_changed_inputs_preserve_partials_without_publishing(tmp_path, options, error):
    output = tmp_path/'capture'
    with pytest.raises(capture.usb.USBError, match=error):
        capture.capture(Device(**options), output)
    assert not output.exists()
    partial = tmp_path/'capture.partial'
    report = json.loads((partial/'report.json').read_text())
    assert report['status'] == 'failed' and not report['nand_writes']
    with pytest.raises(FileExistsError):
        capture.capture(Device(), output)


def test_timeout_and_cancellation_leave_no_completed_capture(tmp_path):
    now = [0]
    device = Device()
    def progress(*args):now[0] = 2
    with pytest.raises(TimeoutError):
        capture.capture(device, tmp_path/'timeout', clock=lambda:now[0], timeout=1, progress=progress)
    assert device.triggers == [2048, 2048]
    assert not (tmp_path/'timeout').exists()
    def cancel(*args):raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        capture.capture(Device(), tmp_path/'cancelled', progress=cancel)
    report = json.loads((tmp_path/'cancelled.partial/report.json').read_text())
    assert report['status'] == 'failed' and report['error'] == 'KeyboardInterrupt'
    assert not (tmp_path/'cancelled').exists()


@pytest.mark.parametrize('command', [0x49,0x4b,0x4e,0x50,0x60,0x61])
def test_transport_rejects_unrelated_control_requests(command):
    device = Device()
    with pytest.raises(ValueError, match='Only an OS-slot'):
        capture.ReadOnlyTransport(device).write(command, value=2048)
    with pytest.raises(ValueError, match='outside the read-only'):
        capture.ReadOnlyTransport(device).read(command)
    assert not device.triggers


def test_publication_failure_leaves_a_partial_directory(tmp_path, monkeypatch):
    output = tmp_path/'capture'
    original = Path.rename
    def rename(source, target):
        if Path(target) == output:
            raise OSError('publication failed')
        return original(source, target)
    monkeypatch.setattr(Path, 'rename', rename)
    with pytest.raises(OSError, match='publication failed'):
        capture.capture(Device(), output)
    assert not output.exists()
    report = json.loads((tmp_path/'capture.partial/report.json').read_text())
    assert report['status'] == 'failed'


@pytest.mark.parametrize('page', [0,2047,6144,65536])
def test_transport_cannot_read_outside_the_existing_os_slot(page):
    device = Device()
    with pytest.raises(ValueError):
        capture.ReadOnlyTransport(device).write(0x51, value=page & 0xffff, index=page >> 16)
    assert not device.triggers
