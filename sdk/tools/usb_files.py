# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded app-management libusb transport; never issues firmware requests."""
import ctypes
import ctypes.util
from contextlib import contextmanager
import os
from pathlib import Path
import signal
import sys
VID,PID=0xCAFE,0x5052
class USBError(RuntimeError):
    pass


@contextmanager
def transfer_interrupts():
    """Deliver CLI Ctrl-C at a client's cancellable transfer checkpoint.

    Interrupting a control transfer can leave its status phase unread, so even
    cleanup would use a desynchronized connection. Repeated signals only mark
    the request; cleanup and an already started commit finish without another
    interrupt. Do not raise on context exit: a verified commit is still success.
    """
    pending = False
    def interrupt(*unused):
        nonlocal pending
        pending = True
    def checkpoint():
        if pending:
            raise KeyboardInterrupt
        return False
    previous = signal.signal(signal.SIGINT, interrupt)
    try:
        yield checkpoint
    finally:
        signal.signal(signal.SIGINT, previous)


def library_name():
    return 'libusb-1.0.dll' if os.name == 'nt' else ('libusb-1.0.dylib' if sys.platform == 'darwin' else 'libusb-1.0.so.0')


def load_library():
    """Frozen bundles use their explicit library, never a host installation."""
    if getattr(sys, 'frozen', False):
        candidates = [str(Path(sys._MEIPASS) / 'usb' / library_name())]
    else:
        candidates = [ctypes.util.find_library('usb-1.0')]
        if sys.platform == 'darwin':
            candidates += [str(path) for path in (
                Path('/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib'),
                Path('/usr/local/opt/libusb/lib/libusb-1.0.dylib')) if path.is_file()]
    loader = ctypes.WinDLL if os.name == 'nt' else ctypes.CDLL
    for candidate in dict.fromkeys(candidates):
        if candidate:
            try:
                return loader(candidate)
            except OSError:
                continue
    if getattr(sys, 'frozen', False):
        raise USBError('Bundled libusb could not be loaded; reinstall the complete SDK folder')
    raise USBError('libusb-1.0 is unavailable; install the native library for this host')


class LibUSB:
    READ_REQUESTS=(0x60,0x68,0x70,0x72)
    WRITE_REQUESTS=(0x71,0x72,0x73,0x74,0x75)
    def __init__(self, vid: int = VID, pid: int = PID) -> None:
        self.lib = load_library()
        self.lib.libusb_init.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        self.lib.libusb_init.restype = ctypes.c_int
        self.lib.libusb_exit.argtypes = [ctypes.c_void_p]
        self.lib.libusb_open_device_with_vid_pid.argtypes = [
            ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16
        ]
        self.lib.libusb_open_device_with_vid_pid.restype = ctypes.c_void_p
        self.lib.libusb_close.argtypes = [ctypes.c_void_p]
        self.lib.libusb_control_transfer.argtypes = [
            ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint8,
            ctypes.c_uint16, ctypes.c_uint16,
            ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint16,
            ctypes.c_uint,
        ]
        self.lib.libusb_control_transfer.restype = ctypes.c_int
        self.context = ctypes.c_void_p()
        result = self.lib.libusb_init(ctypes.byref(self.context))
        if result < 0:
            raise USBError(f"libusb_init failed: {result}")
        self.handle = self.lib.libusb_open_device_with_vid_pid(
            self.context, vid, pid
        )
        if not self.handle:
            self.lib.libusb_exit(self.context)
            raise USBError(
                f"USB device {vid:04X}:{pid:04X} not found or inaccessible"
            )

    def bulk_download(self,target,length,**kwargs):
        from bulk_libusb import transfer
        allowed=[]
        if 0x6a in self.READ_REQUESTS:allowed.append(5)
        if 0x72 in self.READ_REQUESTS:allowed.append(4)
        return transfer(self,target,length,allowed,**kwargs)

    def bulk_upload(self,target,data,**kwargs):
        from bulk_libusb import transfer
        allowed=[]
        if 0x64 in self.WRITE_REQUESTS:allowed.append(2)
        if 0x72 in self.WRITE_REQUESTS:allowed.append(3)
        return transfer(self,target,data,allowed,**kwargs)

    def close(self) -> None:
        if getattr(self, "handle", None):
            self.lib.libusb_close(self.handle)
            self.handle = None
        if getattr(self, "context", None):
            self.lib.libusb_exit(self.context)
            self.context = None

    def read(self, request: int, value: int = 0, index: int = 0,
             length: int = 64) -> bytes:
        if request not in self.READ_REQUESTS or not 0<=length<=512:
            raise USBError("Unsupported SDK file read request")
        buffer = (ctypes.c_ubyte * length)()
        result = self.lib.libusb_control_transfer(
            self.handle, 0xC0, request, value, index, buffer, length, 1500
        )
        if result < 0:
            raise USBError(
                f"control request 0x{request:02X} failed: libusb {result}"
            )
        return bytes(buffer[:result])

    def write(self, request: int, data: bytes = b"", value: int = 0,
              index: int = 0, timeout_ms: int = 3000) -> None:
        if request not in self.WRITE_REQUESTS or len(data)>512:
            raise USBError("Unsupported SDK file write request")
        length = len(data)
        buffer = (ctypes.c_ubyte * max(length, 1))()
        if length:
            buffer[:length] = data
        result = self.lib.libusb_control_transfer(
            self.handle, 0x40, request, value, index, buffer, length, timeout_ms
        )
        if result < 0:
            raise USBError(
                f"control request 0x{request:02X} failed: libusb {result}"
            )
        if result != length:
            raise USBError(f"short file transfer write: {result} of {length} bytes")

    def __enter__(self) -> "LibUSB":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
