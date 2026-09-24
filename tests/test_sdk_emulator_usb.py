# SPDX-License-Identifier: GPL-3.0-or-later
"""Local packet polling keeps transfer errors and retry boundaries intact."""
import io
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sdk/tools'))
import emulator_usb


def host(replies):
    value = object.__new__(emulator_usb.PrimeUSBHost)
    value.stream = io.BytesIO(replies)
    class Socket:
        def __init__(self): self.sent = []
        def sendall(self, data): self.sent.append(data)
    value.socket = Socket()
    return value


def test_only_explicit_naks_retry_the_same_packet(monkeypatch):
    waits = []
    monkeypatch.setattr(emulator_usb.time, 'sleep', waits.append)
    value = host(b'NAK\nNAK\nDATA 6162\n')
    assert value.in_packet(2) == b'ab'
    assert value.socket.sent == [b'IN 2\n'] * 3
    assert waits == [0.0001, 0.0001]


@pytest.mark.parametrize('reply', [b'STALL\n', b'ERROR\n', b''])
def test_terminal_packet_failures_are_never_retried(reply, monkeypatch):
    def unexpected_sleep(_): raise AssertionError('Terminal response retried')
    monkeypatch.setattr(emulator_usb.time, 'sleep', unexpected_sleep)
    value = host(reply)
    with pytest.raises(emulator_usb.USBError): value.out_packet(b'a')
    assert value.socket.sent == [b'OUT 61\n']


def test_setup_nak_is_not_an_automatic_command_retry(monkeypatch):
    waits = []
    monkeypatch.setattr(emulator_usb.time, 'sleep', waits.append)
    value = host(b'NAK\nOK\n')
    with pytest.raises(emulator_usb.USBError): value.setup_packet(0x40, 0x94)
    assert len(value.socket.sent) == 1 and not waits


def test_nak_wait_ends_at_original_deadline(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(emulator_usb.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(emulator_usb.time, 'sleep', lambda delay: now.__setitem__(0, now[0] + delay))
    value = host(b'NAK\n' * 100)
    with pytest.raises(emulator_usb.USBError, match='timed out'):
        value.command('IN 0', retry_nak=True, timeout=0.001)
    assert 0.001 <= now[0] <= 0.0011 and len(value.socket.sent) <= 12


def test_control_transfer_keeps_all_phases(monkeypatch):
    monkeypatch.setattr(emulator_usb.time, 'sleep', lambda _: None)
    value = host(b'OK\nNAK\nOK\nNAK\nDATA\n')
    value.control_out(0x40, 0x92, payload=b'abc')
    assert value.socket.sent == [b'SETUP 4092000000000300\n', b'OUT 616263\n',
                                 b'OUT 616263\n', b'IN 0\n', b'IN 0\n']
